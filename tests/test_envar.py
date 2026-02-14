"""Tests for the envar example app."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from examples.envar.app import app

if TYPE_CHECKING:
    from pathlib import Path

SAMPLE_ENV = """\
DATABASE_URL=postgres://localhost/mydb
API_KEY=secret123
DEBUG=true
APP_NAME=myapp
"""


def _run_json(runner: CliRunner, args: list[str], **kwargs: object):
    result = runner.invoke(app, args, **kwargs)
    assert result.exit_code == 0, result.output
    for line in reversed(result.output.strip().splitlines()):
        data = json.loads(line)
        if "ok" in data:
            return data["result"]
    raise AssertionError("No envelope found in output")


def test_envar_get(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(SAMPLE_ENV, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["get", "API_KEY", "--env-file", str(env_file)])
    assert result["name"] == "API_KEY"
    assert result["value"] == "secret123"
    assert result["source"] == "file"


def test_envar_get_not_found(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(SAMPLE_ENV, encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(app, ["get", "NONEXISTENT", "--env-file", str(env_file)])
    assert result.exit_code != 0


def test_envar_set(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(SAMPLE_ENV, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["set", "NEW_VAR", "hello", "--env-file", str(env_file), "--yes"])
    assert result["written"] is True
    assert result["overwritten"] is False

    get_result = _run_json(runner, ["get", "NEW_VAR", "--env-file", str(env_file)])
    assert get_result["value"] == "hello"


def test_envar_list_masked(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(SAMPLE_ENV, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["list", "--env-file", str(env_file)])
    assert len(result) >= 4
    assert all(r["value"] == "***" for r in result)
    assert all(r["masked"] is True for r in result)


def test_envar_list_show_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(SAMPLE_ENV, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["list", "--env-file", str(env_file), "--show-values"])
    assert any(r["value"] != "***" for r in result)


def test_envar_validate(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(SAMPLE_ENV, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["validate", "--env-file", str(env_file), "--require", "DATABASE_URL,API_KEY,MISSING_VAR"])
    assert result["valid"] is False
    assert "MISSING_VAR" in result["missing"]
    assert "DATABASE_URL" in result["present"]


def test_envar_export_json(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(SAMPLE_ENV, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["export", "--env-file", str(env_file), "--format", "json"])
    assert result["format"] == "json"
    assert result["variable_count"] >= 4
    assert result["variables"]["DEBUG"] == "true"


def test_envar_list_with_prefix(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(SAMPLE_ENV, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["list", "--env-file", str(env_file), "--prefix", "APP_"])
    assert len(result) == 1
    assert result[0]["name"] == "APP_NAME"
