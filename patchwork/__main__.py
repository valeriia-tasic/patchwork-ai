"""Command line: python -m patchwork <command> ...

  init      Ask the first-use questions and write private/profile.json
  validate  [--profile PATH]   Check a profile; prints problems or "ok"
  weekly    --entries PATH [--today YYYY-MM-DD] [--out DIR] [--profile PATH]
            Writes report.txt, report.html, report.json, chart-overview.png, chart-areas.png
  nightly   --entries PATH [--today YYYY-MM-DD] [--profile PATH]
            Prints JSON: {"alerts": [...], "push": "...", "message": "..."}
  sample    [--out PATH] [--weeks N] [--seed N] [--profile PATH]
            Writes a synthetic log for a fictional toddler, following the profile
  page      [--profile PATH] [--out PATH]
            Builds the log page with the profile baked in

Without --profile, private/profile.json is used if it exists, else rules.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

from . import alerts, charts, report, setup
from .data import load_entries
from .rules import PRIVATE_PROFILE, ROOT, load_profile, unwrap, validate


def _today(s: str | None) -> date:
    return date.fromisoformat(s) if s else date.today()


def cmd_init(a) -> int:
    target = Path(a.out)
    if target.exists() and not setup._yes(input(f"{target} already exists. Replace it? [n] ")):
        print("Kept your existing profile.")
        return 0
    profile = setup.run(input)
    print("\n" + setup.summary(profile))
    if not setup._yes(input("\nSave this profile? [y] "), default=True):
        print("Nothing saved.")
        return 1
    setup.write(profile, target)
    print(f"Saved {target}. Next: python -m patchwork page   (builds your log page)")
    return 0


def cmd_validate(a) -> int:
    path = Path(a.profile) if a.profile else (PRIVATE_PROFILE if PRIVATE_PROFILE.exists() else ROOT / "rules.json")
    problems = validate(unwrap(json.loads(path.read_text())))
    print("ok" if not problems else "\n".join(f"- {p}" for p in problems))
    return 0 if not problems else 1


def cmd_weekly(a) -> int:
    p = load_profile(a.profile)
    entries = load_entries(a.entries)
    today = _today(a.today)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    r = report.build_weekly(entries, p, today)
    (out / "report.txt").write_text(report.render_text(r))
    (out / "report.html").write_text(report.render_html(r))
    (out / "report.json").write_text(json.dumps({"subject": r.subject, **r.numbers}, default=str, indent=2))
    charts.weekly_overview(entries, p, today, out / "chart-overview.png")
    charts.by_area(entries, p, today, out / "chart-areas.png")
    print(json.dumps({"subject": r.subject, "dir": str(out)}))
    return 0


def cmd_nightly(a) -> int:
    p = load_profile(a.profile)
    found = alerts.nightly(load_entries(a.entries), p, _today(a.today))
    lines = [x.detail for x in found]
    ctx = found[0].context if found else []
    message = "\n".join(lines + (["Context:"] + ctx if ctx else []))
    print(json.dumps({"alerts": [asdict(x) for x in found], "push": alerts.push_text(found),
                      "message": message}, indent=2))
    return 0


def cmd_sample(a) -> int:
    from .synthetic import generate
    data = generate(weeks=a.weeks, seed=a.seed, end=_today(a.today), profile=load_profile(a.profile))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(data, indent=1))
    print(f"wrote {len(data)} synthetic entries to {a.out}")
    return 0


def cmd_page(a) -> int:
    from .page import build
    out = build(a.profile, a.out)
    print(f"built {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="patchwork")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init")
    i.add_argument("--out", default=str(PRIVATE_PROFILE))
    i.set_defaults(fn=cmd_init)

    v = sub.add_parser("validate")
    v.add_argument("--profile")
    v.set_defaults(fn=cmd_validate)

    for name, fn in (("weekly", cmd_weekly), ("nightly", cmd_nightly)):
        s = sub.add_parser(name)
        s.add_argument("--entries", required=True)
        s.add_argument("--today")
        s.add_argument("--profile")
        if name == "weekly":
            s.add_argument("--out", default="out")
        s.set_defaults(fn=fn)

    s = sub.add_parser("sample")
    s.add_argument("--out", default="data/sample_entries.json")
    s.add_argument("--weeks", type=int, default=12)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--today")
    s.add_argument("--profile")
    s.set_defaults(fn=cmd_sample)

    g = sub.add_parser("page")
    g.add_argument("--profile")
    g.add_argument("--out")
    g.set_defaults(fn=cmd_page)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
