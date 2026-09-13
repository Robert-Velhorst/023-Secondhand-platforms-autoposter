import pytest

from app.database import Base, SessionLocal, engine
from app.models import WorkerHeartbeat
from app.services.worker_health import record_heartbeat, worker_status
from tests.test_api import client


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_worker_status_is_unhealthy_without_a_heartbeat():
    response = client.get("/api/worker-status")

    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert response.json()["active_workers"] == 0


def test_worker_status_reports_a_fresh_heartbeat():
    db = SessionLocal()
    try:
        record_heartbeat(db, "test-worker", processed_jobs=2)
        record_heartbeat(db, "test-worker", processed_jobs=3)
        status = worker_status(db, heartbeat_timeout_seconds=30)
    finally:
        db.close()

    assert status["status"] == "ok"
    assert status["active_workers"] == 1
    assert status["processed_jobs"] == 5

    response = client.get("/api/worker-status")
    assert response.status_code == 200
    assert response.json()["processed_jobs"] == 5


def test_instance_readiness_does_not_reuse_a_previous_workers_fresh_heartbeat():
    previous_id = "worker-" + "a" * 32
    current_id = "worker-" + "b" * 32
    with SessionLocal() as db:
        record_heartbeat(db, previous_id, processed_jobs=9)
    response = client.get("/api/worker-status", params={"worker_id": current_id})
    assert response.status_code == 503
    assert response.json()["active_workers"] == 0
    with SessionLocal() as db:
        record_heartbeat(db, current_id, processed_jobs=2)
    response = client.get("/api/worker-status", params={"worker_id": current_id})
    assert response.status_code == 200
    assert response.json()["active_workers"] == 1
    assert response.json()["worker_id"] == current_id
    assert response.json()["processed_jobs"] == 2
    assert client.get("/api/worker-status").json()["active_workers"] == 2


def test_worker_records_the_launch_identity_after_a_completed_cycle(monkeypatch):
    from app import worker

    expected = "worker-" + "c" * 32

    def stop_after_cycle(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(worker.time, "sleep", stop_after_cycle)
    with pytest.raises(KeyboardInterrupt):
        worker.run_forever(worker_id=expected)
    with SessionLocal() as db:
        rows = db.query(WorkerHeartbeat).all()
        assert len(rows) == 1
        assert rows[0].worker_id == expected


@pytest.mark.parametrize("worker_id", ["not-a-launch-id", "worker-" + "a" * 1000])
def test_worker_status_rejects_malformed_instance_filters(worker_id):
    assert client.get("/api/worker-status", params={"worker_id": worker_id}).status_code == 422
