"""Weekly report: compute once, render as plain text and as email HTML."""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import date
from typing import TypedDict

from . import metrics as m
from .data import Entry
from .rules import Profile


class CreamNumbers(TypedDict, total=False):
    """Per-cream numbers included in the report JSON and used by the agent to read metrics."""

    days: int
    days_last_week: int
    area_counts: dict[str, int]
    area_counts_last_week: dict[str, int]
    avg_per_treated_area: float
    avg_per_treated_area_last_week: float


class ReportNumbers(TypedDict, total=False):
    """All numeric outputs from build_weekly, written to report.json for the agent.

    All keys are optional because antihistamine, allergen, and area-trend numbers
    are only present when those features are enabled in the profile.
    """

    window: list[str]           # [start_iso, end_iso]
    creams: dict[str, CreamNumbers]
    medications: dict[str, dict]  # med_id → {days, gap_days}
    allergen_exposures: int
    rolling_area_average: dict[str, float]

CHART_1 = "{{CHART_1}}"  # replaced by the agent with the inline-image reference its mail tool expects
CHART_2 = "{{CHART_2}}"


@dataclass
class Section:
    """One titled block in the weekly report (e.g. a cream section or the flares section)."""

    title: str
    lines: list[str]


@dataclass
class WeeklyReport:
    """All computed content for one weekly report, ready to render as text or HTML.

    Built by build_weekly and passed to render_text or render_html.
    The `numbers` dict is also written to report.json for the agent to read.
    """

    subject: str
    sections: list[Section]            # creams, antihistamine, flares, allergens
    trends_title: str = ""
    trends: list[str] = field(default_factory=list)   # [summary, rising, falling]
    footer: str = ""
    numbers: ReportNumbers = field(default_factory=dict)  # type: ignore[arg-type]
    notifications: list[str] | None = None  # set when --sent is passed; None omits the section


def _format_date(day: date) -> str:
    """Format a date as 'Mar 9' for use in report text lines."""
    return f"{day:%b} {day.day}"


def _format_days(count: int) -> str:
    """Format a day count as '1 day' or '3 days' for use in report text lines."""
    return f"{count} day" if count == 1 else f"{count} days"


