from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator, AsyncIterable
from typing import Any

from strands.models import Model

from .brief import template_brief
from .schema import RecommendationRecord


class FixturePlannerModel(Model):
    """Offline model that deterministically exercises the real Strands tool loop."""

    tool_sequence = (
        ("list_supported_beaches", {}),
        ("get_nws_hazards", {"zone": "fixture-zone", "date_range": "fixture-range"}),
        ("get_nws_surf_zone_forecast", {"zone": "fixture-zone", "date_range": "fixture-range"}),
        ("get_tide_predictions", {"station": "8658163", "date_range": "fixture-range"}),
        ("get_water_quality_status", {"deq_site": "fixture-site", "date": "2026-08-29"}),
        ("get_marine_forecast", {"latitude": 34.2085, "longitude": -77.7964, "date_range": "fixture-range"}),
    )

    def update_config(self, **model_config: Any) -> None:
        return None

    def get_config(self) -> dict[str, Any]:
        return {"model_id": "fixture-planner-model"}

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs: Any) -> AsyncIterable[dict[str, Any]]:
        intake_tool = next((spec for spec in (tool_specs or []) if spec.get("name") == "IntakeDecision"), None)
        if intake_tool:
            text = next(
                block["text"] for message in reversed(messages) for block in message["content"]
                if "text" in block and block["text"].startswith("INTAKE_REQUEST=")
            )
            request = text.splitlines()[0].removeprefix("INTAKE_REQUEST=").lower()
            skill = re.search(r"skill=(\w+)", request)
            if skill:
                ages_match = re.search(r"ages=([0-9,]*)", request)
                ages = [int(value) for value in ages_match.group(1).split(",") if value] if ages_match else []
                arguments = {"questions": [], "profile": {"skill_level": skill.group(1), "ages": ages}}
            else:
                arguments = {"questions": ["What are the surfers' skill levels and ages?"], "profile": None}
            yield {"messageStart": {"role": "assistant"}}
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": "fixture-intake", "name": "IntakeDecision"}}, "contentBlockIndex": 0}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(arguments)}}, "contentBlockIndex": 0}}
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            yield {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                                "metrics": {"latencyMs": 1}}}
            return
        structured_tool = next((spec for spec in (tool_specs or []) if spec.get("name") == "SurfBrief"), None)
        if structured_tool:
            text = next(
                block["text"] for message in reversed(messages) for block in message["content"]
                if "text" in block and block["text"].startswith("RECORD_JSON=")
            )
            record_json = text.removeprefix("RECORD_JSON=").splitlines()[0]
            record = RecommendationRecord.model_validate_json(record_json)
            arguments = template_brief(record).model_dump(mode="json")
            yield {"messageStart": {"role": "assistant"}}
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": "fixture-brief", "name": "SurfBrief"}}, "contentBlockIndex": 0}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(arguments)}}, "contentBlockIndex": 0}}
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            yield {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                                "metrics": {"latencyMs": 1}}}
            return
        used = {
            block["toolUse"]["name"]
            for message in messages for block in message["content"] if "toolUse" in block
        }
        pending = next(((name, args) for name, args in self.tool_sequence if name not in used), None)
        yield {"messageStart": {"role": "assistant"}}
        if pending:
            name, arguments = pending
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": f"fixture-{len(used)}", "name": name}}, "contentBlockIndex": 0}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(arguments)}}, "contentBlockIndex": 0}}
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockStart": {"start": {}, "contentBlockIndex": 0}}
            yield {"contentBlockDelta": {"delta": {"text": "Retrieval complete."}, "contentBlockIndex": 0}}
            yield {"contentBlockStop": {"contentBlockIndex": 0}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        yield {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                            "metrics": {"latencyMs": 1}}}

    async def structured_output(self, output_model, prompt, system_prompt=None,
                                **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
        text = next(
            block["text"] for message in reversed(prompt) for block in message["content"]
            if "text" in block and block["text"].startswith("RECORD_JSON=")
        )
        record_json = text.removeprefix("RECORD_JSON=").splitlines()[0]
        record = RecommendationRecord.model_validate_json(record_json)
        yield {"output": output_model.model_validate(template_brief(record).model_dump())}
