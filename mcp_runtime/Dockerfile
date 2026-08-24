# AgentCore's MCP service contract expects a container at 0.0.0.0:8000/mcp.
# This image contains the SDK v2 runtime separately from the Strands v1 MCP
# dependency, while copying the one shared deterministic surf application.
FROM ghcr.io/astral-sh/uv:0.11.26 AS uv

FROM python:3.11-slim
COPY --from=uv /uv /uvx /bin/
WORKDIR /app

COPY mcp_runtime/pyproject.toml mcp_runtime/uv.lock /app/mcp_runtime/
RUN cd /app/mcp_runtime && uv sync --frozen --no-dev --no-install-project

COPY surf /app/surf
COPY mcp_runtime/mcp_runtime /app/mcp_runtime/mcp_runtime
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["/app/mcp_runtime/.venv/bin/python", "-m", "mcp_runtime.server"]
