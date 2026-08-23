"""Preference extraction → PreferencePatch (schema-validated)."""

from __future__ import annotations

import re
from typing import Any

from app.schemas.constraints import HardConstraints, PreferencePatch, SoftPreferences
from app.services.gemini import GeminiClient, parse_json_object

LOCALITIES = (
    "Koramangala",
    "HSR Layout",
    "Indiranagar",
    "Whitefield",
    "Jayanagar",
)


def extract_preferences_heuristic(text: str) -> PreferencePatch:
    t = text.lower()
    hard_data: dict[str, Any] = {}
    soft_data: dict[str, Any] = {}

    m = re.search(r"(\d)\s*(?:bhk|bed(?:room)?s?)", t)
    if m:
        hard_data["bedrooms"] = int(m.group(1))

    rent = None
    for pattern in (
        r"(?:under|below|max(?:imum)?|upto|up to|budget(?:\s*of)?)\s*(?:rs\.?|₹|inr)?\s*([0-9][0-9,]{2,})",
        r"([0-9][0-9,]{3,})\s*(?:rs\.?|₹|inr)?\s*(?:budget|max)?",
    ):
        rm = re.search(pattern, t)
        if rm:
            rent = int(rm.group(1).replace(",", ""))
            break
    if rent is not None:
        hard_data["max_rent"] = rent

    for loc in LOCALITIES:
        if loc.lower() in t:
            hard_data["locality"] = loc
            break
    if "locality" not in hard_data:
        if "hsr" in t:
            hard_data["locality"] = "HSR Layout"

    amenities: list[str] = []
    if "parking" in t:
        amenities.append("parking")
    if "balcony" in t:
        amenities.append("balcony")
        soft_data["balcony"] = True
    if "pet" in t:
        amenities.append("pet-friendly")
        soft_data["pet_friendly"] = True
    if amenities:
        hard_data["must_have_amenities"] = amenities

    if re.search(r"\b(near|close to|nearby).*(metro|subway|tube)\b", t) or "metro" in t:
        soft_data["near_metro"] = True

    hard = HardConstraints(**hard_data) if hard_data else None
    soft = SoftPreferences(**soft_data) if soft_data else None
    # Only include models if something was set — use model_construct with unset handling
    patch_hard = None
    if hard_data:
        patch_hard = HardConstraints.model_validate(hard_data)
    patch_soft = None
    if soft_data:
        patch_soft = SoftPreferences.model_validate(soft_data)
    return PreferencePatch(hard=patch_hard, soft=patch_soft, patch_mode="merge")


def extract_preferences(
    text: str,
    *,
    client: GeminiClient | None = None,
) -> PreferencePatch:
    gemini = client
    if gemini is not None and gemini.available:
        try:
            system = (
                "Extract rental preferences for Bengaluru Property Scout. "
                "Return ONLY JSON with optional keys: "
                '{"hard":{"bedrooms":int|null,"locality":string|null,"max_rent":int|null,'
                '"must_have_amenities":[string]},'
                '"soft":{"near_metro":bool|null,"pet_friendly":bool|null,"balcony":bool|null},'
                '"commute_point":string|null,"patch_mode":"merge"}. '
                "Omit unknown fields. Do not invent facts."
            )
            raw = gemini.generate_text(f"User said: {text}", system=system)
            data = parse_json_object(raw)
            data.setdefault("patch_mode", "merge")
            return PreferencePatch.model_validate(data)
        except Exception:
            pass
    return extract_preferences_heuristic(text)
