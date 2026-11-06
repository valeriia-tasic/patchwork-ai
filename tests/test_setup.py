"""The first-use questionnaire, driven by scripted answers."""

from datetime import date

from patchwork import alerts, setup
from patchwork.data import Entry
from patchwork.rules import profile_from_dict, validate


def answers(*replies):
    it = iter(replies)
    return lambda prompt: next(it)


def test_new_family_with_two_creams_and_allergens():
    p = setup.run(answers(
        "Arms, Legs, Torso, Face",          # areas
        "elbows=Arms, ankles=Legs, tail=X",  # sub-areas (last one ignored)
        "",                                  # full body -> suggested (all but Face)
        "Hydrocortisone", "any", "d", "3", "",   # cream 1: any area, daily, 3/area/week, no total
        "Protopic", "Face", "m", "",             # cream 2: face only, morning/night, no total (no per-area q)
        "",                                      # done with creams
        "y", "Claritin", "2", "7",               # antihistamine
        "y", "Kiwi",                             # allergens + extra
        "", "", "", "",                          # delivery defaults
    ), say=lambda s: None)
    assert validate(p) == []
    assert p["areas"]["full_body"]["covers"] == ["Arms", "Legs", "Torso"]
    aliases = p["areas"]["aliases"]
    assert aliases["elbows"] == "Arms" and aliases["ankles"] == "Legs"   # parent-entered
    assert "tail" not in aliases                                          # invalid entry dropped
    assert "side" not in aliases                                          # Back not in this family's areas
    hc, pr = p["creams"]
    assert hc == {**hc, "id": "hydrocortisone", "areas": "any", "schedule": "daily",
                  "limits": {"max_days_per_area_per_week": 3, "max_days_per_week": None}}
    assert pr["areas"] == ["Face"] and pr["schedule"] == "morning_night"
    assert p["antihistamine"]["brand"] == "Claritin" and p["antihistamine"]["limit"] == {"max_doses": 2, "window_days": 7}
    assert p["allergens"]["list"][-1] == "Kiwi" and len(p["allergens"]["list"]) == 10


def test_questionnaire_reproduces_the_original_setup():
    """Answering as the first family did must rebuild the rules Patchwork was designed with."""
    p = setup.run(answers(
        "",
        "shoulders=Arms, side=Back, ankles=Legs",
        "Arms, Legs, Stomach, Back, Neck",
        "Steroid", "any", "d", "2", "",
        "Taci", "Face", "d", "",
        "",
        "y", "Zyrtec", "1", "3",
        "y", "",
        "", "", "", "",
    ), say=lambda s: None)
    prof = profile_from_dict(p)
    assert prof.categories_for("Entire body") == {"Arms", "Legs", "Stomach", "Back", "Neck"}
    assert prof.categories_for("shoulders") == {"Arms"}
    steroid, taci = prof.creams
    assert (steroid.id, steroid.max_days_per_area_per_week, steroid.multi_area) == ("steroid", 2, True)
    assert (taci.id, taci.areas, taci.schedule) == ("taci", ("Face",), "daily")
    # Entries logged before the questionnaire existed still work unchanged.
    log = [Entry("steroid", date(2026, 10, d), ("Arms",)) for d in (20, 22, 24)]
    assert [a.headline for a in alerts.check_creams(log, prof, date(2026, 10, 25))] == ["Arms Steroid 3x this week"]



def test_limits_are_framed_as_the_parents_thresholds():
    assert "doctor" in setup.LIMIT_NOTE and "does not recommend" in setup.LIMIT_NOTE
