from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session, selectinload

from app.models import Listing, PlatformAccount, PublishingJob


def build_action_center(db: Session, owner_id: int) -> dict:
    listings = (
        db.query(Listing)
        .options(selectinload(Listing.images), selectinload(Listing.platform_mappings))
        .filter(Listing.owner_id == owner_id)
        .order_by(Listing.updated_at.desc())
        .all()
    )
    listing_ids = [listing.id for listing in listings]
    jobs = []
    if listing_ids:
        jobs = (
            db.query(PublishingJob)
            .filter(PublishingJob.listing_id.in_(listing_ids))
            .order_by(PublishingJob.updated_at.desc())
            .all()
        )
    accounts = (
        db.query(PlatformAccount)
        .filter(PlatformAccount.owner_id == owner_id)
        .order_by(PlatformAccount.updated_at.desc())
        .all()
    )

    has_listing = bool(listings)
    has_image = any(listing.images for listing in listings)
    has_platform = any(
        mapping.status != "skipped"
        for listing in listings
        for mapping in listing.platform_mappings
    )
    has_job = bool(jobs)
    has_completion = any(
        mapping.status == "published"
        for listing in listings
        for mapping in listing.platform_mappings
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
        if job.status not in {"failed", "needs_user_action"}:
            continue
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
        if not listing.images:
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
        for mapping in listing.platform_mappings:
            if mapping.status == "needs_user_action" and mapping.validation_errors:
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
                        resource_id=listing.id,
                    )
                )
    for account in accounts:
        if account.status in {"ready", "connected", "disabled"}:
            continue
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
