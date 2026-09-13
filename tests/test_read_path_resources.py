from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    Listing,
    ListingImage,
    OperatorControl,
    PlatformAccount,
    PlatformListingMapping,
    PublishingJob,
    User,
    WorkerHeartbeat,
)
from app.services.action_center import build_action_center
from app.services.analytics import build_user_analytics
from app.services.worker_health import worker_status
from scripts.benchmark_read_paths import seed


@pytest.fixture
def isolated_db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_worker_health_does_not_materialize_historical_workers(isolated_db):
    db = isolated_db
    now = datetime.now(UTC)
    db.execute(WorkerHeartbeat.__table__.insert(), [
        {"worker_id": f"stale-{i}", "last_seen_at": now - timedelta(days=1),
         "started_at": now - timedelta(days=2), "processed_jobs": 1000} for i in range(100)
    ] + [
        {"worker_id": "fresh-one", "last_seen_at": now, "started_at": now, "processed_jobs": 3},
        {"worker_id": "fresh-two", "last_seen_at": now, "started_at": now, "processed_jobs": 5},
    ])
    db.commit()
    loaded = []
    event.listen(db, "loaded_as_persistent", lambda _db, obj: loaded.append(type(obj)))
    result = worker_status(db, 30)
    assert result["active_workers"] == 2
    assert result["processed_jobs"] == 8
    assert result["status"] == "ok"
    assert loaded.count(WorkerHeartbeat) <= 1, "Health polling must not load worker history"


def test_worker_health_preserves_stale_details_and_pause_state(isolated_db):
    db = isolated_db
    stale = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    db.execute(WorkerHeartbeat.__table__.insert(), {
        "worker_id": "old", "last_seen_at": stale, "started_at": stale, "processed_jobs": 900,
    })
    db.execute(OperatorControl.__table__.insert(), {"id": 1, "job_processing_paused": True, "reason": "Check"})
    db.commit()
    result = worker_status(db, 30)
    assert result["active_workers"] == 0
    assert result["processed_jobs"] == 0
    assert datetime.fromisoformat(result["last_heartbeat_at"]).replace(tzinfo=UTC) == stale.replace(tzinfo=UTC)
    assert result["status"] == "paused"
    assert result["pause_reason"] == "Check"


def test_analytics_aggregates_history_without_loading_job_payloads(isolated_db):
    db = isolated_db
    seed(db, 600)
    loaded = Counter()
    peak_listings = 0

    def on_load(session, obj):
        nonlocal peak_listings
        loaded[type(obj).__name__] += 1
        peak_listings = max(peak_listings, sum(isinstance(item, Listing) for item in session.identity_map.values()))

    event.listen(db, "loaded_as_persistent", on_load)
    result = build_user_analytics(db, 1)
    assert result["summary"]["listings_total"] == 600
    assert result["summary"]["jobs_total"] == 3000
    assert result["summary"]["inventory_value_cents"] == 600000
    assert result["job_statuses"] == {"published": 3000}
    assert result["selected_platforms"] == {"marktplaats": 600}
    assert result["quality"]["listings_missing_images"] == 600
    assert loaded["PublishingJob"] == 0, "Analytics needs counts, not stored job result payloads"
    assert loaded["PlatformListingMapping"] == 0
    assert peak_listings <= 512, "Quality analysis must use bounded batches"


def test_action_center_keeps_priority_and_owner_scope_without_loading_inventory(isolated_db):
    db = isolated_db
    seed(db, 100)
    db.execute(User.__table__.insert(), {"id": 2, "email": "other@example.com", "password_hash": "unused"})
    db.execute(Listing.__table__.insert(), {"id": 1001, "owner_id": 2, "title": "Foreign item"})
    db.execute(PublishingJob.__table__.insert(), [
        {"id": 1001, "listing_id": 1, "platform": "ebay", "status": "failed", "idempotency_key": "failure"},
        {"id": 1002, "listing_id": 1001, "platform": "ebay", "status": "failed", "idempotency_key": "foreign"},
    ])
    db.commit()
    loaded = []
    event.listen(db, "loaded_as_persistent", lambda _db, obj: loaded.append(type(obj).__name__))
    result = build_action_center(db, 1)
    assert [step["complete"] for step in result["onboarding_steps"]] == [True, False, True, True, False]
    assert len(result["reminders"]) == 20
    assert result["reminders"][0]["id"] == "job-1001-failed"
    assert result["reminders"][1]["id"] == "listing-1-image"
    assert not any(item["id"] == "job-1002-failed" for item in result["reminders"])
    assert len(loaded) <= 100, "Twenty reminders must not materialize hundreds of listings/jobs"


def test_action_center_keeps_all_reminder_kinds_and_ignores_empty_validation_errors(isolated_db):
    db = isolated_db
    db.execute(User.__table__.insert(), {"id": 1, "email": "mixed@example.com", "password_hash": "unused"})
    db.execute(Listing.__table__.insert(), [
        {"id": 1, "owner_id": 1, "title": "With photo"},
        {"id": 2, "owner_id": 1, "title": "No photo"},
    ])
    db.execute(ListingImage.__table__.insert(), {"listing_id": 1, "filename": "photo.png", "storage_path": "unused"})
    db.execute(PlatformListingMapping.__table__.insert(), [
        {"id": 11, "listing_id": 1, "platform": "ebay", "status": "needs_user_action", "validation_errors": ["title"]},
        {"id": 12, "listing_id": 2, "platform": "marktplaats", "status": "skipped", "validation_errors": ["title"]},
        {"id": 13, "listing_id": 2, "platform": "nextdoor", "status": "needs_user_action", "validation_errors": []},
        {"id": 14, "listing_id": 1, "platform": "koopplein", "status": "published", "validation_errors": []},
    ])
    db.execute(PlatformAccount.__table__.insert(), [
        {"id": 1, "owner_id": 1, "platform": "ebay", "display_name": "Incomplete", "status": "needs_setup"},
        {"id": 2, "owner_id": 1, "platform": "nextdoor", "display_name": "Ready", "status": "ready"},
        {"id": 3, "owner_id": 1, "platform": "koopplein", "display_name": "Disabled", "status": "disabled"},
    ])
    db.execute(PublishingJob.__table__.insert(), [
        {"id": 7, "listing_id": 1, "platform": "ebay", "status": "failed", "idempotency_key": "failed"},
        {"id": 8, "listing_id": 1, "platform": "ebay", "status": "needs_user_action", "idempotency_key": "assisted"},
        {"id": 9, "listing_id": 1, "platform": "ebay", "status": "published", "idempotency_key": "done"},
    ])
    db.commit()
    result = build_action_center(db, 1)
    assert result["onboarding_complete"] is True
    assert [item["id"] for item in result["reminders"]] == [
        "job-7-failed", "job-8-needs_user_action", "listing-2-image",
        "mapping-11-validation", "account-1-setup",
    ]
    assert result["reminders"][3]["detail"] == "Missing: title"
    assert result["reminders"][3]["resource_id"] == 1


def test_action_center_top_twenty_never_displaces_failures_with_warnings(isolated_db):
    db = isolated_db
    seed(db, 30)
    db.execute(PublishingJob.__table__.update().values(status="failed"))
    db.commit()
    reminders = build_action_center(db, 1)["reminders"]
    assert len(reminders) == 20
    assert all(item["severity"] == "critical" for item in reminders)
    assert [item["id"] for item in reminders[:4]] == [
        "job-1-failed", "job-10-failed", "job-100-failed", "job-101-failed",
    ]
