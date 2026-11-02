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


def _to_entry(raw_record: dict) -> Entry | None:
    """Parse one raw JSON object into an Entry, returning None if the record is invalid.

    Used by load_entries to silently skip malformed or incomplete log records.
    """
    body = raw_record["data"] if isinstance(raw_record.get("data"), dict) else raw_record
    kind = str(body.get("type", "")).strip()
    day = body.get("day")
    if not kind or not day:
        return None
    try:
        parsed_day = date.fromisoformat(str(day))
    except ValueError:
        return None
    areas = body.get("areas") or []
    if not isinstance(areas, list):
        areas = []
    slot = str(body.get("slot") or "").lower()
    return Entry(
        type=kind,
        day=parsed_day,
        areas=tuple(str(area) for area in areas),
        note=str(body.get("note") or ""),
        at=str(body.get("at") or ""),
        slot=slot if slot in ("morning", "night") else "",
        allergen=str(body.get("allergen") or ""),
        amount=str(body.get("amount") or ""),
    )


def load_entries(path: str | Path) -> list[Entry]:
    """Load all log entries from a file or directory, sorted by day then time.

    Accepts a JSON list, a {"entries": [...]} wrapper, or a directory of per-entry
    JSON files (the Claude artifact database export format). Invalid records are
    dropped silently.
    Used by every patchwork command that processes the log: weekly, nightly, sample.
    """
    source = Path(path)
    if source.is_dir():
        raw_records = [json.loads(file.read_text()) for file in sorted(source.rglob("*.json"))]
    else:
        loaded = json.loads(source.read_text())
        raw_records = loaded.get("entries", []) if isinstance(loaded, dict) else loaded
    entries = [entry for entry in (_to_entry(record) for record in raw_records) if entry is not None]
    return sorted(entries, key=lambda entry: (entry.day, entry.at))
