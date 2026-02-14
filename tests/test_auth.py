"""Tests for command authorization scopes."""

from __future__ import annotations

from typer.testing import CliRunner

from tooli import Tooli
from tooli.schema import generate_tool_schema


def test_authorized_command_executes_with_required_scopes() -> None:
    app = Tooli(name="auth-app", auth_scopes=["scopes:read"])
    runner = CliRunner()

    @app.command(auth=["scopes:read"])
    def read_only() -> str:
        return "ok"

    result = runner.invoke(app, ["read-only", "--text"])
    assert result.exit_code == 0
    assert result.output.strip() == "ok"


def test_unauthorized_command_rejected() -> None:
    app = Tooli(name="auth-app")
    runner = CliRunner()

    @app.command(auth=["scopes:write"])
    def write() -> str:
        return "ok"

    result = runner.invoke(app, ["write", "--text"])
    assert result.exit_code == 30
    assert result.exit_code != 0


def test_auth_scopes_resolve_from_env(monkeypatch) -> None:
    monkeypatch.setenv("TOOLI_AUTH_SCOPES", "scopes:admin")
    app = Tooli(name="auth-app")
    runner = CliRunner()

    @app.command(auth=["scopes:admin"])
    def admin() -> str:
        return "admin"

    result = runner.invoke(app, ["admin", "--text"])
    assert result.exit_code == 0
    assert result.output.strip() == "admin"


def test_schema_includes_auth_requirements() -> None:
    app = Tooli(name="auth-app")

    @app.command(auth=["scopes:one", "scopes:two"])
    def scoped() -> str:
        return "ok"

    result = CliRunner().invoke(app, ["scoped", "--help-agent", "--text"])
    assert result.exit_code == 0
    assert "auth=scopes:one,scopes:two" in result.output

    schema = generate_tool_schema(scoped, name="auth-app.scoped")
    assert schema.auth == ["scopes:one", "scopes:two"]
