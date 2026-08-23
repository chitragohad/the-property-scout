#!/usr/bin/env python3
"""Demo: print a real Overpass OSM response for one Koramangala coordinate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "integrations" / "osm-mcp"))

from client import OverpassOsmClient  # noqa: E402


def main() -> None:
    client = OverpassOsmClient()
    ctx = client.nearby(
        listing_id="blr-km-201",
        lat=12.9352,
        lon=77.6245,
        radius_m=800,
    )
    print(json.dumps(ctx.model_dump(), indent=2))
    print(f"\nraw_call_id={ctx.raw_call_id} pois={len(ctx.pois)} empty_reason={ctx.empty_reason!r}")


if __name__ == "__main__":
    main()
