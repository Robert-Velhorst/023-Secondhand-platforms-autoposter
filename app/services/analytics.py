from collections import Counter
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.models import Listing, PlatformListingMapping, PublishingJob
from app.services.quality import analyze_listing_quality


def build_user_analytics(db: Session, owner_id: int) -> dict[str, Any]:
    listings = (
        db.query(Listing)
        .options(selectinload(Listing.images), selectinload(Listing.platform_mappings))
        .filter(Listing.owner_id == owner_id)
        .all()
    )
    jobs = db.query(PublishingJob).join(Listing).filter(Listing.owner_id == owner_id).all()
    mappings = db.query(PlatformListingMapping).join(Listing).filter(Listing.owner_id == owner_id).all()

    quality_results = [analyze_listing_quality(listing) for listing in listings]
    issue_counter: Counter[str] = Counter()
    for result in quality_results:
        issue_counter.update(issue["field"] for issue in result["issues"])

    listing_statuses = Counter(listing.status for listing in listings)
    job_statuses = Counter(job.status for job in jobs)
    job_platforms = Counter(job.platform for job in jobs)
    mapping_platforms = Counter(mapping.platform for mapping in mappings if mapping.status != "skipped")
    prices = [listing.price_cents for listing in listings if listing.price_cents > 0]
    image_counts = [len(listing.images) for listing in listings]
    quality_scores = [int(result["score"]) for result in quality_results]

    return {
        "source": "local_database",
        "external_tracking": False,
        "summary": {
            "listings_total": len(listings),
            "ready_listings": listing_statuses.get("ready", 0),
            "draft_listings": listing_statuses.get("draft", 0),
            "published_listings": listing_statuses.get("published", 0),
            "jobs_total": len(jobs),
            "needs_action_jobs": job_statuses.get("needs_user_action", 0),
            "failed_jobs": job_statuses.get("failed", 0),
            "average_quality_score": round(mean(quality_scores), 1) if quality_scores else 0,
            "inventory_value_cents": sum(prices),
            "average_price_cents": round(mean(prices)) if prices else 0,
        },
        "listing_statuses": dict(sorted(listing_statuses.items())),
        "job_statuses": dict(sorted(job_statuses.items())),
        "job_platforms": dict(sorted(job_platforms.items())),
        "selected_platforms": dict(sorted(mapping_platforms.items())),
        "quality": {
            "grade_counts": dict(sorted(Counter(result["grade"] for result in quality_results).items())),
            "top_issue_fields": [
                {"field": field, "count": count}
                for field, count in issue_counter.most_common(8)
            ],
            "listings_missing_images": sum(1 for count in image_counts if count == 0),
            "average_images_per_listing": round(mean(image_counts), 1) if image_counts else 0,
        },
    }
