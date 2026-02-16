"""Tests for Tooli orchestration runtime."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from tooli import Tooli


def test_orchestrate_run_plan_from_json() -> None:
    """JSON plan payload should execute multiple commands in order."""
    app = Tooli(name="orch-app")

    @app.command()
    def add(a: int, b: int) -> int:
        return a + b

    @app.command()
    def echo(message: str) -> str:
        return message

    payload = json.dumps(
        [
            {"command": "add", "arguments": {"a": 2, "b": 3}},
            {"command": "echo", "arguments": {"message": "done"}},
        ]
    )

    result = CliRunner().invoke(app, ["orchestrate", "run"], input=payload)
    assert result.exit_code == 0

    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    assert envelope["result"]["ok"] is True
    assert envelope["result"]["steps_executed"] == 2
    assert envelope["result"]["results"][0]["result"] == 5
    assert envelope["result"]["results"][1]["result"] == "done"


def test_orchestrate_run_plan_fails_fast_by_default() -> None:
    """Orchestration should stop at first failed command when continue_on_error is false."""
    app = Tooli(name="orch-app")

    @app.command()
    def add(a: int, b: int) -> int:
        return a + b

    payload = json.dumps(
        [
            {"command": "does-not-exist", "arguments": {}},
            {"command": "add", "arguments": {"a": 1, "b": 1}},
        ]
    )

    result = CliRunner().invoke(app, ["orchestrate", "run", "--json"], input=payload)
    assert result.exit_code == 0

    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    assert envelope["result"]["ok"] is False
    assert envelope["result"]["steps_executed"] == 0
    assert envelope["result"]["errors"][0]["command"] == "does-not-exist"
    assert envelope["result"]["summary"]["failed"] == 1


def test_orchestrate_run_plan_continue_on_error() -> None:
    """Orchestration should continue when continue_on_error is enabled."""
    app = Tooli(name="orch-app")

    @app.command()
    def add(a: int, b: int) -> int:
        return a + b

    payload = json.dumps(
        [
            {"command": "does-not-exist", "arguments": {}},
            {"command": "add", "arguments": {"a": 1, "b": 2}},
        ]
    )

    result = CliRunner().invoke(
        app,
        ["orchestrate", "run", "--continue-on-error", "--json"],
        input=payload,
    )
    assert result.exit_code == 0

    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    assert envelope["result"]["ok"] is False
    assert envelope["result"]["steps_executed"] == 1
    assert envelope["result"]["errors"]
    assert envelope["result"]["results"][0]["result"] == 3


def test_orchestrate_run_plan_from_python_expression() -> None:
    """Python expression mode should accept executable plan payloads from stdin."""
    app = Tooli(name="orch-app")

    @app.command()
    def multiply(a: int, b: int) -> int:
        return a * b

    expression = "[{'command': 'multiply', 'arguments': {'a': 4, 'b': 5}}]"
    result = CliRunner().invoke(app, ["orchestrate", "run", "--python"], input=expression)
    assert result.exit_code == 0

    envelope = json.loads(result.output)
    assert envelope["ok"] is True
    assert envelope["result"]["results"][0]["result"] == 20
