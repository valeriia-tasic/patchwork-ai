"""The profile: everything family-specific, loaded from JSON.

`rules.json` in the repo root is the default profile and schema reference.
`private/profile.json`, written by the first-use questionnaire, replaces it when present.
"""

from __future__ import annotations

import json
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
        return self.areas is None

    @property
    def multi_area(self) -> bool:
        """True when per-area counts mean something (more than one possible area)."""
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
        """Tracked areas a single logged area counts toward.

        Order: full-body name -> tracked area name (case-insensitive) -> alias -> nothing.
        Unknown free text is dropped from counts rather than guessed.
        """
        key = area.strip().lower()
        if key in self.full_body_names:
            return set(self.full_body_covers)
        for a in self.areas:
            if key == a.lower():
                return {a}
        mapped = self.aliases.get(key)
        return {mapped} if mapped else set()

    def categories_for_all(self, areas) -> set[str]:
        out: set[str] = set()
        for a in areas:
            out |= self.categories_for(a)
        return out

    # --- creams ------------------------------------------------------------
    def cream(self, cream_id: str) -> Cream | None:
        return next((c for c in self.creams if c.id == cream_id), None)

    @property
    def cream_ids(self) -> set[str]:
        return {c.id for c in self.creams}

    @property
    def area_cream(self) -> Cream | None:
        """The cream the body-area chart and trends are about: the first multi-area cream."""
        return next((c for c in self.creams if c.multi_area), None)

    def cream_areas(self, cream: Cream) -> tuple[str, ...]:
        return self.areas if cream.areas is None else cream.areas


def _int_or_none(v) -> int | None:
    return None if v in (None, "", 0) else int(v)


def profile_from_dict(raw: dict) -> Profile:
    areas = raw["areas"]
    creams = []
    for i, c in enumerate(raw.get("creams", [])):
        lim = c.get("limits") or {}
        allowed = c.get("areas", "any")
        creams.append(Cream(
            id=c["id"],
            name=c.get("name", c["id"]),
            schedule=c.get("schedule", "daily"),
            areas=None if allowed in (None, "any") else tuple(allowed),
            max_days_per_area_per_week=_int_or_none(lim.get("max_days_per_area_per_week")),
            max_days_per_week=_int_or_none(lim.get("max_days_per_week")),
            color=c.get("color") or PALETTE[i % len(PALETTE)],
        ))
    ah = raw.get("antihistamine") or {}
    al = raw.get("allergens") or {}
    return Profile(
        areas=tuple(areas["tracked"]),
        full_body_names=frozenset(n.lower() for n in areas["full_body"]["names"]),
        full_body_covers=tuple(areas["full_body"]["covers"]),
        aliases={k.lower(): v for k, v in areas.get("aliases", {}).items()},
        area_colors=areas.get("colors", {}),
        creams=tuple(creams),
        antihistamine_enabled=bool(ah.get("enabled", True)),
        antihistamine_brand=ah.get("brand") or "Antihistamine",
        antihistamine_max_doses=_int_or_none((ah.get("limit") or {}).get("max_doses")),
        antihistamine_window_days=_int_or_none((ah.get("limit") or {}).get("window_days")),
        antihistamine_color=ah.get("color", "#6a4fb3"),
        track_allergens=bool(al.get("track", False)),
        allergens=tuple(al.get("list", [])),
        trend_min_change=float(raw.get("trends", {}).get("min_change_per_week", 1.5)),
        trend_baseline_weeks=int(raw.get("trends", {}).get("baseline_weeks", 3)),
        rolling_weeks=int(raw.get("averages", {}).get("rolling_weeks", 12)),
        delivery=raw.get("delivery", {}),
    )


def validate(raw: dict) -> list[str]:
    """Human-readable problems with a profile dict. Empty list = valid."""
    errs: list[str] = []
    try:
        tracked = raw["areas"]["tracked"]
        covers = raw["areas"]["full_body"]["covers"]
    except (KeyError, TypeError):
        return ["areas.tracked and areas.full_body.covers are required"]
    if not tracked:
        errs.append("track at least one body area")
    if len({a.lower() for a in tracked}) != len(tracked):
        errs.append("body areas must be unique")
    for a in covers:
        if a not in tracked:
            errs.append(f"full body covers '{a}', which is not a tracked area")
    for k, v in raw["areas"].get("aliases", {}).items():
        if v not in tracked:
            errs.append(f"'{k}' maps to '{v}', which is not a tracked area")
    seen: set[str] = set()
    for c in raw.get("creams", []):
        cid = c.get("id", "")
        if not cid or not cid.replace("_", "").isalnum() or cid != cid.lower():
            errs.append(f"cream id '{cid}' must be lowercase letters, digits or _")
        if cid in RESERVED_TYPES:
            errs.append(f"cream id '{cid}' is reserved")
        if cid in seen:
            errs.append(f"cream id '{cid}' is used twice")
        seen.add(cid)
        if c.get("schedule", "daily") not in SCHEDULES:
            errs.append(f"cream '{cid}': schedule must be one of {', '.join(SCHEDULES)}")
        allowed = c.get("areas", "any")
        if allowed not in (None, "any"):
            for a in allowed:
                if a not in tracked:
                    errs.append(f"cream '{cid}' uses '{a}', which is not a tracked area")
        for key in ("max_days_per_area_per_week", "max_days_per_week"):
            v = (c.get("limits") or {}).get(key)
            if v not in (None, "") and not (isinstance(v, int) and 1 <= v <= 7):
                errs.append(f"cream '{cid}': {key} must be 1–7 or empty")
    if not raw.get("creams"):
        errs.append("add at least one cream")
    return errs


def unwrap(raw: dict) -> dict:
    """Accept a bare profile or a database export of one ({"id": ..., "data": {...}})."""
    return raw["data"] if isinstance(raw.get("data"), dict) and "areas" in raw["data"] else raw


def load_profile(path: str | Path | None = None) -> Profile:
    """Explicit path, else private/profile.json if it exists, else the default rules.json.

    The path may also be the live log's `config/profile` document exported by the agent.
    """
    if path:
        p = Path(path)
    else:
        p = PRIVATE_PROFILE if PRIVATE_PROFILE.exists() else DEFAULT_PROFILE
    raw = unwrap(json.loads(p.read_text()))
    problems = validate(raw)
    if problems:
        raise ValueError(f"{p} is not a valid profile:\n- " + "\n- ".join(problems))
    return profile_from_dict(raw)


def load_default() -> Profile:
    return load_profile(DEFAULT_PROFILE)
