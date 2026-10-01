from dataclasses import dataclass
from typing import Any

from app.models import Listing


@dataclass(frozen=True)
class QualityIssue:
    field: str
    severity: str
    message: str
    action: str


CATEGORY_RULES: tuple[dict[str, Any], ...] = (
    {
        "key": "electronics",
        "label": "electronics",
        "markers": ("electronics", "audio", "camera", "phone", "laptop", "computer", "console", "appliance"),
        "important_fields": ("brand", "model"),
        "field_message": "Electronics listings work better with brand and model details.",
        "field_action": "Add the brand and model when they are visible on the item.",
        "description_terms": (
            "tested",
            "working",
            "powers on",
            "battery",
            "charger",
            "cable",
            "accessories",
            "serial",
            "no known issues",
        ),
        "description_message": "Electronics testing and included accessories are unclear.",
        "description_action": (
            "Mention whether it is tested/working and which chargers, cables, or accessories are included."
        ),
        "description_line": (
            "Testing/accessories: tested working; include chargers, cables, remotes, or known missing parts."
        ),
        "tag_hints": ("tested", "working"),
    },
    {
        "key": "furniture",
        "label": "home and furniture",
        "markers": ("furniture", "home", "interior", "lamp", "table", "chair", "cabinet", "sofa", "desk"),
        "important_fields": ("dimensions", "material"),
        "field_message": "Home and furniture listings benefit from dimensions and material.",
        "field_action": "Add approximate width, height, depth, and the main material.",
        "description_terms": (
            "dimensions",
            "width",
            "height",
            "depth",
            "cm",
            "material",
            "solid",
            "veneer",
            "assembly",
        ),
        "description_message": "Measurements or material details are thin.",
        "description_action": "Mention dimensions, material, and whether disassembly or transport help is needed.",
        "description_line": "Measurements/material: add width, height, depth, material, and transport notes.",
        "tag_hints": ("furniture", "home"),
    },
    {
        "key": "fashion",
        "label": "fashion",
        "markers": ("clothing", "fashion", "shoes", "shirt", "jacket", "dress", "jeans", "sneakers", "boots"),
        "important_fields": ("brand", "color", "material"),
        "field_message": "Fashion listings benefit from brand, color, and material.",
        "field_action": "Add visible label, color, and fabric/material details.",
        "description_terms": ("size", "fit", "measurements", "waist", "inseam", "length", "eu", "label"),
        "description_message": "Sizing and fit details are unclear.",
        "description_action": "Mention label size, fit, and useful measurements.",
        "description_line": "Sizing/fit: add label size, fit notes, and useful measurements.",
        "tag_hints": ("fashion", "clothing"),
    },
    {
        "key": "vehicle",
        "label": "vehicle",
        "markers": ("bike", "bicycle", "car", "scooter", "moped", "vehicle", "trailer"),
        "important_fields": ("brand", "model"),
        "field_message": "Vehicle listings benefit from brand and model details.",
        "field_action": "Add the brand, model, frame or trim details when known.",
        "description_terms": ("mileage", "km", "service", "battery", "tires", "brakes", "lock", "working"),
        "description_message": "Vehicle condition details are incomplete.",
        "description_action": (
            "Mention mileage or use history, service state, tires/brakes/battery, and included keys or locks."
        ),
        "description_line": (
            "Vehicle condition: add mileage/use history, service state, tires/brakes/battery, and keys or locks."
        ),
        "tag_hints": ("vehicle", "transport"),
    },
)


