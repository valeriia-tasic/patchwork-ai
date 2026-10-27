from datetime import date

import pytest

from patchwork.data import Entry
from patchwork.rules import load_default


@pytest.fixture(scope="session")
def profile():
    """The default profile in rules.json: Steroid (any area, max 2 days/area/week),
    Face cream (Face only, morning/night), Antihistamine (1 in 3 days), allergens on."""
    return load_default()


def e(kind: str, day: str, *areas: str, note: str = "", slot: str = "", allergen: str = "", amount: str = "") -> Entry:
    return Entry(type=kind, day=date.fromisoformat(day), areas=tuple(areas), note=note,
                 slot=slot, allergen=allergen, amount=amount)
