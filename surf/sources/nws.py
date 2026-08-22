from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


NWS_API = "https://api.weather.gov"


def _validate_user_agent(user_agent: str) -> None:
    """Require an application name plus an email address or public contact URL."""
    value = user_agent.strip()
    if not value or ("@" not in value and "http://" not in value and "https://" not in value):
        raise ValueError("NWS User-Agent must contain a non-secret project identifier and contact route")


def fetch_point(latitude: float, longitude: float, user_agent: str, session: Any = requests) -> dict[str, Any]:
    _validate_user_agent(user_agent)
    response = session.get(
        f"{NWS_API}/points/{latitude:.4f},{longitude:.4f}",
        headers={"User-Agent": user_agent, "Accept": "application/geo+json"}, timeout=15,
    )
    response.raise_for_status()
    return response.json()


def fetch_active_alerts(zone: str, user_agent: str, session: Any = requests) -> dict[str, Any]:
    if not zone.strip():
        raise ValueError("NWS zone is required")
    _validate_user_agent(user_agent)
    response = session.get(
        f"{NWS_API}/alerts/active", params={"zone": zone},
        headers={"User-Agent": user_agent, "Accept": "application/geo+json"}, timeout=15,
    )
    response.raise_for_status()
    return response.json()


def fetch_zone_forecast(zone: str, user_agent: str, session: Any = requests) -> dict[str, Any]:
    """Fetch the official NWS forecast-zone product used for surf planning context."""
    if not zone.strip():
        raise ValueError("NWS zone is required")
    _validate_user_agent(user_agent)
    response = session.get(
        f"{NWS_API}/zones/forecast/{zone}/forecast",
        headers={"User-Agent": user_agent, "Accept": "application/geo+json"}, timeout=15,
    )
    response.raise_for_status()
    return response.json()


def capture_active_alerts(zone: str, user_agent: str, output: Path, session: Any = requests,
                          captured_at: datetime | None = None) -> dict[str, Any]:
    """Capture one live NWS alert response for reviewable offline replay.

    The caller supplies the identifying NWS ``User-Agent`` and destination.
    This function never uses a hidden contact address or silently falls back to
    the network during replay.
    """
    payload = {
        "capture_schema_version": 1,
        "source": "api.weather.gov/alerts/active",
        "zone": zone,
        "captured_at": (captured_at or datetime.now(timezone.utc)).isoformat(),
        "response": fetch_active_alerts(zone, user_agent, session),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def replay_active_alerts(snapshot: Path) -> dict[str, Any]:
    """Load a captured NWS response without any network access."""
    payload = json.loads(snapshot.read_text())
    if payload.get("capture_schema_version") != 1 or payload.get("source") != "api.weather.gov/alerts/active":
        raise ValueError("not a supported NWS active-alerts capture")
    response = payload.get("response")
    if not isinstance(response, dict):
        raise ValueError("NWS capture does not contain a JSON object response")
    return response


def capture_zone_forecast(zone: str, user_agent: str, output: Path, session: Any = requests,
                          captured_at: datetime | None = None) -> dict[str, Any]:
    """Capture the official forecast-zone response for offline replay."""
    payload = {
        "capture_schema_version": 1,
        "source": "api.weather.gov/zones/forecast",
        "zone": zone,
        "captured_at": (captured_at or datetime.now(timezone.utc)).isoformat(),
        "response": fetch_zone_forecast(zone, user_agent, session),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def replay_zone_forecast(snapshot: Path) -> dict[str, Any]:
    """Load a captured forecast-zone response without any network access."""
    payload = json.loads(snapshot.read_text())
    if payload.get("capture_schema_version") != 1 or payload.get("source") != "api.weather.gov/zones/forecast":
        raise ValueError("not a supported NWS forecast-zone capture")
    response = payload.get("response")
    if not isinstance(response, dict):
        raise ValueError("NWS capture does not contain a JSON object response")
    return response
