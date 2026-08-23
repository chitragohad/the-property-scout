"""Session constraint manager — single source of truth for preferences."""

from __future__ import annotations

from copy import deepcopy

from app.schemas.constraints import (
    Constraints,
    HardConstraints,
    PreferencePatch,
    SoftPreferences,
)

CRITICAL_FIELDS = ("bedrooms", "locality", "max_rent")


class ConstraintManager:
    def __init__(
        self,
        initial: Constraints | None = None,
        max_clarifications: int = 5,
    ) -> None:
        self._constraints = deepcopy(initial) if initial is not None else Constraints()
        self.max_clarifications = max_clarifications
        self.clarification_count = 0

    @property
    def constraints(self) -> Constraints:
        return deepcopy(self._constraints)

    def merge(self, patch: PreferencePatch) -> Constraints:
        """Merge a preference patch without resetting unrelated fields."""
        if patch.patch_mode != "merge":
            raise ValueError(f"Unsupported patch_mode: {patch.patch_mode}")

        hard = self._constraints.hard.model_copy(deep=True)
        soft = self._constraints.soft.model_copy(deep=True)

        if patch.hard is not None:
            hard = self._merge_model(hard, patch.hard)
        if patch.soft is not None:
            soft = self._merge_model(soft, patch.soft)

        commute = (
            patch.commute_point
            if patch.commute_point is not None
            else self._constraints.commute_point
        )

        self._constraints = Constraints(hard=hard, soft=soft, commute_point=commute)
        return self.constraints

    def missing_critical(self) -> list[str]:
        missing: list[str] = []
        hard = self._constraints.hard
        if hard.bedrooms is None:
            missing.append("bedrooms")
        if not hard.locality:
            missing.append("locality")
        if hard.max_rent is None:
            missing.append("max_rent")
        return missing

    def can_ask_clarification(self) -> bool:
        return self.clarification_count < self.max_clarifications

    def record_clarification(self) -> None:
        if self.clarification_count < self.max_clarifications:
            self.clarification_count += 1

    def is_search_ready(self) -> bool:
        return len(self.missing_critical()) == 0

    @staticmethod
    def _merge_model(current: HardConstraints | SoftPreferences, patch: HardConstraints | SoftPreferences):
        data = current.model_dump()
        updates = patch.model_dump(exclude_unset=True)
        for key, value in updates.items():
            if key == "must_have_amenities" and isinstance(value, list):
                if value:
                    prior = list(data.get("must_have_amenities") or [])
                    data[key] = list(dict.fromkeys([*prior, *value]))
                else:
                    data[key] = []
            else:
                data[key] = value
        return type(current).model_validate(data)
