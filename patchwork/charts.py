"""The two report charts. Same inputs always produce the same picture."""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import metrics as m  # noqa: E402
from .data import Entry  # noqa: E402
from .rules import Profile  # noqa: E402

GRID = "#eeeeee"
MUTED = "#666666"
RISING = "#c0392b"
FALLING = "#2e8b57"
MARKERS = ["o", "D", "^", "v", "P", "X"]


def _clean(ax) -> None:
    ax.grid(color=GRID)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def _end_labels(ax, x: float, points: list[tuple[float, str, str]], gap: float = 0.42) -> None:
    """Label each line's latest value just right of its last point, nudged apart so none overlap."""
    y_last = None
    for value, text, color in sorted(points, key=lambda p: p[0]):
        y = value if y_last is None else max(value, y_last + gap)
        ax.text(x + 0.18, y, text, va="center", ha="left", fontsize=9.5, color=color, weight="bold")
        y_last = y


def weekly_overview(entries: list[Entry], p: Profile, today: date, out: Path, weeks: int = 10) -> Path:
    """One line per cream and one for the antihistamine, per calendar week.

    Multi-area creams plot average applications per treated area; single-area creams
    and the antihistamine plot days used.
    """
    wins = m.calendar_weeks(today, weeks)
    x = range(len(wins))
    series: list[tuple[list[float], str, str, str, bool]] = []  # values, label, color, marker, is_avg
    for i, c in enumerate(p.creams):
        if c.multi_area:
            vals = [m.avg_per_treated_area(m.area_counts(entries, p, c, w)) for w in wins]
            series.append((vals, f"{c.name} — avg applications per treated area", c.color, MARKERS[i % 6], True))
        else:
            vals = [len(m.days_of(entries, c.id, w)) for w in wins]
            series.append((vals, f"{c.name} — days", c.color, MARKERS[i % 6], False))
    if p.antihistamine_enabled:
        series.append(([len(m.days_of(entries, "anti", w)) for w in wins], f"{p.antihistamine_brand} — days",
                       p.antihistamine_color, "s", False))

    fig, ax = plt.subplots(figsize=(9, 4.9), dpi=110)
    for vals, label, color, marker, _ in series:
        ax.plot(x, vals, color=color, marker=marker, lw=3, ms=7, label=label)
    last = len(wins) - 1
    _end_labels(ax, last, [(v[-1], f"{v[-1]:.1f}" if avg else str(int(v[-1])), c) for v, _, c, _, avg in series])
    ax.set_xlim(-0.4, last + 0.7)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{w.start:%b} {w.start.day}" for w in wins], fontsize=8.5)
    ax.set_ylim(-0.7, 7.5)
    ax.set_yticks(range(8))
    ax.set_ylabel("Per week (0–7)")
    ax.set_xlabel("Week starting (Monday)")
    names = [c.name for c in p.creams] + ([p.antihistamine_brand] if p.antihistamine_enabled else [])
    fig.suptitle(f"{_title_list(names)} — last {weeks} weeks", x=0.07, ha="left", fontsize=13, weight="bold")
    fig.text(0.07, 0.905, "Creams used on several areas = applications across areas ÷ areas treated. "
             "Others = days used. Latest values labelled at right.", fontsize=8.5, color=MUTED)
    _clean(ax)
    ax.legend(frameon=False, ncol=min(3, len(series)), loc="upper center", bbox_to_anchor=(0.5, -0.16), fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def by_area(entries: list[Entry], p: Profile, today: date, out: Path, weeks: int = 4) -> Path | None:
    """Small multiples for the main multi-area cream: one panel per area, rolling average in grey."""
    c = p.area_cream
    if c is None:
        return None
    areas = list(p.cream_areas(c))
    wins = m.rolling_weeks(today, weeks)
    counts = {a: [m.area_counts(entries, p, c, w)[a] for w in wins] for a in areas}
    avg = m.rolling_area_average(entries, p, c, today)
    top = max(4, max(max(v) for v in counts.values()) + 1)
    labels = [f"{w.start:%b} {w.start.day}" for w in wins]
    cols = 4
    rows = math.ceil((len(areas) + 1) / cols)

    fig, axs = plt.subplots(rows, cols, figsize=(9.5, 2.65 * rows), dpi=110, sharey=True, squeeze=False)
    flat = list(axs.flat)
    for k, ax in enumerate(flat):
        if k == len(areas):
            _key_panel(ax, p, c.name)
            continue
        if k > len(areas):
            ax.axis("off")
            continue
        a = areas[k]
        v = counts[a]
        col = p.area_colors.get(a, "#333333")
        ax.hlines(avg[a], -0.2, weeks - 1 + 0.1, color="#9a9a9a", linestyle=(0, (4, 3)), lw=1.6, zorder=1)
        ax.text(weeks - 1 + 0.2, avg[a], f"avg\n{avg[a]:.1f}", fontsize=7.5, color="#888", va="center",
                linespacing=0.95)
        ax.plot(range(weeks), v, color=col, marker="o", lw=3, ms=7, zorder=3)
        for i, y in enumerate(v):
            ax.text(i, y + 0.3, str(y), ha="center", fontsize=9, weight="bold", color=col)
        tag, tcol = {"rising": ("▲ rising", RISING), "falling": ("▼ falling", FALLING),
                     "steady": ("— steady", "#888888")}[m.direction(v[-2], v[-1])]
        ax.set_title(a, loc="left", fontsize=11, weight="bold")
        ax.set_title(tag, loc="right", fontsize=8.5, color=tcol)
        ax.set_xticks(range(weeks))
        ax.set_xticklabels(labels, fontsize=7.5)
        ax.set_xlim(-0.3, weeks - 1 + 0.85)
        ax.set_ylim(-0.15, top + 0.2)
        ax.set_yticks(range(0, top + 1, 2))
        ax.grid(axis="y", color=GRID)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    for r in range(rows):
        axs[r][0].set_ylabel("Times / week")
    covers = ", ".join(a.lower() for a in p.full_body_covers)
    fig.suptitle(f"{c.name} by body area — last {weeks} weeks (week starting)", x=0.02, ha="left",
                 fontsize=12.5, weight="bold")
    fig.text(0.02, 1 - 0.085 * 2 / rows, f"Full body counts toward {covers}. Other areas are tracked separately.",
             fontsize=8.5, color=MUTED)
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.1 * 2 / rows))
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def _title_list(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " & " + names[-1]


def _key_panel(ax, p: Profile, cream_name: str) -> None:
    ax.axis("off")
    t = ax.transAxes
    ax.text(0.08, 0.92, "How to read", fontsize=10, weight="bold", transform=t, va="top")
    ax.plot([0.08, 0.28], [0.72, 0.72], color="#e6194b", lw=3, transform=t)
    ax.text(0.33, 0.72, f"{cream_name.lower()} days\nper week", fontsize=8.5, color="#555", transform=t, va="center")
    ax.plot([0.08, 0.28], [0.48, 0.48], color="#9a9a9a", linestyle=(0, (4, 3)), lw=1.6, transform=t)
    ax.text(0.33, 0.48, f"{p.rolling_weeks}-week\naverage", fontsize=8.5, color="#555", transform=t, va="center")
    ax.text(0.08, 0.24, "▲ ▼  this week\nvs last week", fontsize=8.5, color="#555", transform=t, va="center")
