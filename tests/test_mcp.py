"""Tests for MCP integration."""

from __future__ import annotations

import json
from tooli import Tooli
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
