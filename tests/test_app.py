"""Tests for the core Tooli application class."""

from __future__ import annotations

import io
import json
from typing import Annotated, Callable

import typer
from typer.testing import CliRunner

from tooli import Argument, Option, Tooli
from tooli.annotations import Destructive, Idempotent, ReadOnly


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
    result = runner.invoke(app, ["hello", "world", "--text"])
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
    result = runner.invoke(app, ["greet", "world", "--greeting", "Hi", "--text"])
    assert result.exit_code == 0
    assert "Hi world" in result.output


def test_single_command_app() -> None:
    """A Tooli app with a single command should work without subcommands."""
    app = Tooli(name="test-app")

    @app.command()
    def main(name: Annotated[str, Argument(help="Name")]) -> None:
        print(f"Hello {name}")

    runner = CliRunner()
    result = runner.invoke(app, ["main", "world", "--text"])
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
    assert "hello" in result.output


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


def test_global_flag_values_are_stored() -> None:
    """Global flags should populate ToolContext as expected."""
    app = Tooli(name="test-app")

    @app.command()
    def flags(ctx: typer.Context) -> str:
        assert ctx.obj is not None
        return f"{ctx.obj.quiet}|{ctx.obj.verbose}|{ctx.obj.dry_run}|{ctx.obj.yes}"

    runner = CliRunner()
    result = runner.invoke(app, ["flags", "--quiet", "-vv", "--dry-run", "--yes", "--text"])
    assert result.exit_code == 0
    assert result.output.strip() == "True|2|True|True"


def test_response_format_flag_is_stored() -> None:
    """Response format should be available on ToolContext and default to concise."""
    app = Tooli(name="test-app")

    @app.command()
    def fmt(ctx: typer.Context) -> str:
        assert ctx.obj is not None
        return str(ctx.obj.response_format)

    runner = CliRunner()
    result = runner.invoke(app, ["fmt", "--text"])
    assert result.exit_code == 0
    assert result.output.strip() == "concise"

    result = runner.invoke(app, ["fmt", "--response-format", "detailed", "--text"])
    assert result.exit_code == 0
    assert result.output.strip() == "detailed"


def test_help_agent_flag_output() -> None:
    """--help-agent should emit compact command metadata."""
    app = Tooli(name="test-app")

    @app.command()
    def render(
        name: Annotated[str, Argument(help="Name of the item")],
        uppercase: Annotated[bool, Option(help="Uppercase the value")] = False,
    ) -> str:
        return name.upper() if uppercase else name

    runner = CliRunner()
    result = runner.invoke(app, ["render", "item", "--help-agent", "--text"])
    assert result.exit_code == 0
    assert "command render:" in result.output
    assert "help=" in result.output
    assert "params=" in result.output
    assert "item" in result.output or "name" in result.output


def test_yes_skip_prompt() -> None:
    """--yes should bypass confirmation prompts and non-tty should raise InputError."""
    app = Tooli(name="test-app")

    @app.command()
    def confirm(ctx: typer.Context) -> str:
        if ctx.obj.confirm("Proceed with operation?"):
            return "confirmed"
        return "rejected"

    runner = CliRunner()
    result = runner.invoke(app, ["confirm"])
    assert result.exit_code == 2

    result = runner.invoke(app, ["confirm", "--yes", "--text"])
    assert result.exit_code == 0
    assert result.output.strip() == "confirmed"


def test_confirm_uses_tty_prompt_device(monkeypatch) -> None:
    """When stdin is not TTY, confirmation reads from prompt device path."""
    app = Tooli(name="test-app")

    @app.command()
    def confirm(ctx: typer.Context) -> str:
        return "confirmed" if ctx.obj.confirm("Proceed?") else "denied"

    stream = io.StringIO("y\n")

    monkeypatch.setattr("tooli.context._open_tty_prompt_stream", lambda: stream)

    runner = CliRunner()
    result = runner.invoke(app, ["confirm", "--text"])
    assert result.exit_code == 0
    assert result.output.strip() == "confirmed"


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


