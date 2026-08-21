from surf.tools.signals import fetch_surf_conditions, fetch_weather


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Session:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        return Response(self.payload)


def test_fetch_surf_conditions_reshapes_hourly_arrays():
    session = Session({"hourly": {"time": ["2026-08-22T08:00"], "wave_height": [1.0],
                                  "wave_period": [8.0], "swell_wave_height": [0.8],
                                  "swell_wave_period": [10.0]}})
    result = fetch_surf_conditions(33.7, -118.1, "2026-08-22", "America/Los_Angeles", session)
    assert result["hours"] == [{"time": "2026-08-22T08:00", "wave_height_m": 1.0,
                                "wave_period_s": 8.0, "swell_height_m": 0.8, "swell_period_s": 10.0}]
    assert session.calls[0][2] == 15


def test_fetch_weather_reshapes_hourly_arrays():
    session = Session({"hourly": {"time": ["2026-08-22T08:00"], "temperature_2m": [19.0],
                                  "wind_speed_10m": [12.0], "wind_gusts_10m": [22.0]}})
    result = fetch_weather(33.7, -118.1, "2026-08-22", "America/Los_Angeles", session)
    assert result["hours"][0]["gust_kmh"] == 22.0


def test_rejects_misaligned_arrays():
    session = Session({"hourly": {"time": ["2026-08-22T08:00"], "temperature_2m": [],
                                  "wind_speed_10m": [12.0], "wind_gusts_10m": [22.0]}})
    try:
        fetch_weather(33.7, -118.1, "2026-08-22", "America/Los_Angeles", session)
    except ValueError as error:
        assert "misaligned" in str(error)
    else:
        raise AssertionError("expected ValueError")
