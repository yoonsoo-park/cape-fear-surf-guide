from surf.tools.inventory import availability_for_day, load_seed


def test_availability_excludes_existing_booking():
    result = availability_for_day("2026-08-22", load_seed())
    assert not any(slot["time"] == "09:00" and slot["instructor"] == "Maya" for slot in result["slots"])
    assert any(slot["time"] == "08:00" and slot["instructor"] == "Maya" for slot in result["slots"])


def test_pricing_has_base_and_floor_for_every_level():
    pricing = load_seed()["pricing"]
    assert set(pricing) == {"beginner", "intermediate", "advanced"}
    assert all(value["base_price"] >= value["min_price"] for value in pricing.values())
