"""Weekly report: compute once, render as plain text and as email HTML."""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import date

from . import metrics as m
from .data import Entry
from .rules import Profile

CHART_1 = "{{CHART_1}}"  # replaced by the agent with the inline-image reference its mail tool expects
CHART_2 = "{{CHART_2}}"


@dataclass
class Section:
    title: str
    lines: list[str]


@dataclass
class WeeklyReport:
    subject: str
    sections: list[Section]            # creams, antihistamine, flares, allergens
    trends_title: str = ""
    trends: list[str] = field(default_factory=list)   # [summary, rising, falling]
    footer: str = ""
    numbers: dict = field(default_factory=dict)


def _d(d: date) -> str:
    return f"{d:%b} {d.day}"


def _days(n: int) -> str:
    return f"{n} day" if n == 1 else f"{n} days"


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def build_weekly(entries: list[Entry], p: Profile, today: date) -> WeeklyReport:
    this, last = m.rolling_week(today), m.rolling_week(today, 1)
    sections: list[Section] = []
    numbers: dict = {"window": [this.start.isoformat(), this.end.isoformat()], "creams": {}}

    # One section per cream
    for c in p.creams:
        n_now, n_prev = len(m.days_of(entries, c.id, this)), len(m.days_of(entries, c.id, last))
        lines = [f"Total: {_days(n_now)} this week (last week {n_prev})"]
        if c.schedule == "morning_night":
            s = m.slot_counts(entries, c, this)
            lines.append(f"Morning {s['morning']} · Night {s['night']}")
        nums = {"days": n_now, "days_last_week": n_prev}
        if c.multi_area:
            now_c, prev_c = m.area_counts(entries, p, c, this), m.area_counts(entries, p, c, last)
            avg_now, avg_prev = m.avg_per_treated_area(now_c), m.avg_per_treated_area(prev_c)
            top = m.most_affected(now_c)
            lines.append(f"Avg per treated area: {avg_now:.1f} (last week {avg_prev:.1f})")
            lines.append("Most affected: " + (", ".join(f"{a} ({n})" for a, n in top) if top else "none"))
            if c.max_days_per_area_per_week:
                over = m.areas_over_limit(entries, p, c, this)
                lines.append(f"More than {c.max_days_per_area_per_week} applications: " + (
                    "; ".join(f"{a} ({n}) — {', '.join(_d(x) for x in ds)}" for a, n, ds in over) if over else "None"))
            nums.update(area_counts=now_c, area_counts_last_week=prev_c,
                        avg_per_treated_area=avg_now, avg_per_treated_area_last_week=avg_prev)
        if c.max_days_per_week:
            over_total = m.total_over_limit(entries, c, this)
            lines.append(f"Weekly limit ({c.max_days_per_week} days): " + ("over" if over_total else "within"))
        where = "" if c.multi_area else f" ({', '.join(p.cream_areas(c)).lower()})"
        sections.append(Section(c.name.upper() + where.upper(), lines))
        numbers["creams"][c.id] = nums

    # Antihistamine
    if p.antihistamine_enabled:
        a_now, a_prev = len(m.days_of(entries, "anti", this)), len(m.days_of(entries, "anti", last))
        gap = m.antihistamine_gap(entries, this)
        sections.append(Section(p.antihistamine_brand.upper(), [
            f"Total: {_days(a_now)} this week (last week {a_prev})",
            f"Average gap: {m.describe_gap(gap, a_now)}",
        ]))
        numbers.update(antihistamine_days=a_now, antihistamine_gap_days=gap)

    # Flares and notes
    fl = [e for e in entries if e.type == "flare" and e.day in this]
    notes = [e for e in entries if e.day in this and e.note.strip() and e.type in ("flare", "note")]
    sections.append(Section("FLARES", [
        "Reported flares: " + ("; ".join(f"{_d(e.day)} — {', '.join(e.areas) or 'no area'}" for e in fl)
                               if fl else "None logged"),
        "Comments: " + ("; ".join(f"{_d(e.day)}: {e.note.strip()}" for e in notes) if notes else "None"),
    ]))

    # Allergen exposure
    if p.track_allergens:
        ex = [e for e in entries if e.type == "allergen" and e.day in this]
        sections.append(Section("ALLERGEN EXPOSURE", [
            "; ".join(f"{_d(e.day)} — {e.allergen or 'unnamed'}" + (f", {e.amount}" if e.amount else "")
                      for e in ex) if ex else "None logged"
        ]))
        numbers["allergen_exposures"] = len(ex)

    # Trends by area for the main multi-area cream
    trends_title, trends = "", []
    ac = p.area_cream
    if ac:
        now_c, prev_c = m.area_counts(entries, p, ac, this), m.area_counts(entries, p, ac, last)
        avg = m.rolling_area_average(entries, p, ac, today)
        rising = [(a, prev_c[a], now_c[a]) for a in now_c if now_c[a] > prev_c[a]]
        falling = [(a, prev_c[a], now_c[a]) for a in now_c if now_c[a] < prev_c[a]]
        above = [a for a in now_c if now_c[a] - avg[a] >= 1]
        bits = []
        if above:
            bits.append(_and(above) + " above " + ("its" if len(above) == 1 else "their")
                        + f" {p.rolling_weeks}-week average")
        up = [a for a, _, _ in rising if a not in above]
        if up:
            bits.append(_and(up[:3]) + " up")
        if falling:
            bits.append(_and([a for a, _, _ in falling[:2]]) + " easing")
        summary = ("; ".join(bits) + ".") if bits else "No area moved meaningfully this week."
        trends_title = f"TRENDS — {ac.name.lower()} by body area"
        trends = [
            summary[0].upper() + summary[1:],
            "Rising: " + (", ".join(f"{a} ({x} → {y})" for a, x, y in rising) if rising else "None"),
            "Falling: " + (", ".join(f"{a} ({x} → {y})" for a, x, y in falling) if falling else "None"),
        ]
        numbers["rolling_area_average"] = avg

    log_url = p.delivery.get("log_url", "")
    return WeeklyReport(
        subject=f"Skin report — week of {_d(this.start)}",
        sections=sections,
        trends_title=trends_title,
        trends=trends,
        footer=f"Live log: {log_url}" if log_url else "",
        numbers=numbers,
    )


