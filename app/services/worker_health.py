from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import WorkerHeartbeat
from app.services.operator_controls import operator_control_status


def record_heartbeat(db: Session, worker_id: str, processed_jobs: int = 0) -> WorkerHeartbeat:
    heartbeat = db.get(WorkerHeartbeat, worker_id)
    now = datetime.now(UTC)
    if heartbeat is None:
        heartbeat = WorkerHeartbeat(
            worker_id=worker_id,
            started_at=now,
            last_seen_at=now,
            processed_jobs=processed_jobs,
        )
        db.add(heartbeat)
    else:
        heartbeat.last_seen_at = now
        heartbeat.processed_jobs += processed_jobs
    db.commit()
    db.refresh(heartbeat)
    return heartbeat


def worker_status(db: Session, heartbeat_timeout_seconds: int) -> dict:
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=heartbeat_timeout_seconds)
    active_workers, processed_jobs = (
        db.query(func.count(WorkerHeartbeat.worker_id), func.coalesce(func.sum(WorkerHeartbeat.processed_jobs), 0))
        .filter(WorkerHeartbeat.last_seen_at >= cutoff)
        .one()
    )
    latest = (
        db.query(WorkerHeartbeat.last_seen_at, WorkerHeartbeat.started_at)
        .order_by(WorkerHeartbeat.last_seen_at.desc())
        .first()
    )
    control = operator_control_status(db)
    status = "paused" if control["job_processing_paused"] else ("ok" if active_workers else "error")
    return {
        "status": status,
        "active_workers": active_workers,
        "last_heartbeat_at": latest.last_seen_at.isoformat() if latest else None,
        "last_worker_started_at": latest.started_at.isoformat() if latest else None,
        "processed_jobs": processed_jobs,
        "heartbeat_timeout_seconds": heartbeat_timeout_seconds,
        "job_processing_paused": control["job_processing_paused"],
        "pause_reason": control["reason"],
        "control_updated_at": control["updated_at"],
    }
