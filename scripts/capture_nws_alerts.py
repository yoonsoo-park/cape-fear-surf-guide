from __future__ import annotations

import argparse
from pathlib import Path

from surf.sources.nws import capture_active_alerts


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a live NWS active-alerts response for offline replay")
    parser.add_argument("--zone", required=True, help="NWS forecast zone, for example NCZ106")
    parser.add_argument("--user-agent", required=True, help="Identifying NWS User-Agent with a real contact route")
    parser.add_argument("--output", type=Path, required=True, help="Reviewed JSON capture destination")
    args = parser.parse_args()
    capture_active_alerts(args.zone, args.user_agent, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
