from __future__ import annotations

import argparse
import json
from pathlib import Path

from surf.config import Settings
from surf.orchestrator import run_once
from surf.snapshots import load_snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--manifest", default="snapshots/scenarios/manifest.json")
    parser.add_argument("--scenario", action="append", help="Run only the named scenario; repeatable")
    parser.add_argument("--confirm-live-cost", action="store_true")
    args = parser.parse_args()
    if not args.confirm_live_cost:
        parser.error("live Bedrock matrix requires --confirm-live-cost")
    settings = Settings.from_env()
    scenarios = json.loads(Path(args.manifest).read_text())
    if args.scenario:
        scenarios = [item for item in scenarios if item["name"] in set(args.scenario)]
    for scenario in scenarios:
        snapshot = load_snapshot(scenario["snapshot_id"])
        for repeat in range(args.repeats):
            print(f"{scenario['name']} repeat {repeat + 1}/{args.repeats}", flush=True)
            run_once(settings, snapshot["beach"], snapshot["day"], scenario["snapshot_id"], snapshot)


if __name__ == "__main__":
    main()