def analyze_listing_quality(listing: Listing, *, include_suggestions: bool = True) -> dict[str, Any]:
    """Analyze a listing; callers that only aggregate quality can skip copy suggestions."""
    issues: list[QualityIssue] = []

    title = (listing.title or "").strip()
    description = (listing.description or "").strip()
    category = (listing.category or "").strip()
    location = (listing.location or "").strip()

    if not title:
        issues.append(issue("title", "critical", "Title is missing.", "Add a clear item title."))
    elif len(title) < 12:
        issues.append(
            issue("title", "warning", "Title is very short.", "Include brand, item type, or distinguishing detail.")
        )
    elif title.isupper() and len(title) > 8:
        issues.append(
            issue("title", "tip", "Title is all caps.", "Use normal capitalization for a calmer marketplace listing.")
        )

    if not description:
        issues.append(
            issue("description", "critical", "Description is missing.", "Add buyer-facing details and condition notes.")
        )
    elif len(description) < 80:
        issues.append(
            issue(
                "description",
                "warning",
                "Description is short.",
                "Mention condition, included parts, pickup/shipping, and any visible wear.",
            )
        )
    elif len(description) > 3000:
        issues.append(issue("description", "tip", "Description is long.", "Trim repeated details before posting."))

    if listing.price_cents <= 0:
        issues.append(issue("price_cents", "critical", "Price is missing.", "Set a realistic asking price above zero."))
    if not category:
        issues.append(
            issue("category", "critical", "Category is missing.", "Choose a category or add category mappings.")
        )
    if not location:
        issues.append(
            issue("location", "critical", "Location is missing.", "Add the pickup or shipping origin location.")
        )
    if not listing.images:
        issues.append(issue("images", "critical", "No images are attached.", "Upload at least one clear item photo."))
    elif len(listing.images) == 1:
        issues.append(
            issue("images", "tip", "Only one image is attached.", "Add extra angles, labels, defects, or scale photos.")
        )

    if not listing.pickup_allowed and not listing.shipping_allowed:
        issues.append(
            issue(
                "delivery_options",
                "warning",
                "No delivery method is selected.",
                "Enable pickup, shipping, or describe the delivery arrangement.",
            )
        )
    if listing.shipping_allowed and listing.shipping_cost_cents <= 0:
        issues.append(
            issue(
                "shipping_cost_cents",
                "tip",
                "Shipping is enabled without a shipping cost.",
                "Add the shipping cost or mention that it is calculated separately.",
            )
        )
    if listing.shipping_allowed and not listing.weight_grams and not listing.dimensions:
        issues.append(
            issue(
                "dimensions",
                "tip",
                "Shipping details are thin.",
                "Add weight or dimensions so buyers can judge shipping fit.",
            )
        )

    if listing.condition in {"used", "fair", "damaged", "for_parts"} and not mentions_wear(description):
        issues.append(
            issue(
                "description",
                "warning",
                "Condition notes are not explicit.",
                "Mention visible wear, defects, repairs, or say there are no known issues.",
            )
        )

    category_issues, category_checklist = category_specific_checks(listing, description)
    issues.extend(category_issues)

    score = quality_score(issues)
    grade = grade_for_score(score)
    if not include_suggestions:
        return {
            "score": score,
            "grade": grade,
            "issues": [item.__dict__ for item in issues],
        }

    suggestions: list[dict[str, Any]] = []
    suggested_title = build_title(listing)
    if suggested_title and suggested_title.casefold() != title.casefold():
        suggestions.append(
            {
                "field": "title",
                "value": suggested_title,
                "rationale": "Built from brand, model, color/material, and category fields.",
            }
        )

    suggested_description = build_description(listing)
    if suggested_description and len(description) < 160:
        suggestions.append(
            {
                "field": "description",
                "value": suggested_description,
                "rationale": "Structured buyer-facing draft from the current listing fields.",
            }
        )

    suggested_tags = build_tags(listing)
    if suggested_tags and set(tag.casefold() for tag in suggested_tags) != set(tag.casefold() for tag in listing.tags):
        suggestions.append(
            {
                "field": "tags",
                "value": suggested_tags,
                "rationale": "Search tags derived from item, brand, color, material, and category.",
            }
        )

    return {
        "score": score,
        "grade": grade,
        "summary": summary_for_score(score, issues),
        "issues": [item.__dict__ for item in issues],
        "suggestions": suggestions,
        "checklist": {
            "has_title": bool(title),
            "has_description": bool(description),
            "has_price": listing.price_cents > 0,
            "has_category": bool(category),
            "has_location": bool(location),
            "has_images": bool(listing.images),
            "has_delivery_method": bool(listing.pickup_allowed or listing.shipping_allowed),
            **category_checklist,
        },
    }


def issue(field: str, severity: str, message: str, action: str) -> QualityIssue:
    return QualityIssue(field=field, severity=severity, message=message, action=action)


def quality_score(issues: list[QualityIssue]) -> int:
    penalties = {"critical": 15, "warning": 8, "tip": 3}
    return max(0, 100 - sum(penalties.get(item.severity, 3) for item in issues))


def grade_for_score(score: int) -> str:
    if score >= 85:
        return "ready"
    if score >= 70:
        return "good"
    if score >= 50:
        return "needs_work"
    return "blocked"


