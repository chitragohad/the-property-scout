import pytest
from pydantic import ValidationError

from app.schemas.constraints import (
    Constraints,
    HardConstraints,
    PreferencePatch,
    SoftPreferences,
)
from app.schemas.listing import Listing
from app.schemas.ranking import Citation, RankResult
from app.schemas.session import SessionSnapshot, TurnResponse


REQUIRED_LISTING_FIELDS = [
    "listing_id",
    "source_url",
    "location",
    "locality",
    "rent",
    "bedrooms",
    "furnishing",
    "amenities",
    "society_name",
    "square_footage",
    "available_from",
    "deposit_amount",
    "listing_type",
    "food_preference",
    "smoking_preference",
    "neighborhood_guidance",
    "availability_status",
    "latitude",
    "longitude",
]


def _valid_listing_payload() -> dict:
    return {
        "listing_id": "blr-001",
        "source_url": "https://bengaluru.rent/listing/blr-001",
        "location": "Bengaluru",
        "locality": "Koramangala",
        "rent": 35000,
        "bedrooms": 2,
        "furnishing": "semi-furnished",
        "amenities": ["parking", "balcony"],
        "society_name": "Green Heights",
        "square_footage": 1100,
        "available_from": "2026-09-01",
        "deposit_amount": 70000,
        "listing_type": "whole flat",
        "food_preference": "veg",
        "smoking_preference": "no smoking",
        "gender": None,
        "neighborhood_guidance": {
            "locality": "Koramangala",
            "safety": "Busy mixed area; verify society security.",
            "amenities": "Retail, cafes, clinics nearby.",
            "transit_character": "Bus and arterial connectivity; metro catchments nearby.",
            "sources": [
                {"title": "bengaluru.rent", "url": "https://bengaluru.rent/", "snippet": "Public rental listings map."},
                {"title": "OpenStreetMap", "url": "https://www.openstreetmap.org/copyright", "snippet": "Open map data."},
            ],
        },
        "availability_status": "available",
        "latitude": 12.9352,
        "longitude": 77.6245,
    }


def test_listing_requires_all_architecture_fields():
    listing = Listing.model_validate(_valid_listing_payload())
    for field in REQUIRED_LISTING_FIELDS:
        assert field in Listing.model_fields
        assert getattr(listing, field) is not None or field == "amenities"


@pytest.mark.parametrize("missing_field", REQUIRED_LISTING_FIELDS)
def test_listing_rejects_missing_required_field(missing_field: str):
    payload = _valid_listing_payload()
    del payload[missing_field]
    with pytest.raises(ValidationError):
        Listing.model_validate(payload)


def test_constraints_and_preference_patch_defaults():
    constraints = Constraints()
    assert constraints.hard.bedrooms is None
    assert constraints.hard.must_have_amenities == []
    assert constraints.soft.near_metro is None

    patch = PreferencePatch(
        hard=HardConstraints(max_rent=40000),
        soft=SoftPreferences(pet_friendly=True),
    )
    assert patch.patch_mode == "merge"
    assert patch.hard is not None
    assert patch.hard.max_rent == 40000


def test_rank_result_and_citation_shapes():
    rank = RankResult(
        listing_id="blr-001",
        score=87.0,
        matched=["2BHK", "within budget", "parking"],
        missing=["balcony"],
        reason="Strong match for all mandatory requirements.",
    )
    assert rank.excluded is False
    assert rank.exclusion_reasons == []

    citation = Citation(
        id="c1",
        title="Koramangala",
        url="https://en.wikipedia.org/wiki/Koramangala",
        snippet="A locality in Bengaluru.",
        locality="Koramangala",
        topic="neighborhood",
    )
    assert citation.id == "c1"


def test_session_snapshot_and_turn_response():
    snapshot = SessionSnapshot(session_id="sess-1")
    assert snapshot.phase == "idle"
    assert snapshot.constraints.hard.max_rent is None

    response = TurnResponse(
        assistant_text="Got it.",
        constraints=Constraints(
            hard=HardConstraints(
                bedrooms=2,
                locality="Koramangala",
                max_rent=35000,
                must_have_amenities=["parking"],
            )
        ),
        phase="awaiting_confirm",
    )
    assert response.shortlist is None
    assert response.phase == "awaiting_confirm"
