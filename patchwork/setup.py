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
DEFAULT_SEPARATE = {"face", "diaper", "scalp", "groin"}
AREA_COLORS = ["#e6194b", "#3cb44b", "#ffb000", "#4363d8", "#f032e6", "#00b8d4", "#ff6f00",
               "#911eb4", "#469990", "#9a6324"]

LIMIT_NOTE = ("Limits are alert thresholds you set from your doctor's instructions. "
              "Patchwork does not recommend limits; it only tells you when one is crossed.")


def _split(text: str) -> list[str]:
    return [t.strip() for t in re.split(r"[,\n]", text) if t.strip()]


def _yes(text: str, default: bool = False) -> bool:
    t = text.strip().lower()
    return default if not t else t.startswith("y")


def _int(text: str) -> int | None:
    t = text.strip()
    return int(t) if t.isdigit() and 1 <= int(t) <= 7 else None


def _slug(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "cream"
    if base in RESERVED_TYPES:
        base += "_cream"
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}_{n}", n + 1
    return slug


def _match(name: str, areas: list[str]) -> str | None:
    return next((a for a in areas if a.lower() == name.strip().lower()), None)


def run(ask: Ask, say: Callable[[str], None] = print) -> dict:
    say("Patchwork setup. Press Enter to accept the value in [brackets].\n")

    # 1. Body areas, with follow-ups to get the scope right
    while True:
        areas = _split(ask(f"Which body areas do you track? [{', '.join(DEFAULT_AREAS)}] ")) or DEFAULT_AREAS
        if _yes(ask("Do you need left and right tracked separately (e.g. left arm vs right arm)? [n] ")):
            say("Then list each side as its own area, e.g. 'Left arm, Right arm'.")
            continue
        break
    say("Some spots belong under a main area, e.g. elbows -> Arms, ankles -> Legs.")
    aliases: dict[str, str] = {}
    for pair in _split(ask("Anything else you log that belongs under one of these? (e.g. elbows=Arms, ankles=Legs) [skip] ")):
        if "=" in pair:
            k, v = (x.strip() for x in pair.split("=", 1))
            target = _match(v, areas)
            if target:
                aliases[k.lower()] = target
            else:
                say(f"  '{v}' isn't one of your areas, skipped '{pair}'.")

    # 2. Full body definition
    suggested = [a for a in areas if a.lower() not in DEFAULT_SEPARATE]
    covers_in = _split(ask(f"When you log 'full body', which of your areas does that cover? [{', '.join(suggested)}] "))
    covers = [m for m in (_match(c, areas) for c in covers_in) if m] or suggested
    separate = [a for a in areas if a not in covers]
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
            picked = [m for m in (_match(a, areas) for a in _split(where)) if m]
            allowed = picked or "any"
        slot = ask(f"  Log {name} by date only (once a day), or Morning / Night? (d / m) [d] ").strip().lower()
        schedule = "morning_night" if slot.startswith("m") else "daily"
        multi = allowed == "any" or len(allowed) > 1
        per_area = _int(ask(f"  Alert when one area gets {name} on more than N days a week? N = [none] ")) if multi else None
        total = _int(ask(f"  Alert when {name} is used on more than N days a week in total? N = [none] "))
        creams.append({
            "id": _slug(name, {c["id"] for c in creams}),
            "name": name,
            "schedule": schedule,
            "areas": allowed,
            "limits": {"max_days_per_area_per_week": per_area, "max_days_per_week": total},
            "color": PALETTE[len(creams) % len(PALETTE)],
        })
        if len(creams) >= 6:
            say("That's the maximum of 6 creams.")
            break

    # 4. Antihistamine
    uses = _yes(ask("\nDo you give an antihistamine? [y] "), default=True)
    anti = {"enabled": uses, "brand": "Antihistamine", "limit": {"max_doses": 1, "window_days": 3}, "color": "#6a4fb3"}
    if uses:
        anti["brand"] = ask("  Brand name (e.g. Zyrtec, Claritin) [Antihistamine]: ").strip() or "Antihistamine"
        say("  " + LIMIT_NOTE)
        n = ask("  Alert when it's given more than how many times... [1] ").strip()
        w = ask("  ...within how many days? [3] ").strip()
        anti["limit"] = {"max_doses": int(n) if n.isdigit() else 1, "window_days": int(w) if w.isdigit() else 3}

    # 5. Allergen exposure
    track = _yes(ask("\nDo you want to log allergen exposure (food introductions, accidental contact)? [n] "))
    allergens = {"track": track, "list": []}
    if track:
        extra = _split(ask(f"  Buttons will include: {', '.join(COMMON_ALLERGENS)}. Add any others? [none] "))
        allergens["list"] = COMMON_ALLERGENS + [e for e in extra if e.lower() not in {c.lower() for c in COMMON_ALLERGENS}]

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
            "colors": {a: AREA_COLORS[i % len(AREA_COLORS)] for i, a in enumerate(areas)},
        },
        "creams": creams,
        "antihistamine": anti,
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
    a = profile["areas"]
    lines = [
        f"Areas: {', '.join(a['tracked'])}",
        f"Full body: {', '.join(a['full_body']['covers'])}",
    ]
    if a.get("aliases"):
        lines.append("Also counted: " + ", ".join(f"{k} → {v}" for k, v in a["aliases"].items()))
    for c in profile["creams"]:
        where = "any area" if c["areas"] == "any" else ", ".join(c["areas"])
        lim = c["limits"]
        bits = []
        if lim.get("max_days_per_area_per_week"):
            bits.append(f"alert if one area > {lim['max_days_per_area_per_week']} days/week")
        if lim.get("max_days_per_week"):
            bits.append(f"alert if > {lim['max_days_per_week']} days/week total")
        sched = "morning/night" if c["schedule"] == "morning_night" else "once a day"
        lines.append(f"Cream: {c['name']} — {where}, {sched}" + (f", {'; '.join(bits)}" if bits else ""))
    ah = profile["antihistamine"]
    if ah["enabled"]:
        lines.append(f"Antihistamine: {ah['brand']} — alert if more than {ah['limit']['max_doses']} "
                     f"in {ah['limit']['window_days']} days")
    if profile["allergens"]["track"]:
        lines.append("Allergens: " + ", ".join(profile["allergens"]["list"]))
    return "\n".join(lines)


def write(profile: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n")
    return path


assert set(SCHEDULES) == {"daily", "morning_night"}
