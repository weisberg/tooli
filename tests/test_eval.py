"""Tests for invocation recording and evaluation analysis."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from tooli import Tooli
from tooli.errors import InputError
from tooli.eval import analyze_invocations


def test_eval_record_and_analyze_from_invocations(tmp_path) -> None:
    log_path = tmp_path / "invocations.jsonl"
    app = Tooli(name="eval-app", record=str(log_path))
    runner = CliRunner()

    @app.command()
    def add(a: int, b: int) -> int:
        if a == 0:
            raise InputError(message="zero is not allowed", code="E1003")
        return a + b

    @app.command()
    def echo(message: str) -> str:
        return message

    assert runner.invoke(app, ["add", "1", "2", "--text"]).exit_code == 0
    assert runner.invoke(app, ["add", "0", "2", "--text"]).exit_code != 0
    assert runner.invoke(app, ["add", "3", "4", "--text"]).exit_code == 0
    assert runner.invoke(app, ["echo", "hello", "--text"]).exit_code == 0
    assert runner.invoke(app, ["echo", "hello", "--text"]).exit_code == 0
    assert runner.invoke(app, ["echo", "world", "--text"]).exit_code == 0

    analysis = analyze_invocations(log_path)
    assert analysis["total_invocations"] == 6
    assert analysis["invocations_per_command"]["eval-app.add"] == 3
    assert analysis["invocations_per_command"]["eval-app.echo"] == 3
    assert analysis["invalid_parameter_rate"]["eval-app.add"] == 1 / 3
    assert analysis["most_common_error_codes"] == [{"code": "E1003", "count": 1}]

    duplicate = analysis["duplicate_invocations"]
    assert any(
        item["command"] == "eval-app.echo"
        and item["args"] == {"message": "hello"}
        and item["count"] == 2
        for item in duplicate
    )

    assert analysis["average_duration_ms_per_command"]["eval-app.add"] >= 0
    assert analysis["average_duration_ms_per_command"]["eval-app.echo"] >= 0


def test_eval_analyze_command_with_file_path(tmp_path) -> None:
    log_path = tmp_path / "invocations.jsonl"
    app = Tooli(name="eval-app", record=str(log_path))
    runner = CliRunner()

    @app.command()
    def noop() -> dict[str, str]:
        return {"status": "ok"}

    assert runner.invoke(app, ["noop", "--text"]).exit_code == 0

    result = runner.invoke(app, ["eval", "analyze", "--log-path", str(log_path)])
    assert result.exit_code == 0

    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["result"]["total_invocations"] == 1
    assert payload["result"]["invocations_per_command"]["eval-app.noop"] == 1


@pytest.mark.parametrize("path", ["", "   "])
def test_eval_no_path_fails_gracefully(monkeypatch, path: str) -> None:
    monkeypatch.setenv("TOOLI_RECORD", path)
    app = Tooli(name="eval-app")
    app.invocation_recorder = None

    @app.command()
    def noop() -> dict[str, str]:
        return {"status": "ok"}

    result = CliRunner().invoke(app, ["eval", "analyze"])
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert "No log path provided" in payload["result"]["error"]
