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
    p = profile or load_default()
    rng = random.Random(seed)
    end = end or date.today()
    start = end - timedelta(days=7 * weeks - 1)
    travel_start = start + timedelta(days=7 * (weeks // 3))
    calm_start = start + timedelta(days=7 * (weeks // 2))
    sick_start = end - timedelta(days=17)
    allergen = "Peanut" if "Peanut" in p.allergens else (p.allergens[0] if p.allergens else "")
    subs = [s for s in SUB_AREAS if p.categories_for(s)]

    out: list[dict] = []
    last_anti = start - timedelta(days=4)
    d = start
    while d <= end:
        travel = travel_start <= d < travel_start + timedelta(days=4)
        calm = calm_start <= d < calm_start + timedelta(days=7)
        sick = sick_start <= d < sick_start + timedelta(days=6)
        rough = travel or sick

        for i, c in enumerate(p.creams):
            allowed = list(p.cream_areas(c))
            if c.multi_area:
                chance = 0.15 if calm else 0.6 if rough else 0.35
            else:
                chance = 0.05 if calm else 0.3
            if rng.random() >= chance:
                continue
            if c.multi_area and c.any_area and rng.random() < (0.45 if rough else 0.15):
                areas = ["Entire body"] + ([a for a in allowed if a not in p.full_body_covers][:1]
                                           if rng.random() < 0.3 else [])
            elif c.multi_area:
                areas = rng.sample(allowed, k=min(len(allowed), rng.choice([1, 1, 2, 2, 3])))
                if subs and c.any_area and rng.random() < 0.25:
                    areas.append(rng.choice(subs))
            else:
                areas = allowed
            entry = {"type": c.id, "day": d.isoformat(), "areas": areas, "dateOnly": True,
                     "note": "post flight" if travel and i == 0 and rng.random() < 0.5 else ""}
            if c.schedule == "morning_night":
                entry["slot"] = rng.choice(["morning", "night", "night"])
            out.append(entry)

        if p.antihistamine_enabled:
            gap = (d - last_anti).days
            chance = 0.05 if calm else 0.7 if rough else (0.45 if gap >= 4 else 0.1)
            if rng.random() < chance:
                out.append({"type": "anti", "day": d.isoformat(), "at": f"{d.isoformat()}T19:30:00",
                            "areas": [], "note": "travel" if travel else ""})
                last_anti = d

        if p.track_allergens and allergen and d >= end - timedelta(days=27) and d.weekday() in (1, 4):
            out.append({"type": "allergen", "day": d.isoformat(), "at": f"{d.isoformat()}T12:00:00",
                        "allergen": allergen, "amount": "1/12 serving", "areas": [], "note": ""})

        if rough and rng.random() < 0.3:
            out.append({"type": "flare", "day": d.isoformat(), "at": f"{d.isoformat()}T18:00:00",
                        "areas": [rng.choice(list(p.areas))],
                        "note": "after the flight" if travel else "sick, fever"})
        elif rng.random() < 0.06:
            out.append({"type": "note", "day": d.isoformat(), "areas": [], "note": rng.choice(NOTES)})
        d += timedelta(days=1)
    return out
