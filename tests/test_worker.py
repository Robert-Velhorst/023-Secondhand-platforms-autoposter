import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.dialects import postgresql

from app.adapters.base import PublishOutcome
from app.database import Base, SessionLocal, engine
from app.models import PublishingJob
from app.services.jobs import claim_due_queued_job_ids, due_queued_jobs_query, recover_stale_running_jobs
from app.worker import run_once
from tests.test_api import PNG_BYTES, client


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def auth_headers():
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"worker-{uuid.uuid4().hex}@example.com",
            "password": "correct-password",
            "name": "Worker User",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def create_ready_listing(headers):
    response = client.post(
        "/api/listings",
        headers=headers,
        json={
            "title": "Worker queue lamp",
            "description": "Ready for assisted posting.",
            "price_cents": 2200,
            "condition": "used",
            "category": "Home and furniture",
            "location": "Arnhem",
            "delivery_options": {"pickup": True},
        },
    )
    assert response.status_code == 200, response.text
    listing_id = response.json()["id"]
    image_response = client.post(
        f"/api/listings/{listing_id}/images",
        headers=headers,
        files={"file": ("lamp.png", PNG_BYTES, "image/png")},
    )
    assert image_response.status_code == 200, image_response.text
    return listing_id


def test_worker_processes_queued_publish_job(monkeypatch):
    monkeypatch.setenv("JOB_PROCESS_INLINE", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    headers = auth_headers()
    listing_id = create_ready_listing(headers)

    publish_response = client.post(
        f"/api/listings/{listing_id}/publish",
        headers=headers,
        json={"platforms": ["marktplaats"], "process_now": True},
    )

    assert publish_response.status_code == 200, publish_response.text
    queued_job = publish_response.json()[0]
    assert queued_job["status"] == "queued"

    processed = run_once()
    assert processed == 1

    jobs_response = client.get("/api/jobs", headers=headers)
    assert jobs_response.status_code == 200, jobs_response.text
    job = jobs_response.json()[0]
    assert job["status"] == "needs_user_action"
    assert job["attempts"] == 1
    assert job["logs"]

    detail_response = client.get(f"/api/jobs/{job['id']}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["id"] == job["id"]
    assert detail_response.json()["listing_id"] == listing_id

    monkeypatch.delenv("JOB_PROCESS_INLINE")
    get_settings.cache_clear()


def test_jobs_support_pagination_filtering_and_sorting(monkeypatch):
    monkeypatch.setenv("JOB_PROCESS_INLINE", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    headers = auth_headers()
    listing_id = create_ready_listing(headers)
    publish_response = client.post(
        f"/api/listings/{listing_id}/publish",
        headers=headers,
        json={"platforms": ["marktplaats", "ebay"], "process_now": True},
    )
    assert publish_response.status_code == 200, publish_response.text

    response = client.get(
        "/api/jobs?platform=ebay&status=queued&limit=1&offset=0&sort=platform",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.headers["X-Total-Count"] == "1"
    assert response.headers["X-Limit"] == "1"
    assert response.json()[0]["platform"] == "ebay"
    assert response.json()[0]["status"] == "queued"

    page_response = client.get("/api/jobs?limit=1&offset=1&sort=platform", headers=headers)
    assert page_response.status_code == 200, page_response.text
    assert page_response.headers["X-Total-Count"] == "2"
    assert page_response.headers["X-Offset"] == "1"
    assert page_response.json()[0]["platform"] == "marktplaats"

    monkeypatch.delenv("JOB_PROCESS_INLINE")
    get_settings.cache_clear()


def test_due_job_claims_are_atomic_across_worker_sessions(monkeypatch):
    monkeypatch.setenv("JOB_PROCESS_INLINE", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    headers = auth_headers()
    listing_id = create_ready_listing(headers)
    publish_response = client.post(
        f"/api/listings/{listing_id}/publish",
        headers=headers,
        json={"platforms": ["marktplaats"], "process_now": True},
    )
    assert publish_response.status_code == 200, publish_response.text
    job_id = publish_response.json()[0]["id"]

    first_worker_db = SessionLocal()
    second_worker_db = SessionLocal()
    try:
        assert claim_due_queued_job_ids(first_worker_db, limit=10) == [job_id]
        assert claim_due_queued_job_ids(second_worker_db, limit=10) == []
    finally:
        first_worker_db.close()
        second_worker_db.close()

    monkeypatch.delenv("JOB_PROCESS_INLINE")
    get_settings.cache_clear()


def test_postgresql_due_job_claim_query_uses_skip_locked():
    db = SessionLocal()
    try:
        statement = due_queued_jobs_query(
            db,
            datetime(2026, 1, 1, tzinfo=UTC),
            limit=5,
            lock=True,
        ).statement
        compiled = str(statement.compile(dialect=postgresql.dialect()))
    finally:
        db.close()

    assert "FOR UPDATE SKIP LOCKED" in compiled


def test_platform_rate_limit_overrides_delay_same_platform_jobs(monkeypatch):
    monkeypatch.setenv("JOB_PROCESS_INLINE", "false")
    monkeypatch.setenv("PLATFORM_RATE_LIMIT_SECONDS", "0")
    monkeypatch.setenv("PLATFORM_RATE_LIMIT_OVERRIDES", "marktplaats=3600")
    from app.config import get_settings

    get_settings.cache_clear()
    headers = auth_headers()
    first_listing_id = create_ready_listing(headers)
    second_listing_id = create_ready_listing(headers)

    for listing_id in [first_listing_id, second_listing_id]:
        publish_response = client.post(
            f"/api/listings/{listing_id}/publish",
            headers=headers,
            json={"platforms": ["marktplaats"], "process_now": True},
        )
        assert publish_response.status_code == 200, publish_response.text

    assert run_once() == 2

    db = SessionLocal()
    try:
        jobs = (
            db.query(PublishingJob)
            .filter(PublishingJob.platform == "marktplaats")
            .order_by(PublishingJob.id.asc())
            .all()
        )
        assert jobs[0].status == "needs_user_action"
        assert jobs[0].attempts == 1
        assert jobs[1].status == "queued"
        assert jobs[1].attempts == 0
        assert jobs[1].next_retry_at is not None
        next_retry_at = jobs[1].next_retry_at
        if next_retry_at.tzinfo is None:
            next_retry_at = next_retry_at.replace(tzinfo=UTC)
        assert (next_retry_at - datetime.now(UTC)).total_seconds() > 3500
    finally:
        db.close()

    monkeypatch.delenv("JOB_PROCESS_INLINE")
    monkeypatch.delenv("PLATFORM_RATE_LIMIT_SECONDS")
    monkeypatch.delenv("PLATFORM_RATE_LIMIT_OVERRIDES")
    get_settings.cache_clear()


def test_official_api_quota_headers_requeue_job(monkeypatch):
    monkeypatch.setenv("JOB_PROCESS_INLINE", "false")
    monkeypatch.setenv("PLATFORM_RATE_LIMIT_SECONDS", "0")
    import app.services.jobs as job_service
    from app.config import get_settings

    class QuotaLimitedAdapter:
        automation_mode = "official_api"

        def publish_listing(self, listing, account=None, overrides=None):
            return PublishOutcome(
                status="failed",
                message="Quota exhausted.",
                data={
                    "http_status": 429,
                    "rate_limit_headers": {"Retry-After": "120", "X-RateLimit-Remaining": "0"},
                },
            )

    def fake_get_adapter(platform):
        if platform == "ebay":
            return QuotaLimitedAdapter()
        return original_get_adapter(platform)

    get_settings.cache_clear()
    original_get_adapter = job_service.get_adapter
    monkeypatch.setattr(job_service, "get_adapter", fake_get_adapter)
    headers = auth_headers()
    listing_id = create_ready_listing(headers)
    publish_response = client.post(
        f"/api/listings/{listing_id}/publish",
        headers=headers,
        json={"platforms": ["ebay"], "process_now": True},
    )
    assert publish_response.status_code == 200, publish_response.text
    job_id = publish_response.json()[0]["id"]

    assert run_once() == 1

    db = SessionLocal()
    try:
        job = db.get(PublishingJob, job_id)
        assert job.status == "queued"
        assert job.attempts == 1
        assert job.next_retry_at is not None
        next_retry_at = job.next_retry_at
        if next_retry_at.tzinfo is None:
            next_retry_at = next_retry_at.replace(tzinfo=UTC)
        assert (next_retry_at - datetime.now(UTC)).total_seconds() > 100
        assert job.result["rate_limit"]["source"] == "official_api_headers"
        assert any("Official API quota backoff" in log.message for log in job.logs)
    finally:
        db.close()

    monkeypatch.delenv("JOB_PROCESS_INLINE")
    monkeypatch.delenv("PLATFORM_RATE_LIMIT_SECONDS")
    get_settings.cache_clear()


def test_worker_recovers_stale_running_jobs(monkeypatch):
    monkeypatch.setenv("JOB_PROCESS_INLINE", "false")
    monkeypatch.setenv("JOB_STALE_RUNNING_SECONDS", "60")
    from app.config import get_settings

    get_settings.cache_clear()
    headers = auth_headers()
    listing_id = create_ready_listing(headers)
    publish_response = client.post(
        f"/api/listings/{listing_id}/publish",
        headers=headers,
        json={"platforms": ["marktplaats"], "process_now": True},
    )
    assert publish_response.status_code == 200, publish_response.text
    job_id = publish_response.json()[0]["id"]

    db = SessionLocal()
    try:
        job = db.get(PublishingJob, job_id)
        job.status = "running"
        job.started_at = datetime.now(UTC) - timedelta(seconds=120)
        db.commit()
    finally:
        db.close()

    assert run_once() == 1

    db = SessionLocal()
    try:
        job = db.get(PublishingJob, job_id)
        assert job.status == "needs_user_action"
        assert job.attempts == 1
        assert any("Recovered stale running job" in log.message for log in job.logs)
    finally:
        db.close()

    monkeypatch.delenv("JOB_PROCESS_INLINE")
    monkeypatch.delenv("JOB_STALE_RUNNING_SECONDS")
    get_settings.cache_clear()


def test_fresh_running_jobs_are_not_recovered():
    headers = auth_headers()
    listing_id = create_ready_listing(headers)
    db = SessionLocal()
    try:
        job = PublishingJob(
            listing_id=listing_id,
            platform="marktplaats",
            status="running",
            idempotency_key=f"fresh-running-{uuid.uuid4().hex}",
            started_at=datetime.now(UTC),
        )
        db.add(job)
        db.commit()

        assert recover_stale_running_jobs(db, stale_after_seconds=60) == 0
        db.refresh(job)
        assert job.status == "running"
    finally:
        db.close()


def test_worker_ignores_empty_queue():
    assert run_once() == 0
