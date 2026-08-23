"""Curated public sources + fetch helpers for neighborhood RAG."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = ROOT / "data" / "rag" / "raw_sources.json"

# Priority localities from Phase 3 plan
PRIORITY_SOURCES: list[dict[str, str]] = [
    {
        "locality": "Koramangala",
        "title": "Koramangala — Wikipedia",
        "url": "https://en.wikipedia.org/wiki/Koramangala",
    },
    {
        "locality": "HSR Layout",
        "title": "HSR Layout — Wikipedia",
        "url": "https://en.wikipedia.org/wiki/HSR_Layout",
    },
    {
        "locality": "Indiranagar",
        "title": "Indiranagar — Wikipedia",
        "url": "https://en.wikipedia.org/wiki/Indiranagar",
    },
    {
        "locality": "Whitefield",
        "title": "Whitefield, Bangalore — Wikipedia",
        "url": "https://en.wikipedia.org/wiki/Whitefield,_Bangalore",
    },
    {
        "locality": "Jayanagar",
        "title": "Jayanagar — Wikipedia",
        "url": "https://en.wikipedia.org/wiki/Jayanagar",
    },
]


@dataclass
class FetchedSource:
    locality: str
    title: str
    url: str
    text: str
    ok: bool
    error: str | None = None


def _strip_html(html: str) -> str:
    # Prefer extractable plaintext from Wikipedia HTML without heavy deps
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    html = re.sub(r"&nbsp;", " ", html)
    html = re.sub(r"&amp;", "&", html)
    html = re.sub(r"&quot;", '"', html)
    html = re.sub(r"&#\d+;", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def fetch_url(url: str, *, timeout_s: float = 20.0) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "PropertyScoutRAG/0.1 (educational; contact: local)"},
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def fetch_sources(
    sources: list[dict[str, str]] | None = None,
    *,
    use_network: bool = True,
) -> list[FetchedSource]:
    selected = sources or PRIORITY_SOURCES
    out: list[FetchedSource] = []
    for src in selected:
        if not use_network:
            out.append(
                FetchedSource(
                    locality=src["locality"],
                    title=src["title"],
                    url=src["url"],
                    text="",
                    ok=False,
                    error="network disabled",
                )
            )
            continue
        try:
            html = fetch_url(src["url"])
            text = _strip_html(html)
            out.append(
                FetchedSource(
                    locality=src["locality"],
                    title=src["title"],
                    url=src["url"],
                    text=text[:50000],
                    ok=bool(text),
                    error=None if text else "empty body",
                )
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            out.append(
                FetchedSource(
                    locality=src["locality"],
                    title=src["title"],
                    url=src["url"],
                    text="",
                    ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    return out


def save_raw(sources: list[FetchedSource], path: Path | None = None) -> Path:
    target = path or DEFAULT_CACHE
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "locality": s.locality,
            "title": s.title,
            "url": s.url,
            "text": s.text,
            "ok": s.ok,
            "error": s.error,
        }
        for s in sources
    ]
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def load_raw(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or DEFAULT_CACHE
    if not target.exists():
        return []
    return json.loads(target.read_text(encoding="utf-8"))


def main() -> None:
    fetched = fetch_sources(use_network=True)
    path = save_raw(fetched)
    ok = sum(1 for s in fetched if s.ok)
    print(f"Fetched {ok}/{len(fetched)} sources → {path}")


if __name__ == "__main__":
    main()
