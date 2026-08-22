from __future__ import annotations

import argparse
from pathlib import Path

from surf.sources.nws import capture_zone_forecast


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture an NWS forecast-zone response for offline replay")
    parser.add_argument("--zone", required=True, help="NWS forecast zone, for example NCZ108")
    parser.add_argument("--user-agent", required=True, help="Identifying NWS User-Agent with a real contact route")
    parser.add_argument("--output", type=Path, required=True, help="Reviewed JSON capture destination")
    args = parser.parse_args()
    capture_zone_forecast(args.zone, args.user_agent, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
