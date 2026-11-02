"""First-use questionnaire: builds private/profile.json.

Two front ends share this module:
- `python -m patchwork init` asks in the terminal (this file's `run`).
- Claude Code asks conversationally by following SETUP.md, then writes the same
  JSON and checks it with `python -m patchwork validate`.

`run` takes an `ask` function so the whole flow can be tested with scripted answers.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from .rules import PALETTE, RESERVED_TYPES, SCHEDULES, validate

Ask = Callable[[str], str]

COMMON_ALLERGENS = ["Milk", "Egg", "Fish", "Shellfish", "Tree nuts", "Peanut", "Wheat", "Soy", "Sesame"]
DEFAULT_AREAS = ["Arms", "Legs", "Stomach", "Back", "Neck", "Face", "Diaper"]
DEFAULT_SEPARATE = {"face", "diaper", "scalp"}
DEFAULT_ALIASES: dict[str, str] = {
    "ankle": "Legs", "ankles": "Legs", "foot": "Legs", "feet": "Legs",
    "knee": "Legs", "knees": "Legs", "thigh": "Legs", "thighs": "Legs",
    "shin": "Legs", "shins": "Legs",
    "elbow": "Arms", "elbows": "Arms", "hand": "Arms", "hands": "Arms",
    "wrist": "Arms", "wrists": "Arms", "thumb": "Arms", "thumbs": "Arms",
    "finger": "Arms", "fingers": "Arms", "shoulder": "Arms", "shoulders": "Arms",
    "side": "Back",
}
AREA_COLORS = ["#e6194b", "#3cb44b", "#ffb000", "#4363d8", "#f032e6", "#00b8d4", "#ff6f00",
               "#911eb4", "#469990", "#9a6324"]

LIMIT_NOTE = ("Limits are alert thresholds you set from your doctor's instructions. "
              "Patchwork does not recommend limits; it only tells you when one is crossed.")


def _split(text: str) -> list[str]:
    """Split a comma- or newline-separated string into a trimmed list of non-empty items."""
    return [item.strip() for item in re.split(r"[,\n]", text) if item.strip()]


def _yes(text: str, default: bool = False) -> bool:
    """Return True when the response starts with 'y' (case-insensitive), or the default."""
    normalized = text.strip().lower()
    return default if not normalized else normalized.startswith("y")


def _int(text: str) -> int | None:
    """Parse a 1–7 integer from a string, returning None for blank or out-of-range input."""
    stripped = text.strip()
    return int(stripped) if stripped.isdigit() and 1 <= int(stripped) <= 7 else None


def _slug(name: str, taken: set[str]) -> str:
    """Convert a cream name to a unique lowercase id safe for use as an entry type.

    Replaces non-alphanumeric characters with underscores, avoids reserved types,
    and appends a counter when the base slug is already taken.
    """
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "cream"
    if base in RESERVED_TYPES:
        base += "_cream"
    slug, counter = base, 2
    while slug in taken:
        slug, counter = f"{base}_{counter}", counter + 1
    return slug


def _match(name: str, areas: list[str]) -> str | None:
    """Return the area from `areas` whose name matches `name` case-insensitively, or None."""
    return next((area for area in areas if area.lower() == name.strip().lower()), None)


def run(ask: Ask, say: Callable[[str], None] = print) -> dict:
    """Run the interactive first-use questionnaire and return a validated profile dict.

    Covers body areas, full-body definition, creams (with limits), antihistamine,
    allergen tracking, and delivery settings. Validates before returning so the
    caller always gets a profile that passes validate().
    Used by cmd_init (terminal) and the SETUP.md flow (Claude conversation).
    """
    say("Patchwork setup. Press Enter to accept the value in [brackets].\n")

    # 1. Body areas, with follow-ups to get the scope right
    areas = _split(ask(f"Which body areas do you track? [{', '.join(DEFAULT_AREAS)}] ")) or DEFAULT_AREAS
    say("Some spots belong under a main area, e.g. elbows -> Arms, ankles -> Legs.")
    area_set = {area.lower() for area in areas}
    aliases: dict[str, str] = {alias_key: alias_target for alias_key, alias_target in DEFAULT_ALIASES.items() if alias_target.lower() in area_set}
    for pair in _split(ask("Anything else you log that belongs under one of these? (e.g. elbows=Arms, ankles=Legs) [skip] ")):
        if "=" in pair:
            alias_from, alias_to = (part.strip() for part in pair.split("=", 1))
            matched_area = _match(alias_to, areas)
            if matched_area:
                aliases[alias_from.lower()] = matched_area
            else:
                say(f"  '{alias_to}' isn't one of your areas, skipped '{pair}'.")

    # 2. Full body definition
    suggested = [area for area in areas if area.lower() not in DEFAULT_SEPARATE]
    covers_input = _split(ask(f"When you log 'full body', which of your areas does that cover? [{', '.join(suggested)}] "))
    covers = [matched for matched in (_match(item, areas) for item in covers_input) if matched] or suggested
    separate = [area for area in areas if area not in covers]
    if separate:
        say(f"Tracked on their own, never part of full body: {', '.join(separate)}.")

    # 3. Creams
    say("\nNow your creams. " + LIMIT_NOTE)
    creams: list[dict] = []
    while True:
        default_name = "" if creams else "Steroid"
        name = ask(f"Cream name{f' [{default_name}]' if default_name else ' (Enter when done)'}: ").strip() or default_name
        if not name:
            break
        where = ask(f"  Is {name} used on any area, or only some? (any / list areas) [any] ").strip()
        allowed: str | list[str] = "any"
        if where and where.lower() != "any":
            picked = [matched for matched in (_match(area, areas) for area in _split(where)) if matched]
            allowed = picked or "any"
        schedule_input = ask(f"  Log {name} by date only (once a day), or Morning / Night? (d / m) [d] ").strip().lower()
        schedule = "morning_night" if schedule_input.startswith("m") else "daily"
        is_multi_area = allowed == "any" or len(allowed) > 1
        per_area_limit = _int(ask(f"  Alert when one area gets {name} on more than N days a week? N = [none] ")) if is_multi_area else None
        total_limit = _int(ask(f"  Alert when {name} is used on more than N days a week in total? N = [none] "))
        creams.append({
            "id": _slug(name, {cream["id"] for cream in creams}),
            "name": name,
            "schedule": schedule,
            "areas": allowed,
            "limits": {"max_days_per_area_per_week": per_area_limit, "max_days_per_week": total_limit},
            "color": PALETTE[len(creams) % len(PALETTE)],
        })
        if len(creams) >= 6:
            say("That's the maximum of 6 creams.")
            break

    # 4. Antihistamine
    uses_antihistamine = _yes(ask("\nDo you give an antihistamine? [y] "), default=True)
    antihistamine: dict = {"enabled": uses_antihistamine, "brand": "Antihistamine", "limit": {"max_doses": 1, "window_days": 3}, "color": "#6a4fb3"}
    if uses_antihistamine:
        antihistamine["brand"] = ask("  Brand name (e.g. Zyrtec, Claritin) [Antihistamine]: ").strip() or "Antihistamine"
        say("  " + LIMIT_NOTE)
        max_doses_input = ask("  Alert when it's given more than how many times within a window? (blank = no alert) ").strip()
        window_days_input = ask("  ...within how many days? ").strip() if max_doses_input.isdigit() else ""
        antihistamine["limit"] = {
            "max_doses": int(max_doses_input) if max_doses_input.isdigit() else None,
            "window_days": int(window_days_input) if window_days_input.isdigit() else None,
        }

    # 5. Allergen exposure
    track_allergens = _yes(ask("\nDo you want to log allergen exposure (food introductions, accidental contact)? [n] "))
    allergens: dict = {"track": track_allergens, "list": []}
    if track_allergens:
        extra = _split(ask(f"  Buttons will include: {', '.join(COMMON_ALLERGENS)}. Add any others? [none] "))
        allergens["list"] = COMMON_ALLERGENS + [item for item in extra if item.lower() not in {allergen.lower() for allergen in COMMON_ALLERGENS}]

    # 6. Delivery
    say("")
    delivery = {
        "email": ask("Email for the weekly report [none]: ").strip(),
        "log_url": "",
        "timezone": ask("Timezone [America/New_York]: ").strip() or "America/New_York",
        "report_day": ask("Weekly report day [Sunday]: ").strip() or "Sunday",
        "report_time": ask("Report time, 24h [20:00]: ").strip() or "20:00",
    }

    profile = {
        "version": 2,
        "areas": {
            "tracked": areas,
            "full_body": {"names": ["entire body", "full body", "body"], "covers": covers},
            "aliases": aliases,
            "colors": {area: AREA_COLORS[index % len(AREA_COLORS)] for index, area in enumerate(areas)},
        },
        "creams": creams,
        "antihistamine": antihistamine,
        "allergens": allergens,
        "trends": {"min_change_per_week": 1.5, "baseline_weeks": 3},
        "averages": {"rolling_weeks": 12},
        "delivery": delivery,
    }
    problems = validate(profile)
    if problems:
        raise ValueError("Setup produced an invalid profile:\n- " + "\n- ".join(problems))
    return profile


def summary(profile: dict) -> str:
    """Format a profile dict as a human-readable summary string for confirmation.

    Shown to the parent at the end of cmd_init before they confirm saving.
    """
    areas_config = profile["areas"]
    lines = [
        f"Areas: {', '.join(areas_config['tracked'])}",
        f"Full body: {', '.join(areas_config['full_body']['covers'])}",
    ]
    if areas_config.get("aliases"):
        lines.append("Also counted: " + ", ".join(f"{alias_key} → {alias_target}" for alias_key, alias_target in areas_config["aliases"].items()))
    for cream in profile["creams"]:
        where = "any area" if cream["areas"] == "any" else ", ".join(cream["areas"])
        limits = cream["limits"]
        alert_bits = []
        if limits.get("max_days_per_area_per_week"):
            alert_bits.append(f"alert if one area > {limits['max_days_per_area_per_week']} days/week")
        if limits.get("max_days_per_week"):
            alert_bits.append(f"alert if > {limits['max_days_per_week']} days/week total")
        schedule_label = "morning/night" if cream["schedule"] == "morning_night" else "once a day"
        lines.append(f"Cream: {cream['name']} — {where}, {schedule_label}" + (f", {'; '.join(alert_bits)}" if alert_bits else ""))
    antihistamine = profile["antihistamine"]
    if antihistamine["enabled"]:
        lines.append(
            f"Antihistamine: {antihistamine['brand']} — alert if more than {antihistamine['limit']['max_doses']} "
            f"in {antihistamine['limit']['window_days']} days"
        )
    if profile["allergens"]["track"]:
        lines.append("Allergens: " + ", ".join(profile["allergens"]["list"]))
    return "\n".join(lines)


def write(profile: dict, path: Path) -> Path:
    """Write a profile dict to a JSON file, creating parent directories as needed.

    Called by cmd_init after the parent confirms the setup summary.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n")
    return path


assert set(SCHEDULES) == {"daily", "morning_night"}
