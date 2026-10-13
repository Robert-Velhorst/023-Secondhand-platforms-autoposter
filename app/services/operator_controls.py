from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import OperatorControl

CONTROL_ID = 1


def operator_control_status(db: Session) -> dict:
    control = db.get(OperatorControl, CONTROL_ID)
    if control is None:
        return {
            "job_processing_paused": False,
            "reason": "",
            "updated_by": None,
            "updated_at": None,
        }
    return {
        "job_processing_paused": control.job_processing_paused,
        "reason": control.reason,
        "updated_by": control.updated_by,
        "updated_at": control.updated_at.isoformat(),
    }


def set_job_processing_paused(
    db: Session,
    *,
    paused: bool,
    reason: str,
    updated_by: str = "operator-cli",
) -> dict:
    cleaned_reason = reason.strip()
    if paused and not cleaned_reason:
        raise ValueError("A reason is required when pausing job processing")
    control = db.get(OperatorControl, CONTROL_ID)
    if control is None:
        control = OperatorControl(id=CONTROL_ID)
        db.add(control)
    control.job_processing_paused = paused
    control.reason = cleaned_reason if paused else ""
    control.updated_by = updated_by.strip() or "operator-cli"
    control.updated_at = datetime.now(UTC)
    db.commit()
    return operator_control_status(db)


def job_processing_is_paused(db: Session) -> bool:
    control = db.get(OperatorControl, CONTROL_ID)
    return bool(control and control.job_processing_paused)
