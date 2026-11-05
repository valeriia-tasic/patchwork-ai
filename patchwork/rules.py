"""Data model: Cream, Profile, and the constants they depend on.

`rules.json` in the repo root is the default profile and schema reference.
`private/profile.json`, written by the first-use questionnaire, replaces it when present.

Validation and I/O live in _validation.py; they are re-exported here so callers
can continue to import everything from rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE = ROOT / "rules.json"
PRIVATE_PROFILE = ROOT / "private" / "profile.json"

# Entry types that are not creams. A cream id may not reuse one of these.
RESERVED_TYPES = frozenset({"anti", "flare", "allergen", "note"})
SCHEDULES = ("daily", "morning_night")
PALETTE = ["#b26a12", "#2c6e73", "#8a5a9e", "#3d7a3a", "#a83c62", "#5a6b8c"]


@dataclass(frozen=True)
class Cream:
    id: str
    name: str
    schedule: str = "daily"                 # "daily" | "morning_night"
    areas: tuple[str, ...] | None = None    # None = any tracked area
    max_days_per_area_per_week: int | None = None
    max_days_per_week: int | None = None
    color: str = "#b26a12"

    @property
    def any_area(self) -> bool:
        """True when the cream can be applied to any tracked area (no restriction set)."""
        return self.areas is None

    @property
    def multi_area(self) -> bool:
        """True when per-area counts mean something (more than one possible area).

        Used by metrics and report to decide whether to show the per-area breakdown.
        """
        return self.areas is None or len(self.areas) > 1


@dataclass(frozen=True)
class Profile:
    areas: tuple[str, ...]
    full_body_names: frozenset[str]
    full_body_covers: tuple[str, ...]
    aliases: dict[str, str]
    area_colors: dict[str, str]
    creams: tuple[Cream, ...]
    antihistamine_enabled: bool
    antihistamine_brand: str
    antihistamine_max_doses: int | None
    antihistamine_window_days: int | None
    antihistamine_color: str
    track_allergens: bool
    allergens: tuple[str, ...]
    trend_min_change: float
    trend_baseline_weeks: int
    rolling_weeks: int
    delivery: dict = field(default_factory=dict)

    # --- areas -------------------------------------------------------------
    def categories_for(self, area: str) -> set[str]:
        """Return which tracked areas a single logged area string counts toward.

        Resolution order: full-body name → tracked area name (case-insensitive)
        → alias → nothing. Unknown free text is dropped from counts rather than guessed.
        Used by metrics.area_days to map a parent's typed area to canonical tracked areas.
        """
        key = area.strip().lower()
        if key in self.full_body_names:
            return set(self.full_body_covers)
        for tracked_area in self.areas:
            if key == tracked_area.lower():
                return {tracked_area}
        matched = self.aliases.get(key)
        return {matched} if matched else set()

    def categories_for_all(self, areas) -> set[str]:
        """Return the union of tracked areas across a list of logged area strings.

        Used by metrics.area_days to resolve multi-area entries in one call.
        """
        result: set[str] = set()
        for area in areas:
            result |= self.categories_for(area)
        return result

    # --- creams ------------------------------------------------------------
    def cream(self, cream_id: str) -> Cream | None:
        """Return the Cream with the given id, or None if it is not in the profile.

        Used by the agent when resolving a log entry's type string to a Cream object.
        """
        return next((cream for cream in self.creams if cream.id == cream_id), None)

    @property
    def cream_ids(self) -> set[str]:
        """Set of all cream entry-type ids defined in the profile.

        Used by the page and validation to distinguish cream entries from other types.
        """
        return {cream.id for cream in self.creams}

    @property
    def area_cream(self) -> Cream | None:
        """The cream the body-area chart and trends are about: the first multi-area cream.

        Used by report.build_weekly and charts.by_area to select which cream gets the
        per-area breakdown.
        """
        return next((cream for cream in self.creams if cream.multi_area), None)

    def cream_areas(self, cream: Cream) -> tuple[str, ...]:
        """Return the areas a cream can be applied to.

        Returns all tracked areas when the cream has no restriction, or the cream's own
        restricted list. Used by metrics and report to know which areas to count.
        """
        return self.areas if cream.areas is None else cream.areas


# Re-export validation and I/O so callers can import from here unchanged.
from ._validation import (  # noqa: E402, F401
    load_default,
    load_profile,
    profile_from_dict,
    unwrap,
    validate,
)
