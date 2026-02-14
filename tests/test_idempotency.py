"""Tests for command idempotency keys."""

from __future__ import annotations

import typer
from typer.testing import CliRunner

from tooli import Tooli
from tooli.annotations import Idempotent


def test_idempotent_command_reuses_cached_result_for_duplicate_key() -> None:
    app = Tooli(name="idem-app")
    state = {"runs": 0}

    @app.command(annotations=Idempotent)
    def increment() -> int:
        state["runs"] += 1
        return state["runs"]

    runner = CliRunner()
    first = runner.invoke(app, ["increment", "--idempotency-key", "k-repeat", "--text"])
    second = runner.invoke(app, ["increment", "--idempotency-key", "k-repeat", "--text"])

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert first.output.strip() == "1"
    assert second.output.strip() == "1"
    assert state["runs"] == 1


def test_non_idempotent_duplicate_key_returns_error() -> None:
    app = Tooli(name="idem-app")

    @app.command()
    def bump() -> str:
        return "ok"

    runner = CliRunner()
    first = runner.invoke(app, ["bump", "--idempotency-key", "k-dup", "--text"])
    second = runner.invoke(app, ["bump", "--idempotency-key", "k-dup", "--text"])

    assert first.exit_code == 0
    assert second.exit_code != 0
    assert "Duplicate idempotency key" in second.output


def test_idempotency_key_visible_in_context() -> None:
    app = Tooli(name="idem-app")
    observed: dict[str, str | None] = {"key": None}

    @app.command()
    def report(ctx: typer.Context) -> str:
        assert ctx.obj is not None
        observed["key"] = ctx.obj.idempotency_key
        return "ok"

    result = CliRunner().invoke(app, ["report", "--idempotency-key", "ctx-key", "--text"])
    assert result.exit_code == 0
    assert observed["key"] == "ctx-key"
