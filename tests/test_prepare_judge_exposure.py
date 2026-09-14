from datetime import datetime, timezone

import pytest

from scripts.prepare_judge_exposure import build_plan


def test_build_plan_produces_cloudformation_compatible_window():
    plan = build_plan(
        now=datetime(2026, 9, 17, 14, 30, tzinfo=timezone.utc),
        hours=72,
        suffix="A1b2C3d4",
    )

    assert plan == {
        "generated_at_utc": "2026-09-17T14:30:00Z",
        "exposure_id": "judge-20260917-143000-a1b2c3d4",
        "public_until_utc": "2026-09-20T14:30:00",
        "duration_hours": 72,
        "max_valid_mcp_posts": 120,
        "requires_personal_aws_identity_confirmation": True,
        "per_judge_api_key_required": True,
        "aws_changes_performed": False,
    }


@pytest.mark.parametrize("hours", [0, 73])
def test_build_plan_rejects_windows_outside_policy(hours):
    with pytest.raises(ValueError, match="between 1 and 72"):
        build_plan(
            now=datetime(2026, 9, 17, tzinfo=timezone.utc),
            hours=hours,
            suffix="abcd1234",
        )


def test_build_plan_rejects_non_alphanumeric_suffix():
    with pytest.raises(ValueError, match="only letters and digits"):
        build_plan(
            now=datetime(2026, 9, 17, tzinfo=timezone.utc),
            hours=72,
            suffix="judge_key",
        )
