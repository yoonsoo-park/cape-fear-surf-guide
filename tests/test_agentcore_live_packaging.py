from __future__ import annotations

import importlib.util
from pathlib import Path
from zipfile import ZipFile


def _packaging_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "package_agentcore_live_agent.py"
    spec = importlib.util.spec_from_file_location("package_agentcore_live_agent", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_agentcore_direct_code_artifact_is_deterministic_and_has_http_entrypoint(tmp_path: Path):
    packaging = _packaging_module()
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    assert packaging.package(first, include_dependencies=False) == packaging.package(second, include_dependencies=False)
    assert first.read_bytes() == second.read_bytes()
    with ZipFile(first) as archive:
        members = set(archive.namelist())
    assert {"agentcore_live_entrypoint.py", "agentcore_runtime/server.py", "surf/live_agent.py", "surf/data/seed.json"} <= members
    assert not any(name.endswith("Dockerfile") for name in members)


def test_live_agentcore_packager_targets_agentcore_arm64_manylinux():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "package_agentcore_live_agent.py").read_text()
    assert "aarch64-manylinux2014" in source
