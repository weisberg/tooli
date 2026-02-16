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
