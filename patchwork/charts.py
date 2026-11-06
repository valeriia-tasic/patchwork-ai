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
    """Apply the standard grid and spine style to a matplotlib Axes object.

    Removes the top and right spines and puts the grid behind the data.
    Used by weekly_overview and by_area for visual consistency across charts.
    """
    ax.grid(color=GRID)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def _end_labels(ax, x: float, points: list[tuple[float, str, str]], gap: float = 0.42) -> None:
    """Label each line's latest value just right of its last point, nudged apart so none overlap.

    Used by weekly_overview to annotate the rightmost data point of each series
    without the labels stacking on top of each other.
    """
    last_y = None
    for value, text, color in sorted(points, key=lambda point: point[0]):
        y = value if last_y is None else max(value, last_y + gap)
        ax.text(x + 0.18, y, text, va="center", ha="left", fontsize=9.5, color=color, weight="bold")
        last_y = y


def weekly_overview(entries: list[Entry], profile: Profile, today: date, out: Path, weeks: int = 10) -> Path:
    """Build and save the weekly overview chart: one line per cream and one for the antihistamine.

    Multi-area creams plot average applications per treated area; single-area creams
    and the antihistamine plot days used. The x-axis shows calendar weeks.
    Called by cmd_weekly; the PNG is attached to the email alongside the report.
    """
    windows = m.calendar_weeks(today, weeks)
    x = range(len(windows))
    # Each series: (values, label, color, marker, is_average_metric)
    series: list[tuple[list[float], str, str, str, bool]] = []
    for index, cream in enumerate(profile.creams):
        if cream.multi_area:
            values = [m.avg_per_treated_area(m.area_counts(entries, profile, cream, window)) for window in windows]
            series.append((values, f"{cream.name} — avg applications per treated area", cream.color, MARKERS[index % 6], True))
        else:
            values = [len(m.days_of(entries, cream.id, window)) for window in windows]
            series.append((values, f"{cream.name} — days", cream.color, MARKERS[index % 6], False))
    for med in profile.medications:
        series.append((
            [len(m.days_of(entries, med.id, window)) for window in windows],
            f"{med.name} — days",
            med.color,
            "s",
            False,
        ))

    fig, ax = plt.subplots(figsize=(9, 4.9), dpi=110)
    for values, label, color, marker, _ in series:
        ax.plot(x, values, color=color, marker=marker, lw=3, ms=7, label=label)
    last_index = len(windows) - 1
    _end_labels(
        ax,
        last_index,
        [(values[-1], f"{values[-1]:.1f}" if is_avg else str(int(values[-1])), color)
         for values, _, color, _, is_avg in series],
    )
    ax.set_xlim(-0.4, last_index + 0.7)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{window.start:%b} {window.start.day}" for window in windows], fontsize=8.5)
    ax.set_ylim(-0.7, 7.5)
    ax.set_yticks(range(8))
    ax.set_ylabel("Per week (0–7)")
    ax.set_xlabel("Week starting (Monday)")
    names = [cream.name for cream in profile.creams] + [med.name for med in profile.medications]
    fig.suptitle(f"{_title_list(names)} — last {weeks} weeks", x=0.07, ha="left", fontsize=13, weight="bold")
    fig.text(
        0.07, 0.905,
        "Creams used on several areas = applications across areas ÷ areas treated. "
        "Others = days used. Latest values labelled at right.",
        fontsize=8.5, color=MUTED,
    )
    _clean(ax)
    ax.legend(frameon=False, ncol=min(3, len(series)), loc="upper center", bbox_to_anchor=(0.5, -0.16), fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def by_area(entries: list[Entry], profile: Profile, today: date, out: Path, weeks: int = 4) -> Path | None:
    """Build and save the per-area small-multiples chart for the main multi-area cream.

    One panel per body area shows days used per week with a rolling-average reference
    line. Returns None when the profile has no multi-area cream.
    Called by cmd_weekly; the PNG is attached to the email alongside the report.
    """
    area_cream = profile.area_cream
    if area_cream is None:
        return None
    areas = list(profile.cream_areas(area_cream))
    windows = m.rolling_weeks(today, weeks)
    counts = {area: [m.area_counts(entries, profile, area_cream, window)[area] for window in windows] for area in areas}
    rolling_avg = m.rolling_area_average(entries, profile, area_cream, today)
    top = max(4, max(max(values) for values in counts.values()) + 1)
    labels = [f"{window.start:%b} {window.start.day}" for window in windows]
    num_cols = 4
    num_rows = math.ceil((len(areas) + 1) / num_cols)

    fig, axes = plt.subplots(num_rows, num_cols, figsize=(9.5, 2.65 * num_rows), dpi=110, sharey=True, squeeze=False)
    axes_flat = list(axes.flat)
    for index, ax in enumerate(axes_flat):
        if index == len(areas):
            _key_panel(ax, profile, area_cream.name)
            continue
        if index > len(areas):
            ax.axis("off")
            continue
        area = areas[index]
        values = counts[area]
        color = profile.area_colors.get(area, "#333333")
        ax.hlines(rolling_avg[area], -0.2, weeks - 1 + 0.1, color="#9a9a9a", linestyle=(0, (4, 3)), lw=1.6, zorder=1)
        ax.text(weeks - 1 + 0.2, rolling_avg[area], f"avg\n{rolling_avg[area]:.1f}", fontsize=7.5, color="#888",
                va="center", linespacing=0.95)
        ax.plot(range(weeks), values, color=color, marker="o", lw=3, ms=7, zorder=3)
        for i, y in enumerate(values):
            ax.text(i, y + 0.3, str(y), ha="center", fontsize=9, weight="bold", color=color)
        direction_tag, direction_color = {
            "rising": ("▲ rising", RISING),
            "falling": ("▼ falling", FALLING),
            "steady": ("— steady", "#888888"),
        }[m.direction(values[-2], values[-1])]
        ax.set_title(area, loc="left", fontsize=11, weight="bold")
        ax.set_title(direction_tag, loc="right", fontsize=8.5, color=direction_color)
        ax.set_xticks(range(weeks))
        ax.set_xticklabels(labels, fontsize=7.5)
        ax.set_xlim(-0.3, weeks - 1 + 0.85)
        ax.set_ylim(-0.15, top + 0.2)
        ax.set_yticks(range(0, top + 1, 2))
        ax.grid(axis="y", color=GRID)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    for row in range(num_rows):
        axes[row][0].set_ylabel("Times / week")
    covers = ", ".join(area.lower() for area in profile.full_body_covers)
    fig.suptitle(f"{area_cream.name} by body area — last {weeks} weeks (week starting)", x=0.02, ha="left",
                 fontsize=12.5, weight="bold")
    fig.text(
        0.02, 1 - 0.085 * 2 / num_rows,
        f"Full body counts toward {covers}. Other areas are tracked separately.",
        fontsize=8.5, color=MUTED,
    )
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.1 * 2 / num_rows))
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def _title_list(names: list[str]) -> str:
    """Format a list of names as 'A', 'A & B', or 'A, B & C' for chart titles."""
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " & " + names[-1]


def _key_panel(ax, profile: Profile, cream_name: str) -> None:
    """Draw a legend panel into an axes, explaining how to read the by_area chart.

    Occupies the spare panel after the last area in the small-multiples grid.
    """
    ax.axis("off")
    transform = ax.transAxes
    ax.text(0.08, 0.92, "How to read", fontsize=10, weight="bold", transform=transform, va="top")
    ax.plot([0.08, 0.28], [0.72, 0.72], color="#e6194b", lw=3, transform=transform)
    ax.text(0.33, 0.72, f"{cream_name.lower()} days\nper week", fontsize=8.5, color="#555", transform=transform, va="center")
    ax.plot([0.08, 0.28], [0.48, 0.48], color="#9a9a9a", linestyle=(0, (4, 3)), lw=1.6, transform=transform)
    ax.text(0.33, 0.48, f"{profile.rolling_weeks}-week\naverage", fontsize=8.5, color="#555", transform=transform, va="center")
    ax.text(0.08, 0.24, "▲ ▼  this week\nvs last week", fontsize=8.5, color="#555", transform=transform, va="center")
