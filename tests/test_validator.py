import json

from surf.validator import extract_json, validate_recommendation


def snapshot(swell=0.8, gust=20.0):
    return {
        "conditions": {"hours": [{"time": "2026-08-22T09:00", "swell_height_m": swell}]},
        "weather": {"hours": [{"time": "2026-08-22T09:00", "gust_kmh": gust}]},
    }


def recommendation(**overrides):
    slot = {"time": "09:00", "level": "beginner", "instructor": "Maya",
            "swell_height_m": 0.8, "gust_kmh": 20.0, "price": 95, "min_price": 75}
    slot.update(overrides)
    return json.dumps({"slots": [slot], "safety_note": "checked", "evidence_summary": "observed"})


def test_extracts_nested_json_from_surrounding_text():
    parsed = extract_json(f"prefix\n```json\n{recommendation()}\n```\nsuffix")
    assert parsed["slots"][0]["instructor"] == "Maya"


def test_flags_beginner_safety_violation_using_snapshot_not_claimed_values():
    result = validate_recommendation(recommendation(swell_height_m=0.8), snapshot(swell=1.8))
    assert {item["type"] for item in result["violations"]} == {"beginner_safety", "measurement_mismatch"}


def test_flags_price_floor_violation():
    result = validate_recommendation(recommendation(price=70), snapshot())
    assert any(item["type"] == "price_floor" for item in result["violations"])


def test_boundary_values_are_allowed():
    result = validate_recommendation(recommendation(swell_height_m=1.2, gust_kmh=30.0), snapshot(1.2, 30.0))
    assert result["violations"] == []


def test_accepts_level_price_maps_observed_in_baseline():
    value = recommendation(
        level=["beginner", "intermediate"],
        price={"beginner": 95, "intermediate": 115},
        min_price={"beginner": 75, "intermediate": 90},
    )
    result = validate_recommendation(value, snapshot())
    assert result["schema_variant"] == "flat-list"
    assert result["slot_count"] == 2
    assert result["violations"] == []


def test_accepts_nested_approved_slots_observed_in_high_swell_run():
    value = json.dumps({"slots": {"approved_slots": [{
        "time": "09:00", "instructor": "Maya", "swell_height_m": 1.8, "gust_kmh": 20.0,
        "levels_offered": [{"level": "intermediate", "price": 115, "min_price": 90}],
    }]}})
    result = validate_recommendation(value, snapshot(swell=1.8))
    assert result["schema_variant"] == "nested-approved-slots"
    assert result["violations"] == []
