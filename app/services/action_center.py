from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import String, case, cast, func
from sqlalchemy.orm import Session

from app.models import Listing, ListingImage, PlatformAccount, PlatformListingMapping, PublishingJob


def build_action_center(db: Session, owner_id: int) -> dict:
    owned_listings = db.query(Listing.id).filter(Listing.owner_id == owner_id)
    owned_mappings = db.query(PlatformListingMapping.id).join(Listing).filter(Listing.owner_id == owner_id)
    owned_jobs = db.query(PublishingJob.id).join(Listing).filter(Listing.owner_id == owner_id)
    has_listing, has_image, has_platform, has_job, has_completion = db.query(
        owned_listings.exists(),
        db.query(ListingImage.id).join(Listing).filter(Listing.owner_id == owner_id).exists(),
        owned_mappings.filter(PlatformListingMapping.status != "skipped").exists(),
        owned_jobs.exists(),
        owned_mappings.filter(PlatformListingMapping.status == "published").exists(),
    ).one()

    # Each category contributes at most 20 candidates to the global top 20.
    # Preserve the response's existing severity/lexical-ID order in SQL.
    jobs = (
        db.query(PublishingJob.id, PublishingJob.status, PublishingJob.platform, PublishingJob.error_message)
        .join(Listing)
        .filter(Listing.owner_id == owner_id, PublishingJob.status.in_(["failed", "needs_user_action"]))
        .order_by(case((PublishingJob.status == "failed", 0), else_=1), cast(PublishingJob.id, String))
        .limit(20).all()
    )
    listings = (
        db.query(Listing.id, Listing.title)
        .filter(Listing.owner_id == owner_id, ~Listing.images.any())
        .order_by(cast(Listing.id, String)).limit(20).all()
    )
    mappings = (
        db.query(PlatformListingMapping.id, PlatformListingMapping.platform,
                 PlatformListingMapping.listing_id, PlatformListingMapping.validation_errors)
        .join(Listing)
        .filter(Listing.owner_id == owner_id, PlatformListingMapping.status == "needs_user_action",
                func.json_array_length(PlatformListingMapping.validation_errors) > 0)
        .order_by(cast(PlatformListingMapping.id, String)).limit(20).all()
    )
    accounts = (
        db.query(PlatformAccount.id, PlatformAccount.platform, PlatformAccount.display_name, PlatformAccount.status)
        .filter(PlatformAccount.owner_id == owner_id, PlatformAccount.status.notin_(["ready", "connected", "disabled"]))
        .order_by(cast(PlatformAccount.id, String)).limit(20).all()
    )
    steps = [
        step("create-listing", "Create your first reusable listing", has_listing, "listings"),
        step("add-image", "Add at least one item image", has_image, "listings"),
        step("select-platform", "Select and validate a marketplace", has_platform, "listings"),
        step("queue-package", "Queue an assisted posting package", has_job, "queue"),
        step("record-completion", "Record the final marketplace URL after manual posting", has_completion, "queue"),
    ]

    reminders: list[dict] = []
    for job in jobs:
        failed = job.status == "failed"
        reminders.append(
            action(
                id=f"job-{job.id}-{job.status}",
                kind="job",
                severity="critical" if failed else "warning",
                title=f"{job.platform.title()} package {'failed' if failed else 'needs your action'}",
                detail=job.error_message or "Open the job to review its latest log and required next step.",
                next_action="Review the job, fix the reported issue, then retry or record manual completion.",
                target_view="queue",
                resource_type="job",
                resource_id=job.id,
            )
        )
    for listing in listings:
        reminders.append(
            action(
                id=f"listing-{listing.id}-image",
                kind="listing_quality",
                severity="warning",
                title=f"Add an image to {listing.title or 'Untitled listing'}",
                detail="Marketplace packages require at least one real item image.",
                next_action="Open the listing and upload an item image before validation.",
                target_view="listings",
                resource_type="listing",
                resource_id=listing.id,
            )
        )
    for mapping in mappings:
        reminders.append(
            action(
                id=f"mapping-{mapping.id}-validation",
                kind="validation",
                severity="warning",
                title=f"Complete {mapping.platform.title()} requirements",
                detail=f"Missing: {', '.join(mapping.validation_errors)}",
                next_action="Open the listing, use the prepublish review fixes, and validate again.",
                target_view="listings",
                resource_type="listing",
                resource_id=mapping.listing_id,
            )
        )
    for account in accounts:
        reminders.append(
            action(
                id=f"account-{account.id}-setup",
                kind="account",
                severity="info",
                title=f"Finish {account.platform.title()} account setup",
                detail=f"{account.display_name} is currently {account.status.replace('_', ' ')}.",
                next_action="Open Accounts and complete the provider-owned authorization steps.",
                target_view="accounts",
                resource_type="account",
                resource_id=account.id,
            )
        )

    priority = {"critical": 0, "warning": 1, "info": 2}
    reminders.sort(key=lambda item: (priority[item["severity"]], item["id"]))
    return {
        "source": "derived_local",
        "generated_at": datetime.now(UTC),
        "onboarding_complete": all(item["complete"] for item in steps),
        "onboarding_steps": steps,
        "reminders": reminders[:20],
    }


def step(id: str, label: str, complete: bool, target_view: str) -> dict:
    return {"id": id, "label": label, "complete": complete, "target_view": target_view}


def action(**values) -> dict:
    return values
