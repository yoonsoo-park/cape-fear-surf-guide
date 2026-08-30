"""Run one private, bounded AgentCore Web Search smoke after human approval."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlparse

from surf.web_context import (
    AgentCoreWebSearchAdapter,
    WebContextSettings,
    collect_web_context,
)

from setup_web_search_target import APPROVED_PERSONAL_ACCOUNT, _session


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--endpoint", required=True, help="private AgentCore Gateway MCP endpoint")
    parser.add_argument("--query", default="Wrightsville Beach official surf conditions")
    parser.add_argument("--max-results", type=int, default=3)
    parser.add_argument("--timeout-s", type=float, default=8.0)
    parser.add_argument("--evidence-file", type=Path, default=Path("dist/agentcore-web-search-evidence.json"))
    parser.add_argument("--confirm-live", action="store_true", help="confirm the approved private smoke")
    args = parser.parse_args()
    if not args.confirm_live:
        raise SystemExit("live Web Search smoke requires --confirm-live after human AWS approval")
    if args.account != APPROVED_PERSONAL_ACCOUNT:
        raise SystemExit("refusing non-approved or nCino account")
    if args.region != "us-east-1":
        raise SystemExit("AgentCore Web Search is restricted to us-east-1")
    _session(args)  # STS identity check; credentials are never printed or persisted.
    settings = WebContextSettings(enabled=True, max_results=args.max_results, timeout_s=args.timeout_s)
    adapter = AgentCoreWebSearchAdapter(endpoint=args.endpoint, region=args.region, profile=args.profile)
    started = time.perf_counter()
    outcome = collect_web_context(args.query, adapter=adapter, settings=settings)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    if outcome["status"] not in {"ok", "empty"}:
        raise SystemExit(f"Web Search smoke failed closed with status={outcome['status']}")

    endpoint_host = urlparse(args.endpoint).netloc
    evidence = {
        "account": args.account,
        "region": args.region,
        "profile": args.profile,
        "endpoint_host": endpoint_host,
        "tool": "WebSearchTool",
        "query_length": len(args.query),
        "elapsed_ms": elapsed_ms,
        "estimated_query_cost_usd": 0.007,
        "status": outcome["status"],
        "result_count": len(outcome["results"]),
        "results": [
            {
                "source_kind": item["source_kind"],
                "title": item["title"],
                "url": item["url"],
                "published_at": item["published_at"],
                "freshness_state": item["freshness_state"],
            }
            for item in outcome["results"]
        ],
        "policy_signal": outcome["policy_signal"],
    }
    args.evidence_file.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_file.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