def test_print0_list_output() -> None:
    """TEXT output should support NUL-delimited lists with --print0."""
    app = Tooli(name="test-app")

    @app.command(list_processing=True)
    def items() -> list[str]:
        return ["alpha", "beta", "gamma"]

    @app.command()
    def noop() -> None:
        return None

    runner = CliRunner()
    result = runner.invoke(app, ["items", "--print0", "--text"])
    assert result.exit_code == 0
    assert result.output == "alpha\0beta\0gamma"


def test_print0_output_round_trip_with_null_input() -> None:
    """--print0 output should interoperate with --null input parsing."""
    app = Tooli(name="test-app")

    @app.command(list_processing=True)
    def items() -> list[str]:
        return ["alpha", "beta", "gamma"]

    @app.command(list_processing=True)
    def join(values: list[str] | None = None) -> str:
        return "|".join(values or [])

    runner = CliRunner()
    printed = runner.invoke(app, ["items", "--print0", "--text"])
    assert printed.exit_code == 0
    assert printed.output == "alpha\0beta\0gamma"

    parsed = runner.invoke(app, ["join", "--null", "--text"], input=printed.output)
    assert parsed.exit_code == 0
    assert parsed.output.strip() == "alpha|beta|gamma"
    assert parsed.output.count("\0") == 0


def test_null_input_parsing_for_list_commands() -> None:
    """--null should parse NUL-delimited list input for list-processing commands."""
    app = Tooli(name="test-app")

    @app.command(list_processing=True)
    def join(values: list[str] | None = None) -> str:
        return "|".join(values or [])

    runner = CliRunner()
    result = runner.invoke(app, ["join", "--null", "--text"], input="a\0b\0c\0")
    assert result.exit_code == 0
    assert result.output.strip() == "a|b|c"


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


def test_error_category_exit_codes() -> None:
    """Each ToolError category should map to the expected exit code."""
    from tooli.errors import AuthError, InternalError, InputError, ToolRuntimeError, StateError

    categories = [
        ("input", InputError, 2),
        ("auth", AuthError, 30),
        ("state", StateError, 10),
        ("runtime", ToolRuntimeError, 70),
        ("internal", InternalError, 70),
    ]

    for name, error_type, expected_code in categories:
        app = Tooli(name="test-app")

        command_name = f"fail_{name}"

        def _make_fail(error_cls: type[Exception]) -> Callable[[], None]:
            def fail() -> None:
                raise error_cls(message="boom")

            return fail

        app.command(name=command_name)(_make_fail(error_type))

        runner = CliRunner()
        result = runner.invoke(app, [command_name])
        assert result.exit_code == expected_code, f"exit code for {name} should be {expected_code}"



def test_click_usage_error_maps_to_input_exit_code() -> None:
    """Click usage errors should map to ToolError input-category exit code."""
    app = Tooli(name="test-app")

    @app.command()
    def need_arg(name: str) -> str:
        return name

    runner = CliRunner()
    result = runner.invoke(app, ["need-arg"])
    assert result.exit_code == 2


def test_help_output_includes_behavior_line() -> None:
    """--help output should include a Behavior summary when annotations are present."""
    app = Tooli(name="test-app")

    @app.command(annotations=ReadOnly | Idempotent)
    def info() -> None:
        """Report read-only status."""
        return None

    runner = CliRunner()
    result = runner.invoke(app, ["info", "--help", "--text"])
    assert result.exit_code == 0
    assert "Behavior: [read-only, idempotent]" in result.output


def test_help_agent_output_includes_annotations() -> None:
    """--help-agent should include annotations and governance metadata."""
    app = Tooli(name="test-app")

    @app.command(annotations=Destructive, cost_hint="medium", human_in_the_loop=True)
    def remove_item() -> None:
        """Remove one item."""
        return None

    runner = CliRunner()
    result = runner.invoke(app, ["remove-item", "--help-agent", "--text"])
    assert result.exit_code == 0
    assert "annotations=destructive" in result.output
    assert "cost_hint=medium" in result.output
    assert "human_in_the_loop=true" in result.output


