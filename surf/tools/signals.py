from __future__ import annotations

from typing import Any

import requests
from strands import ToolContext, tool


MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def _get(url: str, params: dict[str, Any], session: Any = requests) -> dict[str, Any]:
    response = session.get(url, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_surf_conditions(latitude: float, longitude: float, day: str, timezone: str, session: Any = requests) -> dict:
    payload = _get(MARINE_URL, {
        "latitude": latitude, "longitude": longitude,
        "hourly": "wave_height,wave_period,swell_wave_height,swell_wave_period",
        "start_date": day, "end_date": day, "timezone": timezone,
    }, session)
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    required = ["wave_height", "wave_period", "swell_wave_height", "swell_wave_period"]
    if not times or any(len(hourly.get(field, [])) != len(times) for field in required):
        raise ValueError("marine response has missing or misaligned hourly arrays")
    return {"source": "open-meteo-marine", "hours": [
        {"time": times[i], "wave_height_m": hourly["wave_height"][i],
         "wave_period_s": hourly["wave_period"][i], "swell_height_m": hourly["swell_wave_height"][i],
         "swell_period_s": hourly["swell_wave_period"][i]}
        for i in range(len(times))
    ]}


def fetch_weather(latitude: float, longitude: float, day: str, timezone: str, session: Any = requests) -> dict:
    payload = _get(WEATHER_URL, {
        "latitude": latitude, "longitude": longitude,
        "hourly": "temperature_2m,wind_speed_10m,wind_gusts_10m",
        "start_date": day, "end_date": day, "timezone": timezone,
    }, session)
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    required = ["temperature_2m", "wind_speed_10m", "wind_gusts_10m"]
    if not times or any(len(hourly.get(field, [])) != len(times) for field in required):
        raise ValueError("weather response has missing or misaligned hourly arrays")
    return {"source": "open-meteo-weather", "hours": [
        {"time": times[i], "temperature_c": hourly["temperature_2m"][i],
         "wind_kmh": hourly["wind_speed_10m"][i], "gust_kmh": hourly["wind_gusts_10m"][i]}
        for i in range(len(times))
    ]}


def _snapshot(tool_context: ToolContext) -> dict:
    invocation_state = tool_context.invocation_state
    if "snapshot" not in invocation_state:
        raise ValueError("snapshot is required in invocation_state")
    return invocation_state["snapshot"]


@tool(context=True)
def get_surf_conditions(tool_context: ToolContext) -> dict:
    """Return the captured hourly wave and swell observations for this booking request."""
    return _snapshot(tool_context)["conditions"]


@tool(context=True)
def get_weather(tool_context: ToolContext) -> dict:
    """Return the captured hourly wind, gust, and temperature observations for this booking request."""
    return _snapshot(tool_context)["weather"]
