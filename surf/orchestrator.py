from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strands import Agent, ToolContext, tool
from strands.models import BedrockModel
from strands.multiagent import Swarm

from .agents import ToolCallRecorder, build_specialists
from .config import EXPECTED_PATH, Settings
from .runlog import append_run
from .tools.inventory import load_seed
from .validator import validate_recommendation

EXPERIMENT_VERSION = "compact-handoff-v1"


def _node_metrics(result: Any) -> dict[str, Any]:
    return {
        name: {
            "status": node.status.value,
            "execution_time_ms": node.execution_time,
            "usage": dict(node.accumulated_usage),
            "metrics": dict(node.accumulated_metrics),
        }
        for name, node in result.results.items()
    }


def execute_swarm(model: BedrockModel, state: dict[str, Any]) -> dict[str, Any]:
    recorder = ToolCallRecorder()
    specialists = build_specialists(model, recorder)
    swarm = Swarm(
        specialists,
        entry_point=specialists[0],
        max_handoffs=6,
        max_iterations=6,
        execution_timeout=300,
        node_timeout=90,
    )
    task = (
        f"Recommend lesson slots and prices for {state['beach']} on {state['day']}. "
        "Follow the specialist sequence and finish with the required JSON object."
    )
    started = time.perf_counter()
    result = swarm(task, invocation_state=state)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    path = [node.node_id for node in result.node_history]
    pricing_result = str(result.results.get("pricing_agent", ""))
    return {
        "recommendation": pricing_result,
        "swarm_text": str(result),
        "node_path": path,
        "path_complete": path == EXPECTED_PATH,
        "handoff_count": max(0, len(path) - 1),
        "tool_calls": dict(recorder.calls),
        "elapsed_ms": elapsed_ms,
        "execution_time_ms": result.execution_time,
        "usage": dict(result.accumulated_usage),
        "metrics": dict(result.accumulated_metrics),
        "nodes": _node_metrics(result),
        "status": result.status.value,
    }


def run_once(settings: Settings, beach: str, day: str, snapshot_id: str, snapshot: dict,
             log_path: Path | None = None) -> dict[str, Any]:
    swarm_model = BedrockModel(
        region_name=settings.region,
        model_id=settings.model_id,
        temperature=0,
        max_tokens=4_000,
    )
    orchestrator_model = BedrockModel(
        region_name=settings.region,
        model_id=settings.model_id,
        temperature=0,
        max_tokens=800,
    )
    holder: dict[str, Any] = {}

    @tool(name="recommend_surf_bookings", context=True)
    def recommend_surf_bookings(tool_context: ToolContext) -> dict:
        """Run the surf-school specialist swarm exactly once and return its evidence-rich result."""
        holder["swarm"] = execute_swarm(swarm_model, tool_context.invocation_state)
        return {
            "status": holder["swarm"]["status"],
            "node_path": holder["swarm"]["node_path"],
            "recommendation": holder["swarm"]["recommendation"],
        }

    orchestrator = Agent(
        name="orchestrator_agent",
        agent_id="orchestrator_agent",
        model=orchestrator_model,
        tools=[recommend_surf_bookings],
        callback_handler=None,
        system_prompt=(
            "Call recommend_surf_bookings exactly once. Do not calculate or invent any data yourself. "
            "After the tool returns, summarize the recommendation in at most 10 lines. "
            "Do not repeat the complete slot JSON or tables."
        ),
    )
    state = {
        "beach": beach,
        "day": day,
        "snapshot": snapshot,
        "inventory": snapshot.get("inventory", load_seed()),
    }
    record: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "beach": beach,
        "day": day,
        "snapshot_id": snapshot_id,
        "model_id": settings.model_id,
        "mode": "prompt-only",
        "experiment_version": EXPERIMENT_VERSION,
    }
    started = time.perf_counter()
    try:
        orchestrator_result = orchestrator(
            f"Recommend surf-school bookings for {beach} on {day}.",
            invocation_state=state,
        )
        record["orchestrator_response"] = str(orchestrator_result)
        record["orchestrator_usage"] = dict(orchestrator_result.metrics.accumulated_usage)
        record["orchestrator_metrics"] = dict(orchestrator_result.metrics.accumulated_metrics)
        if "swarm" not in holder:
            raise RuntimeError("orchestrator completed without calling recommend_surf_bookings")
        record.update(holder["swarm"])
        record["validation"] = validate_recommendation(record["recommendation"], snapshot)
        record["success"] = record["status"] == "completed"
    except Exception as error:
        record.update({
            "success": False,
            "error_type": type(error).__name__,
            "error": str(error),
        })
    record["total_elapsed_ms"] = round((time.perf_counter() - started) * 1000)
    append_run(record, log_path or Path(settings.run_log))
    return record
