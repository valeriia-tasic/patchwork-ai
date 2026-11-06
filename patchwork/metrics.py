"""Pure, deterministic metrics over log entries. No I/O, no LLM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from .data import Entry
from .rules import Cream, Profile


@dataclass(frozen=True)
class Window:
    """Inclusive date range used to slice log entries for any metric."""

    start: date
    end: date

    def __contains__(self, day: date) -> bool:
        """Return True when `day` falls within this window (inclusive on both ends)."""
        return self.start <= day <= self.end

    def label(self) -> str:
        """Return a human-readable label like 'Mar 9–Mar 15' for display in reports."""
        return f"{self.start:%b} {self.start.day}–{self.end:%b} {self.end.day}"


def rolling_week(end: date, weeks_back: int = 0) -> Window:
    """Return the 7-day window ending on `end`, shifted back by whole weeks.

    Used by report and alerts to define 'this week' (weeks_back=0) and
    'last week' (weeks_back=1) for comparison.
    """
    shifted_end = end - timedelta(days=7 * weeks_back)
    return Window(shifted_end - timedelta(days=6), shifted_end)


def rolling_weeks(end: date, n: int) -> list[Window]:
    """Return n consecutive 7-day windows, oldest first, the last one ending on `end`.

    Used by charts.by_area to build the x-axis of the per-area small-multiples chart.
    """
    return [rolling_week(end, i) for i in range(n - 1, -1, -1)]


def calendar_weeks(today: date, n: int) -> list[Window]:
    """Return n Monday–Sunday weeks, oldest first, the last one containing `today`.

    Used by charts.weekly_overview so week boundaries align with calendar weeks.
    """
    monday = today - timedelta(days=today.weekday())
    return [
        Window(monday - timedelta(weeks=i), monday - timedelta(weeks=i) + timedelta(days=6))
        for i in range(n - 1, -1, -1)
    ]


def days_of(entries: Iterable[Entry], kind: str, window: Window | None = None) -> set[date]:
    """Return the distinct days with at least one entry of `kind`, optionally within a window.

    Several entries on the same day count once. Used throughout metrics, report, and
    alerts to count how many days a cream or antihistamine was used.
    """
    return {entry.day for entry in entries if entry.type == kind and (window is None or entry.day in window)}


# --- creams ------------------------------------------------------------------

def area_days(
    entries: Iterable[Entry],
    profile: Profile,
    cream: Cream,
    window: Window | None = None,
) -> dict[str, set[date]]:
    """Return the distinct days the cream was applied per area, optionally within a window.

    Creams are counted at most once per day per area, so morning and night on the
    same area and day count once. A single-area cream logged without areas counts
    toward its one area automatically.
    Used by area_counts, areas_over_limit, rolling_area_average, and charts.by_area.
    """
    allowed = profile.cream_areas(cream)
    result: dict[str, set[date]] = {area: set() for area in allowed}
    for entry in entries:
        if entry.type != cream.id or (window is not None and entry.day not in window):
            continue
        matched_areas = profile.categories_for_all(entry.areas) if entry.areas else (
            set(allowed) if len(allowed) == 1 else set()
        )
        for area in matched_areas:
            if area in result:
                result[area].add(entry.day)
    return result


def area_counts(
    entries: Iterable[Entry],
    profile: Profile,
    cream: Cream,
    window: Window,
) -> dict[str, int]:
    """Return days per area in the window, in profile order (zeros included).

    Used by report.build_weekly and charts to show which areas were treated most.
    """
    return {area: len(day_set) for area, day_set in area_days(entries, profile, cream, window).items()}


def most_affected(counts: dict[str, int], top: int = 3) -> list[tuple[str, int]]:
    """Return the top areas by days treated, preserving profile order for ties.

    Used by report.build_weekly to highlight the most-treated areas in the weekly summary.
    """
    order = list(counts)
    ranked = sorted(
        ((area, count) for area, count in counts.items() if count > 0),
        key=lambda pair: (-pair[1], order.index(pair[0])),
    )
    return ranked[:top]


def avg_per_treated_area(counts: dict[str, int]) -> float:
    """Return total area-days divided by the number of areas actually treated.

    Example: Legs 2 + Arms 1 → 3 / 2 = 1.5. Untreated areas don't dilute the number.
    Used by report.build_weekly and charts.weekly_overview to give a single summary
    number for multi-area creams without penalising areas that weren't touched.
    """
    treated = [count for count in counts.values() if count > 0]
    return round(sum(treated) / len(treated), 2) if treated else 0.0


def areas_over_limit(
    entries: Iterable[Entry],
    profile: Profile,
    cream: Cream,
    window: Window,
) -> list[tuple[str, int, list[date]]]:
    """Return (area, days_used, sorted_dates) for areas that exceeded the per-area weekly limit.

    Returns an empty list when the cream has no per-area limit set.
    Used by alerts.check_creams and report.build_weekly to flag over-limit applications.
    """
    limit = cream.max_days_per_area_per_week
    if not limit:
        return []
    return [
        (area, len(day_set), sorted(day_set))
        for area, day_set in area_days(entries, profile, cream, window).items()
        if len(day_set) > limit
    ]


def total_over_limit(
    entries: Iterable[Entry],
    cream: Cream,
    window: Window,
) -> tuple[int, int] | None:
    """Return (days_used, limit) when the cream's total weekly limit is exceeded, else None.

    Used by alerts.check_creams and report.build_weekly to flag total over-limit usage.
    """
    limit = cream.max_days_per_week
    days_used = len(days_of(entries, cream.id, window))
    return (days_used, limit) if limit and days_used > limit else None


def slot_counts(entries: Iterable[Entry], cream: Cream, window: Window) -> dict[str, int]:
    """Return how many days had a morning and how many had a night application of the cream.

    Only meaningful for morning_night-schedule creams.
    Used by report.build_weekly to show the morning/night split for scheduled creams.
    """
    result: dict[str, set[date]] = {"morning": set(), "night": set()}
    for entry in entries:
        if entry.type == cream.id and entry.day in window and entry.slot in result:
            result[entry.slot].add(entry.day)
    return {slot: len(day_set) for slot, day_set in result.items()}


def rolling_area_average(
    entries: list[Entry],
    profile: Profile,
    cream: Cream,
    end: date,
) -> dict[str, float]:
    """Return the average days per week for each area over the profile's rolling window.

    If the cream's log is younger than the full window, average over the weeks actually
    logged rather than inflating the denominator with empty weeks.
    Used by charts.by_area (dashed reference line) and report.build_weekly (trend summary).
    """
    span_start = end - timedelta(days=7 * profile.rolling_weeks - 1)
    logged_days = sorted(days_of(entries, cream.id))
    if logged_days and logged_days[0] > span_start:
        span_start = logged_days[0]
    span_weeks = max(1.0, ((end - span_start).days + 1) / 7)
    day_sets = area_days(entries, profile, cream, Window(span_start, end))
    return {area: round(len(day_set) / span_weeks, 2) for area, day_set in day_sets.items()}


# --- medications -------------------------------------------------------------

def medication_gap(entries: Iterable[Entry], med_id: str, window: Window) -> float | None:
    """Return the mean days between consecutive doses of a medication touching the window.

    The gap from the last dose before the window counts too, so a single dose in the
    week still has a gap to compare. Returns None when there are no doses or nothing
    to compare.
    Used by report.build_weekly to show dosing frequency in the medication sections.
    """
    all_days = sorted(days_of(entries, med_id))
    inside = [day for day in all_days if day in window]
    if not inside:
        return None
    before = [day for day in all_days if day < window.start]
    date_sequence = ([before[-1]] if before else []) + inside
    gaps = [(later_date - earlier_date).days for earlier_date, later_date in zip(date_sequence, date_sequence[1:])]
    return round(sum(gaps) / len(gaps), 2) if gaps else None


def describe_gap(gap: float | None, doses: int) -> str:
    """Convert a numeric gap in days to a human-readable frequency string.

    Used by report.build_weekly to render the antihistamine gap as plain English.
    """
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
    """Return 'rising', 'falling', or 'steady' by comparing two values.

    Used by charts.by_area to label each area panel with a trend indicator.
    """
    if current > previous:
        return "rising"
    if current < previous:
        return "falling"
    return "steady"
