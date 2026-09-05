import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.adapters import get_adapter
from app.database import Base, SessionLocal, engine
from app.models import Listing, ListingDraft, PlatformAccount, PublicationAttempt, PublishingJob, PublishingJobLog
from app.services.jobs import enqueue_publish_job, process_due_jobs, process_job, retry_job
from tests.test_api import client
from tests.test_owner_isolation import auth_headers, create_ready_listing


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def create_account(headers, platform="marktplaats"):
    response = client.post("/api/accounts", headers=headers, json={
        "platform": platform, "display_name": "Private account", "status": "needs_setup",
    })
    assert response.status_code == 200, response.text
    return response.json()["id"]


@pytest.mark.parametrize("representation", [int, str, float])
def test_publish_rejects_another_owners_account_without_writes(representation):
    owner = auth_headers("listing-owner")
    other = auth_headers("account-owner")
    listing_id = create_ready_listing(owner)
    account_id = create_account(other)
    before = client.get(f"/api/listings/{listing_id}", headers=owner).json()["revision"]
    with SessionLocal() as db:
        drafts_before = db.query(ListingDraft).count()
    response = client.post(f"/api/listings/{listing_id}/publish", headers=owner, json={
        "platforms": ["marktplaats"], "account_ids": {"marktplaats": representation(account_id)},
        "force_new_revision": True, "process_now": False,
    })
    assert response.status_code == 404, response.text
    assert "Private account" not in response.text
    with SessionLocal() as db:
        assert db.get(Listing, listing_id).revision == before
        assert db.query(ListingDraft).count() == drafts_before
        assert db.query(PublishingJob).count() == 0
        assert db.query(PublishingJobLog).count() == 0


@pytest.mark.parametrize("invalid_kind", ["wrong-platform", "missing", "zero", "negative", "oversized"])
def test_invalid_later_account_does_not_partially_queue(invalid_kind):
    owner = auth_headers("owner")
    listing_id = create_ready_listing(owner)
    wrong_platform = create_account(owner, "marktplaats")
    account_id = {
        "wrong-platform": wrong_platform, "missing": 999999, "zero": 0, "negative": -1, "oversized": 2**63,
    }[invalid_kind]
    response = client.post(f"/api/listings/{listing_id}/publish", headers=owner, json={
        "platforms": ["marktplaats", "ebay"], "account_ids": {"ebay": account_id}, "process_now": False,
    })
    assert response.status_code == 404, response.text
    assert client.get("/api/jobs", headers=owner).json() == []


@pytest.mark.parametrize("with_account", [False, True])
def test_valid_assisted_publish_preserves_optional_account_and_idempotency(with_account):
    owner = auth_headers("valid-owner")
    listing_id = create_ready_listing(owner)
    account_id = create_account(owner) if with_account else None
    payload = {"platforms": ["marktplaats"], "process_now": True}
    if with_account:
        payload["account_ids"] = {"marktplaats": account_id}
    first = client.post(f"/api/listings/{listing_id}/publish", headers=owner, json=payload)
    assert first.status_code == 200, first.text
    job = first.json()[0]
    assert job["status"] == "needs_user_action"
    assert job["account_id"] == account_id
    repeated = client.post(f"/api/listings/{listing_id}/publish", headers=owner, json=payload)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()[0]["id"] == job["id"]
    assert repeated.json()[0]["attempts"] == 1


def test_direct_enqueue_rejects_foreign_account():
    owner = auth_headers("owner")
    other = auth_headers("other")
    listing_id = create_ready_listing(owner)
    account_id = create_account(other)
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="account"):
            enqueue_publish_job(db, db.get(Listing, listing_id), "marktplaats", account_id)
        assert db.query(PublishingJob).count() == 0


@pytest.mark.parametrize("entrypoint", ["worker", "recovered-worker", "retry", "retry-api"])
@pytest.mark.parametrize("invalid_kind", ["foreign-owner", "platform-changed"])
def test_persisted_job_revalidates_account_before_adapter_use(monkeypatch, entrypoint, invalid_kind):
    owner = auth_headers("owner")
    other = auth_headers("other")
    listing_id = create_ready_listing(owner)
    account_id = create_account(other if invalid_kind == "foreign-owner" else owner)
    with SessionLocal() as db:
        # Reproduce a legacy invalid row, or a valid queued row whose account changes later.
        status = {"worker": "queued", "recovered-worker": "running"}.get(entrypoint, "failed")
        job = PublishingJob(listing_id=listing_id, platform="marktplaats", account_id=account_id,
                            idempotency_key=uuid.uuid4().hex, status=status)
        if entrypoint == "recovered-worker":
            job.started_at = datetime.now(UTC) - timedelta(days=1)
        db.add(job)
        db.commit()
        job_id = job.id
    observed_accounts = []
    adapter = get_adapter("marktplaats")
    publish = adapter.publish_listing

    def capture_account(listing, account=None, overrides=None):
        observed_accounts.append(account.id if account else None)
        return publish(listing, account, overrides)

    monkeypatch.setattr(adapter, "publish_listing", capture_account)
    with SessionLocal() as db:
        cached_account = db.get(PlatformAccount, account_id)
        if invalid_kind == "platform-changed":
            with engine.begin() as connection:
                connection.execute(
                    update(PlatformAccount).where(PlatformAccount.id == account_id).values(platform="ebay")
                )
            assert cached_account.platform == "marktplaats"  # Deliberately stale identity-map entry.
        if entrypoint in {"worker", "recovered-worker"}:
            if entrypoint == "worker":
                result = process_job(db, job_id)
            else:
                assert process_due_jobs(db, 1) == 1
                result = db.get(PublishingJob, job_id)
            assert observed_accounts == [], "Unauthorized account objects must never reach an adapter"
            assert result.status == "failed"
            assert result.attempts == 1
            assert result.finished_at is not None
            assert "account" in result.error_message.lower()
            assert db.query(PublicationAttempt).filter_by(job_id=job_id).count() == 1
        elif entrypoint == "retry":
            with pytest.raises(ValueError, match="account"):
                retry_job(db, db.get(PublishingJob, job_id))
        else:
            response = client.post(f"/api/jobs/{job_id}/retry", headers=owner)
            assert response.status_code == 404, response.text
    assert observed_accounts == [], "Unauthorized account objects must never reach an adapter"
    with SessionLocal() as db:
        job = db.get(PublishingJob, job_id)
        assert job.status == "failed"
        if entrypoint not in {"worker", "recovered-worker"}:
            assert job.attempts == 0
            assert db.query(PublishingJobLog).filter_by(job_id=job_id).count() == 0
