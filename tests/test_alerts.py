from datetime import date

from patchwork import alerts

from .conftest import e

TODAY = date(2026, 3, 15)


def test_antihistamine_twice_in_three_days_alerts(profile):
    a = alerts.check_antihistamine([e("anti", "2026-03-13"), e("anti", "2026-03-15")], profile, TODAY)
    assert a is not None and "2 of last 3 days" in a.headline


def test_antihistamine_every_third_day_is_quiet(profile):
    log = [e("anti", d) for d in ("2026-03-09", "2026-03-12", "2026-03-15")]
    assert alerts.check_antihistamine(log, profile, TODAY) is None


def test_cream_area_alert_names_area_and_cream(profile):
    log = [e("steroid", d, "Legs") for d in ("2026-03-10", "2026-03-12", "2026-03-14")]
    assert [a.headline for a in alerts.check_creams(log, profile, TODAY)] == ["Legs Steroid 3x this week"]


def test_quiet_night_has_no_alerts_and_no_push(profile):
    found = alerts.nightly([e("steroid", "2026-03-10", "Arms"), e("anti", "2026-03-11")], profile, TODAY)
    assert found == [] and alerts.push_text(found) == ""


def test_allergen_exposure_shows_up_as_context(profile):
    log = [e("anti", "2026-03-14"), e("anti", "2026-03-15"),
           e("allergen", "2026-03-13", allergen="Egg", amount="1/12 egg")]
    found = alerts.nightly(log, profile, TODAY)
    assert "Mar 13: allergen — Egg, 1/12 egg" in found[0].context
    assert alerts.push_text(found).startswith("Hey!")
