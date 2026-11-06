from datetime import date

from patchwork import alerts

from .conftest import e

TODAY = date(2026, 3, 15)


def test_medication_over_limit_alerts(profile):
    found = alerts.check_medications([e("anti", "2026-03-13"), e("anti", "2026-03-15")], profile, TODAY)
    assert len(found) == 1 and "2 of last 3 days" in found[0].headline


def test_medication_within_limit_is_quiet(profile):
    log = [e("anti", d) for d in ("2026-03-09", "2026-03-12", "2026-03-15")]
    assert alerts.check_medications(log, profile, TODAY) == []


def test_cream_area_alert_names_area_and_cream(profile):
    log = [e("steroid", d, "Legs") for d in ("2026-03-10", "2026-03-12", "2026-03-14")]
    assert [a.headline for a in alerts.check_creams(log, profile, TODAY)] == ["Legs Steroid 3x this week"]


def test_quiet_night_has_no_alerts_and_no_push(profile):
    found = alerts.nightly([e("steroid", "2026-03-10", "Arms"), e("anti", "2026-03-11")], profile, TODAY)
    assert found == [] and alerts.push_text(found) == ""


def test_alert_keys_are_set(profile):
    log = [e("anti", "2026-03-14"), e("anti", "2026-03-15")]
    med_alerts = alerts.check_medications(log, profile, TODAY)
    assert len(med_alerts) == 1 and med_alerts[0].key == "medication:anti"

    cream_log = [e("steroid", d, "Legs") for d in ("2026-03-10", "2026-03-12", "2026-03-14")]
    cream_alerts = alerts.check_creams(cream_log, profile, TODAY)
    assert cream_alerts[0].key == "cream_area:steroid:Legs"


def test_filter_new_suppresses_already_sent_key(profile):
    log = [e("anti", "2026-03-14"), e("anti", "2026-03-15")]
    found = alerts.nightly(log, profile, TODAY)
    limit_alerts = [a for a in found if a.key == "medication:anti"]
    assert len(limit_alerts) == 1

    # Same key sent 3 days ago — suppressed
    sent = [{"key": "medication:anti", "date": "2026-03-12", "headline": "..."}]
    assert alerts.filter_new(limit_alerts, sent, TODAY) == []

    # Same key sent 7 days ago — no longer suppressed
    sent_old = [{"key": "medication:anti", "date": "2026-03-08", "headline": "..."}]
    assert alerts.filter_new(limit_alerts, sent_old, TODAY) == limit_alerts

    # Trend alerts (key="") always pass through regardless of sent history
    trend_alerts = [a for a in found if not a.key]
    assert alerts.filter_new(trend_alerts, sent, TODAY) == trend_alerts


def test_allergen_exposure_shows_up_as_context(profile):
    log = [e("anti", "2026-03-14"), e("anti", "2026-03-15"),
           e("allergen", "2026-03-13", allergen="Egg", amount="1/12 egg")]
    found = alerts.nightly(log, profile, TODAY)
    assert "Mar 13: allergen — Egg, 1/12 egg" in found[0].context
    assert alerts.push_text(found).startswith("Hey!")
