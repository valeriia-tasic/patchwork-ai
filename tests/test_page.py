import json

from patchwork import page
from patchwork.rules import DEFAULT_PROFILE, ROOT


def test_log_page_embeds_the_default_profile():
    embedded = page.embedded((ROOT / "web" / "index.html").read_text())
    assert embedded is not None, "PROFILE block missing from web/index.html"
    assert embedded == page.page_profile(json.loads(DEFAULT_PROFILE.read_text())), (
        "web/index.html is out of date — run: python -m patchwork page --profile rules.json")


def test_page_never_embeds_delivery_details():
    raw = json.loads(DEFAULT_PROFILE.read_text())
    raw["delivery"]["email"] = "someone@example.com"
    assert "delivery" not in page.page_profile(raw)
