"""Assemble shortlist export payloads and trigger n8n email delivery."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.session_store import SessionRecord

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_EMAIL_IN_TEXT_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass
class ExportResult:
    ok: bool
    message: str
    payload: dict[str, Any] | None = None
    delivered: bool = False


def validate_recipient_email(email: str) -> str:
    normalized = email.strip().lower()
    if not _EMAIL_RE.match(normalized):
        raise ValueError("Enter a valid email address.")
    return normalized


def extract_email_from_text(text: str) -> str | None:
    match = _EMAIL_IN_TEXT_RE.search(text)
    if not match:
        return None
    try:
        return validate_recipient_email(match.group(0))
    except ValueError:
        return None


def build_export_payload(record: SessionRecord, recipient_email: str) -> dict[str, Any]:
    constraints = record.constraints.constraints.model_dump()
    shortlist = [item.model_dump(mode="json") for item in record.shortlist]
    citations = [c.model_dump() for c in record.citations]
    booking = record.booking.model_dump() if record.booking else None

    properties = []
    for item in record.shortlist:
        listing = item.listing
        properties.append(
            {
                "listing_id": listing.listing_id,
                "society_name": listing.society_name,
                "locality": listing.locality,
                "rent": listing.rent,
                "bedrooms": listing.bedrooms,
                "amenities": listing.amenities,
                "match_score": item.rank.score,
                "match_reason": item.rank.reason,
                "matched": item.rank.matched,
                "neighborhood_notes": [n.model_dump() for n in item.neighborhood_notes],
                "neighborhood_guidance": listing.neighborhood_guidance.model_dump(),
                "citations": [c.model_dump() for c in item.citations],
            }
        )

    return {
        "session_id": record.session_id,
        "recipient_email": recipient_email,
        "constraints": constraints,
        "shortlist": shortlist,
        "citations": citations,
        "booking": booking,
        "selected_listing_id": record.selected_listing_id,
        "export_view": {
            "preferences_summary": constraints,
            "properties": properties,
            "session_citations": citations,
            "visit": booking,
        },
    }


def _write_dev_export(payload: dict[str, Any]) -> Path:
    out_dir = _REPO_ROOT / "data" / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_email = payload["recipient_email"].replace("@", "_at_")
    path = out_dir / f"{payload['session_id']}-{safe_email}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _post_n8n_webhook(url: str, payload: dict[str, Any], *, timeout: float = 20.0) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "PropertyScout/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            if response.status >= 400:
                raise RuntimeError(f"n8n webhook returned HTTP {response.status}")
            raw = response.read().decode("utf-8").strip()
            if not raw:
                return {"ok": True, "delivered": True}
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                return {"ok": True, "delivered": True, "raw": raw}
            if isinstance(body, dict):
                return body
            return {"ok": True, "delivered": True, "raw": body}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        message = detail or f"HTTP {exc.code}"
        raise RuntimeError(f"n8n webhook error: {message}") from exc


def export_shortlist_email(record: SessionRecord, email: str) -> ExportResult:
    if not record.shortlist:
        return ExportResult(ok=False, message="No shortlist to email.")

    recipient = validate_recipient_email(email)
    payload = build_export_payload(record, recipient)
    settings = get_settings()
    webhook = (settings.n8n_webhook_url or "").strip()

    if not webhook:
        path = _write_dev_export(payload)
        return ExportResult(
            ok=True,
            delivered=False,
            message=(
                f"Shortlist saved for {recipient}. "
                f"Local export: {path.name}. "
                "Set N8N_WEBHOOK_URL to deliver the PDF to your inbox."
            ),
            payload=None,
        )

    try:
        n8n_response = _post_n8n_webhook(webhook, payload)
    except urllib.error.URLError as exc:
        logger.warning("n8n export failed: %s", exc)
        return ExportResult(
            ok=False,
            message="Could not send the email right now. Please try again shortly.",
            payload=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("n8n export failed: %s", exc)
        return ExportResult(
            ok=False,
            message="Could not send the email right now. Please try again shortly.",
            payload=None,
        )

    if isinstance(n8n_response, dict) and n8n_response.get("ok") is False:
        detail = str(n8n_response.get("message") or "n8n workflow rejected the export.")
        return ExportResult(ok=False, message=detail, payload=None)

    return ExportResult(
        ok=True,
        delivered=True,
        message=f"Your shortlist is on its way to {recipient}.",
        payload=None,
    )
