"""HTTP contract for the AgentCore-hosted live Strands planner."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from typing import Any

from surf.live_agent import LiveAgentPlanningResult, plan_live_with_agent
from surf.planner_agent import bedrock_model


REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("CAPE_FEAR_MODEL_ID", "us.amazon.nova-lite-v1:0")
MAX_BODY_BYTES = 65_536


def process_invocation(payload: dict[str, Any], *, planner: Any = plan_live_with_agent) -> tuple[int, dict[str, Any]]:
    """Return a redaction-safe AgentCore response without exposing request content in logs."""
    request = payload.get("input", payload)
    if not isinstance(request, dict):
        return HTTPStatus.BAD_REQUEST, _error("invalid_input", "input must be a JSON object")
    requested_date = request.get("date")
    party_profile = request.get("party_profile")
    if not isinstance(requested_date, str) or not isinstance(party_profile, dict):
        return HTTPStatus.BAD_REQUEST, _error("invalid_input", "date and party_profile are required")
    try:
        result = planner(
            requested_date, party_profile, bedrock_model(REGION, MODEL_ID),
            request.get("preferred_area"), request.get("time_range"),
        )
    except Exception as error:
        # Keep the live response fail-closed while retaining one non-sensitive
        # diagnostic for the private AgentCore invocation smoke test.
        return HTTPStatus.OK, _error(
            "agent_unavailable",
            "The planner could not complete this request.",
            {"error_type": type(error).__name__},
        )
    if isinstance(result, tuple):
        code, message, details = result
        return HTTPStatus.BAD_REQUEST, _error(code, message, details)
    required_fields = ("record", "brief", "brief_source", "tool_calls", "model_schema_valid", "invariant_violations")
    if not isinstance(result, LiveAgentPlanningResult) and not all(hasattr(result, field) for field in required_fields):
        return HTTPStatus.INTERNAL_SERVER_ERROR, _error("agent_unavailable", "The planner returned an invalid result.")
    return HTTPStatus.OK, {
        "output": {
            "record": result.record.model_dump(mode="json"),
            "brief": result.brief.model_dump(mode="json"),
            "brief_source": result.brief_source,
            "tool_calls": [call["name"] for call in result.tool_calls],
            "model_schema_valid": result.model_schema_valid,
            "invariant_violations": result.invariant_violations,
            "safety_limit": "This is a planning aid, not a guarantee that ocean activity is safe. Check posted flags, lifeguards, and local officials.",
        }
    }


def _error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


class AgentCoreHandler(BaseHTTPRequestHandler):
    server_version = "CapeFearAgentCore/0.1"

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/ping":
            self._write(HTTPStatus.NOT_FOUND, _error("not_found", "endpoint not found"))
            return
        self._write(HTTPStatus.OK, {"status": "healthy"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/invocations":
            self._write(HTTPStatus.NOT_FOUND, _error("not_found", "endpoint not found"))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._write(HTTPStatus.BAD_REQUEST, _error("invalid_content_length", "Content-Length must be an integer"))
            return
        if length < 1 or length > MAX_BODY_BYTES:
            self._write(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, _error("request_too_large", "request body exceeds the limit"))
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self._write(HTTPStatus.BAD_REQUEST, _error("invalid_json", "request body must be JSON"))
            return
        if not isinstance(payload, dict):
            self._write(HTTPStatus.BAD_REQUEST, _error("invalid_input", "request body must be an object"))
            return
        status, response = process_invocation(payload)
        self._write(status, response)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress request paths and bodies from application logs."""

    def _write(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    ThreadingHTTPServer(("0.0.0.0", 8080), AgentCoreHandler).serve_forever()


if __name__ == "__main__":
    main()
