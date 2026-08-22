from __future__ import annotations

import importlib.util
from pathlib import Path
from zipfile import ZipFile


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_packager():
    path = REPO_ROOT / "scripts" / "package_external_mcp_lambda.py"
    spec = importlib.util.spec_from_file_location("package_external_mcp_lambda", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_external_lambda_template_is_short_lived_and_has_no_network_or_token_escape_hatch():
    template = (REPO_ROOT / "infra" / "external-mcp-demo" / "runtime.yaml").read_text()
    artifact_template = (REPO_ROOT / "infra" / "external-mcp-demo" / "artifact-bucket.yaml").read_text()
    assert "AWS::Lambda::Url" in template
    assert "NoEcho: true" in template
    assert "ssm:GetParameter" in template
    assert "ssm:PutParameter" in template
    assert "ssm:DeleteParameter" in template
    assert "Type: Custom::DemoSecureString" in template
    assert "ReservedConcurrentExecutions" in template
    assert "LogRetentionDays" in template
    assert "MCP_MAX_REQUEST_BODY_BYTES" in template
    assert "AWS::EC2::" not in template
    assert "AWS::NATGateway" not in template
    assert "MCP_AUTH_TOKEN:" not in template
    assert "ArtifactObjectVersion" in template
    assert "S3ObjectVersion: !Ref ArtifactObjectVersion" in template
    assert "Token: !Ref DemoBearerToken" in template
    assert "DemoBearerToken" not in template.split("Outputs:", 1)[1]
    assert "AWS::S3::Bucket" in artifact_template
    assert "AWS::NATGateway" not in artifact_template
    assert "AWS::BedrockAgentCore" not in artifact_template


def test_external_lambda_package_contains_only_the_frozen_service_sources(tmp_path: Path):
    packager = _load_packager()
    archive = tmp_path / "external-mcp.zip"
    first = packager.package(archive, include_dependencies=False)
    second = packager.package(tmp_path / "external-mcp-second.zip", include_dependencies=False)
    with ZipFile(archive) as bundle:
        members = set(bundle.namelist())
    assert first == second
    assert {
        "mcp_runtime/lambda_entrypoint.py",
        "mcp_runtime/server.py",
        "surf/mcp_contract.py",
        "fixtures/normal.json",
        "fixtures/hazard.json",
    } <= members
    assert all(not name.startswith("strands") for name in members)


def test_external_lambda_packager_targets_the_lambda_compatible_manylinux_baseline():
    packager = _load_packager()
    assert "x86_64-manylinux2014" in (REPO_ROOT / "scripts" / "package_external_mcp_lambda.py").read_text()