def summary_for_score(score: int, issues: list[QualityIssue]) -> str:
    critical = sum(1 for item in issues if item.severity == "critical")
    warnings = sum(1 for item in issues if item.severity == "warning")
    if critical:
        return f"Fix {critical} required item before publishing."
    if warnings:
        return f"Listing is usable, with {warnings} quality improvement to consider."
    if score < 100:
        return "Listing is ready; optional polish remains."
    return "Listing has the core details buyers expect."


def mentions_wear(description: str) -> bool:
    markers = [
        "wear",
        "scratch",
        "scratches",
        "dent",
        "defect",
        "damage",
        "used",
        "condition",
        "working",
        "tested",
        "no known issues",
        "as pictured",
    ]
    return mentions_any(description, markers)


def category_specific_checks(listing: Listing, description: str) -> tuple[list[QualityIssue], dict[str, bool]]:
    rule = category_rule_for(listing.category)
    if not rule:
        return [], {}

    issues: list[QualityIssue] = []
    missing_fields = [field for field in rule["important_fields"] if not has_listing_value(listing, field)]
    if missing_fields:
        issues.append(
            issue(
                missing_fields[0],
                "tip",
                rule["field_message"],
                rule["field_action"],
            )
        )

    has_description_detail = bool(description) and mentions_any(description, rule["description_terms"])
    if description and not has_description_detail:
        issues.append(
            issue(
                "description",
                "warning",
                rule["description_message"],
                rule["description_action"],
            )
        )

    checklist_key = f"has_{rule['key']}_details"
    return issues, {checklist_key: not missing_fields and has_description_detail}


def category_rule_for(category: str) -> dict[str, Any] | None:
    text = (category or "").casefold()
    if not text:
        return None
    for rule in CATEGORY_RULES:
        if any(marker in text for marker in rule["markers"]):
            return rule
    return None


def has_listing_value(listing: Listing, field: str) -> bool:
    value = getattr(listing, field, None)
    if isinstance(value, dict | list):
        return bool(value)
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def mentions_any(text: str, markers: list[str] | tuple[str, ...]) -> bool:
    normalized = (text or "").casefold()
    return any(marker in normalized for marker in markers)


def build_title(listing: Listing) -> str:
    parts = [listing.brand, listing.model, listing.color, listing.material, listing.category or listing.title]
    cleaned = []
    seen = set()
    for part in parts:
        value = (part or "").strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return " ".join(cleaned)[:160]


def build_description(listing: Listing) -> str:
    lines = []
    title = (listing.title or build_title(listing) or "Item").strip()
    lines.append(f"{title} in {format_condition(listing.condition)} condition.")
    detail_parts = [listing.brand, listing.model, listing.color, listing.material]
    details = ", ".join(part.strip() for part in detail_parts if part and part.strip())
    if details:
        lines.append(f"Details: {details}.")
    if listing.notes:
        lines.append(str(listing.notes).strip())
    if listing.pickup_allowed and listing.shipping_allowed:
        lines.append("Available for pickup or shipping.")
    elif listing.pickup_allowed:
        lines.append("Available for pickup.")
    elif listing.shipping_allowed:
        lines.append("Shipping is available.")
    if listing.location:
        lines.append(f"Location: {listing.location}.")
    lines.extend(category_description_lines(listing))
    return "\n".join(lines)


def format_condition(condition: str) -> str:
    return (condition or "used").replace("_", " ")


def build_tags(listing: Listing) -> list[str]:
    rule = category_rule_for(listing.category)
    raw_values = [
        *(listing.tags or []),
        listing.category,
        listing.brand,
        listing.model,
        listing.color,
        listing.material,
        *(rule["tag_hints"] if rule else ()),
    ]
    tags = []
    seen = set()
    for raw_value in raw_values:
        value = str(raw_value or "").strip()
        if not value:
            continue
        for candidate in split_tag_value(value):
            key = candidate.casefold()
            if key not in seen and len(candidate) <= 40:
                seen.add(key)
                tags.append(candidate)
            if len(tags) >= 10:
                return tags
    return tags


def split_tag_value(value: str) -> list[str]:
    if "," in value:
        return [part.strip() for part in value.split(",") if part.strip()]
    return [value]


def category_description_lines(listing: Listing) -> list[str]:
    rule = category_rule_for(listing.category)
    if not rule:
        return []
    description = (listing.description or "").strip()
    if mentions_any(description, rule["description_terms"]):
        return []
    return [rule["description_line"]]
