import json
from datetime import date
from pathlib import Path

import pytest

from patchwork.data import Entry
from patchwork.rules import profile_from_dict


@pytest.fixture(scope="session")
def profile():
    """Test profile with explicit limits for alert testing:
    Steroid (any area, max 2 days/area/week), Face cream (Face only, morning/night),
    Antihistamine (max 1 dose in 3 days), allergens on.
    Limits are defined here for test purposes — Patchwork does not recommend any limits."""
    raw = json.loads((Path(__file__).parent.parent / "rules.json").read_text())
    raw["creams"][0]["limits"]["max_days_per_area_per_week"] = 2
    raw["medications"][0]["limit"] = {"max_doses": 1, "window_days": 3}
    return profile_from_dict(raw)


def e(kind: str, day: str, *areas: str, note: str = "", slot: str = "", allergen: str = "", amount: str = "") -> Entry:
    return Entry(type=kind, day=date.fromisoformat(day), areas=tuple(areas), note=note,
                 slot=slot, allergen=allergen, amount=amount)
