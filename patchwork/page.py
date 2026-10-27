"""Build the phone log page with a profile baked in.

`web/index.html` holds a PROFILE block. `python -m patchwork page` fills it from
the active profile. Only what the page needs is embedded: areas, creams,
antihistamine and allergens. Email, links and timezone stay out of the page.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .rules import DEFAULT_PROFILE, PRIVATE_PROFILE, ROOT, unwrap, validate

TEMPLATE = ROOT / "web" / "index.html"
BLOCK = re.compile(r"(const PROFILE=/\*PROFILE\*/)(.*?)(/\*END_PROFILE\*/;)", re.S)
PAGE_KEYS = ("areas", "creams", "antihistamine", "allergens", "averages")


def page_profile(raw: dict) -> dict:
    return {k: raw[k] for k in PAGE_KEYS if k in raw}


def embedded(text: str) -> dict | None:
    m = BLOCK.search(text)
    return json.loads(m.group(2)) if m else None


def build(profile_path: str | Path | None = None, out: str | Path | None = None) -> Path:
    """Default profile -> refresh web/index.html. Private profile -> private/dist/index.html."""
    src = Path(profile_path) if profile_path else (PRIVATE_PROFILE if PRIVATE_PROFILE.exists() else DEFAULT_PROFILE)
    raw = unwrap(json.loads(src.read_text()))
    problems = validate(raw)
    if problems:
        raise ValueError("Profile is not valid:\n- " + "\n- ".join(problems))
    is_default = src.resolve() == DEFAULT_PROFILE.resolve()
    target = Path(out) if out else (TEMPLATE if is_default else ROOT / "private" / "dist" / "index.html")
    text = TEMPLATE.read_text()
    if not BLOCK.search(text):
        raise ValueError("PROFILE block not found in web/index.html")
    blob = json.dumps(page_profile(raw), separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(BLOCK.sub(lambda m: m.group(1) + blob + m.group(3), text))
    return target
