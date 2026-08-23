"""Export / email shortlist tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.export import (
    build_export_payload,
    export_shortlist_email,
    extract_email_from_text,
    validate_recipient_email,
)
from app.services.session_store import SessionRecord
from tests.test_explain import _item


def test_validate_recipient_email():
    assert validate_recipient_email("  User@Example.com ") == "user@example.com"


def test_validate_recipient_email_rejects_invalid():
    with pytest.raises(ValueError):
        validate_recipient_email("not-an-email")


def test_build_export_payload_includes_recipient():
    record = SessionRecord(session_id="sess-test")
    record.shortlist = [_item()]

    payload = build_export_payload(record, "renter@example.com")
    assert payload["recipient_email"] == "renter@example.com"
    assert payload["session_id"] == "sess-test"
    assert len(payload["shortlist"]) == 1
    assert payload["export_view"]["properties"]
    assert payload["export_view"]["properties"][0]["match_reason"]


def test_export_without_webhook_prepares_payload(monkeypatch: pytest.MonkeyPatch):
    record = SessionRecord(session_id="sess-test")
    record.shortlist = [_item()]
    monkeypatch.setenv("N8N_WEBHOOK_URL", "")
    from app.config import get_settings

    get_settings.cache_clear()

    result = export_shortlist_email(record, "renter@example.com")
    assert result.ok is True
    assert result.delivered is False
    assert "renter@example.com" in result.message
    assert result.payload is None
    get_settings.cache_clear()


def test_extract_email_from_text():
    assert extract_email_from_text("email me at renter@example.com please") == "renter@example.com"
    assert extract_email_from_text("no address here") is None


def test_export_with_webhook_delivers(monkeypatch: pytest.MonkeyPatch):
    record = SessionRecord(session_id="sess-test")
    record.shortlist = [_item()]
    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://n8n.example/hook")
    from app.config import get_settings

    get_settings.cache_clear()

    with patch("app.services.export._post_n8n_webhook") as post:
        post.return_value = {"ok": True, "delivered": True}
        result = export_shortlist_email(record, "renter@example.com")

    assert result.ok is True
    assert result.delivered is True
    post.assert_called_once()
    get_settings.cache_clear()


def test_export_with_webhook_rejects_n8n_failure(monkeypatch: pytest.MonkeyPatch):
    record = SessionRecord(session_id="sess-test")
    record.shortlist = [_item()]
    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://n8n.example/hook")
    from app.config import get_settings

    get_settings.cache_clear()

    with patch("app.services.export._post_n8n_webhook") as post:
        post.return_value = {"ok": False, "message": "SMTP not configured"}
        result = export_shortlist_email(record, "renter@example.com")

    assert result.ok is False
    assert result.delivered is False
    assert "SMTP" in result.message
    get_settings.cache_clear()
