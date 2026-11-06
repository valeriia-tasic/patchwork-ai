from datetime import date

from patchwork import metrics as m

from .conftest import e

TODAY = date(2026, 3, 15)  # a Sunday
WEEK = m.rolling_week(TODAY)


def test_rolling_week_is_seven_days_inclusive():
    assert (WEEK.start, WEEK.end) == (date(2026, 3, 9), date(2026, 3, 15))


def test_calendar_weeks_start_on_monday():
    weeks = m.calendar_weeks(date(2026, 3, 11), 2)
    assert [w.start.weekday() for w in weeks] == [0, 0]


def test_several_entries_on_one_day_count_once():
    log = [e("anti", "2026-03-10"), e("anti", "2026-03-10"), e("anti", "2026-03-12")]
    assert len(m.days_of(log, "anti", WEEK)) == 2


def test_avg_per_treated_area_example_from_design(profile):
    steroid = profile.cream("steroid")
    log = [e("steroid", "2026-03-10", "Legs"), e("steroid", "2026-03-12", "Legs", "Arms")]
    counts = m.area_counts(log, profile, steroid, WEEK)
    assert counts["Legs"] == 2 and counts["Arms"] == 1
    assert m.avg_per_treated_area(counts) == 1.5


def test_morning_and_night_same_day_count_once_toward_limits(profile):
    face = profile.cream("taci")
    log = [e("taci", "2026-03-10", "Face", slot="morning"), e("taci", "2026-03-10", "Face", slot="night")]
    assert m.area_counts(log, profile, face, WEEK)["Face"] == 1
    assert m.slot_counts(log, face, WEEK) == {"morning": 1, "night": 1}


def test_single_area_cream_logged_without_areas_counts_on_its_area(profile):
    face = profile.cream("taci")
    assert m.area_counts([e("taci", "2026-03-10")], profile, face, WEEK)["Face"] == 1


def test_full_body_day_counts_for_each_covered_area(profile):
    steroid = profile.cream("steroid")
    log = [e("steroid", "2026-03-10", "Entire body"), e("steroid", "2026-03-11", "Arms")]
    counts = m.area_counts(log, profile, steroid, WEEK)
    assert counts["Arms"] == 2 and counts["Neck"] == 1 and counts["Face"] == 0


def test_area_over_limit_needs_more_than_the_limit(profile):
    steroid = profile.cream("steroid")
    two = [e("steroid", d, "Arms") for d in ("2026-03-10", "2026-03-12")]
    three = two + [e("steroid", "2026-03-14", "shoulders")]
    assert m.areas_over_limit(two, profile, steroid, WEEK) == []
    assert [(a, n) for a, n, _ in m.areas_over_limit(three, profile, steroid, WEEK)] == [("Arms", 3)]


def test_medication_gap_includes_dose_before_the_week():
    log = [e("anti", "2026-03-06"), e("anti", "2026-03-09"), e("anti", "2026-03-11")]
    assert m.medication_gap(log, "anti", WEEK) == 2.5
    assert m.describe_gap(2.5, 2) == "every 2.5 days"


def test_describe_gap_wording():
    assert m.describe_gap(None, 0) == "none this week"
    assert m.describe_gap(1.0, 7) == "daily"
    assert m.describe_gap(2.1, 3) == "every second day"


def test_rolling_average_uses_logged_span_when_log_is_young(profile):
    steroid = profile.cream("steroid")
    log = [e("steroid", "2026-03-02", "Arms"), e("steroid", "2026-03-10", "Arms")]
    assert m.rolling_area_average(log, profile, steroid, TODAY)["Arms"] == 1.0
