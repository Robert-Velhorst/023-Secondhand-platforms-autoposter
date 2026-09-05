from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_session, get_current_user
from app.models import (
    CategoryMapping,
    HaiConnectorToken,
    HaiListingChange,
    Listing,
    ListingDraft,
    ListingImage,
    ListingTemplate,
    PlatformAccount,
    PlatformListingMapping,
    PlatformOAuthState,
    PublicationAttempt,
    PublishingJob,
    PublishingJobLog,
    User,
    UserSession,
)
from app.rate_limit import check_login_rate_limit, record_failed_login, record_successful_login
from app.schemas import AuthLogin, AuthRegister, AuthToken, UserOut
from app.security import create_session, hash_password, password_needs_rehash, revoke_session, verify_password
from app.services.audit import record_audit_event
from app.storage import delete_stored_file

router = APIRouter(prefix="/api")


@router.post("/auth/register", response_model=AuthToken, tags=["Auth"])
def register(payload: AuthRegister, db: Session = Depends(get_db)) -> AuthToken:
    existing = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email is already registered")
    user = User(
        email=payload.email.lower(),
        name=payload.name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_session(db, user)
    return AuthToken(token=token, user=UserOut.model_validate(user))


@router.post("/auth/login", response_model=AuthToken, tags=["Auth"])
def login(payload: AuthLogin, request: Request, db: Session = Depends(get_db)) -> AuthToken:
    identifier = f"{request.client.host if request.client else 'unknown'}:{payload.email.lower()}"
    check_login_rate_limit(db, identifier)
    user = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        record_failed_login(db, identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
        db.commit()
    record_successful_login(db, identifier)
    token = create_session(db, user)
    return AuthToken(token=token, user=UserOut.model_validate(user))


@router.post("/auth/logout", status_code=204, tags=["Auth"])
def logout(session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)):
    if session.token_hash != "dev-auto-login":
        revoke_session(db, session)
    return None


@router.get("/auth/me", response_model=UserOut, tags=["Auth"])
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.delete("/auth/me", status_code=204, tags=["Auth"])
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    delete_user_data(db, user)
    return None


def delete_user_data(db: Session, user: User) -> None:
    user_id = user.id
    listing_ids = [id_ for (id_,) in db.query(Listing.id).filter(Listing.owner_id == user_id).all()]
    job_ids = []
    image_paths = []
    if listing_ids:
        job_ids = [id_ for (id_,) in db.query(PublishingJob.id).filter(PublishingJob.listing_id.in_(listing_ids)).all()]
        image_paths = [
            path
            for (path,) in db.query(ListingImage.storage_path)
            .filter(ListingImage.listing_id.in_(listing_ids))
            .all()
        ]
    record_audit_event(
        db,
        user,
        "account_deleted",
        {
            "listings_deleted": len(listing_ids),
            "jobs_deleted": len(job_ids),
            "images_deleted": len(image_paths),
            "templates_deleted": db.query(ListingTemplate).filter(ListingTemplate.owner_id == user_id).count(),
            "category_mappings_deleted": db.query(CategoryMapping).filter(CategoryMapping.owner_id == user_id).count(),
            "platform_accounts_deleted": db.query(PlatformAccount).filter(PlatformAccount.owner_id == user_id).count(),
            "oauth_states_deleted": db.query(PlatformOAuthState).filter(PlatformOAuthState.user_id == user_id).count(),
        },
    )
    if listing_ids:
        if job_ids:
            db.query(PublicationAttempt).filter(PublicationAttempt.job_id.in_(job_ids)).delete(synchronize_session=False)
            db.query(PublishingJobLog).filter(PublishingJobLog.job_id.in_(job_ids)).delete(synchronize_session=False)
            db.query(PublishingJob).filter(PublishingJob.id.in_(job_ids)).delete(synchronize_session=False)
        db.query(ListingDraft).filter(ListingDraft.listing_id.in_(listing_ids)).delete(synchronize_session=False)
        db.query(PlatformListingMapping).filter(PlatformListingMapping.listing_id.in_(listing_ids)).delete(
            synchronize_session=False
        )
        db.query(ListingImage).filter(ListingImage.listing_id.in_(listing_ids)).delete(synchronize_session=False)
        db.query(Listing).filter(Listing.id.in_(listing_ids)).delete(synchronize_session=False)
        for image_path in image_paths:
            delete_stored_file(image_path)
    db.query(ListingTemplate).filter(ListingTemplate.owner_id == user_id).delete(synchronize_session=False)
    db.query(CategoryMapping).filter(CategoryMapping.owner_id == user_id).delete(synchronize_session=False)
    db.query(PlatformAccount).filter(PlatformAccount.owner_id == user_id).delete(synchronize_session=False)
    db.query(PlatformOAuthState).filter(PlatformOAuthState.user_id == user_id).delete(synchronize_session=False)
    db.query(HaiConnectorToken).filter(HaiConnectorToken.user_id == user_id).delete(synchronize_session=False)
    db.query(HaiListingChange).filter(HaiListingChange.owner_id == user_id).delete(synchronize_session=False)
    db.query(UserSession).filter(UserSession.user_id == user_id).delete(synchronize_session=False)
    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
    db.commit()
