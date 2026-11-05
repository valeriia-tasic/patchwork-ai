"""Command line: python -m patchwork <command> ...

  init      Ask the first-use questions and write private/profile.json
  validate  [--profile PATH]   Check a profile; prints problems or "ok"
  weekly    --entries PATH [--today YYYY-MM-DD] [--output DIR] [--profile PATH]
            Writes report.txt, report.html, report.json, chart-overview.png, chart-areas.png
  nightly   --entries PATH [--today YYYY-MM-DD] [--profile PATH]
            Prints JSON: {"alerts": [...], "push": "...", "message": "..."}
  sample    [--output PATH] [--weeks N] [--seed N] [--profile PATH]
            Writes a synthetic log for a fictional toddler, following the profile
  page      [--profile PATH] [--output PATH]
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


def _today(date_string: str | None) -> date:
    """Parse an ISO date string or return today's date when no string is given.

    Used by every command that needs a reference date for metric windows.
    """
    return date.fromisoformat(date_string) if date_string else date.today()


def cmd_init(args) -> int:
    """Run the first-use questionnaire and write private/profile.json.

    Asks the parent about their body areas, creams, antihistamine, and allergens
    via the terminal, then saves the profile for all future commands.
    """
    target = Path(args.output)
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


def cmd_validate(args) -> int:
    """Validate a profile JSON file and print any problems, or 'ok'.

    Useful after editing rules.json or private/profile.json by hand.
    Exit code 1 when problems are found, 0 when the profile is valid.
    """
    profile_path = Path(args.profile) if args.profile else (PRIVATE_PROFILE if PRIVATE_PROFILE.exists() else ROOT / "rules.json")
    problems = validate(unwrap(json.loads(profile_path.read_text())))
    print("ok" if not problems else "\n".join(f"- {problem}" for problem in problems))
    return 0 if not problems else 1


def cmd_weekly(args) -> int:
    """Compute the weekly report, render it as text/HTML/JSON, and save the two charts.

    Output files go into --output (default: out/): report.txt, report.html, report.json,
    chart-overview.png, chart-areas.png. Prints a JSON summary on stdout for the agent.
    """
    profile = load_profile(args.profile)
    entries = load_entries(args.entries)
    today = _today(args.today)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    weekly_report = report.build_weekly(entries, profile, today)
    (output_dir / "report.txt").write_text(report.render_text(weekly_report))
    (output_dir / "report.html").write_text(report.render_html(weekly_report))
    (output_dir / "report.json").write_text(
        json.dumps({"subject": weekly_report.subject, **weekly_report.numbers}, default=str, indent=2)
    )
    charts.weekly_overview(entries, profile, today, output_dir / "chart-overview.png")
    charts.by_area(entries, profile, today, output_dir / "chart-areas.png")
    print(json.dumps({"subject": weekly_report.subject, "dir": str(output_dir)}))
    return 0


def cmd_nightly(args) -> int:
    """Run the nightly alert checks and print a JSON object for the agent.

    The JSON contains 'alerts' (list), 'push' (push-notification string), and
    'message' (multi-line body). The agent reads this and decides how to deliver it.
    """
    profile = load_profile(args.profile)
    found = alerts.nightly(load_entries(args.entries), profile, _today(args.today))
    lines = [alert.detail for alert in found]
    context_lines = found[0].context if found else []
    message = "\n".join(lines + (["Context:"] + context_lines if context_lines else []))
    print(json.dumps(
        {"alerts": [asdict(alert) for alert in found], "push": alerts.push_text(found), "message": message},
        indent=2,
    ))
    return 0


def cmd_sample(args) -> int:
    """Generate a synthetic log for a fictional toddler and write it to a JSON file.

    The sample follows the active profile and includes built-in patterns (travel week,
    sick week, allergen introduction) so any profile can be demoed without real data.
    """
    from .synthetic import generate
    data = generate(weeks=args.weeks, seed=args.seed, end=_today(args.today), profile=load_profile(args.profile))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(data, indent=1))
    print(f"wrote {len(data)} synthetic entries to {args.output}")
    return 0


def cmd_page(args) -> int:
    """Build the phone log page with the active profile baked in and write it to disk.

    Default profile → updates web/index.html in place. Private profile → writes to
    private/dist/index.html to keep real family config out of the public repo.
    """
    from .page import build
    output_path = build(args.profile, args.output)
    print(f"built {output_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and dispatch to the appropriate command function.

    Entry point for `python -m patchwork`. Returns an exit code (0 = success).
    """
    parser = argparse.ArgumentParser(prog="patchwork")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    init_subparser = subparsers.add_parser("init")
    init_subparser.add_argument("--output", default=str(PRIVATE_PROFILE))
    init_subparser.set_defaults(fn=cmd_init)

    validate_subparser = subparsers.add_parser("validate")
    validate_subparser.add_argument("--profile")
    validate_subparser.set_defaults(fn=cmd_validate)

    for name, handler_fn in (("weekly", cmd_weekly), ("nightly", cmd_nightly)):
        entry_subparser = subparsers.add_parser(name)
        entry_subparser.add_argument("--entries", required=True)
        entry_subparser.add_argument("--today")
        entry_subparser.add_argument("--profile")
        if name == "weekly":
            entry_subparser.add_argument("--output", default="output")
        entry_subparser.set_defaults(fn=handler_fn)

    sample_subparser = subparsers.add_parser("sample")
    sample_subparser.add_argument("--output", default="data/sample_entries.json")
    sample_subparser.add_argument("--weeks", type=int, default=12)
    sample_subparser.add_argument("--seed", type=int, default=7)
    sample_subparser.add_argument("--today")
    sample_subparser.add_argument("--profile")
    sample_subparser.set_defaults(fn=cmd_sample)

    page_subparser = subparsers.add_parser("page")
    page_subparser.add_argument("--profile")
    page_subparser.add_argument("--output")
    page_subparser.set_defaults(fn=cmd_page)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
