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
PAGE_KEYS = ("areas", "creams", "medications", "antihistamine", "allergens", "averages")


def page_profile(raw: dict) -> dict:
    """Extract only the keys the page needs from a full profile dict.

    Keeps areas, creams, antihistamine, allergens, and averages; strips delivery
    settings (email, timezone, log_url) so they never appear in the public page.
    Used by build to produce the JSON blob embedded in index.html.
    """
    return {key: raw[key] for key in PAGE_KEYS if key in raw}


def embedded(text: str) -> dict | None:
    """Parse and return the PROFILE object currently embedded in an index.html string.

    Returns None when no PROFILE block is found. Used in tests to verify that build
    round-trips the profile correctly.
    """
    block_match = BLOCK.search(text)
    return json.loads(block_match.group(2)) if block_match else None


def build(profile_path: str | Path | None = None, out: str | Path | None = None) -> Path:
    """Embed the active profile into the log page template and write it to disk.

    Default profile → refreshes web/index.html in place.
    Private profile → writes to private/dist/index.html to keep family config out
    of the public repo.
    Called by cmd_page after the parent runs `python -m patchwork page`.
    """
    source_path = Path(profile_path) if profile_path else (PRIVATE_PROFILE if PRIVATE_PROFILE.exists() else DEFAULT_PROFILE)
    raw = unwrap(json.loads(source_path.read_text()))
    problems = validate(raw)
    if problems:
        raise ValueError("Profile is not valid:\n- " + "\n- ".join(problems))
    is_default = source_path.resolve() == DEFAULT_PROFILE.resolve()
    target = Path(out) if out else (TEMPLATE if is_default else ROOT / "private" / "dist" / "index.html")
    template_text = TEMPLATE.read_text()
    if not BLOCK.search(template_text):
        raise ValueError("PROFILE block not found in web/index.html")
    profile_blob = json.dumps(page_profile(raw), separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(BLOCK.sub(lambda match: match.group(1) + profile_blob + match.group(3), template_text))
    return target
