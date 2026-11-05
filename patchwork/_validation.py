"""Profile validation and construction: validate, profile_from_dict, load_profile.

Private helper — import from rules.py for the public API.
"""

from __future__ import annotations

import json
from pathlib import Path

from .rules import (
    Cream,
    DEFAULT_PROFILE,
    PALETTE,
    PRIVATE_PROFILE,
    Profile,
    RESERVED_TYPES,
    SCHEDULES,
)


def _int_or_none(value) -> int | None:
    """Convert a profile limit value to int, treating 0 and blank as no limit."""
    return None if value in (None, "", 0) else int(value)


def profile_from_dict(raw: dict) -> Profile:
    """Build a Profile dataclass from a validated profile dict.

    Called by load_profile after validation passes. The dict comes from rules.json
    or private/profile.json. Parses creams, antihistamine, and allergen sections.
    """
    areas = raw["areas"]
    creams = []
    for index, cream_raw in enumerate(raw.get("creams", [])):
        limits = cream_raw.get("limits") or {}
        allowed = cream_raw.get("areas", "any")
        creams.append(Cream(
            id=cream_raw["id"],
            name=cream_raw.get("name", cream_raw["id"]),
            schedule=cream_raw.get("schedule", "daily"),
            areas=None if allowed in (None, "any") else tuple(allowed),
            max_days_per_area_per_week=_int_or_none(limits.get("max_days_per_area_per_week")),
            max_days_per_week=_int_or_none(limits.get("max_days_per_week")),
            color=cream_raw.get("color") or PALETTE[index % len(PALETTE)],
        ))
    antihistamine = raw.get("antihistamine") or {}
    allergens_config = raw.get("allergens") or {}
    return Profile(
        areas=tuple(areas["tracked"]),
        full_body_names=frozenset(name.lower() for name in areas["full_body"]["names"]),
        full_body_covers=tuple(areas["full_body"]["covers"]),
        aliases={alias_key.lower(): alias_target for alias_key, alias_target in areas.get("aliases", {}).items()},
        area_colors=areas.get("colors", {}),
        creams=tuple(creams),
        antihistamine_enabled=bool(antihistamine.get("enabled", True)),
        antihistamine_brand=antihistamine.get("brand") or "Antihistamine",
        antihistamine_max_doses=_int_or_none((antihistamine.get("limit") or {}).get("max_doses")),
        antihistamine_window_days=_int_or_none((antihistamine.get("limit") or {}).get("window_days")),
        antihistamine_color=antihistamine.get("color", "#6a4fb3"),
        track_allergens=bool(allergens_config.get("track", False)),
        allergens=tuple(allergens_config.get("list", [])),
        trend_min_change=float(raw.get("trends", {}).get("min_change_per_week", 1.5)),
        trend_baseline_weeks=int(raw.get("trends", {}).get("baseline_weeks", 3)),
        rolling_weeks=int(raw.get("averages", {}).get("rolling_weeks", 12)),
        delivery=raw.get("delivery", {}),
    )


def validate(raw: dict) -> list[str]:
    """Return a list of human-readable problems with a profile dict; empty means valid.

    Used by load_profile, cmd_validate, and setup.run to catch bad configuration
    before it reaches the metrics or rendering code.
    """
    errors: list[str] = []
    try:
        tracked = raw["areas"]["tracked"]
        covers = raw["areas"]["full_body"]["covers"]
    except (KeyError, TypeError):
        return ["areas.tracked and areas.full_body.covers are required"]
    if not tracked:
        errors.append("track at least one body area")
    if len({area.lower() for area in tracked}) != len(tracked):
        errors.append("body areas must be unique")
    for area in covers:
        if area not in tracked:
            errors.append(f"full body covers '{area}', which is not a tracked area")
    for alias_key, alias_target in raw["areas"].get("aliases", {}).items():
        if alias_target not in tracked:
            errors.append(f"'{alias_key}' maps to '{alias_target}', which is not a tracked area")
    seen: set[str] = set()
    for cream_raw in raw.get("creams", []):
        cream_id = cream_raw.get("id", "")
        if not cream_id or not cream_id.replace("_", "").isalnum() or cream_id != cream_id.lower():
            errors.append(f"cream id '{cream_id}' must be lowercase letters, digits or _")
        if cream_id in RESERVED_TYPES:
            errors.append(f"cream id '{cream_id}' is reserved")
        if cream_id in seen:
            errors.append(f"cream id '{cream_id}' is used twice")
        seen.add(cream_id)
        if cream_raw.get("schedule", "daily") not in SCHEDULES:
            errors.append(f"cream '{cream_id}': schedule must be one of {', '.join(SCHEDULES)}")
        allowed = cream_raw.get("areas", "any")
        if allowed not in (None, "any"):
            for area in allowed:
                if area not in tracked:
                    errors.append(f"cream '{cream_id}' uses '{area}', which is not a tracked area")
        for limit_key in ("max_days_per_area_per_week", "max_days_per_week"):
            value = (cream_raw.get("limits") or {}).get(limit_key)
            if value not in (None, "") and not (isinstance(value, int) and 1 <= value <= 7):
                errors.append(f"cream '{cream_id}': {limit_key} must be 1–7 or empty")
    if not raw.get("creams"):
        errors.append("add at least one cream")
    return errors


def unwrap(raw: dict) -> dict:
    """Accept a bare profile dict or a database export wrapping one ({"id": ..., "data": {...}}).

    Used by load_profile, cmd_validate, and page.build to handle both the direct
    JSON file format and the log's config/profile document export format.
    """
    return raw["data"] if isinstance(raw.get("data"), dict) and "areas" in raw["data"] else raw


def load_profile(path: str | Path | None = None) -> Profile:
    """Load, validate, and return a Profile from disk.

    Search order when no path is given: private/profile.json if it exists, else
    rules.json. The path may also be the live log's config/profile document exported
    by the scheduled agent.
    Used by every patchwork command that needs the family's configuration.
    """
    if path:
        profile_path = Path(path)
    else:
        profile_path = PRIVATE_PROFILE if PRIVATE_PROFILE.exists() else DEFAULT_PROFILE
    raw = unwrap(json.loads(profile_path.read_text()))
    problems = validate(raw)
    if problems:
        raise ValueError(f"{profile_path} is not a valid profile:\n- " + "\n- ".join(problems))
    return profile_from_dict(raw)


def load_default() -> Profile:
    """Load the default public profile from rules.json.

    Used by synthetic.generate when no private profile is provided, so the sample
    log always works without setup.
    """
    return load_profile(DEFAULT_PROFILE)
