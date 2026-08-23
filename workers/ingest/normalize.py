"""Normalize raw listing payloads into the Property Scout schema."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from pii import assert_no_pii_keys, scrub_listing_dict
from neighborhood_guidance import guidance_for_locality

UNAVAILABLE_STATUSES = frozenset(
    {
        "not for rent",
        "not_for_rent",
        "transparency",
        "transparency-only",
        "unavailable",
        "rented",
        "inactive",
    }
)

AVAILABLE_STATUSES = frozenset(
    {
        "available",
        "avlb",
        "avail",
        "for rent",
        "for_rent",
        "listed",
        "active",
        "whole avbl",
    }
)

AMENITY_ALIASES: dict[str, str] = {
    "car parking": "parking",
    "bike parking": "parking",
    "two wheeler parking": "parking",
    "covered parking": "parking",
    "open parking": "parking",
    "park": "parking",
    "pet friendly": "pet-friendly",
    "pets allowed": "pet-friendly",
    "pets": "pet-friendly",
    "balconies": "balcony",
    "private balcony": "balcony",
    "gymnasium": "gym",
    "power backup": "power-backup",
    "lift": "elevator",
    "lifts": "elevator",
    "security": "security",
    "cctv": "security",
    "swimming pool": "pool",
    "club house": "clubhouse",
}


def normalize_amenity(token: str) -> str:
    cleaned = re.sub(r"\s+", " ", token.strip().lower())
    cleaned = cleaned.replace("_", " ")
    return AMENITY_ALIASES.get(cleaned, cleaned.replace(" ", "-"))


def normalize_amenities(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = re.split(r"[,|/]", raw)
    elif isinstance(raw, list):
        parts = [str(item) for item in raw]
    else:
        parts = [str(raw)]
    normalized: list[str] = []
    seen: set[str] = set()
    for part in parts:
        token = normalize_amenity(part)
        if not token or token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    return normalized


def _parse_rent(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).lower().replace(",", "").replace("₹", "").strip()
    text = text.replace("/month", "").replace("per month", "").strip()
    if text.endswith("k"):
        try:
            return int(float(text[:-1]) * 1000)
        except ValueError:
            return None
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None


def _parse_bedrooms(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).lower()
    match = re.search(r"(\d+)\s*(?:bhk|bed)?", text)
    return int(match.group(1)) if match else None


def _availability_status(raw: dict[str, Any]) -> str:
    candidates = [
        raw.get("availability_status"),
        raw.get("status"),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        normalized = str(candidate).strip().lower()
        if normalized in UNAVAILABLE_STATUSES or "not for rent" in normalized:
            return "not_for_rent"
        if normalized in AVAILABLE_STATUSES or "avail" in normalized or "avlb" in normalized:
            return "available"
    # Explicit boolean flags from map pins
    if raw.get("for_rent") is False or raw.get("is_available") is False:
        return "not_for_rent"
    if raw.get("for_rent") is True or raw.get("is_available") is True:
        return "available"
    return "unknown"


def is_currently_available(raw: dict[str, Any]) -> bool:
    return _availability_status(raw) == "available"


def _stable_listing_id(raw: dict[str, Any], source_url: str) -> str:
    if raw.get("listing_id"):
        return str(raw["listing_id"])
    if raw.get("id"):
        return f"blr-{raw['id']}"
    digest = hashlib.sha1(source_url.encode("utf-8")).hexdigest()[:12]
    return f"blr-{digest}"


def _parse_available_from(value: Any) -> str:
    """Normalize to ISO date YYYY-MM-DD; default to a near-term available date."""
    if value is None or value == "":
        return "2026-08-21"
    text = str(value).strip()
    # Already ISO
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    # DD/MM/YYYY or DD-MM-YYYY
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"
    # Immediate / immediate possession
    if "immediate" in text.lower() or text.lower() in {"now", "asap"}:
        return "2026-08-21"
    return text[:32]


def _parse_deposit(value: Any, rent: int | None = None) -> int:
    """Parse deposit to integer INR; default to 2 months' rent when missing."""
    if value is None or value == "":
        return int(rent * 2) if rent else 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).lower().replace(",", "").replace("₹", "").strip()
    # "2 months" / "3 month deposit"
    months = re.search(r"(\d+)\s*months?", text)
    if months and rent:
        return int(months.group(1)) * int(rent)
    if text.endswith("k"):
        try:
            return int(float(text[:-1]) * 1000)
        except ValueError:
            return int(rent * 2) if rent else 0
    match = re.search(r"\d+", text)
    if match:
        return int(match.group())
    return int(rent * 2) if rent else 0


LISTING_TYPE_WHOLE = "whole flat"
LISTING_TYPE_ROOM = "room in a flat"


def _parse_listing_type(value: Any) -> str:
    """Normalize to 'whole flat' or 'room in a flat'."""
    if value is None or value == "":
        return LISTING_TYPE_WHOLE
    text = str(value).strip().lower().replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    room_markers = (
        "room in a flat",
        "room in flat",
        "shared room",
        "single room",
        "room only",
        "pg room",
        "flatmate",
        "looking for: room",
    )
    if text in {"room", "rooms"} or any(marker in text for marker in room_markers):
        return LISTING_TYPE_ROOM
    if "whole" in text or text in {"flat", "apartment", "entire flat", "full flat"}:
        return LISTING_TYPE_WHOLE
    return LISTING_TYPE_WHOLE


