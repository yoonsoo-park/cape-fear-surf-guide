from __future__ import annotations

from typing import Any

from strands import ToolContext, tool

from .locations import BEACHES


def _state(tool_context: ToolContext) -> dict[str, Any]:
    return tool_context.invocation_state


def _record(tool_context: ToolContext, name: str, arguments: dict[str, Any], outcome: Any) -> Any:
    _state(tool_context).setdefault("tool_calls", []).append({
        "name": name, "arguments": arguments, "outcome": outcome,
    })
    return outcome


def _evidence(tool_context: ToolContext, source_kind: str) -> list[dict[str, Any]]:
    evidence = _state(tool_context).get("evidence", _state(tool_context).get("fixture_evidence", []))
    aliases = {
        "nws_surf_zone_forecast": {"nws_surf_zone_forecast", "nws_forecast"},
        "noaa_tide_predictions": {"noaa_tide_predictions", "noaa_tides"},
    }
    accepted_kinds = aliases.get(source_kind, {source_kind})
    return [item for item in evidence if item["source_kind"] in accepted_kinds]


@tool(context=True)
def list_supported_beaches(tool_context: ToolContext) -> dict[str, Any]:
    """Return supported Cape Fear beach identifiers and names; this tool never returns a verdict."""
    outcome = {"beaches": [{"id": item.id, "name": item.name} for item in BEACHES.values()]}
    return _record(tool_context, "list_supported_beaches", {}, outcome)


@tool(context=True)
def get_nws_hazards(zone: str, date_range: str, tool_context: ToolContext) -> dict[str, Any]:
    """Return normalized NWS hazard facts for a zone and date range; this tool never returns a verdict."""
    arguments = {"zone": zone, "date_range": date_range}
    outcome = {"evidence": _evidence(tool_context, "nws_hazards")}
    return _record(tool_context, "get_nws_hazards", arguments, outcome)


@tool(context=True)
def get_nws_surf_zone_forecast(zone: str, date_range: str, tool_context: ToolContext) -> dict[str, Any]:
    """Return normalized NWS surf-zone facts; this tool never returns a verdict."""
    arguments = {"zone": zone, "date_range": date_range}
    outcome = {"evidence": _evidence(tool_context, "nws_surf_zone_forecast")}
    return _record(tool_context, "get_nws_surf_zone_forecast", arguments, outcome)


@tool(context=True)
def get_tide_predictions(station: str, date_range: str, tool_context: ToolContext) -> dict[str, Any]:
    """Return normalized NOAA tide facts; this tool never returns a verdict."""
    arguments = {"station": station, "date_range": date_range}
    outcome = {"evidence": _evidence(tool_context, "noaa_tide_predictions")}
    return _record(tool_context, "get_tide_predictions", arguments, outcome)


@tool(context=True)
def get_water_quality_status(deq_site: str, date: str, tool_context: ToolContext) -> dict[str, Any]:
    """Return normalized NC DEQ status facts; missing coverage is data, not a safety verdict."""
    arguments = {"deq_site": deq_site, "date": date}
    outcome = {"evidence": _evidence(tool_context, "nc_deq_water_quality")}
    return _record(tool_context, "get_water_quality_status", arguments, outcome)


@tool(context=True)
def get_marine_forecast(latitude: float, longitude: float, date_range: str,
                        tool_context: ToolContext) -> dict[str, Any]:
    """Return normalized supplemental marine facts; this tool never returns a verdict."""
    arguments = {"latitude": latitude, "longitude": longitude, "date_range": date_range}
    outcome = {"evidence": _evidence(tool_context, "marine_forecast")}
    return _record(tool_context, "get_marine_forecast", arguments, outcome)


PLANNER_TOOLS = [
    list_supported_beaches, get_nws_hazards, get_nws_surf_zone_forecast,
    get_tide_predictions, get_water_quality_status, get_marine_forecast,
]
