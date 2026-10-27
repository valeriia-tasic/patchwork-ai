"""Fails the build if personal data slips into files that would be published.

Checks every file git tracks (or would track) outside private/. Generic patterns run
everywhere; an optional private/denylist.txt adds your own terms (names, places,
links) without publishing the list itself.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "private", "out", "__pycache__", ".pytest_cache", ".venv", "venv"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".html", ".txt", ".yml", ".yaml", ".toml", ".cfg", ".js", ".css", ""}

GENERIC = [
    (re.compile(r"[A-Za-z0-9._%+-]+@(?!example\.com|users\.noreply\.github\.com)[A-Za-z0-9.-]+\.[a-z]{2,}"),
     "email address"),
    (re.compile(r"claude\.ai/(?:code/)?artifact/[A-Za-z0-9-]{8,}"), "link to a real artifact"),
    (re.compile(r"trig_[A-Za-z0-9]{10,}"), "scheduled task id"),
]


def _files():
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        paths = [ROOT / p for p in out]
    except (subprocess.CalledProcessError, FileNotFoundError):
        paths = [p for p in ROOT.rglob("*") if p.is_file()]
    for p in paths:
        rel = p.relative_to(ROOT)
        if p.is_file() and not (set(rel.parts) & SKIP_DIRS) and p.suffix in TEXT_SUFFIXES:
            yield p


def _denylist():
    f = ROOT / "private" / "denylist.txt"
    if not f.exists():
        return []
    terms = [t.strip() for t in f.read_text().splitlines() if t.strip() and not t.startswith("#")]
    return [(re.compile(re.escape(t), re.IGNORECASE), f"private term '{t[:3]}…'") for t in terms]


def test_no_personal_data_in_published_files():
    checks = GENERIC + _denylist()
    problems = []
    for path in _files():
        if path.name == "test_privacy.py":
            continue
        text = path.read_text(errors="ignore")
        for pattern, what in checks:
            if pattern.search(text):
                problems.append(f"{path.relative_to(ROOT)}: {what}")
    assert not problems, "Personal data found:\n" + "\n".join(problems)


def test_private_folder_is_gitignored():
    assert "private/" in (ROOT / ".gitignore").read_text()
