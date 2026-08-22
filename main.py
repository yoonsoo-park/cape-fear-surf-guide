from __future__ import annotations

import argparse
import json
from pathlib import Path

from surf.application import plan_fixture
from surf.planner_agent import plan_fixture_with_agent
from surf.render import render_html
from surf.replay_model import FixturePlannerModel


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Generate a Cape Fear Surf Guide planning record")
    command.add_argument("--fixture", choices=("normal", "hazard", "stale", "conflict"), default="normal")
    command.add_argument("--deterministic-only", action="store_true", help="Skip the offline Strands agent brief")
    command.add_argument("--html", type=Path, help="Write a static HTML report")
    return command


def main() -> int:
    args = parser().parse_args()
    result = (plan_fixture(args.fixture) if args.deterministic_only
              else plan_fixture_with_agent(args.fixture, FixturePlannerModel()))
    if args.html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(render_html(result))
    payload = {"record": result.record.model_dump(mode="json"),
               "brief": result.brief.model_dump(mode="json"),
               "brief_source": result.brief_source}
    if hasattr(result, "tool_calls"):
        payload["tool_calls"] = result.tool_calls
        payload["metrics"] = {"elapsed_ms": result.elapsed_ms,
                              "estimated_cost_usd": result.estimated_cost_usd,
                              "findings": result.findings,
                              "trace_id": result.trace_id,
                              "usage": result.usage}
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
