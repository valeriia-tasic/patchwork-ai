"""Synthetic log for a fictional toddler, so anyone can run Patchwork without real health data.

The generator builds in a few patterns worth finding: a travel week that flares,
a sick week, a calm stretch, and an allergen introduction, on top of everyday noise.
It follows whatever profile it is given, so a new family's setup can be demoed
before they log anything real.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from .rules import Profile, load_default

NOTES = ["new laundry detergent", "teething, drooling a lot", "ate tomato sauce at daycare",
         "long day outside", "slept badly", "new bath wash", "very scratchy at bedtime"]
SUB_AREAS = ["elbows", "knees", "ankles", "shoulders", "wrists", "side"]


def generate(weeks: int = 12, seed: int = 7, end: date | None = None, profile: Profile | None = None) -> list[dict]:
    """Generate a synthetic log as a list of raw entry dicts following the given profile.

    Builds realistic-looking patterns (travel flare, sick week, calm stretch, allergen
    introduction) seeded for reproducibility. Uses the default profile when none is given.
    Called by cmd_sample and written to data/sample_entries.json.
    """
    active_profile = profile or load_default()
    rng = random.Random(seed)
    end = end or date.today()
    start = end - timedelta(days=7 * weeks - 1)
    travel_start = start + timedelta(days=7 * (weeks // 3))
    calm_start = start + timedelta(days=7 * (weeks // 2))
    sick_start = end - timedelta(days=17)
    allergen = "Peanut" if "Peanut" in active_profile.allergens else (active_profile.allergens[0] if active_profile.allergens else "")
    sub_areas = [sub for sub in SUB_AREAS if active_profile.categories_for(sub)]

    entries: list[dict] = []
    last_antihistamine_day = start - timedelta(days=4)
    current_date = start
    while current_date <= end:
        is_travel = travel_start <= current_date < travel_start + timedelta(days=4)
        is_calm = calm_start <= current_date < calm_start + timedelta(days=7)
        is_sick = sick_start <= current_date < sick_start + timedelta(days=6)
        is_rough = is_travel or is_sick

        for cream_index, cream in enumerate(active_profile.creams):
            allowed_areas = list(active_profile.cream_areas(cream))
            if cream.multi_area:
                application_chance = 0.15 if is_calm else 0.6 if is_rough else 0.35
            else:
                application_chance = 0.05 if is_calm else 0.3
            if rng.random() >= application_chance:
                continue
            if cream.multi_area and cream.any_area and rng.random() < (0.45 if is_rough else 0.15):
                areas = ["Entire body"] + (
                    [area for area in allowed_areas if area not in active_profile.full_body_covers][:1]
                    if rng.random() < 0.3 else []
                )
            elif cream.multi_area:
                areas = rng.sample(allowed_areas, k=min(len(allowed_areas), rng.choice([1, 1, 2, 2, 3])))
                if sub_areas and cream.any_area and rng.random() < 0.25:
                    areas.append(rng.choice(sub_areas))
            else:
                areas = allowed_areas
            entry: dict = {
                "type": cream.id,
                "day": current_date.isoformat(),
                "areas": areas,
                "dateOnly": True,
                "note": "post flight" if is_travel and cream_index == 0 and rng.random() < 0.5 else "",
            }
            if cream.schedule == "morning_night":
                entry["slot"] = rng.choice(["morning", "night", "night"])
            entries.append(entry)

        if active_profile.antihistamine_enabled:
            days_since_last = (current_date - last_antihistamine_day).days
            anti_chance = 0.05 if is_calm else 0.7 if is_rough else (0.45 if days_since_last >= 4 else 0.1)
            if rng.random() < anti_chance:
                entries.append({
                    "type": "anti",
                    "day": current_date.isoformat(),
                    "at": f"{current_date.isoformat()}T19:30:00",
                    "areas": [],
                    "note": "travel" if is_travel else "",
                })
                last_antihistamine_day = current_date

        if active_profile.track_allergens and allergen and current_date >= end - timedelta(days=27) and current_date.weekday() in (1, 4):
            entries.append({
                "type": "allergen",
                "day": current_date.isoformat(),
                "at": f"{current_date.isoformat()}T12:00:00",
                "allergen": allergen,
                "amount": "1/12 serving",
                "areas": [],
                "note": "",
            })

        if is_rough and rng.random() < 0.3:
            entries.append({
                "type": "flare",
                "day": current_date.isoformat(),
                "at": f"{current_date.isoformat()}T18:00:00",
                "areas": [rng.choice(list(active_profile.areas))],
                "note": "after the flight" if is_travel else "sick, fever",
            })
        elif rng.random() < 0.06:
            entries.append({
                "type": "note",
                "day": current_date.isoformat(),
                "areas": [],
                "note": rng.choice(NOTES),
            })
        current_date += timedelta(days=1)
    return entries
