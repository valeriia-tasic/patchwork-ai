"""Pure, deterministic metrics over log entries. No I/O, no LLM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from .data import Entry
from .rules import Cream, Profile


@dataclass(frozen=True)
class Window:
    """Inclusive date range."""

    start: date
    end: date

    def __contains__(self, d: date) -> bool:
        return self.start <= d <= self.end

    def label(self) -> str:
        return f"{self.start:%b} {self.start.day}–{self.end:%b} {self.end.day}"


def rolling_week(end: date, weeks_back: int = 0) -> Window:
    """The 7 days ending on `end`, shifted back by whole weeks."""
    e = end - timedelta(days=7 * weeks_back)
    return Window(e - timedelta(days=6), e)


def rolling_weeks(end: date, n: int) -> list[Window]:
    """n consecutive 7-day windows, oldest first, the last one ending on `end`."""
    return [rolling_week(end, i) for i in range(n - 1, -1, -1)]


def calendar_weeks(today: date, n: int) -> list[Window]:
    """n Monday–Sunday weeks, oldest first, the last one containing `today`."""
    monday = today - timedelta(days=today.weekday())
    return [Window(monday - timedelta(weeks=i), monday - timedelta(weeks=i) + timedelta(days=6))
            for i in range(n - 1, -1, -1)]


def days_of(entries: Iterable[Entry], kind: str, window: Window | None = None) -> set[date]:
    """Distinct days with at least one entry of `kind`. Several entries in a day count once."""
    return {e.day for e in entries if e.type == kind and (window is None or e.day in window)}


# --- creams ------------------------------------------------------------------

def area_days(entries: Iterable[Entry], profile: Profile, cream: Cream,
              window: Window | None = None) -> dict[str, set[date]]:
    """For each area the cream can be used on, the distinct days it was applied there.

    Creams are at most once a day, so limits count days: morning and night on the
    same area and day count once. A single-area cream logged without areas
    counts toward its one area.
    """
    allowed = profile.cream_areas(cream)
    out: dict[str, set[date]] = {a: set() for a in allowed}
    for e in entries:
        if e.type != cream.id or (window is not None and e.day not in window):
            continue
        cats = profile.categories_for_all(e.areas) if e.areas else (
            set(allowed) if len(allowed) == 1 else set())
        for a in cats:
            if a in out:
                out[a].add(e.day)
    return out


def area_counts(entries, profile: Profile, cream: Cream, window: Window) -> dict[str, int]:
    """Days per area in the window, in profile order (zeros included)."""
    return {a: len(d) for a, d in area_days(entries, profile, cream, window).items()}


def most_affected(counts: dict[str, int], top: int = 3) -> list[tuple[str, int]]:
    order = list(counts)
    ranked = sorted(((a, n) for a, n in counts.items() if n > 0), key=lambda x: (-x[1], order.index(x[0])))
    return ranked[:top]


def avg_per_treated_area(counts: dict[str, int]) -> float:
    """Total area-days divided by the number of areas treated.

    Legs 2 + Arms 1 -> 3 / 2 = 1.5. Untreated areas don't dilute the number.
    """
    treated = [n for n in counts.values() if n > 0]
    return round(sum(treated) / len(treated), 2) if treated else 0.0


def areas_over_limit(entries, profile: Profile, cream: Cream, window: Window) -> list[tuple[str, int, list[date]]]:
    """Areas where the cream went on more days than its per-area weekly limit."""
    limit = cream.max_days_per_area_per_week
    if not limit:
        return []
    return [(a, len(d), sorted(d)) for a, d in area_days(entries, profile, cream, window).items() if len(d) > limit]


def total_over_limit(entries, cream: Cream, window: Window) -> tuple[int, int] | None:
    """(days used, limit) when the cream's total weekly limit is exceeded, else None."""
    limit = cream.max_days_per_week
    n = len(days_of(entries, cream.id, window))
    return (n, limit) if limit and n > limit else None


def slot_counts(entries, cream: Cream, window: Window) -> dict[str, int]:
    """Days with a morning and days with a night application of the cream."""
    out = {"morning": set(), "night": set()}
    for e in entries:
        if e.type == cream.id and e.day in window and e.slot in out:
            out[e.slot].add(e.day)
    return {k: len(v) for k, v in out.items()}


def rolling_area_average(entries: list[Entry], profile: Profile, cream: Cream, end: date) -> dict[str, float]:
    """Days per week for each area over the last `rolling_weeks` weeks.

    If the cream's log is younger than that, average over the weeks actually logged.
    """
    start = end - timedelta(days=7 * profile.rolling_weeks - 1)
    used = sorted(days_of(entries, cream.id))
    if used and used[0] > start:
        start = used[0]
    span_weeks = max(1.0, ((end - start).days + 1) / 7)
    days = area_days(entries, profile, cream, Window(start, end))
    return {a: round(len(d) / span_weeks, 2) for a, d in days.items()}


# --- antihistamine -----------------------------------------------------------

def antihistamine_gap(entries: Iterable[Entry], window: Window) -> float | None:
    """Mean days between consecutive doses that land in the window.

    The gap from the last dose before the window counts too, so a single dose in
    the week still has a gap. None when there are no doses, or nothing to compare.
    """
    all_days = sorted(days_of(entries, "anti"))
    inside = [d for d in all_days if d in window]
    if not inside:
        return None
    before = [d for d in all_days if d < window.start]
    seq = ([before[-1]] if before else []) + inside
    gaps = [(b - a).days for a, b in zip(seq, seq[1:])]
    return round(sum(gaps) / len(gaps), 2) if gaps else None


def describe_gap(gap: float | None, doses: int) -> str:
    if doses == 0:
        return "none this week"
    if gap is None:
        return "1 dose — no earlier dose to compare"
    half = round(gap * 2) / 2
    if half <= 1:
        return "daily"
    if half == 2:
        return "every second day"
    shown = int(half) if half == int(half) else half
    return f"every {shown} days"


def direction(previous: float, current: float) -> str:
    if current > previous:
        return "rising"
    if current < previous:
        return "falling"
    return "steady"