def _join_and(items: list[str]) -> str:
    """Join a list of strings with commas and 'and' before the last item."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def build_weekly(entries: list[Entry], profile: Profile, today: date, sent: list[dict] | None = None) -> WeeklyReport:
    """Compute all metrics for the current week and assemble a WeeklyReport.

    Covers every cream (total days, slot split, per-area counts, limits), the
    antihistamine, flares, allergen exposures, and area trends for the main
    multi-area cream.
    Called by cmd_weekly; the result is passed to render_text, render_html, and
    written to report.json.
    """
    this_week = m.rolling_week(today)
    last_week = m.rolling_week(today, 1)
    sections: list[Section] = []
    numbers: ReportNumbers = {"window": [this_week.start.isoformat(), this_week.end.isoformat()], "creams": {}}

    # One section per cream
    for cream in profile.creams:
        days_this_week = len(m.days_of(entries, cream.id, this_week))
        days_last_week = len(m.days_of(entries, cream.id, last_week))
        lines = [f"Total: {_format_days(days_this_week)} this week (last week {days_last_week})"]
        if cream.schedule == "morning_night":
            slots = m.slot_counts(entries, cream, this_week)
            lines.append(f"Morning {slots['morning']} · Night {slots['night']}")
        cream_numbers: dict = {"days": days_this_week, "days_last_week": days_last_week}
        if cream.multi_area:
            counts_this_week = m.area_counts(entries, profile, cream, this_week)
            counts_last_week = m.area_counts(entries, profile, cream, last_week)
            avg_this_week = m.avg_per_treated_area(counts_this_week)
            avg_last_week = m.avg_per_treated_area(counts_last_week)
            top_areas = m.most_affected(counts_this_week)
            lines.append(f"Avg per treated area: {avg_this_week:.1f} (last week {avg_last_week:.1f})")
            lines.append("Most affected: " + (
                ", ".join(f"{area} ({count})" for area, count in top_areas) if top_areas else "none"
            ))
            if cream.max_days_per_area_per_week:
                over_areas = m.areas_over_limit(entries, profile, cream, this_week)
                lines.append(f"More than {cream.max_days_per_area_per_week} applications: " + (
                    "; ".join(
                        f"{area} ({count}) — {', '.join(_format_date(day) for day in days)}"
                        for area, count, days in over_areas
                    ) if over_areas else "None"
                ))
            cream_numbers.update(
                area_counts=counts_this_week,
                area_counts_last_week=counts_last_week,
                avg_per_treated_area=avg_this_week,
                avg_per_treated_area_last_week=avg_last_week,
            )
        if cream.max_days_per_week:
            over_total = m.total_over_limit(entries, cream, this_week)
            lines.append(f"Weekly limit ({cream.max_days_per_week} days): " + ("over" if over_total else "within"))
        area_label = "" if cream.multi_area else f" ({', '.join(profile.cream_areas(cream)).lower()})"
        sections.append(Section(cream.name.upper() + area_label.upper(), lines))
        numbers["creams"][cream.id] = cream_numbers

    # Medications — one section per medication
    meds_numbers: dict[str, dict] = {}
    for med in profile.medications:
        days_this_week = len(m.days_of(entries, med.id, this_week))
        days_last_week = len(m.days_of(entries, med.id, last_week))
        gap = m.medication_gap(entries, med.id, this_week)
        sections.append(Section(med.name.upper(), [
            f"Total: {_format_days(days_this_week)} this week (last week {days_last_week})",
            f"Average gap: {m.describe_gap(gap, days_this_week)}",
        ]))
        meds_numbers[med.id] = {"days": days_this_week, "gap_days": gap}
    if meds_numbers:
        numbers["medications"] = meds_numbers

    # Flares and notes
    flares = [entry for entry in entries if entry.type == "flare" and entry.day in this_week]
    notes = [entry for entry in entries if entry.day in this_week and entry.note.strip() and entry.type in ("flare", "note")]
    sections.append(Section("FLARES", [
        "Reported flares: " + (
            "; ".join(
                f"{_format_date(entry.day)} — {', '.join(entry.areas) or 'no area'}"
                for entry in flares
            ) if flares else "None logged"
        ),
        "Comments: " + (
            "; ".join(f"{_format_date(entry.day)}: {entry.note.strip()}" for entry in notes)
            if notes else "None"
        ),
    ]))

    # Allergen exposure
    if profile.track_allergens:
        exposures = [entry for entry in entries if entry.type == "allergen" and entry.day in this_week]
        sections.append(Section("ALLERGEN EXPOSURE", [
            "; ".join(
                f"{_format_date(entry.day)} — {entry.allergen or 'unnamed'}"
                + (f", {entry.amount}" if entry.amount else "")
                for entry in exposures
            ) if exposures else "None logged"
        ]))
        numbers["allergen_exposures"] = len(exposures)

    # Trends by area for the main multi-area cream
    trends_title, trends = "", []
    area_cream = profile.area_cream
    if area_cream:
        counts_this_week = m.area_counts(entries, profile, area_cream, this_week)
        counts_last_week = m.area_counts(entries, profile, area_cream, last_week)
        rolling_avg = m.rolling_area_average(entries, profile, area_cream, today)
        rising = [(area, counts_last_week[area], counts_this_week[area]) for area in counts_this_week if counts_this_week[area] > counts_last_week[area]]
        falling = [(area, counts_last_week[area], counts_this_week[area]) for area in counts_this_week if counts_this_week[area] < counts_last_week[area]]
        above_average = [area for area in counts_this_week if counts_this_week[area] - rolling_avg[area] >= 1]
        bits = []
        if above_average:
            bits.append(
                _join_and(above_average) + " above "
                + ("its" if len(above_average) == 1 else "their")
                + f" {profile.rolling_weeks}-week average"
            )
        rising_not_above = [area for area, _, _ in rising if area not in above_average]
        if rising_not_above:
            bits.append(_join_and(rising_not_above[:3]) + " up")
        if falling:
            bits.append(_join_and([area for area, _, _ in falling[:2]]) + " easing")
        summary = ("; ".join(bits) + ".") if bits else "No area moved meaningfully this week."
        trends_title = f"TRENDS — {area_cream.name.lower()} by body area"
        trends = [
            summary[0].upper() + summary[1:],
            "Rising: " + (", ".join(f"{area} ({prev} → {curr})" for area, prev, curr in rising) if rising else "None"),
            "Falling: " + (", ".join(f"{area} ({prev} → {curr})" for area, prev, curr in falling) if falling else "None"),
        ]
        numbers["rolling_area_average"] = rolling_avg

    # Notifications sent this week (only when sent history is provided)
    notifications: list[str] | None = None
    if sent is not None:
        fired_this_week = []
        for item in sent:
            try:
                sent_date = date.fromisoformat(item["date"])
            except (KeyError, ValueError):
                continue
            if sent_date in this_week:
                fired_this_week.append(f"{_format_date(sent_date)}: {item.get('headline', item.get('key', ''))}")
        notifications = fired_this_week if fired_this_week else ["None sent this week."]

    log_url = profile.delivery.get("log_url", "")
    return WeeklyReport(
        subject=f"Skin report — week of {_format_date(this_week.start)}",
        sections=sections,
        trends_title=trends_title,
        trends=trends,
        footer=f"Live log: {log_url}" if log_url else "",
        numbers=numbers,
        notifications=notifications,
    )


def render_text(weekly_report: WeeklyReport) -> str:
    """Render a WeeklyReport as plain text for the email text body.

    Used by cmd_weekly, which writes the result to report.txt.
    """
    parts = [weekly_report.subject]
    parts += [
        section.title + "\n" + "\n".join(f"- {line}" for line in section.lines)
        for section in weekly_report.sections
    ]
    parts.append("[Chart: weekly overview]")
    if weekly_report.trends:
        parts.append(
            weekly_report.trends_title + "\n"
            + weekly_report.trends[0] + "\n"
            + "\n".join(f"- {trend}" for trend in weekly_report.trends[1:])
        )
        parts.append("[Chart: by body area]")
    if weekly_report.notifications is not None:
        parts.append("NOTIFICATIONS SENT\n" + "\n".join(f"- {line}" for line in weekly_report.notifications))
    if weekly_report.footer:
        parts.append(weekly_report.footer)
    return "\n\n".join(parts) + "\n"


def render_html(weekly_report: WeeklyReport) -> str:
    """Render a WeeklyReport as an inline HTML email body.

    Chart placeholders (CHART_1, CHART_2) are left as-is for the agent to replace
    with actual image references before sending.
    Used by cmd_weekly, which writes the result to report.html.
    """
    escape = html.escape
    heading_template = '<h3 style="margin:18px 0 6px;font-size:15px;letter-spacing:.04em">{}</h3>'
    list_template = '<ul style="margin:0;padding-left:18px;line-height:1.5">{}</ul>'
    image_template = '<p style="margin:16px 0"><img src="{}" alt="{}" style="width:100%;max-width:640px;height:auto"></p>'
    out = ['<meta charset="utf-8">',
           '<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1d2230;'
           'max-width:640px;font-size:14px">']
    for section in weekly_report.sections:
        out.append(
            heading_template.format(escape(section.title))
            + list_template.format("".join(f"<li>{escape(line)}</li>" for line in section.lines))
        )
    out.append(image_template.format(CHART_1, "Weekly overview chart"))
    if weekly_report.trends:
        out.append(heading_template.format(escape(weekly_report.trends_title)))
        out.append(f'<p style="margin:0 0 4px">{escape(weekly_report.trends[0])}</p>')
        out.append(list_template.format("".join(f"<li>{escape(trend)}</li>" for trend in weekly_report.trends[1:])))
        out.append(image_template.format(CHART_2, "Body area chart"))
    if weekly_report.notifications is not None:
        out.append(heading_template.format("NOTIFICATIONS SENT"))
        out.append(list_template.format("".join(f"<li>{escape(line)}</li>" for line in weekly_report.notifications)))
    if weekly_report.footer:
        out.append(f'<p style="color:#888;font-size:12px;margin-top:20px">{escape(weekly_report.footer)}</p>')
    out.append("</div>")
    return "".join(out)
