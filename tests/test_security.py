"""Tests for security policy enforcement and output sanitization."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from tooli import Tooli
from tooli.annotations import Destructive


def test_standard_mode_sanitizes_and_requires_force_or_yes() -> None:
    app = Tooli(name="sec-app", security_policy="standard")
    runner = CliRunner()

    @app.command(annotations=Destructive)
    def wipe(target: str) -> str:
        return f"\x1b[31mRemoving\x1b[0m {target}; $(rm -rf /)"

    denied = runner.invoke(app, ["wipe", "files", "--text"])
    assert denied.exit_code == 2

    with_force = runner.invoke(app, ["wipe", "files", "--force", "--text"])
    assert with_force.exit_code == 0
    assert "\x1b[31m" not in with_force.output
    assert "$(" not in with_force.output

    with_yes = runner.invoke(app, ["wipe", "files", "--yes", "--text"])
    assert with_yes.exit_code == 0
    assert "Removing" in with_yes.output


def test_strict_mode_human_in_the_loop_blocks_yes() -> None:
    app = Tooli(name="sec-app", security_policy="strict")
    runner = CliRunner()

    @app.command(annotations=Destructive, human_in_the_loop=True)
    def wipe() -> str:
        return "executed"

    denied = runner.invoke(app, ["wipe", "--yes", "--text"])
    assert denied.exit_code == 2

    forced = runner.invoke(app, ["wipe", "--force", "--text"])
    assert forced.exit_code == 0
    assert forced.output.strip().endswith("executed")


def test_security_policy_defaults_to_standard() -> None:
    app = Tooli(name="sec-app")
    runner = CliRunner()

    @app.command(annotations=Destructive)
    def wipe() -> str:
        return "removed"

    denied = runner.invoke(app, ["wipe", "--text"])
    assert denied.exit_code == 2

    with_yes = runner.invoke(app, ["wipe", "--yes", "--text"])
    assert with_yes.exit_code == 0


def test_tooli_yes_env_var_skips_confirmation(monkeypatch) -> None:
    monkeypatch.setenv("TOOLI_YES", "1")
    monkeypatch.delenv("TOOLI_NONINTERACTIVE", raising=False)

    app = Tooli(name="sec-app", security_policy="standard")
    runner = CliRunner()

    @app.command(annotations=Destructive)
    def wipe() -> str:
        return "removed"

    result = runner.invoke(app, ["wipe", "--text"])
    assert result.exit_code == 0
    assert result.output.strip().endswith("removed")


def test_tooli_noninteractive_env_var_skips_confirmation(monkeypatch) -> None:
    monkeypatch.setenv("TOOLI_NONINTERACTIVE", "yes")
    monkeypatch.delenv("TOOLI_YES", raising=False)

    app = Tooli(name="sec-app", security_policy="standard")
    runner = CliRunner()

    @app.command(annotations=Destructive)
    def wipe() -> str:
        return "removed"

    result = runner.invoke(app, ["wipe", "--text"])
    assert result.exit_code == 0
    assert result.output.strip().endswith("removed")


def test_tooli_yes_env_var_false_does_not_skip_confirmation(monkeypatch) -> None:
    monkeypatch.setenv("TOOLI_YES", "0")
    monkeypatch.delenv("TOOLI_NONINTERACTIVE", raising=False)

    app = Tooli(name="sec-app", security_policy="standard")
    runner = CliRunner()

    @app.command(annotations=Destructive)
    def wipe() -> str:
        return "removed"

    result = runner.invoke(app, ["wipe", "--text"])
    assert result.exit_code == 2


@pytest.mark.parametrize(
    "value, expected_mode",
    [
        ("strict", "strict"),
        ("STANDARD", "standard"),
        ("off", "off"),
        ("  standard  ", "standard"),
        ("", "standard"),
        ("bad-mode", "standard"),
        (None, "standard"),
    ],
)
def test_security_policy_resolves_value_hierarchy(
    monkeypatch: object, value: str | None, expected_mode: str
) -> None:
    if value is None:
        monkeypatch.delenv("TOOLI_SECURITY_POLICY", raising=False)
    else:
        monkeypatch.setenv("TOOLI_SECURITY_POLICY", value)

    app = Tooli(name="sec-app", security_policy=None)

    @app.command(annotations=Destructive)
    def wipe() -> str:
        return "removed"

    requires_confirmation = expected_mode in {"standard", "strict"}
    denied = CliRunner().invoke(app, ["wipe", "--text"])
    assert denied.exit_code == (2 if requires_confirmation else 0)


def test_security_policy_constructor_overrides_env(monkeypatch: object) -> None:
    monkeypatch.setenv("TOOLI_SECURITY_POLICY", "strict")

    app = Tooli(name="sec-app", security_policy="off")

    @app.command(annotations=Destructive)
    def wipe() -> str:
        return "removed"

    denied = CliRunner().invoke(app, ["wipe", "--text"])
    assert denied.exit_code == 0
    assert denied.output.strip() == "removed"


def test_sanitizer_preserves_generic_type_syntax() -> None:
    """Backtick-quoted generic types like `StdinOr[T]` must not be redacted."""
    from tooli.security.sanitizer import sanitize_text

    assert sanitize_text("`StdinOr[T]`") == "`StdinOr[T]`"
    assert sanitize_text("`SecretInput[str]`") == "`SecretInput[str]`"
    assert sanitize_text("## StdinOr[T]") == "## StdinOr[T]"


def test_sanitizer_still_blocks_injection() -> None:
    """Shell injection patterns should still be redacted."""
    from tooli.security.sanitizer import sanitize_text

    assert "$(" not in sanitize_text("$(rm -rf /)")
    assert "${" not in sanitize_text("${HOME}")
    assert ">(" not in sanitize_text(">(cat /etc/passwd)")
    assert "<(" not in sanitize_text("<(ls)")
