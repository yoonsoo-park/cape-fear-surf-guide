from datetime import datetime, timezone
from pathlib import Path

from surf.sources.nws import (
    capture_active_alerts,
    capture_zone_forecast,
    fetch_active_alerts,
    fetch_point,
    fetch_zone_forecast,
    replay_active_alerts,
    replay_zone_forecast,
)


class Response:
    def raise_for_status(self): return None
    def json(self): return {"ok": True}


class Session:
    def __init__(self): self.calls = []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response()


def test_nws_point_contract_uses_identity_header_and_exact_url():
    session = Session()
    assert fetch_point(34.2085, -77.7964, "cape-fear-surf-guide contact@example.com", session) == {"ok": True}
    url, options = session.calls[0]
    assert url == "https://api.weather.gov/points/34.2085,-77.7964"
    assert options["headers"]["User-Agent"].startswith("cape-fear-surf-guide")
    assert options["timeout"] == 15


def test_nws_contract_accepts_a_public_url_contact_route():
    assert fetch_point(34.2085, -77.7964, "cape-fear-surf-guide/0.1 https://github.com/yoonsoo-park/cape-fear-surf-guide", Session()) == {"ok": True}


def test_nws_alert_contract_scopes_the_zone():
    session = Session()
    fetch_active_alerts("NCZ106", "cape-fear-surf-guide contact@example.com", session)
    assert session.calls[0][1]["params"] == {"zone": "NCZ106"}


def test_nws_forecast_contract_scopes_the_zone_path():
    session = Session()
    assert fetch_zone_forecast("NCZ108", "cape-fear-surf-guide contact@example.com", session) == {"ok": True}
    assert session.calls[0][0] == "https://api.weather.gov/zones/forecast/NCZ108/forecast"


def test_nws_alert_capture_replays_without_a_network_session(tmp_path):
    output = tmp_path / "nws-alerts.json"
    captured = capture_active_alerts(
        "NCZ106", "cape-fear-surf-guide contact@example.com", output, Session(),
        captured_at=datetime(2026, 8, 22, 12, tzinfo=timezone.utc),
    )
    assert captured["zone"] == "NCZ106"
    assert output.exists()
    assert replay_active_alerts(output) == {"ok": True}


def test_reviewed_live_nws_capture_replays_offline():
    response = replay_active_alerts(Path("fixtures/captured/nws-alerts-NCZ108-2026-08-22.json"))
    assert response["type"] == "FeatureCollection"


def test_nws_forecast_capture_replays_without_a_network_session(tmp_path):
    output = tmp_path / "nws-forecast.json"
    capture_zone_forecast(
        "NCZ108", "cape-fear-surf-guide contact@example.com", output, Session(),
        captured_at=datetime(2026, 8, 22, 12, tzinfo=timezone.utc),
    )
    assert replay_zone_forecast(output) == {"ok": True}


def test_reviewed_live_nws_forecast_capture_replays_offline():
    response = replay_zone_forecast(Path("fixtures/captured/nws-zone-forecast-NCZ108-2026-08-22.json"))
    assert response["type"] == "Feature"
    assert len(response["properties"]["periods"]) == 10
