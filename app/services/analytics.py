from collections import Counter
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Listing, ListingImage, PlatformListingMapping, PublishingJob
from app.services.quality import analyze_listing_quality


@dataclass(frozen=True, slots=True)
class _QualityListing:
    title: str
    description: str
    price_cents: int
    condition: str
    category: str
    location: str
    pickup_allowed: bool
    shipping_allowed: bool
    shipping_cost_cents: int
    dimensions: dict
    weight_grams: int
    brand: str
    model: str
    color: str
    material: str


def build_user_analytics(db: Session, owner_id: int) -> dict[str, Any]:
    listings = db.query(
        Listing.id,
        Listing.title,
        Listing.description,
        Listing.price_cents,
        Listing.condition,
        Listing.category,
        Listing.location,
        Listing.status,
        Listing.pickup_allowed,
        Listing.shipping_allowed,
        Listing.shipping_cost_cents,
        Listing.dimensions,
        Listing.weight_grams,
        Listing.brand,
        Listing.model,
        Listing.color,
        Listing.material,
        func.count(ListingImage.id).label("image_count"),
    ).outerjoin(ListingImage, ListingImage.listing_id == Listing.id)
    listings = (
        listings.filter(Listing.owner_id == owner_id)
        .group_by(Listing.id)
        .order_by(Listing.id)
        .yield_per(250)
    )
    job_groups = (
        db.query(PublishingJob.status, PublishingJob.platform, func.count(PublishingJob.id))
        .join(Listing).filter(Listing.owner_id == owner_id)
        .group_by(PublishingJob.status, PublishingJob.platform).all()
    )
    mapping_platforms = dict(
        db.query(PlatformListingMapping.platform, func.count(PlatformListingMapping.id))
        .join(Listing)
        .filter(Listing.owner_id == owner_id, PlatformListingMapping.status != "skipped")
        .group_by(PlatformListingMapping.platform).all()
    )
    job_statuses: Counter[str] = Counter()
    job_platforms: Counter[str] = Counter()
    for status, platform, count in job_groups:
        job_statuses[status] += count
        job_platforms[platform] += count

    listing_statuses: Counter[str] = Counter()
    grade_counts: Counter[str] = Counter()
    issue_counter: Counter[str] = Counter()
    listing_count = price_count = price_sum = image_sum = missing_images = quality_sum = 0
    for row in listings:
        listing = _QualityListing(
            title=row.title,
            description=row.description,
            price_cents=row.price_cents,
            condition=row.condition,
            category=row.category,
            location=row.location,
            pickup_allowed=row.pickup_allowed,
            shipping_allowed=row.shipping_allowed,
            shipping_cost_cents=row.shipping_cost_cents,
            dimensions=row.dimensions,
            weight_grams=row.weight_grams,
            brand=row.brand,
            model=row.model,
            color=row.color,
            material=row.material,
        )
        image_count = row.image_count or 0
        result = analyze_listing_quality(listing, include_suggestions=False, image_count=image_count)
        issue_counter.update(issue["field"] for issue in result["issues"])
        listing_statuses[row.status] += 1
        grade_counts[result["grade"]] += 1
        listing_count += 1
        quality_sum += int(result["score"])
        image_sum += image_count
        missing_images += image_count == 0
        if row.price_cents > 0:
            price_sum += row.price_cents
            price_count += 1

    return {
        "source": "local_database",
        "external_tracking": False,
        "summary": {
            "listings_total": listing_count,
            "ready_listings": listing_statuses.get("ready", 0),
            "draft_listings": listing_statuses.get("draft", 0),
            "published_listings": listing_statuses.get("published", 0),
            "jobs_total": sum(job_statuses.values()),
            "needs_action_jobs": job_statuses.get("needs_user_action", 0),
            "failed_jobs": job_statuses.get("failed", 0),
            "average_quality_score": round(quality_sum / listing_count, 1) if listing_count else 0,
            "inventory_value_cents": price_sum,
            "average_price_cents": round(price_sum / price_count) if price_count else 0,
        },
        "listing_statuses": dict(sorted(listing_statuses.items())),
        "job_statuses": dict(sorted(job_statuses.items())),
        "job_platforms": dict(sorted(job_platforms.items())),
        "selected_platforms": dict(sorted(mapping_platforms.items())),
        "quality": {
            "grade_counts": dict(sorted(grade_counts.items())),
            "top_issue_fields": [
                {"field": field, "count": count}
                for field, count in issue_counter.most_common(8)
            ],
            "listings_missing_images": missing_images,
            "average_images_per_listing": round(image_sum / listing_count, 1) if listing_count else 0,
        },
    }
