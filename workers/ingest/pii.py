"""PII scrubbing for listing ingestion.

Removes contact/owner/agent fields and redacts phone/email patterns from free text
before data enters the database, UI, logs, or LLM context.
"""

from __future__ import annotations

import copy
import re
from typing import Any

FORBIDDEN_KEYS = frozenset(
    {
        "owner_name",
        "agent_name",
        "phone",
        "email",
        "contact",
        "whatsapp",
        "owner",
        "agent",
        "mobile",
        "phone_number",
        "email_address",
        "contact_number",
        "owner_phone",
        "agent_phone",
        "owner_email",
        "agent_email",
    }
)

# Nested keys that may appear under alternate casings
_FORBIDDEN_NORMALIZED = frozenset(k.lower().replace("-", "_") for k in FORBIDDEN_KEYS)

_PHONE_RE = re.compile(
    r"(?:\+?91[\s-]*)?(?:\d[\s-]*){10}|\b\d{5}[\s-]?\d{5}\b"
)
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)
_NAME_HINT_RE = re.compile(
    r"(?i)\b(?:contact|call|whatsapp|owner|agent)\s*[:\-]\s*[A-Za-z][A-Za-z .]{1,40}"
)


def _normalize_key(key: str) -> str:
    return key.lower().replace("-", "_").strip()


def scrub_text(value: str) -> str:
    """Redact phones, emails, and contact-name hints from free text."""
    redacted = _EMAIL_RE.sub("[redacted-email]", value)
    redacted = _PHONE_RE.sub("[redacted-phone]", redacted)
    redacted = _NAME_HINT_RE.sub("[redacted-contact]", redacted)
    return redacted


def _scrub_value(value: Any) -> Any:
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, list):
        return [_scrub_value(item) for item in value]
    if isinstance(value, dict):
        return scrub_listing_dict(value)
    return value


def scrub_listing_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a deep-copied listing dict with PII keys removed and text redacted."""
    if not isinstance(raw, dict):
        raise TypeError("listing payload must be a dict")

    cleaned: dict[str, Any] = {}
    for key, value in copy.deepcopy(raw).items():
        if _normalize_key(str(key)) in _FORBIDDEN_NORMALIZED:
            continue
        cleaned[str(key)] = _scrub_value(value)

    # Defense in depth: ensure no forbidden keys remain after nested scrub
    for key in list(cleaned.keys()):
        if _normalize_key(key) in _FORBIDDEN_NORMALIZED:
            del cleaned[key]

    return cleaned


def assert_no_pii_keys(payload: dict[str, Any]) -> None:
    """Raise ValueError if any forbidden key is present (recursive)."""

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                full = f"{path}.{key}" if path else key
                if _normalize_key(str(key)) in _FORBIDDEN_NORMALIZED:
                    raise ValueError(f"Forbidden PII key present: {full}")
                walk(value, full)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{path}[{i}]")

    walk(payload)
