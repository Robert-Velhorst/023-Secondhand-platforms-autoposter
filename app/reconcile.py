from __future__ import annotations

import argparse
import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings, validate_startup_safety
from app.database import SessionLocal
from app.models import Listing, ListingImage, PlatformListingMapping, PublishingJob


def reconcile_database(db: Session, *, repair_safe: bool = False) -> dict:
    issues: list[dict] = []
    repairs: list[dict] = []

    orphan_images = (
        db.query(func.count(ListingImage.id))
        .outerjoin(Listing, ListingImage.listing_id == Listing.id)
        .filter(Listing.id.is_(None))
        .scalar()
        or 0
    )
    orphan_mappings = (
        db.query(func.count(PlatformListingMapping.id))
        .outerjoin(Listing, PlatformListingMapping.listing_id == Listing.id)
        .filter(Listing.id.is_(None))
        .scalar()
        or 0
    )
    orphan_jobs = (
        db.query(func.count(PublishingJob.id))
        .outerjoin(Listing, PublishingJob.listing_id == Listing.id)
        .filter(Listing.id.is_(None))
        .scalar()
        or 0
    )
    for name, count in (
        ("orphan_images", orphan_images),
        ("orphan_platform_mappings", orphan_mappings),
        ("orphan_jobs", orphan_jobs),
    ):
        if count:
            issues.append({"code": name, "count": count, "safe_to_auto_repair": False})

    listings = db.query(Listing).order_by(Listing.id.asc()).all()
    for listing in listings:
        ordered = sorted(listing.images, key=lambda image: (image.position, image.id))
        expected = list(range(len(ordered)))
        actual = [image.position for image in ordered]
        if actual != expected:
            issues.append(
                {
                    "code": "image_position_gap",
                    "listing_id": listing.id,
                    "actual": actual,
                    "expected": expected,
                    "safe_to_auto_repair": True,
                }
            )
            if repair_safe:
                for position, image in enumerate(ordered):
                    image.position = position
                repairs.append(
                    {"code": "image_positions_reindexed", "listing_id": listing.id}
                )

        for mapping in listing.platform_mappings:
            if mapping.status == "published" and not (mapping.platform_url or mapping.platform_listing_id):
                issues.append(
                    {
                        "code": "published_mapping_missing_external_reference",
                        "listing_id": listing.id,
                        "platform": mapping.platform,
                        "safe_to_auto_repair": False,
                    }
                )

    if repairs:
        db.commit()
    return {
        "status": "ok" if not issues else "issues_found",
        "repair_mode": repair_safe,
        "issues": issues,
        "repairs": repairs,
        "counts": {
            "listings": len(listings),
            "issues": len(issues),
            "repairs": len(repairs),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check database consistency and apply explicitly safe repairs")
    parser.add_argument("--repair-safe", action="store_true")
    args = parser.parse_args(argv)
    validate_startup_safety(get_settings())
    db = SessionLocal()
    try:
        result = reconcile_database(db, repair_safe=args.repair_safe)
    finally:
        db.close()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
