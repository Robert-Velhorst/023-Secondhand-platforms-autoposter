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


def test_worker_id_is_stable_and_scoped_to_the_container_hostname():
    from app.worker_identity import worker_id_for_host

    first = worker_id_for_host("container-a")
    assert first == worker_id_for_host("container-a")
    assert first != worker_id_for_host("container-b")
    assert len(first) == 39
    assert first.startswith("worker-")
    assert all(character in "0123456789abcdef" for character in first.removeprefix("worker-"))


def test_worker_cli_uses_the_same_container_identity_as_its_healthcheck(monkeypatch):
    from app import worker

    expected = "worker-" + "c" * 32
    observed = {}
    monkeypatch.setattr(worker, "worker_id_for_host", lambda: expected)
    monkeypatch.setattr(worker, "run_forever", lambda **kwargs: observed.update(kwargs))

    worker.main()

    assert observed == {"worker_id": expected}


def test_exact_worker_health_does_not_accept_a_healthy_sibling():
    expected_id = "worker-" + "a" * 32
    sibling_id = "worker-" + "b" * 32
    with SessionLocal() as db:
        record_heartbeat(db, sibling_id, processed_jobs=1)

    response = client.get("/api/worker-status", params={"worker_id": expected_id})

    assert response.status_code == 503
    assert response.json()["worker_id"] == expected_id
    assert response.json()["active_workers"] == 0
    assert client.get("/api/worker-status").json()["active_workers"] == 1


@pytest.mark.parametrize("worker_id", ["not-a-launch-id", "worker-" + "a" * 1000])
def test_worker_status_rejects_malformed_instance_filters(worker_id):
    assert client.get("/api/worker-status", params={"worker_id": worker_id}).status_code == 422