def render_text(r: WeeklyReport) -> str:
    parts = [r.subject]
    parts += [s.title + "\n" + "\n".join(f"- {line}" for line in s.lines) for s in r.sections]
    parts.append("[Chart: weekly overview]")
    if r.trends:
        parts.append(r.trends_title + "\n" + r.trends[0] + "\n" + "\n".join(f"- {t}" for t in r.trends[1:]))
        parts.append("[Chart: by body area]")
    if r.footer:
        parts.append(r.footer)
    return "\n\n".join(parts) + "\n"


def render_html(r: WeeklyReport) -> str:
    e = html.escape
    h3 = '<h3 style="margin:18px 0 6px;font-size:15px;letter-spacing:.04em">{}</h3>'
    ul = '<ul style="margin:0;padding-left:18px;line-height:1.5">{}</ul>'
    img = '<p style="margin:16px 0"><img src="{}" alt="{}" style="width:100%;max-width:640px;height:auto"></p>'
    out = ['<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1d2230;'
           'max-width:640px;font-size:14px">']
    for s in r.sections:
        out.append(h3.format(e(s.title)) + ul.format("".join(f"<li>{e(x)}</li>" for x in s.lines)))
    out.append(img.format(CHART_1, "Weekly overview chart"))
    if r.trends:
        out.append(h3.format(e(r.trends_title)))
        out.append(f'<p style="margin:0 0 4px">{e(r.trends[0])}</p>')
        out.append(ul.format("".join(f"<li>{e(t)}</li>" for t in r.trends[1:])))
        out.append(img.format(CHART_2, "Body area chart"))
    if r.footer:
        out.append(f'<p style="color:#888;font-size:12px;margin-top:20px">{e(r.footer)}</p>')
    out.append("</div>")
    return "".join(out)
