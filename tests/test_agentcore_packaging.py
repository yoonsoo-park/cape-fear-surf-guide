from __future__ import annotations

import importlib.util
from pathlib import Path
from zipfile import ZipFile


def _packaging_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "package_agentcore_spike.py"
    spec = importlib.util.spec_from_file_location("package_agentcore_spike", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agentcore_artifact_is_deterministic_and_contains_only_the_frozen_mcp_service(tmp_path: Path):
    packaging = _packaging_module()
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    assert packaging.package(first, include_dependencies=False) == packaging.package(second, include_dependencies=False)
    assert first.read_bytes() == second.read_bytes()

    with ZipFile(first) as archive:
        members = set(archive.namelist())
    assert {"__init__.py", "agentcore_entrypoint.py", "requirements.txt", "mcp_runtime/server.py"} <= members
    assert {"fixtures/normal.json", "fixtures/hazard.json", "fixtures/stale.json", "fixtures/conflict.json"} <= members
    assert "fixtures/captured/nws-zone-forecast-NCZ108-2026-08-22.json" not in members
    assert "surf/planner_agent.py" not in members
