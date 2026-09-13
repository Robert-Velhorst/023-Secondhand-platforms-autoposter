from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
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
from app.rate_limit import clear_successful_login, reserve_login_attempt
from app.schemas import AuthLogin, AuthRegister, AuthToken, UserOut
from app.security import create_session, hash_password, password_needs_rehash, revoke_session, verify_password
from app.services.audit import record_audit_event
from app.services.storage_cleanup import cleanup_after_commit, queue_storage_deletions

router = APIRouter(prefix="/api")


@router.post("/auth/register", response_model=AuthToken, tags=["Auth"])
def register(payload: AuthRegister, db: Session = Depends(get_db)) -> AuthToken:
    email = payload.email.lower()
    existing = db.query(User.id).filter(User.email == email).one_or_none()
    # This is only a cheap duplicate fast path; the unique index arbitrates
    # races. No connection or transaction should span password hashing.
    db.rollback()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email is already registered")
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        insert = postgres_insert
    elif dialect == "sqlite":
        insert = sqlite_insert
    else:
        raise RuntimeError("Registration requires SQLite or PostgreSQL")
    user = db.scalars(
        insert(User)
        .values(email=email, name=payload.name, password_hash=hash_password(payload.password))
        .on_conflict_do_nothing(index_elements=[User.email])
        .returning(User)
    ).one_or_none()
    if user is None:
        raise HTTPException(status_code=409, detail="Email is already registered")
    # Keep the new account uncommitted until its initial session is stored.
    user_out = UserOut.model_validate(user)
    token = create_session(db, user)
    return AuthToken(token=token, user=user_out)


@router.post("/auth/login", response_model=AuthToken, tags=["Auth"])
def login(payload: AuthLogin, request: Request, db: Session = Depends(get_db)) -> AuthToken:
    identifier = f"{request.client.host if request.client else 'unknown'}:{payload.email.lower()}"
    reservation = reserve_login_attempt(db, identifier)
    credentials = (
        db.query(User.id, User.email, User.password_hash, User.is_active)
        .filter(User.email == payload.email.lower())
        .one_or_none()
    )
    # Keep only scalar credentials, returning the connection before costly hash
    # work. The already-committed admission reservation survives this rollback.
    db.rollback()
    if not credentials or not credentials.is_active or not verify_password(payload.password, credentials.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    replacement_hash = credentials.password_hash
    if password_needs_rehash(replacement_hash):
        replacement_hash = hash_password(payload.password)

    # A conditional write both validates the snapshot and locks the current row
    # through session commit on SQLite/PostgreSQL. A plain second SELECT leaves
    # a race; an unconditional rehash could overwrite a changed password.
    user = db.scalars(
        update(User)
        .where(
            User.id == credentials.id,
            User.email == credentials.email,
            User.password_hash == credentials.password_hash,
            User.is_active.is_(True),
        )
        .values(password_hash=replacement_hash)
        .returning(User)
    ).one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    clear_successful_login(db, reservation)
    user_out = UserOut.model_validate(user)
    token = create_session(db, user)
    return AuthToken(token=token, user=user_out)


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
    db.query(ListingTemplate).filter(ListingTemplate.owner_id == user_id).delete(synchronize_session=False)
    db.query(CategoryMapping).filter(CategoryMapping.owner_id == user_id).delete(synchronize_session=False)
    db.query(PlatformAccount).filter(PlatformAccount.owner_id == user_id).delete(synchronize_session=False)
    db.query(PlatformOAuthState).filter(PlatformOAuthState.user_id == user_id).delete(synchronize_session=False)
    db.query(HaiConnectorToken).filter(HaiConnectorToken.user_id == user_id).delete(synchronize_session=False)
    db.query(HaiListingChange).filter(HaiListingChange.owner_id == user_id).delete(synchronize_session=False)
    db.query(UserSession).filter(UserSession.user_id == user_id).delete(synchronize_session=False)
    cleanup_ids = queue_storage_deletions(db, image_paths)
    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
    db.commit()
    cleanup_after_commit(cleanup_ids)
