from __future__ import annotations

from collections import defaultdict
from typing import Any

from strands import Agent
from strands.models import BedrockModel

from .tools.inventory import get_base_pricing, get_instructor_availability
from .tools.signals import get_surf_conditions, get_weather


class ToolCallRecorder:
    def __init__(self) -> None:
        self.calls: dict[str, list[str]] = defaultdict(list)

    def handler(self, agent_name: str):
        def record(**kwargs: Any) -> None:
            tool_use = kwargs.get("event", {}).get("contentBlockStart", {}).get("start", {}).get("toolUse")
            if tool_use:
                self.calls[agent_name].append(tool_use["name"])
        return record


def build_specialists(model: BedrockModel, recorder: ToolCallRecorder) -> list[Agent]:
    shared = (
        "This is an evidence PoC. Use observed tool values only; never invent measurements. "
        "Only analyze lesson hours 07:00 through 15:00. Carry exact values and source times "
        "in compact JSON; do not add narrative, tables, or repeat unused hours."
    )
    specs = [
        ("conditions_agent", [get_surf_conditions],
         "Call get_surf_conditions. Classify lesson hours from wave and swell data. "
         "Then call handoff_to_agent with agent_name='weather_agent'."),
        ("weather_agent", [get_weather],
         "Call get_weather. Flag windy, gusty, or cold lesson hours. Preserve prior observations. "
         "Then call handoff_to_agent with agent_name='availability_agent'."),
        ("availability_agent", [get_instructor_availability],
         "Call get_instructor_availability. Match open instructors to skill levels and observed hours. "
         "Then call handoff_to_agent with agent_name='safety_agent'."),
        ("safety_agent", [],
         "Apply this prompt-only safety rule: never recommend a beginner lesson when swell_height_m > 1.2 "
         "or gust_kmh > 30. Explain each veto. Then call handoff_to_agent with agent_name='pricing_agent'."),
        ("pricing_agent", [get_base_pricing],
         "Call get_base_pricing. Recommend safe slots and prices. Never price below min_price. "
         "Return ONLY one JSON object. The slots key MUST be a JSON array, never an object. "
         "Return at most 8 best recommendations. Create one item per instructor and skill level. "
         "Every item MUST contain exactly time, level "
         "as one string, instructor, swell_height_m, gust_kmh, price as one number, and min_price as "
         "one number. Also include one short safety_note and evidence_summary. No markdown or prose."),
    ]
    agents = []
    for name, tools, prompt in specs:
        agents.append(Agent(
            name=name, agent_id=name, model=model, tools=tools,
            system_prompt=f"{shared} {prompt}", callback_handler=recorder.handler(name),
        ))
    return agents
