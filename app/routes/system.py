from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.adapters import list_platforms
from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.doctor import run_checks
from app.models import CategoryMapping, Listing, ListingTemplate, PlatformAccount, PublishingJob, User
from app.schemas import AccountReadiness, AccountUsage, ActionCenterResult, AnalyticsResult, UserOut
from app.services.action_center import build_action_center
from app.services.analytics import build_user_analytics
from app.services.localization import localization_metadata
from app.services.operator_controls import operator_control_status
from app.services.worker_health import worker_status
from app.version import __version__

router = APIRouter(prefix="/api")


@router.get("/health", tags=["Health"])
def health() -> dict:
    return {"status": "ok", "version": __version__, "time": datetime.now(UTC).isoformat()}


@router.get("/worker-status", tags=["Diagnostics"])
def worker_status_endpoint(response: Response, db: Session = Depends(get_db)) -> dict:
    status = worker_status(db, get_settings().worker_heartbeat_timeout_seconds)
    if status["status"] != "ok":
        response.status_code = 503
    return status


@router.get("/diagnostics", tags=["Diagnostics"])
def diagnostics(db: Session = Depends(get_db)) -> dict:
    doctor = run_checks()
    return {
        "status": doctor["status"],
        "version": __version__,
        "listings": db.query(Listing).count(),
        "jobs": db.query(PublishingJob).count(),
        "platforms": [platform["key"] for platform in list_platforms()],
        "doctor": doctor,
        "operator_control": operator_control_status(db),
    }


@router.get("/metrics", tags=["Diagnostics"])
def metrics(db: Session = Depends(get_db)) -> dict:
    listing_statuses = dict(db.query(Listing.status, func.count(Listing.id)).group_by(Listing.status).all())
    job_statuses = dict(
        db.query(PublishingJob.status, func.count(PublishingJob.id)).group_by(PublishingJob.status).all()
    )
    return {
        "listings_total": db.query(Listing).count(),
        "publishing_jobs_total": db.query(PublishingJob).count(),
        "users_total": db.query(User).count(),
        "platform_accounts_total": db.query(PlatformAccount).count(),
        "listing_statuses": listing_statuses,
        "publishing_job_statuses": job_statuses,
    }


@router.get("/localization", tags=["Diagnostics"])
def localization() -> dict:
    return localization_metadata(get_settings())


@router.get("/analytics", response_model=AnalyticsResult, tags=["Diagnostics"])
def analytics(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_user_analytics(db, user.id)


@router.get("/action-center", response_model=ActionCenterResult, tags=["Account"])
def action_center(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_action_center(db, user.id)


@router.get("/account/readiness", response_model=AccountReadiness, tags=["Account"])
def account_readiness(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AccountReadiness:
    listing_ids = [id_ for (id_,) in db.query(Listing.id).filter(Listing.owner_id == user.id).all()]
    job_count = 0
    if listing_ids:
        job_count = db.query(PublishingJob).filter(PublishingJob.listing_id.in_(listing_ids)).count()
    return AccountReadiness(
        user=UserOut.model_validate(user),
        usage=AccountUsage(
            listings=len(listing_ids),
            publishing_jobs=job_count,
            platform_accounts=db.query(PlatformAccount).filter(PlatformAccount.owner_id == user.id).count(),
            templates=db.query(ListingTemplate).filter(ListingTemplate.owner_id == user.id).count(),
            category_mappings=db.query(CategoryMapping).filter(CategoryMapping.owner_id == user.id).count(),
        ),
    )
