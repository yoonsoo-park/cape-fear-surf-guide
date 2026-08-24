"""Small, bounded live-source adapters for the public Wrightsville MCP path."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests

from .locations import BEACHES, BeachLocation
from .schema import EvidenceItem, FreshnessState
from .sources.nws import fetch_active_alerts, fetch_zone_forecast

NWS_USER_AGENT = "cape-fear-surf-guide/0.1 https://github.com/yoonsoo-park/cape-fear-surf-guide"
NOAA_TIDES_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
OPEN_METEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
OPEN_METEO_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
DEQ_RECREATIONAL_WATER_URL = "https://www.deq.nc.gov/about/divisions/water-resources/water-resources-data/water-quality-programs/recreational-water-quality"
SOURCE_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class SourceFailure:
    source_kind: str
    source_name: str
    source_url: str
    reason: str


def _parse_source_time(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return fallback
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _window_bounds(day: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=zone)
    return start, start + timedelta(days=1) - timedelta(microseconds=1)


def _nws_url(path: str) -> str:
    return f"https://api.weather.gov{path}"


def fetch_nws(location: BeachLocation, day: date, retrieved_at: datetime, *, session: Any = requests) -> tuple[EvidenceItem, EvidenceItem]:
    """Fetch both required NWS signals as one source category."""
    if not location.nws_zone:
        raise ValueError("Wrightsville Beach requires a verified NWS zone")
    alerts = fetch_active_alerts(location.nws_zone, NWS_USER_AGENT, session, timeout=SOURCE_TIMEOUT_SECONDS)
    forecast = fetch_zone_forecast(location.nws_zone, NWS_USER_AGENT, session, timeout=SOURCE_TIMEOUT_SECONDS)
    zone = ZoneInfo(location.timezone)
    starts, ends = _window_bounds(day, zone)
    active = [feature for feature in alerts.get("features", []) if isinstance(feature, dict)]
    active_hazard = bool(active)
    alert_properties = [feature.get("properties", {}) for feature in active]
    issued = min((_parse_source_time(item.get("sent"), retrieved_at) for item in alert_properties), default=retrieved_at)
    alert_until = max((_parse_source_time(item.get("expires"), ends) for item in alert_properties), default=ends)
    hazards = EvidenceItem(
        source_name="National Weather Service active alerts",
        source_url=f"{_nws_url('/alerts/active')}?zone={location.nws_zone}",
        source_kind="nws_hazards",
        issued_at=issued,
        valid_from=starts,
        valid_until=max(alert_until, ends),
        retrieved_at=retrieved_at,
        location=location.id,
        facts={
            "active_official_hazard": active_hazard,
            "alert_count": len(active),
            "alerts": [
                {"event": item.get("event"), "headline": item.get("headline"), "expires": item.get("expires")}
                for item in alert_properties
            ],
        },
        freshness_state=FreshnessState.current,
        original_timezone="UTC",
        raw_reference=f"nws-active-alerts:{location.nws_zone}:{retrieved_at.isoformat()}",
    )
    forecast_properties = forecast.get("properties", {})
    forecast_item = EvidenceItem(
        source_name="National Weather Service forecast zone",
        source_url=_nws_url(f"/zones/forecast/{location.nws_zone}/forecast"),
        source_kind="nws_forecast",
        issued_at=_parse_source_time(forecast_properties.get("updated"), retrieved_at),
        valid_from=starts,
        valid_until=ends,
        retrieved_at=retrieved_at,
        location=location.id,
        facts={"periods": forecast_properties.get("periods", []), "zone": forecast_properties.get("zone")},
        freshness_state=FreshnessState.current,
        original_timezone="UTC",
        raw_reference=f"nws-zone-forecast:{location.nws_zone}:{retrieved_at.isoformat()}",
    )
    return hazards, forecast_item


def fetch_noaa_tides(location: BeachLocation, day: date, retrieved_at: datetime, *, session: Any = requests) -> EvidenceItem:
    if not location.noaa_station:
        raise ValueError("Wrightsville Beach requires a verified NOAA station")
    params = {
        "product": "predictions", "application": "cape-fear-surf-guide", "begin_date": day.strftime("%Y%m%d"),
        "end_date": day.strftime("%Y%m%d"), "datum": "MLLW", "station": location.noaa_station,
        "time_zone": "lst_ldt", "units": "metric", "interval": "hilo", "format": "json",
    }
    response = session.get(NOAA_TIDES_URL, params=params, timeout=SOURCE_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload.get("predictions"), list):
        raise ValueError("NOAA tide response does not contain predictions")
    zone = ZoneInfo(location.timezone)
    starts, ends = _window_bounds(day, zone)
    return EvidenceItem(
        source_name="NOAA Tides and Currents",
        source_url=f"{NOAA_TIDES_URL}?{urlencode(params)}",
        source_kind="noaa_tides",
        issued_at=retrieved_at,
        valid_from=starts,
        valid_until=ends,
        retrieved_at=retrieved_at,
        location=location.id,
        facts={"station": location.noaa_station, "station_reason": location.noaa_station_reason, "predictions": payload["predictions"]},
        freshness_state=FreshnessState.current,
        original_timezone=location.timezone,
        raw_reference=f"noaa-tides:{location.noaa_station}:{day.isoformat()}:{retrieved_at.isoformat()}",
    )


def fetch_open_meteo(location: BeachLocation, day: date, retrieved_at: datetime, *, session: Any = requests) -> EvidenceItem:
    common = {"latitude": location.latitude, "longitude": location.longitude, "timezone": location.timezone, "forecast_days": 7}
    marine_response = session.get(OPEN_METEO_MARINE_URL, params={**common, "hourly": "wave_height,wave_direction,wave_period"}, timeout=SOURCE_TIMEOUT_SECONDS)
    weather_response = session.get(OPEN_METEO_WEATHER_URL, params={**common, "hourly": "wind_speed_10m,precipitation_probability,weather_code"}, timeout=SOURCE_TIMEOUT_SECONDS)
    marine_response.raise_for_status()
    weather_response.raise_for_status()
    marine, weather = marine_response.json(), weather_response.json()
    marine_hourly, weather_hourly = marine.get("hourly"), weather.get("hourly")
    if not isinstance(marine_hourly, dict) or not isinstance(weather_hourly, dict):
        raise ValueError("Open-Meteo response does not contain hourly forecasts")
    times = marine_hourly.get("time")
    if not isinstance(times, list) or not times or times != weather_hourly.get("time"):
        raise ValueError("Open-Meteo marine and weather hours do not align")
    by_time = {
        value: {
            "wave_height_m": marine_hourly.get("wave_height", [None] * len(times))[index],
            "wave_direction": marine_hourly.get("wave_direction", [None] * len(times))[index],
            "swell_period_s": marine_hourly.get("wave_period", [None] * len(times))[index],
            "wind_kmh": weather_hourly.get("wind_speed_10m", [None] * len(times))[index],
            "precipitation_probability": weather_hourly.get("precipitation_probability", [None] * len(times))[index],
            "weather_code": weather_hourly.get("weather_code", [None] * len(times))[index],
        }
        for index, value in enumerate(times)
    }
    zone = ZoneInfo(location.timezone)
    starts, ends = _window_bounds(day, zone)
    matching_hours = {key: value for key, value in by_time.items() if key.startswith(day.isoformat())}
    if not matching_hours:
        raise ValueError("Open-Meteo response does not cover the requested date")
    return EvidenceItem(
        source_name="Open-Meteo Marine and Weather",
        source_url=f"{OPEN_METEO_MARINE_URL}?{urlencode({**common, 'hourly': 'wave_height,wave_direction,wave_period'})}",
        source_kind="marine_forecast",
        issued_at=retrieved_at,
        valid_from=starts,
        valid_until=ends,
        retrieved_at=retrieved_at,
        location=location.id,
        facts={"hours": matching_hours, "weather_source_url": f"{OPEN_METEO_WEATHER_URL}?{urlencode({**common, 'hourly': 'wind_speed_10m,precipitation_probability,weather_code'})}"},
        freshness_state=FreshnessState.current,
        original_timezone=location.timezone,
        raw_reference=f"open-meteo:{location.id}:{day.isoformat()}:{retrieved_at.isoformat()}",
    )


def unverified_deq_status(location: BeachLocation, day: date, retrieved_at: datetime) -> EvidenceItem:
    """Expose the official direct-check link without treating absence as safety evidence."""
    zone = ZoneInfo(location.timezone)
    starts, ends = _window_bounds(day, zone)
    return EvidenceItem(
        source_name="NC DEQ recreational water quality",
        source_url=DEQ_RECREATIONAL_WATER_URL,
        source_kind="nc_deq_water_quality",
        issued_at=retrieved_at,
        valid_from=starts,
        valid_until=ends,
        retrieved_at=retrieved_at,
        location=location.id,
        facts={"status": "feed_unavailable", "mapping_status": "unverified", "reason": location.deq_site_reason},
        freshness_state=FreshnessState.unavailable,
        original_timezone=location.timezone,
        raw_reference=f"nc-deq-unverified:{location.id}:{day.isoformat()}",
    )


def fetch_live_evidence(day: date, *, now: datetime | None = None, session: Any = requests) -> tuple[EvidenceItem, ...]:
    """Fetch the three source categories concurrently, with no source cache or fixture fallback."""
    retrieved_at = now or datetime.now(timezone.utc)
    if retrieved_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    location = BEACHES["wrightsville-beach"]
    tasks: dict[Any, tuple[str, str, str]] = {}
    evidence: list[EvidenceItem] = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        tasks[executor.submit(fetch_nws, location, day, retrieved_at, session=session)] = ("nws_hazards", "National Weather Service", _nws_url("/"))
        tasks[executor.submit(fetch_noaa_tides, location, day, retrieved_at, session=session)] = ("noaa_tides", "NOAA Tides and Currents", NOAA_TIDES_URL)
        tasks[executor.submit(fetch_open_meteo, location, day, retrieved_at, session=session)] = ("marine_forecast", "Open-Meteo Marine and Weather", OPEN_METEO_MARINE_URL)
        for task in as_completed(tasks):
            source_kind, source_name, source_url = tasks[task]
            try:
                value = task.result()
                evidence.extend(value if isinstance(value, tuple) else (value,))
            except Exception as error:  # public boundary returns no provider internals
                evidence.append(_unavailable_evidence(source_kind, source_name, source_url, location, day, retrieved_at, type(error).__name__))
                if source_kind == "nws_hazards":
                    evidence.append(_unavailable_evidence("nws_forecast", "National Weather Service forecast zone", source_url, location, day, retrieved_at, type(error).__name__))
    evidence.append(unverified_deq_status(location, day, retrieved_at))
    return tuple(sorted(evidence, key=lambda item: item.source_kind))


def _unavailable_evidence(source_kind: str, source_name: str, source_url: str, location: BeachLocation, day: date,
                          retrieved_at: datetime, reason: str) -> EvidenceItem:
    starts, ends = _window_bounds(day, ZoneInfo(location.timezone))
    return EvidenceItem(
        source_name=source_name, source_url=source_url, source_kind=source_kind,
        issued_at=retrieved_at, valid_from=starts, valid_until=ends, retrieved_at=retrieved_at,
        location=location.id, facts={"retrieval_error": reason}, freshness_state=FreshnessState.unavailable,
        original_timezone=location.timezone, raw_reference=f"unavailable:{source_kind}:{retrieved_at.isoformat()}",
    )
