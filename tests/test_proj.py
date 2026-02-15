"""Tests for the proj example app."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from examples.proj.app import app

if TYPE_CHECKING:
    from pathlib import Path


def _run_json(runner: CliRunner, args: list[str], **kwargs: object):
    result = runner.invoke(app, args, **kwargs)
    assert result.exit_code == 0, result.output
    for line in reversed(result.output.strip().splitlines()):
        data = json.loads(line)
        if "ok" in data:
            return data["result"]
    raise AssertionError("No envelope found in output")


def test_proj_init(tmp_path: Path) -> None:
    runner = CliRunner()

    result = _run_json(runner, ["init", "myapp", "--directory", str(tmp_path), "--yes"])
    assert result["project"] == "myapp"
    assert result["template"] == "python"
    assert result["file_count"] >= 5

    project_dir = tmp_path / "myapp"
    assert project_dir.exists()
    assert (project_dir / "pyproject.toml").exists()
    assert (project_dir / "README.md").exists()
    assert (project_dir / "src" / "myapp" / "__init__.py").exists()


def test_proj_init_dry_run(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["init", "dryapp", "--directory", str(tmp_path), "--dry-run", "--yes"])
    assert result.exit_code == 0

    # Parse the envelope line (skip security audit lines)
    payload = None
    for line in reversed(result.output.strip().splitlines()):
        data = json.loads(line)
        if "ok" in data:
            payload = data
            break
    assert payload is not None

    # In dry-run mode, DryRunRecorder returns the action list
    actions = payload["result"]
    assert isinstance(actions, list)
    assert len(actions) >= 5
    assert all(a["action"] == "create_file" for a in actions)

    # Files should NOT actually exist
    assert not (tmp_path / "dryapp").exists()


def test_proj_init_cli_template(tmp_path: Path) -> None:
    runner = CliRunner()

    result = _run_json(runner, ["init", "mycli", "--template", "cli", "--directory", str(tmp_path), "--yes"])
    assert result["template"] == "cli"
    assert (tmp_path / "mycli" / "src" / "mycli" / "cli.py").exists()


def test_proj_validate(tmp_path: Path) -> None:
    runner = CliRunner()

    _run_json(runner, ["init", "validproj", "--directory", str(tmp_path), "--yes"])
    result = _run_json(runner, ["validate", "--directory", str(tmp_path / "validproj")])
    assert result["valid"] is True
    assert result["has_src_package"] is True
    assert result["has_tests"] is True


def test_proj_validate_missing(tmp_path: Path) -> None:
    runner = CliRunner()

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    result = _run_json(runner, ["validate", "--directory", str(empty_dir)])
    assert result["valid"] is False
    assert "pyproject.toml" in result["missing"]


def test_proj_add_tool(tmp_path: Path) -> None:
    runner = CliRunner()

    _run_json(runner, ["init", "toolproj", "--directory", str(tmp_path), "--yes"])
    result = _run_json(runner, ["add-tool", "greet", "--directory", str(tmp_path / "toolproj"), "--yes"])
    assert len(result["files_created"]) == 2
    assert (tmp_path / "toolproj" / "src" / "toolproj" / "greet.py").exists()
