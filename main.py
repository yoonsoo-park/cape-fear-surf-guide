from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from surf.config import BEACHES, Settings
from surf.orchestrator import run_once
from surf.snapshots import capture_snapshot, load_snapshot


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Run the Surf School Strands Swarm evidence PoC")
    command.add_argument("--once", nargs=2, metavar=("BEACH", "YYYY-MM-DD"))
    command.add_argument("--snapshot", help="Reuse a captured snapshot id")
    return command


def main() -> int:
    args = parser().parse_args()
    if args.once:
        beach, day = args.once
    else:
        beach = input("Beach: ").strip()
        day = input("Day (YYYY-MM-DD): ").strip()
    if beach not in BEACHES:
        print(f"Unsupported beach. Choose one of: {', '.join(BEACHES)}", file=sys.stderr)
        return 2
    try:
        datetime.strptime(day, "%Y-%m-%d")
        snapshot_id, snapshot = (args.snapshot, load_snapshot(args.snapshot)) if args.snapshot else capture_snapshot(beach, day)
        record = run_once(Settings.from_env(), beach, day, snapshot_id, snapshot)
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(json.dumps(record, indent=2))
    return 0 if record["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
