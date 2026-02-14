"""Tests for transform pipeline and provider system."""

from __future__ import annotations

import json
from tooli import Tooli
from tooli.transforms import NamespaceTransform, VisibilityTransform
from tooli.testing import TooliTestClient


def test_namespace_transform() -> None:
    app = Tooli(name="test-app")

    @app.command()
    def greet() -> str:
        return "hello"

    view = app.with_transforms(NamespaceTransform("git"))
    
    tools = view.get_tools()
    assert any(t.name == "git_greet" for t in tools)


def test_visibility_transform() -> None:
    app = Tooli(name="test-app")

    @app.command()
    def public() -> str:
        return "public"

    @app.command(hidden=True)
    def private() -> str:
        return "private"

    # Default view includes everything from providers if no transforms
    tools = app.get_tools()
    assert any(t.name == "public" for t in tools)
    assert any(t.name == "private" for t in tools)

    # View with include_hidden=False
    view = app.with_transforms(VisibilityTransform(include_hidden=False))
    tools = view.get_tools()
    assert any(t.name == "public" for t in tools)
    assert not any(t.name == "private" for t in tools)


def test_mcp_export_with_transforms() -> None:
    app = Tooli(name="test-app")

    @app.command()
    def status() -> str:
        return "ok"

    view = app.with_transforms(NamespaceTransform("sys"))
    
    from tooli.mcp.export import export_mcp_tools
    tools = export_mcp_tools(view)
    
    assert any(t["name"] == "sys_status" for t in tools)
