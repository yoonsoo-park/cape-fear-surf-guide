#!/usr/bin/env python3
"""Generate non-secret inputs for a short-lived judge access window.

This helper is deliberately offline. It does not call AWS, create an API key,
or change the public endpoint.
"""

from __future__ import annotations

import argparse
import json
import secrets
from datetime import datetime, timedelta, timezone


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_plan(*, now: datetime, hours: int, suffix: str) -> dict[str, object]:
    if not 1 <= hours <= 72:
        raise ValueError("hours must be between 1 and 72")
    if not suffix or not suffix.isalnum():
        raise ValueError("suffix must contain only letters and digits")

    now = now.astimezone(timezone.utc).replace(microsecond=0)
    public_until = now + timedelta(hours=hours)
    exposure_id = f"judge-{now:%Y%m%d-%H%M%S}-{suffix.lower()}"
    return {
        "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
        "exposure_id": exposure_id,
        "public_until_utc": public_until.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_hours": hours,
        "max_valid_mcp_posts": 120,
        "requires_personal_aws_identity_confirmation": True,
        "per_judge_api_key_required": True,
        "aws_changes_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=72)
    parser.add_argument(
        "--now",
        type=parse_utc,
        default=datetime.now(timezone.utc),
        help="UTC ISO-8601 time used for a reproducible dry run",
    )
    parser.add_argument(
        "--suffix",
        default=None,
        help="Alphanumeric exposure suffix; a random eight-character value is the default",
    )
    args = parser.parse_args()

    suffix = args.suffix or secrets.token_hex(4)
    try:
        plan = build_plan(now=args.now, hours=args.hours, suffix=suffix)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
