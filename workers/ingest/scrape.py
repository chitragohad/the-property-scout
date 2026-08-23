"""Fetch listing payloads for ingestion.

Primary source of truth for the product is https://bengaluru.rent/.

Live HTML is a map SPA; bulk pin APIs are rate-limited and not a stable
public contract. This module therefore supports:

1. ``INGEST_JSON_PATH`` — path to a JSON array of raw listing dicts
2. ``INGEST_SOURCE_URL`` — optional HTTP JSON endpoint returning a list/object
3. Bundled seed data (always available for local/dev/demo)

Rate limiting: sleeps between HTTP requests when configured.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from seed_data import SEED_RAW_LISTINGS

DEFAULT_USER_AGENT = "PropertyScoutIngest/0.1 (+local research; respectful rate limit)"
MIN_REQUEST_INTERVAL_SEC = 1.5


def _load_json_file(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _coerce_list(payload)


def _coerce_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("listings", "pins", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    raise ValueError("Unsupported JSON shape for listings ingest")


def fetch_from_http(url: str, *, timeout: float = 20.0) -> list[dict[str, Any]]:
    """GET JSON from a configured URL with a polite User-Agent and delay."""
    time.sleep(MIN_REQUEST_INTERVAL_SEC)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to fetch ingest source: {exc}") from exc
    return _coerce_list(json.loads(body))


def load_raw_listings(
    *,
    json_path: str | None = None,
    source_url: str | None = None,
    use_seed: bool = True,
) -> list[dict[str, Any]]:
    """Load raw listings from file, HTTP, and/or seed (in that preference order)."""
    path = json_path or os.getenv("INGEST_JSON_PATH")
    url = source_url or os.getenv("INGEST_SOURCE_URL")

    if path:
        return _load_json_file(Path(path).expanduser().resolve())

    if url:
        return fetch_from_http(url)

    if use_seed:
        return list(SEED_RAW_LISTINGS)

    raise RuntimeError(
        "No ingest source configured. Set INGEST_JSON_PATH, INGEST_SOURCE_URL, "
        "or allow seed fallback."
    )
