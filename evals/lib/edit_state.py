"""Session state snapshots and deep diffs for voice-edit evaluations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.services.session_store import SessionRecord


@dataclass
class EditViolation:
    path: str
    before: Any
    after: Any
    message: str


def snapshot_session(record: SessionRecord) -> dict[str, Any]:
    constraints = record.constraints.constraints.model_dump()
    return {
        "phase": record.phase,
        "constraints": constraints,
        "shortlist_ids": [item.listing.listing_id for item in record.shortlist],
        "selected_listing_id": record.selected_listing_id,
        "booking": record.booking.model_dump() if record.booking else None,
        "clarification_count": record.constraints.clarification_count,
        "citation_count": len(record.citations),
    }


def remove_listing_at_position(state: dict[str, Any], position: int) -> dict[str, Any]:
    """Reference edit used to validate eval diff logic (expected remove-by-position behavior)."""
    updated = deepcopy(state)
    ids = list(updated["shortlist_ids"])
    if position < 0 or position >= len(ids):
        raise IndexError(f"shortlist position {position} out of range")
    ids.pop(position)
    updated["shortlist_ids"] = ids
    return updated


def remove_listing_by_id(state: dict[str, Any], listing_id: str) -> dict[str, Any]:
    updated = deepcopy(state)
    updated["shortlist_ids"] = [lid for lid in updated["shortlist_ids"] if lid != listing_id]
    return updated


def diff_states(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    allowed_changed_paths: set[str],
) -> list[EditViolation]:
    violations: list[EditViolation] = []

    def walk(path: str, left: Any, right: Any) -> None:
        if path in allowed_changed_paths:
            return
        if isinstance(left, dict) and isinstance(right, dict):
            keys = set(left) | set(right)
            for key in sorted(keys):
                child = f"{path}.{key}" if path else key
                walk(child, left.get(key), right.get(key))
            return
        if left != right:
            violations.append(
                EditViolation(
                    path=path,
                    before=left,
                    after=right,
                    message=f"unexpected change at {path}",
                )
            )

    walk("", before, after)
    return violations


def assert_only_paths_changed(
    before: dict[str, Any],
    after: dict[str, Any],
    allowed_changed_paths: set[str],
) -> list[EditViolation]:
    return diff_states(before, after, allowed_changed_paths=allowed_changed_paths)
