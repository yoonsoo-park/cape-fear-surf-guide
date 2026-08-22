"""AgentCore code-artifact entry point for the MCP v2 compatibility spike."""

from __future__ import annotations

import uvicorn

from mcp_runtime.server import create_agentcore_app


if __name__ == "__main__":
    uvicorn.run(create_agentcore_app(), host="0.0.0.0", port=8000)
