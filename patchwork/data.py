"""Read log entries from a JSON export.

Accepted inputs:
- a JSON file holding a list of entries, or {"entries": [...]}
- a directory of one-JSON-file-per-entry (the Claude artifact database export),
  where each file is an entry or {"id", "data"}.

Entry types: a cream id from the profile (e.g. "steroid"), "anti", "flare",
"allergen" or "note". Every entry has a local `day` (YYYY-MM-DD).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Entry:
    type: str
    day: date
    areas: tuple[str, ...] = ()
    note: str = ""
    at: str = ""
    slot: str = ""        # creams with a morning/night schedule: "morning" | "night"
    allergen: str = ""    # allergen entries
    amount: str = ""      # allergen entries


def _to_entry(raw: dict) -> Entry | None:
    body = raw["data"] if isinstance(raw.get("data"), dict) else raw
    kind = str(body.get("type", "")).strip()
    day = body.get("day")
    if not kind or not day:
        return None
    try:
        parsed = date.fromisoformat(str(day))
    except ValueError:
        return None
    areas = body.get("areas") or []
    if not isinstance(areas, list):
        areas = []
    slot = str(body.get("slot") or "").lower()
    return Entry(
        type=kind,
        day=parsed,
        areas=tuple(str(a) for a in areas),
        note=str(body.get("note") or ""),
        at=str(body.get("at") or ""),
        slot=slot if slot in ("morning", "night") else "",
        allergen=str(body.get("allergen") or ""),
        amount=str(body.get("amount") or ""),
    )


def load_entries(path: str | Path) -> list[Entry]:
    p = Path(path)
    if p.is_dir():
        raws = [json.loads(f.read_text()) for f in sorted(p.rglob("*.json"))]
    else:
        loaded = json.loads(p.read_text())
        raws = loaded.get("entries", []) if isinstance(loaded, dict) else loaded
    entries = [e for e in (_to_entry(r) for r in raws) if e is not None]
    return sorted(entries, key=lambda e: (e.day, e.at))
