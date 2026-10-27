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


def _fmt(days: list[date]) -> str:
    return ", ".join(f"{d:%b} {d.day}" for d in days)


def check_antihistamine(entries: list[Entry], p: Profile, today: date) -> Alert | None:
    if not p.antihistamine_enabled:
        return None
    span, limit = p.antihistamine_window_days, p.antihistamine_max_doses
    recent = sorted(m.days_of(entries, "anti", m.Window(today - timedelta(days=span - 1), today)))
    if len(recent) <= limit:
        return None
    last7 = len(m.days_of(entries, "anti", m.rolling_week(today)))
    last14 = len(m.days_of(entries, "anti", m.Window(today - timedelta(days=13), today)))
    brand = p.antihistamine_brand
    return Alert(
        kind="antihistamine",
        headline=f"{brand} {len(recent)} of last {span} days",
        detail=f"{brand} on {_fmt(recent)} — {last7} days in the last 7, {last14} in the last 14.",
    )


def check_creams(entries: list[Entry], p: Profile, today: date) -> list[Alert]:
    week = m.rolling_week(today)
    out: list[Alert] = []
    for c in p.creams:
        for area, n, days in m.areas_over_limit(entries, p, c, week):
            where = f"{area} " if c.multi_area else ""
            out.append(Alert(
                kind="cream_area",
                headline=f"{where}{c.name} {n}x this week",
                detail=f"{c.name} on {area}: {n} days in the last 7 ({_fmt(days)}), "
                       f"over your limit of {c.max_days_per_area_per_week}.",
            ))
        over = m.total_over_limit(entries, c, week)
        if over:
            n, limit = over
            out.append(Alert(
                kind="cream_total",
                headline=f"{c.name} {n} days this week",
                detail=f"{c.name}: {n} days in the last 7, over your limit of {limit}.",
            ))
    return out


def check_trends(entries: list[Entry], p: Profile, today: date) -> list[Alert]:
    """Last 7 days vs the weekly average of the baseline weeks before it."""
    base_n = p.trend_baseline_weeks
    now = m.rolling_week(today)
    base = [m.rolling_week(today, i) for i in range(1, base_n + 1)]

    series: dict[str, callable] = {}
    for c in p.creams:
        series[f"{c.name} days"] = (lambda cid: lambda w: len(m.days_of(entries, cid, w)))(c.id)
        if c.multi_area:
            for a in p.cream_areas(c):
                series[f"{a} {c.name}"] = (lambda cc, aa: lambda w: m.area_counts(entries, p, cc, w)[aa])(c, a)
    if p.antihistamine_enabled:
        series[f"{p.antihistamine_brand} days"] = lambda w: len(m.days_of(entries, "anti", w))
    series["Flares"] = lambda w: sum(1 for e in entries if e.type == "flare" and e.day in w)

    out = []
    for name, fn in series.items():
        cur, avg = fn(now), sum(fn(w) for w in base) / base_n
        if abs(cur - avg) >= p.trend_min_change:
            word = "up" if cur > avg else "down"
            out.append(Alert(kind="trend", headline=f"{name} {word}",
                             detail=f"{name} {word}: {cur:g} this week vs ~{avg:.1f}/week before."))
    return out


def context(entries: list[Entry], today: date) -> list[str]:
    """Notes and allergen exposures from the last 7 days."""
    week = m.rolling_week(today)
    lines = []
    for e in entries:
        if e.day not in week:
            continue
        if e.type == "allergen":
            lines.append(f"{e.day:%b} {e.day.day}: allergen — {e.allergen or 'unnamed'}"
                         + (f", {e.amount}" if e.amount else ""))
        elif e.note.strip():
            lines.append(f"{e.day:%b} {e.day.day}: {e.note.strip()}")
    return lines


def nightly(entries: list[Entry], p: Profile, today: date) -> list[Alert]:
    alerts: list[Alert] = []
    a = check_antihistamine(entries, p, today)
    if a:
        alerts.append(a)
    alerts += check_creams(entries, p, today)
    alerts += check_trends(entries, p, today)
    if alerts:
        alerts[0].context = context(entries, today)
    return alerts


def push_text(alerts: list[Alert], limit: int = 200) -> str:
    if not alerts:
        return ""
    text = "Hey! " + " · ".join(a.headline for a in alerts)
    return text if len(text) <= limit else text[: limit - 1] + "…"