def _parse_food_preference(value: Any) -> str:
    if value is None or value == "":
        return "any"
    text = str(value).strip().lower().replace("_", " ").replace("-", " ")
    if "non" in text and "veg" in text:
        return "non-veg"
    if text in {"veg", "vegetarian", "pure veg", "veg only"}:
        return "veg"
    if text in {"any", "both", "eggetarian", "no preference"}:
        return "any"
    return "any"


def _parse_smoking_preference(value: Any) -> str:
    if value is None or value == "":
        return "any"
    text = str(value).strip().lower().replace("_", " ").replace("-", " ")
    if any(token in text for token in ("no smoke", "non smoke", "no smoking", "not allowed", "smoke free")):
        return "no smoking"
    if any(token in text for token in ("smoking allowed", "smoker", "smoking ok", "yes")):
        return "smoking allowed"
    if text in {"any", "no preference", "okay either"}:
        return "any"
    return "any"


def _parse_gender(value: Any, listing_type: str) -> str | None:
    """Gender preference only applies to room-in-a-flat listings."""
    if listing_type != LISTING_TYPE_ROOM:
        return None
    if value is None or value == "":
        return "any"
    text = str(value).strip().lower()
    if text in {"male", "m", "men", "boys", "boy"}:
        return "male"
    if text in {"female", "f", "women", "girls", "girl"}:
        return "female"
    if text in {"any", "both", "all", "no preference"}:
        return "any"
    return "any"


def normalize_listing(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Scrub + normalize. Returns None if unavailable or missing critical fields."""
    scrubbed = scrub_listing_dict(raw)
    assert_no_pii_keys(scrubbed)

    status = _availability_status(scrubbed)
    if status != "available":
        return None

    source_url = (
        scrubbed.get("source_url")
        or scrubbed.get("url")
        or scrubbed.get("permalink")
    )
    if not source_url:
        listing_key = scrubbed.get("listing_id") or scrubbed.get("id")
        if listing_key:
            source_url = f"https://bengaluru.rent/#listing-{listing_key}"
        else:
            return None

    rent = _parse_rent(scrubbed.get("rent") or scrubbed.get("price") or scrubbed.get("rent_inr"))
    bedrooms = _parse_bedrooms(
        scrubbed.get("bedrooms") or scrubbed.get("bhk") or scrubbed.get("beds")
    )
    lat = scrubbed.get("latitude", scrubbed.get("lat"))
    lon = scrubbed.get("longitude", scrubbed.get("lng", scrubbed.get("lon")))
    if rent is None or bedrooms is None or lat is None or lon is None:
        return None

    locality = (
        scrubbed.get("locality")
        or scrubbed.get("neighborhood")
        or scrubbed.get("neighbourhood")
        or scrubbed.get("area")
        or "Bengaluru"
    )
    location = scrubbed.get("location") or f"Bengaluru, {locality}"

    listing_type = _parse_listing_type(
        scrubbed.get("listing_type")
        or scrubbed.get("type")
        or scrubbed.get("pin_type")
        or scrubbed.get("flat_type")
    )

    return {
        "listing_id": _stable_listing_id(scrubbed, str(source_url)),
        "source_url": str(source_url),
        "location": str(location),
        "locality": str(locality),
        "rent": int(rent),
        "bedrooms": int(bedrooms),
        "furnishing": str(
            scrubbed.get("furnishing") or scrubbed.get("furnished") or "unknown"
        ).lower(),
        "amenities": normalize_amenities(scrubbed.get("amenities") or scrubbed.get("facilities")),
        "society_name": str(
            scrubbed.get("society_name") or scrubbed.get("society") or scrubbed.get("building") or "Unknown society"
        ),
        "square_footage": float(
            scrubbed.get("square_footage")
            or scrubbed.get("sqft")
            or scrubbed.get("area_sqft")
            or 0
        ),
        "available_from": _parse_available_from(
            scrubbed.get("available_from")
            or scrubbed.get("available_date")
            or scrubbed.get("possession_date")
            or scrubbed.get("move_in_date")
        ),
        "deposit_amount": _parse_deposit(
            scrubbed.get("deposit_amount")
            or scrubbed.get("deposit")
            or scrubbed.get("security_deposit"),
            rent=int(rent),
        ),
        "listing_type": listing_type,
        "food_preference": _parse_food_preference(
            scrubbed.get("food_preference")
            or scrubbed.get("food")
            or scrubbed.get("food_pref")
        ),
        "smoking_preference": _parse_smoking_preference(
            scrubbed.get("smoking_preference")
            or scrubbed.get("smoking")
            or scrubbed.get("smoke")
        ),
        "gender": _parse_gender(
            scrubbed.get("gender") or scrubbed.get("gender_preference") or scrubbed.get("preferred_gender"),
            listing_type,
        ),
        "neighborhood_guidance": scrubbed.get("neighborhood_guidance")
        if isinstance(scrubbed.get("neighborhood_guidance"), dict)
        else guidance_for_locality(str(locality)),
        "availability_status": "available",
        "latitude": float(lat),
        "longitude": float(lon),
    }
