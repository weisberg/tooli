"""Tests for the syswatch example app."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from examples.syswatch.app import app


def _run_json(runner: CliRunner, args: list[str], **kwargs: object):
    result = runner.invoke(app, args, **kwargs)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    return payload["result"]


def test_syswatch_status() -> None:
    runner = CliRunner()
    result = _run_json(runner, ["status"])
    assert "hostname" in result
    assert "os" in result
    assert "python" in result
    assert "cpu_count" in result
    assert result["cpu_count"] is None or result["cpu_count"] > 0


def test_syswatch_disk() -> None:
    runner = CliRunner()
    result = _run_json(runner, ["disk"])
    assert len(result) >= 1
    entry = result[0]
    assert "total_gb" in entry
    assert "used_gb" in entry
    assert "free_gb" in entry
    assert "percent_used" in entry
    assert entry["total_gb"] > 0


def test_syswatch_watch_single() -> None:
    runner = CliRunner()
    result = _run_json(runner, ["watch", "--checks", "1"])
    assert result["check_count"] == 1
    assert len(result["snapshots"]) == 1
    snapshot = result["snapshots"][0]
    assert snapshot["check"] == 1
    assert "cpu_count" in snapshot


def test_syswatch_watch_multiple() -> None:
    runner = CliRunner()
    result = _run_json(runner, ["watch", "--checks", "2", "--interval", "0.1"])
    assert result["check_count"] == 2
    assert len(result["snapshots"]) == 2


def test_syswatch_disk_invalid_path() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["disk", "--path", "/nonexistent/path/xyz"])
    assert result.exit_code != 0
