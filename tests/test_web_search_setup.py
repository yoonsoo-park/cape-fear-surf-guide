import argparse

import pytest

from scripts.setup_web_search_target import (
    APPROVED_PERSONAL_ACCOUNT,
    _target_configuration,
    _validate_args,
)
from surf.web_context import _parse_mcp_result, _resolve_web_tool_name


def _args(**overrides):
    values = {
        "account": APPROVED_PERSONAL_ACCOUNT,
        "region": "us-east-1",
        "profile": "aws-dimly",
        "action": "describe",
        "confirm_live": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_web_search_configuration_matches_agentcore_connector_contract():
    assert _target_configuration("1.1.0") == {
        "mcp": {
            "connector": {
                "source": {"connectorId": "web-search", "version": "1.1.0"},
                "configurations": [{"name": "WebSearch", "parameterValues": {}}],
            }
        }
    }


def test_setup_rejects_non_personal_or_wrong_region_and_requires_live_confirmation():
    _validate_args(_args())
    with pytest.raises(SystemExit, match="non-approved"):
        _validate_args(_args(account="000000000000"))
    with pytest.raises(SystemExit, match="us-east-1"):
        _validate_args(_args(region="us-west-2"))
    with pytest.raises(SystemExit, match="confirm-live"):
        _validate_args(_args(action="apply"))
    with pytest.raises(SystemExit, match="nCino/company"):
        _validate_args(_args(profile="company"))


def test_mcp_web_search_parser_accepts_text_or_structured_results_only():
    assert _parse_mcp_result({"structuredContent": {"results": [{"url": "https://example.com"}]}})["results"]
    assert _parse_mcp_result({"content": [{"type": "text", "text": '{"id":"x","results":[{"url":"https://example.com"}]}'}]})["results"]
    assert _parse_mcp_result({"content": [{"type": "text", "text": "not json"}]}) == {"results": []}


def test_gateway_target_namespace_resolves_semantic_web_search_tool():
    assert _resolve_web_tool_name({"web-search-tool___WebSearch"}, "WebSearchTool") == "web-search-tool___WebSearch"
    assert _resolve_web_tool_name({"WebSearchTool"}, "WebSearchTool") == "WebSearchTool"
