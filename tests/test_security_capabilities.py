"""Tests for security policy capability enforcement (#162)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from tooli import Tooli
from tooli.annotations import Destructive, ReadOnly


def _find_envelope(output: str) -> dict:
    """Find the error envelope line in output (may include audit events on stderr)."""
    for line in output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if "ok" in data:
                return data
        except (json.JSONDecodeError, ValueError):
            continue
    msg = f"No envelope found in output: {output!r}"
    raise ValueError(msg)


def test_strict_mode_blocks_denied_capabilities(monkeypatch) -> None:
    monkeypatch.setenv("TOOLI_ALLOWED_CAPABILITIES", "fs:read,net:read")

    app = Tooli(name="sec-app", security_policy="strict")
    runner = CliRunner()

    @app.command(capabilities=["fs:read", "fs:write"])
    def write_files(path: str) -> str:
        return f"wrote {path}"

    result = runner.invoke(app, ["write-files", "test.txt", "--json"])
    assert result.exit_code != 0
    data = _find_envelope(result.output)
    assert data["ok"] is False
    assert "fs:write" in data["error"]["message"]
    assert data["error"]["code"] == "E2002"


def test_strict_mode_allows_matching_capabilities(monkeypatch) -> None:
    monkeypatch.setenv("TOOLI_ALLOWED_CAPABILITIES", "fs:read,net:read")

    app = Tooli(name="sec-app", security_policy="strict")
    runner = CliRunner()

    @app.command(annotations=ReadOnly, capabilities=["fs:read"])
    def read_files(path: str) -> str:
        return f"read {path}"

    result = runner.invoke(app, ["read-files", "test.txt", "--text"])
    assert result.exit_code == 0
    assert "read test.txt" in result.output


def test_strict_mode_wildcard_capabilities(monkeypatch) -> None:
    monkeypatch.setenv("TOOLI_ALLOWED_CAPABILITIES", "fs:*")

    app = Tooli(name="sec-app", security_policy="strict")
    runner = CliRunner()

    @app.command(capabilities=["fs:read", "fs:write", "fs:delete"])
    def manage_files(action: str) -> str:
        return f"done: {action}"

    result = runner.invoke(app, ["manage-files", "cleanup", "--text"])
    assert result.exit_code == 0


def test_no_allowlist_skips_enforcement(monkeypatch) -> None:
    monkeypatch.delenv("TOOLI_ALLOWED_CAPABILITIES", raising=False)

    app = Tooli(name="sec-app", security_policy="strict")
    runner = CliRunner()

    @app.command(capabilities=["fs:write", "net:write"])
    def dangerous_op() -> str:
        return "executed"

    # No --yes needed since not destructive annotation
    result = runner.invoke(app, ["dangerous-op", "--text"])
    assert result.exit_code == 0


def test_standard_mode_ignores_capability_enforcement(monkeypatch) -> None:
    monkeypatch.setenv("TOOLI_ALLOWED_CAPABILITIES", "fs:read")

    app = Tooli(name="sec-app", security_policy="standard")
    runner = CliRunner()

    @app.command(capabilities=["fs:write"])
    def write_op() -> str:
        return "wrote"

    result = runner.invoke(app, ["write-op", "--text"])
    assert result.exit_code == 0


def test_off_mode_ignores_capability_enforcement(monkeypatch) -> None:
    monkeypatch.setenv("TOOLI_ALLOWED_CAPABILITIES", "fs:read")

    app = Tooli(name="sec-app", security_policy="off")
    runner = CliRunner()

    @app.command(capabilities=["fs:write"])
    def write_op() -> str:
        return "wrote"

    result = runner.invoke(app, ["write-op", "--text"])
    assert result.exit_code == 0


def test_no_capabilities_skips_enforcement(monkeypatch) -> None:
    monkeypatch.setenv("TOOLI_ALLOWED_CAPABILITIES", "fs:read")

    app = Tooli(name="sec-app", security_policy="strict")
    runner = CliRunner()

    @app.command()
    def simple() -> str:
        return "ok"

    result = runner.invoke(app, ["simple", "--text"])
    assert result.exit_code == 0


def test_destructive_still_requires_confirmation_in_strict() -> None:
    """Verify existing destructive enforcement isn't broken."""
    app = Tooli(name="sec-app", security_policy="strict")
    runner = CliRunner()

    @app.command(annotations=Destructive, capabilities=["fs:delete"])
    def wipe() -> str:
        return "wiped"

    # Without --yes, should be blocked
    denied = runner.invoke(app, ["wipe", "--text"])
    assert denied.exit_code == 2

    # With --yes, should work (no allowlist, so no capability block)
    with_yes = runner.invoke(app, ["wipe", "--yes", "--text"])
    assert with_yes.exit_code == 0
