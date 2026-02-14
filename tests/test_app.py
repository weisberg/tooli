"""Tests for the core Tooli application class."""

from __future__ import annotations

import json
from typing import Annotated

from typer.testing import CliRunner

from tooli import Argument, Option, Tooli


def test_tooli_creates_basic_app() -> None:
    """Tooli instance should be usable as a CLI app."""
    app = Tooli(name="test-app")
    assert app.info.name == "test-app"


def test_tooli_stores_version() -> None:
    """Tooli should store version metadata."""
    app = Tooli(name="test-app", version="1.2.3")
    assert app.version == "1.2.3"


def test_tooli_default_version() -> None:
    """Tooli should default to 0.0.0 version."""
    app = Tooli(name="test-app")
    assert app.version == "0.0.0"


def test_tooli_stores_config() -> None:
    """Tooli should store agent-specific configuration."""
    app = Tooli(
        name="test-app",
        default_output="json",
        mcp_transport="http",
        skill_auto_generate=True,
        permissions={"fs": "read"},
    )
    assert app.default_output == "json"
    assert app.mcp_transport == "http"
    assert app.skill_auto_generate is True
    assert app.permissions == {"fs": "read"}


def test_command_decorator_works() -> None:
    """@app.command() should work identically to Typer's."""
    app = Tooli(name="test-app")

    @app.command()
    def hello(name: Annotated[str, Argument(help="Name to greet")]) -> None:
        print(f"Hello {name}")

    runner = CliRunner()
    result = runner.invoke(app, ["world", "--text"])
    assert result.exit_code == 0
    assert "Hello world" in result.output


def test_command_with_options() -> None:
    """Commands with Options should parse correctly."""
    app = Tooli(name="test-app")

    @app.command()
    def greet(
        name: Annotated[str, Argument(help="Name to greet")],
        greeting: Annotated[str, Option(help="Greeting to use")] = "Hello",
    ) -> None:
        print(f"{greeting} {name}")

    runner = CliRunner()
    result = runner.invoke(app, ["world", "--greeting", "Hi", "--text"])
    assert result.exit_code == 0
    assert "Hi world" in result.output


def test_single_command_app() -> None:
    """A Tooli app with a single command should work without subcommands."""
    app = Tooli(name="test-app")

    @app.command()
    def main(name: Annotated[str, Argument(help="Name")]) -> None:
        print(f"Hello {name}")

    runner = CliRunner()
    result = runner.invoke(app, ["world", "--text"])
    assert result.exit_code == 0
    assert "Hello world" in result.output


def test_multi_command_app() -> None:
    """A Tooli app with multiple commands should use subcommand names."""
    app = Tooli(name="test-app")

    @app.command()
    def hello(name: Annotated[str, Argument(help="Name")]) -> None:
        print(f"Hello {name}")

    @app.command()
    def goodbye(name: Annotated[str, Argument(help="Name")]) -> None:
        print(f"Goodbye {name}")

    runner = CliRunner()
    result = runner.invoke(app, ["hello", "world", "--text"])
    assert result.exit_code == 0
    assert "Hello world" in result.output

    result = runner.invoke(app, ["goodbye", "world", "--text"])
    assert result.exit_code == 0
    assert "Goodbye world" in result.output


def test_help_output() -> None:
    """--help should work on Tooli apps."""
    app = Tooli(name="test-app", help="A test application")

    @app.command()
    def hello(name: Annotated[str, Argument(help="Name to greet")]) -> None:
        """Say hello to someone."""
        print(f"Hello {name}")

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Say hello to someone" in result.output
    assert "Name to greet" in result.output


def test_return_value_json_envelope() -> None:
    """Non-TTY invocations default to JSON envelope output."""
    app = Tooli(name="file-tools", version="1.0.0")

    @app.command()
    def info() -> dict:
        return {"ok": 1}

    # Force a multi-command app so the command name is part of the command path.
    @app.command()
    def noop() -> None:
        return None

    runner = CliRunner()
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["result"] == {"ok": 1}
    assert payload["meta"]["tool"] == "file-tools.info"
    assert payload["meta"]["version"] == "1.0.0"
    assert isinstance(payload["meta"]["duration_ms"], int)


def test_output_alias_last_wins() -> None:
    """If multiple output flags are provided, the last one wins."""
    app = Tooli(name="test-app")

    @app.command()
    def val() -> dict:
        return {"x": 1}

    @app.command()
    def noop() -> None:
        return None

    runner = CliRunner()
    result = runner.invoke(app, ["val", "--json", "--text"])
    assert result.exit_code == 0
    assert result.output.strip() == "{'x': 1}"


def test_output_jsonl_list() -> None:
    """JSONL emits one object per line for list return values."""
    app = Tooli(name="test-app", version="0.0.0")

    @app.command()
    def items() -> list[dict]:
        return [{"a": 1}, {"a": 2}]

    @app.command()
    def noop() -> None:
        return None

    runner = CliRunner()
    result = runner.invoke(app, ["items", "--jsonl"])
    assert result.exit_code == 0
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["ok"] is True and first["result"] == {"a": 1}
    assert second["ok"] is True and second["result"] == {"a": 2}


def test_command_timeout() -> None:
    """--timeout should terminate command execution."""
    import time
    app = Tooli(name="test-app")

    @app.command()
    def slow() -> str:
        time.sleep(2)
        return "done"

    @app.command()
    def noop() -> None:
        pass

    runner = CliRunner()
    # Use a short timeout
    result = runner.invoke(app, ["slow", "--timeout", "0.1"])
    assert result.exit_code == 50
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert "timed out" in payload["error"]["message"]


def test_structured_error_output() -> None:
    """ToolError should produce structured JSON in non-TTY mode."""
    from tooli.errors import StateError, Suggestion
    app = Tooli(name="test-app")

    @app.command()
    def fail() -> None:
        raise StateError(
            message="Resource not found",
            code="E3001",
            suggestion=Suggestion(action="check", fix="Try another ID")
        )

    @app.command()
    def noop() -> None:
        pass

    runner = CliRunner()
    result = runner.invoke(app, ["fail"])
    assert result.exit_code == 10
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "E3001"
    assert payload["error"]["suggestion"]["fix"] == "Try another ID"


def test_internal_error_with_verbose() -> None:
    """Unexpected errors should include traceback in verbose mode."""
    app = Tooli(name="test-app")

    @app.command()
    def crash() -> None:
        raise ValueError("Boom")

    @app.command()
    def noop() -> None:
        pass

    runner = CliRunner()
    # Without verbose, no traceback
    result = runner.invoke(app, ["crash"])
    assert result.exit_code == 70
    payload = json.loads(result.output)
    assert "Internal error: Boom" in payload["error"]["message"]
    assert "traceback" not in payload["error"]["details"]

    # With verbose, traceback included
    result = runner.invoke(app, ["crash", "-v"])
    assert result.exit_code == 70
    payload = json.loads(result.output)
    assert "traceback" in payload["error"]["details"]
    assert "ValueError: Boom" in payload["error"]["details"]["traceback"]


def test_imports() -> None:
    """Key symbols should be importable from tooli."""
    from tooli import Annotated, Argument, Option, Tooli

    assert Tooli is not None
    assert Annotated is not None
    assert Option is not None
    assert Argument is not None
