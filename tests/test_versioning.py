"""Tests for tool versioning and version filtering."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from tooli import Tooli, VersionFilter
from tooli.testing import TooliTestClient


def _parse_last_json_line(output: str) -> dict:
    for line in reversed(output.strip().splitlines()):
        if not line.strip():
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise AssertionError(f"No JSON object found in output: {output!r}")


def test_versioned_commands_default_to_latest_name() -> None:
    """Registering multiple versions should expose the latest by default."""
    app = Tooli(name="versioned-app")

    @app.command(name="search", version="1.0.0")
    def search_v1(path: str) -> str:
        return f"legacy:{path}"

    @app.command(name="search", version="2.0.0")
    def search_v2(path: str) -> str:
        return f"current:{path}"

    runner = CliRunner()
    latest = runner.invoke(app, ["search", "/tmp/example.txt", "--text"])
    assert latest.exit_code == 0
    assert latest.output.strip() == "current:/tmp/example.txt"

    v1 = runner.invoke(app, ["search-v1.0.0", "/tmp/example.txt", "--text"])
    assert v1.exit_code == 0
    assert v1.output.strip() == "legacy:/tmp/example.txt"


def test_schema_includes_version_and_deprecated_metadata() -> None:
    """Schema output should include tool version and deprecation fields."""
    app = Tooli(name="versioned-app")

    @app.command(
        name="old-command",
        version="1.0.0",
        deprecated=True,
        deprecated_message="Use new-command instead.",
        deprecated_version="2.0.0",
    )
    def old(path: str) -> dict[str, str]:
        return {"path": path}

    runner = CliRunner()
    response = runner.invoke(app, ["old-command-v1.0.0", "/tmp/example", "--schema", "--text"])
    assert response.exit_code == 0
    payload = json.loads(response.output)

    assert payload["version"] == "1.0.0"
    assert payload["deprecated"] is True
    assert payload["deprecated_message"] == "Use new-command instead."
    assert payload["deprecated_version"] == "2.0.0"


def test_deprecated_command_warns_before_removal_version() -> None:
    app = Tooli(name="versioned-app", version="1.9.9")

    @app.command(
        name="legacy",
        version="1.0.0",
        deprecated=True,
        deprecated_message="Use modern command instead.",
        deprecated_version="2.0.0",
    )
    def legacy() -> str:
        return "ok"

    runner = CliRunner()
    result = runner.invoke(app, ["legacy", "--json"])
    assert result.exit_code == 0
    payload = _parse_last_json_line(result.output)
    assert payload["ok"] is True
    warnings = payload["meta"].get("warnings", [])
    assert any("Use modern command instead." in warning for warning in warnings)
    assert any("Scheduled for removal in v2.0.0." in warning for warning in warnings)


def test_removed_command_returns_structured_migration_error() -> None:
    app = Tooli(name="versioned-app", version="2.0.0")

    @app.command(
        name="legacy",
        version="1.0.0",
        deprecated=True,
        deprecated_message="Use modern command instead.",
        deprecated_version="2.0.0",
    )
    def legacy() -> str:
        return "ok"

    runner = CliRunner()
    result = runner.invoke(app, ["legacy", "--json"])
    assert result.exit_code == 2
    payload = _parse_last_json_line(result.output)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "E1001"
    assert payload["error"]["suggestion"]["action"] == "migrate command usage"
    assert payload["error"]["suggestion"]["fix"] == "Use modern command instead."
    assert payload["error"]["details"]["deprecated_version"] == "2.0.0"


def test_version_filter_transform() -> None:
    """VersionFilter should keep commands that fall within the selected range."""
    app = Tooli(name="versioned-app")

    @app.command(name="transform", version="1.0.0")
    def old(input: str) -> str:
        return f"v1:{input}"

    @app.command(name="transform", version="1.1.0")
    def mid(input: str) -> str:
        return f"v2:{input}"

    @app.command(name="transform", version="2.0.0")
    def latest(input: str) -> str:
        return f"v3:{input}"

    transformer = VersionFilter(min_version="1.1.0", max_version="2.0.0")
    transformed = transformer.apply(app.registered_commands)
    names = {cmd.name for cmd in transformed if cmd is not None}

    assert "transform-v1.0.0" not in names
    assert "transform-v1.1.0" in names
    assert "transform" in names
    assert "transform-v2.0.0" in names


def test_mcp_export_uses_schema_filtering_for_hidden_versions() -> None:
    """MCP export should not include hidden historical version commands."""
    app = Tooli(name="versioned-app")

    @app.command(name="clean", version="1.0.0")
    def clean_v1() -> None:
        return None

    @app.command(name="clean", version="1.1.0")
    def clean_v11() -> None:
        return None

    client = TooliTestClient(app)
    result = client.invoke(["mcp", "export"])
    assert result.exit_code == 0

    tools = json.loads(result.output)
    names = {tool["name"] for tool in tools}
    assert "clean-v1.0.0" not in names
    assert "clean-v1.1.0" not in names
    assert "clean" in names
    clean_tool = next(tool for tool in tools if tool["name"] == "clean")
    assert clean_tool["version"] == "1.1.0"
