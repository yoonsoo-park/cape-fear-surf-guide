from datetime import datetime, timezone

from surf.sources.open_meteo import normalize_hourly_marine


def test_normalizes_open_meteo_hours_and_preserves_original_timezone():
    conditions = {"hours": [{"time": "2026-08-29T08:00", "wave_height_m": 0.7, "swell_period_s": 9.0}]}
    weather = {"hours": [{"time": "2026-08-29T08:00", "wind_kmh": 8.0}]}
    evidence = normalize_hourly_marine(
        conditions, weather, location="wrightsville-beach", timezone_name="America/New_York",
        retrieved_at=datetime(2026, 8, 29, 10, tzinfo=timezone.utc),
    )
    assert evidence[0].valid_from.isoformat() == "2026-08-29T08:00:00-04:00"
    assert evidence[0].original_timezone == "America/New_York"
    assert evidence[0].facts["wave_height_m"] == 0.7
