from datetime import date

from patchwork import report

from .conftest import e

TODAY = date(2026, 3, 15)


def _log():
    return [
        e("steroid", "2026-03-03", "Diaper"), e("steroid", "2026-03-04", "Diaper"),
        e("steroid", "2026-03-10", "Entire body"), e("steroid", "2026-03-12", "Neck"),
        e("taci", "2026-03-11", "Face", slot="morning"), e("taci", "2026-03-12", "Face", slot="night"),
        e("anti", "2026-03-08"), e("anti", "2026-03-11"),
        e("flare", "2026-03-12", "Neck", note="after swimming"),
        e("allergen", "2026-03-13", allergen="Peanut", amount="one bite"),
    ]


def test_report_sections_follow_the_profile(profile):
    r = report.build_weekly(_log(), profile, TODAY)
    titles = [s.title for s in r.sections]
    assert titles == ["STEROID", "FACE CREAM (FACE)", "ANTIHISTAMINE", "FLARES", "ALLERGEN EXPOSURE"]
    assert r.subject == "Skin report — week of Mar 9"


def test_report_numbers(profile):
    r = report.build_weekly(_log(), profile, TODAY)
    steroid, face, anti, flares, allergen = (s.lines for s in r.sections)
    assert steroid[0] == "Total: 2 days this week (last week 2)"
    assert face[:2] == ["Total: 2 days this week (last week 0)", "Morning 1 · Night 1"]
    assert anti[0] == "Total: 1 day this week (last week 1)"
    assert "Neck (0 → 2)" in r.trends[1] and "Diaper (2 → 0)" in r.trends[2]
    assert flares[1] == "Comments: Mar 12: after swimming"
    assert allergen == ["Mar 13 — Peanut, one bite"]


def test_html_has_chart_slots_and_escapes_notes(profile):
    page = report.render_html(report.build_weekly(_log() + [e("note", "2026-03-13", note="<script>x</script>")],
                                                  profile, TODAY))
    assert report.CHART_1 in page and report.CHART_2 in page and "<script>" not in page
