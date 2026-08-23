"""Tests for listing PII scrubber."""

from __future__ import annotations

import pytest

from pii import FORBIDDEN_KEYS, assert_no_pii_keys, scrub_listing_dict, scrub_text


def test_removes_forbidden_keys():
    raw = {
        "listing_id": "blr-001",
        "owner_name": "Ravi Kumar",
        "agent_name": "Broker Bob",
        "phone": "9876543210",
        "email": "owner@example.com",
        "contact": "call me",
        "whatsapp": "+91 98765 43210",
        "society_name": "Green Heights",
        "rent": 35000,
    }
    cleaned = scrub_listing_dict(raw)
    for key in FORBIDDEN_KEYS:
        assert key not in cleaned
    assert cleaned["listing_id"] == "blr-001"
    assert cleaned["society_name"] == "Green Heights"
    assert cleaned["rent"] == 35000
    assert_no_pii_keys(cleaned)


def test_redacts_phone_and_email_in_free_text():
    text = "Call 9876543210 or email owner@example.com for visit"
    redacted = scrub_text(text)
    assert "9876543210" not in redacted
    assert "owner@example.com" not in redacted
    assert "[redacted-phone]" in redacted
    assert "[redacted-email]" in redacted


def test_redacts_nested_and_alternate_keys():
    raw = {
        "listing_id": "blr-002",
        "meta": {
            "Owner-Name": "Anita",
            "Phone-Number": "9988776655",
            "notes": "WhatsApp +91 99887 76655",
        },
        "amenities": ["parking"],
    }
    cleaned = scrub_listing_dict(raw)
    assert "Owner-Name" not in cleaned.get("meta", {})
    assert "Phone-Number" not in cleaned.get("meta", {})
    assert "9988776655" not in str(cleaned)
    assert_no_pii_keys(cleaned)


def test_assert_no_pii_keys_raises():
    with pytest.raises(ValueError, match="Forbidden PII key"):
        assert_no_pii_keys({"phone": "9999999999"})
