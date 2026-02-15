"""Tests for MCP integration."""

from __future__ import annotations

import json
import sys
import types

import pytest

from tooli import Tooli
from tooli.mcp.server import serve_mcp
from tooli.testing import TooliTestClient


def test_mcp_export() -> None:
    """mcp export should output valid MCP tool definitions."""
    app = Tooli(name="test-mcp")

    @app.command()
    def greet(name: str) -> str:
        """Greet someone."""
        return f"Hello {name}"

    @app.command()
    def noop() -> None:
        pass

    client = TooliTestClient(app)
    result = client.invoke(["mcp", "export"])
    assert result.exit_code == 0

    tools = json.loads(result.output)
    assert isinstance(tools, list)
    assert len(tools) >= 2

    greet_tool = next(t for t in tools if t["name"] == "greet")
    assert greet_tool["description"] == "Greet someone."
    assert "name" in greet_tool["inputSchema"]["properties"]


def test_serve_mcp_rejects_unsupported_transport() -> None:
    """serve_mcp should reject unsupported MCP transport values."""
    app = Tooli(name="test-mcp")

    with pytest.raises(ValueError, match="Unsupported MCP transport: websocket"):
        serve_mcp(app, transport="websocket")


def test_serve_mcp_forwards_transport_args(monkeypatch) -> None:
    """serve_mcp should pass host/port and transport to FastMCP.run."""
    app = Tooli(name="test-mcp")
    run_state: dict[str, object] = {"kwargs": None}

    class FakeFastMCP:
        def __init__(self, name: str) -> None:
            self.name = name

        def tool(self, *, name: str | None = None, description: str = "", **_kwargs: object) -> object:
            def _register(callback: object) -> object:
                return callback

            return _register

        def run(self, **kwargs: object) -> None:
            run_state["kwargs"] = kwargs

    monkeypatch.setitem(sys.modules, "fastmcp", types.SimpleNamespace(FastMCP=FakeFastMCP))
    serve_mcp(app, transport="http", host="127.0.0.1", port=5000)
    assert run_state["kwargs"] == {"transport": "http", "host": "127.0.0.1", "port": 5000}
