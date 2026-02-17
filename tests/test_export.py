"""Tests for framework export generation builtins."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from typer.testing import CliRunner

from tooli import Argument, Option, StdinOr, Tooli
from tooli.annotations import Destructive, ReadOnly


def _build_app() -> Tooli:
    app = Tooli(name="sample-tool", help="Search and patch local files")

    @app.command(annotations=ReadOnly)
    def find_files(
        pattern: Annotated[str, Argument(help="Glob pattern to match")],
        root: Annotated[Path, Option(help="Root directory")] = Path("."),
        tags: Annotated[list[str] | None, Option(help="Optional tag filter")] = None,
        source: Annotated[StdinOr[str], Option(help="Path, URL, or '-' for stdin")] = "-",
    ) -> list[dict[str, str]]:
        """Find files matching a glob pattern in a directory tree."""
        return [{"pattern": pattern, "root": str(root), "source": str(source), "tags": str(tags)}]

    @app.command(annotations=Destructive)
    def replace_text(
        file_path: Annotated[str, Argument(help="File path to patch")],
        search: Annotated[str, Option(help="Exact text to find")] = "",
        replace: Annotated[str, Option(help="Replacement text")] = "",
        dry_run: Annotated[bool, Option(help="Preview changes without writing")] = False,
    ) -> dict[str, int]:
        """Replace text in a file."""
        del file_path, search, replace
        return {"replacements": 0 if dry_run else 1}

    return app


def test_export_builtin_registered_hidden() -> None:
    app = Tooli(name="registry-check")
    export_cmd = next((cmd for cmd in app.registered_commands if cmd.name == "export"), None)
    assert export_cmd is not None
    assert export_cmd.hidden is True


def test_export_requires_target() -> None:
    app = _build_app()
    runner = CliRunner()
    result = runner.invoke(app, ["export"])
    assert result.exit_code == 2
    assert "--target" in result.output


def test_export_validates_target_and_mode() -> None:
    app = _build_app()
    runner = CliRunner()

    bad_target = runner.invoke(app, ["export", "--target", "unknown"])
    assert bad_target.exit_code == 2
    assert "target must be one of" in bad_target.output

    bad_mode = runner.invoke(app, ["export", "--target", "openai", "--mode", "broken"])
    assert bad_mode.exit_code == 2
    assert "mode must be one of" in bad_mode.output


def test_export_openai_subprocess_generation() -> None:
    app = _build_app()
    runner = CliRunner()
    result = runner.invoke(app, ["export", "--target", "openai"])
    assert result.exit_code == 0
    assert "@function_tool" in result.output
    assert "TOOLI_CALLER': 'openai-agents-sdk'" in result.output
    assert "def find_files(" in result.output
    assert "root: str = '.'" in result.output
    assert "tags: str | None = None" in result.output
    assert "source: str = '-'" in result.output
    compile(result.output, "<openai-export>", "exec")


def test_export_openai_import_mode_and_command_filter() -> None:
    app = _build_app()
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["export", "--target", "openai", "--mode", "import", "--command", "find-files"],
    )
    assert result.exit_code == 0
    assert "app.call('find-files'" in result.output
    assert "json.dumps({'ok': result.ok" in result.output
    assert "def replace_text(" not in result.output
    compile(result.output, "<openai-import-export>", "exec")


def test_export_langchain_generation_modes() -> None:
    app = _build_app()
    runner = CliRunner()

    subprocess_result = runner.invoke(app, ["export", "--target", "langchain"])
    assert subprocess_result.exit_code == 0
    assert "from langchain_core.tools import tool" in subprocess_result.output
    assert "TOOLI_CALLER': 'langchain'" in subprocess_result.output
    assert "raise ValueError" in subprocess_result.output
    compile(subprocess_result.output, "<langchain-export>", "exec")

    import_result = runner.invoke(
        app,
        ["export", "--target", "langchain", "--mode", "import", "--command", "replace-text"],
    )
    assert import_result.exit_code == 0
    assert "result = app.call('replace-text'" in import_result.output
    assert "raise ValueError(message)" in import_result.output
    compile(import_result.output, "<langchain-import-export>", "exec")


def test_export_adk_yaml_contains_mcp_server_and_instruction() -> None:
    app = _build_app()
    runner = CliRunner()
    result = runner.invoke(app, ["export", "--target", "adk"])
    assert result.exit_code == 0
    assert "name: sample-tool-agent" in result.output
    assert "model: gemini-2.0-flash" in result.output
    assert "tools:" in result.output
    assert "server_command: sample-tool mcp serve --transport stdio" in result.output
    assert "uses the sample-tool CLI for Search and patch local files." in result.output


def test_export_python_wrapper_generation() -> None:
    app = _build_app()
    runner = CliRunner()
    result = runner.invoke(app, ["export", "--target", "python"])
    assert result.exit_code == 0
    assert "from sample_tool import app" in result.output
    assert "def find_files(" in result.output
    assert "-> list[dict[str, str]]:" in result.output
    assert "return app.call('find-files'" in result.output
    assert ").unwrap()" in result.output
    compile(result.output, "<python-export>", "exec")


def test_export_command_filter_rejects_unknown_command() -> None:
    app = _build_app()
    runner = CliRunner()
    result = runner.invoke(app, ["export", "--target", "python", "--command", "nope"])
    assert result.exit_code == 2
    assert "Unknown command 'nope'" in result.output
