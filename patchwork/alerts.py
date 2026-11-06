"""Nightly checks. Returns alerts; the agent decides how to deliver them."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from . import metrics as m
from .data import Entry
from .rules import Profile


@dataclass
class Alert:
    kind: str          # "antihistamine" | "cream_area" | "cream_total" | "trend"
    headline: str      # short, push-sized
    detail: str        # one line for the message body
    context: list[str] = field(default_factory=list)
    key: str = ""      # stable dedup id; set by check functions, empty for trend alerts


def _format_dates(days: list[date]) -> str:
    """Format a list of dates as a readable comma-separated string like 'Mar 9, Mar 11'.

    Used by check_antihistamine and check_creams to list the days inside an alert detail.
    """
    return ", ".join(f"{day:%b} {day.day}" for day in days)


def check_medications(entries: list[Entry], profile: Profile, today: date) -> list[Alert]:
    """Return Alerts for any medication that exceeded its dose limit within its window.

    Loops all medications in the profile; skips those with no limit set.
    Used by nightly to build the push notification.
    """
    found: list[Alert] = []
    for med in profile.medications:
        if med.max_doses is None or med.window_days is None:
            continue
        window = m.Window(today - timedelta(days=med.window_days - 1), today)
        recent = sorted(m.days_of(entries, med.id, window))
        if len(recent) <= med.max_doses:
            continue
        last_7 = len(m.days_of(entries, med.id, m.rolling_week(today)))
        last_14 = len(m.days_of(entries, med.id, m.Window(today - timedelta(days=13), today)))
        found.append(Alert(
            kind="medication",
            headline=f"{med.name} {len(recent)} of last {med.window_days} days",
            detail=f"{med.name} on {_format_dates(recent)} — {last_7} days in the last 7, {last_14} in the last 14.",
            key=f"medication:{med.id}",
        ))
    return found


def check_creams(entries: list[Entry], profile: Profile, today: date) -> list[Alert]:
    """Return Alerts for any cream that exceeded its per-area or total weekly limit.

    Checks every cream in the profile against the rolling 7-day window ending today.
    Used by nightly to populate the cream-limit section of the push notification.
    """
    week = m.rolling_week(today)
    alerts: list[Alert] = []
    for cream in profile.creams:
        for area, count, days in m.areas_over_limit(entries, profile, cream, week):
            where = f"{area} " if cream.multi_area else ""
            alerts.append(Alert(
                kind="cream_area",
                headline=f"{where}{cream.name} {count}x this week",
                detail=f"{cream.name} on {area}: {count} days in the last 7 ({_format_dates(days)}), "
                       f"over your limit of {cream.max_days_per_area_per_week}.",
                key=f"cream_area:{cream.id}:{area}",
            ))
        over_total = m.total_over_limit(entries, cream, week)
        if over_total:
            count, limit = over_total
            alerts.append(Alert(
                kind="cream_total",
                headline=f"{cream.name} {count} days this week",
                detail=f"{cream.name}: {count} days in the last 7, over your limit of {limit}.",
                key=f"cream_total:{cream.id}",
            ))
    return alerts


def check_trends(entries: list[Entry], profile: Profile, today: date) -> list[Alert]:
    """Return Alerts for any tracked metric that moved meaningfully vs its baseline.

    Compares the last 7 days against the rolling average of the baseline weeks
    defined in the profile. Covers per-cream days, per-area counts, antihistamine
    days, and flares.
    Used by nightly to surface week-on-week changes the parent might not notice.
    """
    baseline_week_count = profile.trend_baseline_weeks
    current_window = m.rolling_week(today)
    baseline_windows = [m.rolling_week(today, i) for i in range(1, baseline_week_count + 1)]

    # Build (name, current_value, baseline_average) for each metric directly —
    # no lambda captures needed, which makes the closure behaviour explicit.
    metrics_to_check: list[tuple[str, float, float]] = []

    for cream in profile.creams:
        current_value = len(m.days_of(entries, cream.id, current_window))
        baseline_average = sum(len(m.days_of(entries, cream.id, window)) for window in baseline_windows) / baseline_week_count
        metrics_to_check.append((f"{cream.name} days", current_value, baseline_average))

        if cream.multi_area:
            for area in profile.cream_areas(cream):
                current_value = m.area_counts(entries, profile, cream, current_window)[area]
                baseline_average = (
                    sum(m.area_counts(entries, profile, cream, window)[area] for window in baseline_windows)
                    / baseline_week_count
                )
                metrics_to_check.append((f"{area} {cream.name}", current_value, baseline_average))

    for med in profile.medications:
        current_value = len(m.days_of(entries, med.id, current_window))
        baseline_average = sum(len(m.days_of(entries, med.id, window)) for window in baseline_windows) / baseline_week_count
        metrics_to_check.append((f"{med.name} days", current_value, baseline_average))

    flares_this_week = sum(1 for entry in entries if entry.type == "flare" and entry.day in current_window)
    flares_baseline = (
        sum(
            sum(1 for entry in entries if entry.type == "flare" and entry.day in window)
            for window in baseline_windows
        )
        / baseline_week_count
    )
    metrics_to_check.append(("Flares", flares_this_week, flares_baseline))

    trend_alerts = []
    for name, current_value, baseline_average in metrics_to_check:
        if abs(current_value - baseline_average) >= profile.trend_min_change:
            direction_word = "up" if current_value > baseline_average else "down"
            trend_alerts.append(Alert(
                kind="trend",
                headline=f"{name} {direction_word}",
                detail=f"{name} {direction_word}: {current_value:g} this week vs ~{baseline_average:.1f}/week before.",
            ))
    return trend_alerts


def context(entries: list[Entry], today: date) -> list[str]:
    """Return notes and allergen exposures from the last 7 days as plain text lines.

    Used by nightly to attach recent context to the first alert so the parent
    can see what else happened this week alongside the alert summary.
    """
    week = m.rolling_week(today)
    lines = []
    for entry in entries:
        if entry.day not in week:
            continue
        if entry.type == "allergen":
            lines.append(
                f"{entry.day:%b} {entry.day.day}: allergen — {entry.allergen or 'unnamed'}"
                + (f", {entry.amount}" if entry.amount else "")
            )
        elif entry.note.strip():
            lines.append(f"{entry.day:%b} {entry.day.day}: {entry.note.strip()}")
    return lines


def filter_new(found: list[Alert], sent: list[dict], today: date) -> list[Alert]:
    """Return only alerts not already sent within the last 7 days.

    `sent` is a list of dicts with 'key' and 'date' (ISO string). Alerts with an
    empty key (trend alerts) are always passed through. Suppresses a keyed alert
    if the same key was sent on a date still within the 7-day rolling window.
    """
    recent_keys = {
        item["key"] for item in sent
        if (today - date.fromisoformat(item["date"])).days < 7
    }
    return [a for a in found if not a.key or a.key not in recent_keys]


def nightly(entries: list[Entry], profile: Profile, today: date) -> list[Alert]:
    """Run all nightly checks and return every Alert that fired.

    Runs antihistamine, cream-limit, and trend checks in order. Attaches recent
    context to the first alert when any alert fires.
    Called by cmd_nightly, which serialises the result to JSON for the agent.
    """
    found_alerts: list[Alert] = []
    found_alerts += check_medications(entries, profile, today)
    found_alerts += check_creams(entries, profile, today)
    found_alerts += check_trends(entries, profile, today)
    if found_alerts:
        found_alerts[0].context = context(entries, today)
    return found_alerts


def push_text(alerts: list[Alert], limit: int = 200) -> str:
    """Build a single push-notification string from a list of alerts, truncated to `limit` chars.

    Returns an empty string when there are no alerts (quiet night).
    Used by cmd_nightly to fill the 'push' field in the JSON output.
    """
    if not alerts:
        return ""
    text = "Hey! " + " · ".join(alert.headline for alert in alerts)
    return text if len(text) <= limit else text[: limit - 1] + "…"
