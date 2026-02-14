"""Tests for secret input handling."""

from __future__ import annotations

import io
import json
import warnings
from pathlib import Path
from typing import Annotated

import pytest
import typer
from typer.testing import CliRunner

from tooli import SecretInput, Tooli
from tooli.input import read_secret_value_from_file, read_secret_value_from_stdin, redact_secret_values, resolve_secret_value


def test_resolve_secret_from_file(tmp_path: Path) -> None:
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("token-abc\n")
    assert read_secret_value_from_file(str(secret_file)) == "token-abc"


def test_resolve_secret_from_stdin(monkeypatch) -> None:
    stream = io.StringIO("from-stdin\n")
    monkeypatch.setattr("sys.stdin", stream)
    assert read_secret_value_from_stdin() == "from-stdin"


def test_resolve_secret_from_env_with_deprecation(monkeypatch) -> None:
    monkeypatch.setenv("TOOLI_SECRET_TOKEN", "env-token")

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        resolved = resolve_secret_value(explicit_value=None, param_name="token")

    assert resolved == "env-token"
    assert any("deprecated" in str(w.message).lower() for w in captured)


def test_redact_secret_values_nested_output() -> None:
    payload = {"api_key": "abc123", "nested": ["abc123", "safe"]}
    redacted = redact_secret_values(payload, ["abc123"])
    assert redacted == {"api_key": "***REDACTED***", "nested": ["***REDACTED***", "safe"]}


def test_secret_in_command_is_redacted_in_json_output(tmp_path: Path) -> None:
    app = Tooli(name="secret-tool")

    @app.command()
    def reveal(
        token: Annotated[SecretInput[str], typer.Option(help="Secret token")] = None,
    ) -> dict[str, str]:
        return {"token": token or ""}

    secret_file = tmp_path / "token.txt"
    secret_file.write_text("very-secret")

    runner = CliRunner()
    result = runner.invoke(app, ["reveal", "--secret-file", str(secret_file)])
    assert result.exit_code == 0

    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["result"]["token"] == "***REDACTED***"


def test_secret_in_command_is_redacted_in_text_output(tmp_path: Path) -> None:
    app = Tooli(name="secret-tool")

    @app.command()
    def reveal(token: Annotated[SecretInput[str], typer.Option(help="Secret token")] = None) -> str:
        return token or ""

    secret_file = tmp_path / "token.txt"
    secret_file.write_text("very-secret")

    runner = CliRunner()
    result = runner.invoke(app, ["reveal", "--secret-file", str(secret_file), "--text"])
    assert result.exit_code == 0
    assert result.output.strip() == "***REDACTED***"


def test_secret_in_error_output_is_redacted(monkeypatch) -> None:
    app = Tooli(name="secret-tool")

    @app.command()
    def fail(token: Annotated[SecretInput[str], typer.Option(help="Secret token")] = None) -> None:
        raise ValueError(f"bad token: {token}")

    monkeypatch.setenv("TOOLI_SECRET_TOKEN", "exploit")
    runner = CliRunner()
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        result = runner.invoke(app, ["fail", "--text"])

    assert result.exit_code == 70
    assert "***REDACTED***" in result.output
    assert "exploit" not in result.output