def test_schema_output_includes_annotations_object() -> None:
    """--schema should expose MCP-style annotations."""
    app = Tooli(name="test-app")

    @app.command(annotations=ReadOnly | Destructive, cost_hint="low")
    def items() -> list[dict[str, str]]:
        return []

    runner = CliRunner()
    result = runner.invoke(app, ["items", "--schema", "--text"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["annotations"] == {"readOnlyHint": True, "destructiveHint": True}
    assert payload["cost_hint"] == "low"
    assert payload["annotations"]["readOnlyHint"] is True


def test_json_envelope_meta_includes_annotations() -> None:
    """JSON envelope meta should include annotation hints."""
    app = Tooli(name="test-app")

    @app.command(annotations=Idempotent)
    def stats() -> list[int]:
        return [1, 2, 3]

    runner = CliRunner()
    result = runner.invoke(app, ["stats", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["meta"]["annotations"] == {"idempotentHint": True}


def test_paginated_list_returns_cursor_and_truncation() -> None:
    """Paginated commands should include pagination metadata."""
    app = Tooli(name="test-app")

    @app.command(paginated=True)
    def numbers() -> list[int]:
        return list(range(10))

    runner = CliRunner()
    first = runner.invoke(app, ["numbers", "--json", "--limit", "3"])
    assert first.exit_code == 0
    payload = json.loads(first.output)
    assert payload["result"] == [0, 1, 2]
    assert payload["meta"]["truncated"] is True
    assert payload["meta"]["next_cursor"] == "3"
    assert "Use --cursor 3" in payload["meta"]["truncation_message"]


def test_paginated_cursor_continues_result_set() -> None:
    """Pagination with cursor should continue from the prior page."""
    app = Tooli(name="test-app")

    @app.command(paginated=True)
    def numbers() -> list[int]:
        return list(range(10))

    runner = CliRunner()
    first = runner.invoke(app, ["numbers", "--json", "--limit", "3"])
    cursor = json.loads(first.output)["meta"]["next_cursor"]

    second = runner.invoke(app, ["numbers", "--json", "--limit", "3", "--cursor", cursor])
    assert second.exit_code == 0
    payload = json.loads(second.output)
    assert payload["result"] == [3, 4, 5]


def test_paginated_fields_filtering() -> None:
    """--fields and --select should filter top-level output keys."""
    app = Tooli(name="test-app")

    @app.command(paginated=True)
    def records() -> list[dict[str, str]]:
        return [
            {"id": "1", "name": "alpha", "secret": "s1"},
            {"id": "2", "name": "beta", "secret": "s2"},
        ]

    runner = CliRunner()
    result = runner.invoke(app, ["records", "--json", "--fields", "id,name"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["result"] == [
        {"id": "1", "name": "alpha"},
        {"id": "2", "name": "beta"},
    ]


def test_paginated_filter_flag() -> None:
    """--filter should reduce list output before truncation."""
    app = Tooli(name="test-app")

    @app.command(paginated=True)
    def records() -> list[dict[str, str]]:
        return [
            {"kind": "a", "name": "alpha"},
            {"kind": "b", "name": "bravo"},
            {"kind": "a", "name": "adam"},
        ]

    runner = CliRunner()
    result = runner.invoke(app, ["records", "--json", "--filter", "kind=a"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["result"] == [
        {"kind": "a", "name": "alpha"},
        {"kind": "a", "name": "adam"},
    ]


def test_paginated_max_items_truncates() -> None:
    """--max-items should cap the result set and set truncation metadata."""
    app = Tooli(name="test-app")

    @app.command(paginated=True)
    def numbers() -> list[int]:
        return list(range(10))

    runner = CliRunner()
    result = runner.invoke(app, ["numbers", "--json", "--max-items", "4"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["result"] == [0, 1, 2, 3]
    assert payload["meta"]["truncated"] is True
    assert payload["meta"]["next_cursor"] == "4"
    assert "Use --cursor 4" in payload["meta"]["truncation_message"]


def test_imports() -> None:
    """Key symbols should be importable from tooli."""
    from tooli import Annotated, Argument, Option, Tooli

    assert Tooli is not None
    assert Annotated is not None
    assert Option is not None
    assert Argument is not None
