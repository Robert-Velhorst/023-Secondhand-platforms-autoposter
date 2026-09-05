from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.adapters import list_platforms
from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.doctor import run_checks
from app.models import CategoryMapping, Listing, ListingTemplate, PlatformAccount, PublishingJob, User
from app.schemas import (
    AccountReadiness,
    AccountUsage,
    ActionCenterResult,
    AnalyticsResult,
    DashboardResult,
    UserOut,
)
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
def diagnostics(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    doctor = run_checks()
    listing_query = db.query(Listing).filter(Listing.owner_id == user.id)
    job_query = db.query(PublishingJob).join(Listing).filter(Listing.owner_id == user.id)
    return {
        "status": doctor["status"],
        "version": __version__,
        "listings": listing_query.count(),
        "jobs": job_query.count(),
        "platforms": [platform["key"] for platform in list_platforms()],
        "doctor": doctor,
        "operator_control": operator_control_status(db),
    }


@router.get("/metrics", tags=["Diagnostics"])
def metrics(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    listing_statuses = dict(
        db.query(Listing.status, func.count(Listing.id))
        .filter(Listing.owner_id == user.id)
        .group_by(Listing.status)
        .all()
    )
    job_statuses = dict(
        db.query(PublishingJob.status, func.count(PublishingJob.id))
        .join(Listing)
        .filter(Listing.owner_id == user.id)
        .group_by(PublishingJob.status)
        .all()
    )
    return {
        "listings_total": db.query(Listing).filter(Listing.owner_id == user.id).count(),
        "publishing_jobs_total": (
            db.query(PublishingJob).join(Listing).filter(Listing.owner_id == user.id).count()
        ),
        "platform_accounts_total": db.query(PlatformAccount).filter(PlatformAccount.owner_id == user.id).count(),
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


@router.get("/dashboard", response_model=DashboardResult, tags=["Account"])
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DashboardResult:
    recent_listings = (
        db.query(Listing)
        .options(selectinload(Listing.images), selectinload(Listing.platform_mappings))
        .filter(Listing.owner_id == user.id)
        .order_by(Listing.updated_at.desc(), Listing.id.desc())
        .limit(5)
        .all()
    )
    latest_jobs = (
        db.query(PublishingJob)
        .options(selectinload(PublishingJob.logs))
        .join(Listing)
        .filter(Listing.owner_id == user.id)
        .order_by(PublishingJob.created_at.desc(), PublishingJob.id.desc())
        .limit(5)
        .all()
    )
    return DashboardResult(
        analytics=build_user_analytics(db, user.id),
        action_center=build_action_center(db, user.id),
        recent_listings=recent_listings,
        latest_jobs=latest_jobs,
    )


@router.get("/account/readiness", response_model=AccountReadiness, tags=["Account"])
def account_readiness(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AccountReadiness:
    listing_count = db.query(Listing).filter(Listing.owner_id == user.id).count()
    job_count = db.query(PublishingJob).join(Listing).filter(Listing.owner_id == user.id).count()
    return AccountReadiness(
        user=UserOut.model_validate(user),
        usage=AccountUsage(
            listings=listing_count,
            publishing_jobs=job_count,
            platform_accounts=db.query(PlatformAccount).filter(PlatformAccount.owner_id == user.id).count(),
            templates=db.query(ListingTemplate).filter(ListingTemplate.owner_id == user.id).count(),
            category_mappings=db.query(CategoryMapping).filter(CategoryMapping.owner_id == user.id).count(),
        ),
    )
