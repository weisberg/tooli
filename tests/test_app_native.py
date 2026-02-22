"""Tests for the native fallback CLI backend."""

from __future__ import annotations

from typing import Annotated
import json
from contextlib import redirect_stdout
from io import StringIO

from tooli.app_native import Tooli
from tooli.backends.native import Argument, Option


def _run_native(app: Tooli, args: list[str]) -> tuple[int, str]:
    buffer = StringIO()
    with redirect_stdout(buffer):
        code = app.main(args=args, prog_name=app.name)
    return code, buffer.getvalue().strip()


def test_native_backend_executes_command() -> None:
    app = Tooli(name="native-demo")

    @app.command()
    def greet(name: str) -> str:
        return f"Hello, {name}"

    code, output = _run_native(app, ["greet", "Alice"])
    assert code == 0
    assert output == "Hello, Alice"


def test_native_backend_json_envelope() -> None:
    app = Tooli(name="native-demo", version="1.2.3")

    @app.command()
    def ping() -> int:
        return 7

    code, output = _run_native(app, ["ping", "--json"])
    assert code == 0
    payload = json.loads(output)
    assert payload["ok"] is True
    assert payload["result"] == 7
    assert payload["meta"]["tool"] == "native-demo.ping"
    assert payload["meta"]["version"] == "1.2.3"


def test_native_backend_schema_and_help_agent() -> None:
    app = Tooli(name="native-demo")

    @app.command()
    def status(path: str = "build") -> str:
        return f"path={path}"

    schema_code, schema_output = _run_native(app, ["status", "--schema"])
    assert schema_code == 0
    schema_payload = json.loads(schema_output)
    assert schema_payload["name"] == "status"
    assert "input_schema" in schema_payload

    help_code, help_output = _run_native(app, ["status", "--help-agent"])
    assert help_code == 0
    assert "command: status" in help_output
    assert "description:" in help_output
    assert "params:" in help_output
    assert "output:" in help_output


def test_native_backend_argument_option_markers() -> None:
    """Native Argument/Option markers are honored by the argparse fallback backend."""
    app = Tooli(name="native-markers", backend="native")

    @app.command()
    def transform(
        path: Annotated[str, Argument(...)] ,
        mode: Annotated[str, Option("--mode", help="Transformation mode")] = "snake",
    ) -> str:
        return f"{mode}:{path}"

    code, output = _run_native(app, ["transform", "value", "--mode", "upper"])
    assert code == 0
    assert output == "upper:value"

def test_native_backend_dry_run_payload() -> None:
    app = Tooli(name="native-demo")

    @app.command(supports_dry_run=True)
    def rewrite(pattern: str) -> str:
        return f"rewrite:{pattern}"

    code, output = _run_native(app, ["rewrite", "abc", "--dry-run", "--json"])
    assert code == 0
    payload = json.loads(output)
    assert payload["dry_run"] is True
    assert payload["tool"] == "native-demo.rewrite"
    assert payload["command"] == "rewrite"


def test_native_backend_optional_type_parameters() -> None:
    """T | None parameters must not crash argparse (issue #203)."""
    app = Tooli(name="native-optional")

    @app.command()
    def search(
        query: str = "default",
        limit: Annotated[int | None, Option(help="Max results")] = None,
    ) -> dict:
        return {"query": query, "limit": limit}

    code, output = _run_native(app, ["search", "--json"])
    assert code == 0
    payload = json.loads(output)
    assert payload["ok"] is True
    assert payload["result"]["limit"] is None

    code2, output2 = _run_native(app, ["search", "--limit", "10", "--json"])
    assert code2 == 0
    payload2 = json.loads(output2)
    assert payload2["result"]["limit"] == 10


def test_native_backend_triggers_anti_triggers_rules() -> None:
    """triggers, anti_triggers, and rules are accepted and stored (issue #202)."""
    app = Tooli(
        name="native-agent",
        triggers=["analyzing data"],
        anti_triggers=["modifying state"],
        rules=["Always validate input"],
    )

    @app.command()
    def analyze(data: str) -> str:
        return f"analyzed: {data}"

    assert app.triggers == ["analyzing data"]
    assert app.anti_triggers == ["modifying state"]
    assert app.rules == ["Always validate input"]


def test_native_backend_extra_kwargs_stored() -> None:
    """Unknown kwargs are stored as attributes instead of crashing."""
    app = Tooli(name="native-compat", env_vars={"FOO": "bar"})

    assert app.env_vars == {"FOO": "bar"}
