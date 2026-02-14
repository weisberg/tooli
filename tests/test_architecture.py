"""Tests for transform pipeline and provider system."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pytest

from tooli import Tooli
from tooli.providers import FileSystemProvider
from tooli.testing import TooliTestClient
from tooli.transforms import NamespaceTransform, VisibilityTransform


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


@pytest.mark.xfail(reason="Typer help rendering doesn't yet delegate to get_tools()")
def test_help_uses_transformed_names() -> None:
    app = Tooli(name="test-app")

    @app.command()
    def hello() -> str:
        return "ok"

    runner = TooliTestClient(app.with_transforms(NamespaceTransform("demo"))).invoke(["--help"])

    assert runner.exit_code == 0
    assert "demo_hello" in runner.output


def test_filesystem_provider_discovers_tools(tmp_path: Path) -> None:
    module_path = tmp_path / "dyn.py"
    module_path.write_text(
        '''
from tooli.command_meta import CommandMeta


def public_tool() -> str:
    """Public tool."""
    return "ok"


def hidden_tool() -> str:
    """Hidden tool."""
    return "secret"

public_tool.__tooli_meta__ = CommandMeta(version="1.0.0")
hidden_tool.__tooli_meta__ = CommandMeta(hidden=True)
'''
    )

    app = Tooli(name="provider-app")
    app.add_provider(FileSystemProvider(tmp_path))

    tools = app.get_tools()
    tool_names = {tool.name for tool in tools}
    assert "public_tool" in tool_names
    assert "hidden_tool" in tool_names
    assert any(tool.name == "hidden_tool" and tool.hidden for tool in tools)

    visible = app.with_transforms(VisibilityTransform()).get_tools()
    assert any(tool.name == "public_tool" for tool in visible)
    assert not any(tool.name == "hidden_tool" for tool in visible)
