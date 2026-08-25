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


def test_judge_gated_live_template_has_api_key_rest_api_waf_ttl_and_no_function_url_or_bearer_path():
    template = (REPO_ROOT / "infra" / "external-mcp-demo" / "runtime.yaml").read_text()
    assert "AWS::ApiGateway::RestApi" in template
    assert "AWS::ApiGateway::Method" in template
    assert "HttpMethod: POST" in template
    assert "AWS::WAFv2::WebACL" in template
    assert "AWS::WAFv2::WebACLAssociation" in template
    assert "Limit: 30" in template
    assert "AggregateKeyType: IP" in template
    assert "AggregateKeyType: CONSTANT" in template
    assert "GlobalMcpPostRateLimit" in template
    assert "Default: 60" in template
    assert "ThrottlingRateLimit: !Ref ApiRateLimit" in template
    assert "Default: 1" in template
    assert "Default: 120" in template
    assert "MCP_MAX_PUBLIC_POST_REQUESTS" in template
    assert "AWS::Lambda::EventSourceMapping" in template
    assert "AWS::CloudWatch::Alarm" in template
    assert "Threshold: 40" in template
    assert "AWS::Scheduler::Schedule" in template
    assert "AWS::Budgets::Budget" in template
    assert "ApiKeyRequired: true" in template
    assert "AWS::ApiGateway::UsagePlan" in template
    assert "AgentCoreRuntimeArn" in template
    assert "bedrock-agentcore:InvokeAgentRuntime" in template
    assert "MCP_AGENTCORE_RUNTIME_ARN" in template
    assert "Timeout: 30" in template
    assert "ReservedConcurrentExecutions=0" not in template
    assert "AWSManagedRulesCommonRuleSet" in template
    assert "ReservedConcurrentExecutions" in template
    assert "dynamodb:GetItem, dynamodb:UpdateItem" in template
    assert "lambda:PutFunctionConcurrency" in template
    assert "TimeToLiveSpecification" in template
    assert "AttributeName: expires_at" in template
    assert "SSEEnabled: true" in template
    assert "AWS::Lambda::Url" not in template
    assert "InvokeFunctionUrl" not in template
    assert "DemoBearerToken" not in template
    assert "ssm:" not in template
    assert "AWS::EC2::" not in template
    assert "AWS::NATGateway" not in template


def test_public_live_lambda_package_contains_live_sources_but_no_fixtures_or_strands(tmp_path: Path):
    packager = _load_packager()
    archive = tmp_path / "live-mcp.zip"
    first = packager.package(archive, include_dependencies=False)
    second = packager.package(tmp_path / "live-mcp-second.zip", include_dependencies=False)
    with ZipFile(archive) as bundle:
        members = set(bundle.namelist())
    assert first == second
    assert {"mcp_runtime/lambda_entrypoint.py", "mcp_runtime/server.py", "mcp_runtime/agentcore_planner.py", "mcp_runtime/exposure_control.py",
            "mcp_runtime/circuit_breaker.py", "surf/live_planner.py",
            "surf/live_sources.py", "surf/live_store.py", "surf/sources/nws.py"} <= members
    assert not any(name.startswith("fixtures/") for name in members)
    assert "mcp_runtime/claude_desktop_bridge.py" not in members
    assert all(not name.startswith("strands") for name in members)


def test_external_lambda_packager_targets_the_lambda_compatible_manylinux_baseline():
    assert "x86_64-manylinux2014" in (REPO_ROOT / "scripts" / "package_external_mcp_lambda.py").read_text()
