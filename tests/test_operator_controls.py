from app.database import Base, SessionLocal, engine
from app.services.jobs import process_due_jobs
from app.services.operator_controls import operator_control_status, set_job_processing_paused
from app.services.worker_health import record_heartbeat, worker_status


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_operator_pause_is_persistent_and_stops_job_claiming():
    db = SessionLocal()
    try:
        status = set_job_processing_paused(db, paused=True, reason="Marketplace incident")
        assert status["job_processing_paused"] is True
        assert process_due_jobs(db, 10) == 0
        assert operator_control_status(db)["reason"] == "Marketplace incident"
    finally:
        db.close()


def test_worker_status_exposes_intentional_pause():
    db = SessionLocal()
    try:
        record_heartbeat(db, "paused-worker")
        set_job_processing_paused(db, paused=True, reason="Operator maintenance")
        status = worker_status(db, heartbeat_timeout_seconds=30)
    finally:
        db.close()

    assert status["status"] == "paused"
    assert status["active_workers"] == 1
    assert status["pause_reason"] == "Operator maintenance"


def test_pause_requires_a_reason():
    db = SessionLocal()
    try:
        try:
            set_job_processing_paused(db, paused=True, reason="")
        except ValueError as exc:
            assert "reason is required" in str(exc)
        else:
            raise AssertionError("pause unexpectedly accepted an empty reason")
    finally:
        db.close()
