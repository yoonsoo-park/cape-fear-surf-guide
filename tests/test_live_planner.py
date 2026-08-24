from datetime import date, datetime, timezone

from surf.live_planner import plan_live, validate_live_request
from surf.live_sources import fetch_live_evidence
from surf.live_store import DynamoDbRecordStore, InMemoryRecordStore
from surf.schema import FreshnessState


class Response:
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): pass
    def json(self): return self.payload


class LiveSession:
    def __init__(self, *, hazard: bool = False): self.hazard = hazard
    def get(self, url, **kwargs):
        if url.endswith("/alerts/active"):
            features = [{"properties": {"event": "Beach Hazards Statement", "headline": "Dangerous surf", "expires": "2026-08-22T23:00:00+00:00"}}] if self.hazard else []
            return Response({"type": "FeatureCollection", "features": features})
        if "/zones/forecast/" in url:
            return Response({"type": "Feature", "properties": {"updated": "2026-08-22T00:00:00+00:00", "zone": "NCZ108", "periods": []}})
        if "tidesandcurrents" in url:
            return Response({"predictions": [{"t": "2026-08-22 03:15", "v": "0.958", "type": "H"}]})
        if "marine-api" in url:
            return Response({"hourly": {"time": ["2026-08-22T09:00"], "wave_height": [0.5], "wave_direction": [90], "wave_period": [8.0]}})
        if "open-meteo.com" in url:
            return Response({"hourly": {"time": ["2026-08-22T09:00"], "wind_speed_10m": [7.0], "precipitation_probability": [0], "weather_code": [1]}})
        raise AssertionError(url)


def test_live_request_is_limited_to_wrightsville_and_the_next_seven_local_dates():
    today = date(2026, 8, 22)
    assert validate_live_request("2026-08-21", {"skill_level": "beginner"}, None, None, today=today)[0] == "date_out_of_range"
    assert validate_live_request("2026-08-29", {"skill_level": "beginner"}, None, None, today=today)[0] == "date_out_of_range"
    assert validate_live_request("2026-08-22", {"skill_level": "beginner"}, "carolina-beach", None, today=today)[0] == "unsupported_area"
    assert validate_live_request("2026-08-28", {"skill_level": "beginner"}, "wrightsville-beach", "morning", today=today)[0] == date(2026, 8, 28)


def test_live_source_failure_becomes_unavailable_evidence_without_a_fixture_fallback():
    class BrokenSession:
        def get(self, *args, **kwargs):
            raise OSError("offline")

    evidence = fetch_live_evidence(date(2026, 8, 22), now=datetime(2026, 8, 22, tzinfo=timezone.utc), session=BrokenSession())
    kinds = {item.source_kind for item in evidence}
    assert {"nws_hazards", "nws_forecast", "noaa_tides", "marine_forecast", "nc_deq_water_quality"} <= kinds
    assert all(item.freshness_state == FreshnessState.unavailable for item in evidence)
    assert all("fixture" not in item.raw_reference for item in evidence)


def test_live_plan_fails_closed_when_a_required_source_is_unavailable():
    class BrokenSession:
        def get(self, *args, **kwargs):
            raise OSError("offline")

    result = plan_live(
        "2026-08-22", {"skill_level": "beginner", "ages": [12, 40]}, "wrightsville-beach", now=datetime(2026, 8, 22, tzinfo=timezone.utc),
        today=date(2026, 8, 22), fetcher=lambda requested, now: fetch_live_evidence(requested, now=now, session=BrokenSession()),
    )
    assert result.record.decision.state.value == "insufficient_data"
    assert len(result.record.window_id) == 32


def test_live_plan_normalizes_all_required_sources_and_applies_an_official_nws_veto():
    now = datetime(2026, 8, 22, tzinfo=timezone.utc)
    base = {"skill_level": "beginner", "ages": [12, 40]}
    normal = plan_live("2026-08-22", base, "wrightsville-beach", now=now, today=date(2026, 8, 22),
                       fetcher=lambda requested, now: fetch_live_evidence(requested, now=now, session=LiveSession()))
    hazard = plan_live("2026-08-22", base, "wrightsville-beach", now=now, today=date(2026, 8, 22),
                       fetcher=lambda requested, now: fetch_live_evidence(requested, now=now, session=LiveSession(hazard=True)))
    assert normal.record.decision.state.value == "recommended_window"
    assert {item.source_kind for item in normal.record.evidence} == {"nws_hazards", "nws_forecast", "noaa_tides", "marine_forecast", "nc_deq_water_quality"}
    assert next(item.facts["status"] for item in normal.record.evidence if item.source_kind == "nc_deq_water_quality") == "feed_unavailable"
    assert hazard.record.decision.state.value == "official_advisory_present"


def test_dynamodb_store_uses_only_window_id_payload_and_expiry_fields():
    class Client:
        def __init__(self): self.kwargs = None
        def put_item(self, **kwargs): self.kwargs = kwargs
        def get_item(self, **kwargs): return {"Item": {"window_id": {"S": "w"}, "expires_at": {"N": "5"}, "payload": {"S": "{\"ok\":true}"}}}

    client = Client()
    store = DynamoDbRecordStore("records", client=client)
    store.put("w", {"ok": True}, 5)
    assert client.kwargs == {"TableName": "records", "Item": {"window_id": {"S": "w"}, "expires_at": {"N": "5"}, "payload": {"S": "{\"ok\":true}"}}}
    assert store.get("w") == ({"ok": True}, 5)
    assert InMemoryRecordStore().get("missing") == (None, None)
