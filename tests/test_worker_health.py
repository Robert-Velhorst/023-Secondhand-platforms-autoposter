from app.database import Base, SessionLocal, engine
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
