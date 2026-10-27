import copy
import json

from patchwork.rules import DEFAULT_PROFILE, validate


def test_full_body_covers_five_areas_not_face_or_diaper(profile):
    assert profile.categories_for("Entire body") == {"Arms", "Legs", "Stomach", "Back", "Neck"}
    assert "Face" not in profile.categories_for("full body")


def test_area_names_match_case_insensitively(profile):
    assert profile.categories_for(" diaper ") == {"Diaper"}


def test_sub_areas_roll_up(profile):
    assert profile.categories_for("shoulders") == {"Arms"}
    assert profile.categories_for("ankles") == {"Legs"}
    assert profile.categories_for("side") == {"Back"}


def test_unknown_areas_are_ignored(profile):
    assert profile.categories_for("left earlobe") == set()


def test_creams_from_profile(profile):
    steroid, face = profile.creams
    assert steroid.any_area and steroid.multi_area and steroid.max_days_per_area_per_week == 2
    assert face.areas == ("Face",) and not face.multi_area and face.schedule == "morning_night"
    assert profile.area_cream is steroid


def _raw():
    return json.loads(DEFAULT_PROFILE.read_text())


def test_default_profile_is_valid():
    assert validate(_raw()) == []


def test_validation_catches_mistakes():
    raw = copy.deepcopy(_raw())
    raw["areas"]["full_body"]["covers"].append("Tail")
    raw["creams"][1]["id"] = "anti"
    raw["creams"][0]["schedule"] = "hourly"
    raw["creams"][0]["limits"]["max_days_per_area_per_week"] = 9
    problems = " | ".join(validate(raw))
    assert "Tail" in problems and "reserved" in problems and "schedule" in problems and "1–7" in problems


def test_profile_exported_from_the_log_database_loads(tmp_path):
    from patchwork.rules import load_profile
    doc = tmp_path / "profile.json"
    doc.write_text(json.dumps({"id": "profile", "data": _raw(), "version": 3}))
    assert load_profile(doc).cream("steroid") is not None
