"""Agent-oriented CLI validation harness."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict, cast

import click

from tooli.command_meta import get_command_meta
from tooli.manifest import generate_agent_manifest

if False:  # pragma: no cover
    from tooli.app import Tooli


class TestFailure(TypedDict):
    command: str
    test: str
    expected: Any
    actual: Any
    error: str


def _build_sample_value(type_name: str) -> str:
    if "INTEGER" in type_name.upper():
        return "1"
    if "FLOAT" in type_name.upper():
        return "1.1"
    if type_name == "bool" or "BOOLEAN" in type_name.upper():
        return "true"
    if "PATH" in type_name.upper():
        return "."
    if "CHOICE" in type_name.upper():
        return "1"
    return "sample"


def _is_terminal_option(flag: str) -> bool:
    return bool(flag.startswith("--")) and len(flag) > 2


def _build_harness_args(app: "Tooli", command_name: str, include_dry_run: bool) -> list[str]:
    from tooli.app import Tooli

    command = next(
        (item for item in app.registered_commands if getattr(item, "name", None) == command_name),
        None,
    )
    if command is None:
        return ["--help"]

    args: list[str] = [command_name, "--json", "--quiet"]
    if include_dry_run:
        args.append("--dry-run")
    args.append("--yes")

    for parameter in getattr(command, "params", []):
        if not getattr(parameter, "expose_value", False):
            continue
        if parameter.name in {"text", "help", "version", "json", "jsonl", "plain"}:
            continue
        if getattr(parameter, "required", False):
            if isinstance(parameter, click.Option):
                if getattr(parameter, "is_flag", False):
                    args.append(cast(str, next(iter(parameter.opts), f"--{parameter.name}")))
                    continue

                flag = cast(str, next(iter(parameter.opts), f"--{parameter.name.replace('_', '-')}"))
                sample_type = parameter.type.name or "string"
                sample = _build_sample_value(sample_type)
                args.extend([flag, sample])
            else:
                sample_type = parameter.type.name or "string"
                args.append(_build_sample_value(sample_type))

    # Remove duplicate global flags and keep order.
    deduped: list[str] = []
    seen: set[str] = set()
    for arg in args:
        if arg.startswith("--") and "=" not in arg and _is_terminal_option(arg):
            if arg in seen:
                continue
            seen.add(arg)
        deduped.append(arg)
    return deduped


def _safe_json_loads(raw: str) -> dict[str, Any] | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _validate_output_against_schema(payload: dict[str, Any], output_schema: Any) -> str | None:
    if output_schema is None:
        return None
    if "result" not in payload:
        return "missing result field"

    result = payload["result"]
    schema = output_schema.get("type")
    if schema is None:
        return None

    if schema == "array" and not isinstance(result, list):
        return f"expected array, got {type(result).__name__}"
    if schema == "object" and not isinstance(result, dict):
        return f"expected object, got {type(result).__name__}"
    if schema == "string" and not isinstance(result, str):
        return f"expected string, got {type(result).__name__}"
    if schema == "integer" and not isinstance(result, int):
        return f"expected integer, got {type(result).__name__}"
    if schema == "number" and not isinstance(result, (int, float)):
        return f"expected number, got {type(result).__name__}"
    if schema == "boolean" and not isinstance(result, bool):
        return f"expected boolean, got {type(result).__name__}"
    return None


def run_agent_tests(
    app: "Tooli",
    command_names: list[str] | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    from click.testing import CliRunner
    from tooli.schema import generate_tool_schema

    tooli_name = app.info.name or "tooli"
    prog_name = app.info.name or "tooli"
    selected_names = set(command_names or [])

    manifest = generate_agent_manifest(app)
    command_payloads = {
        entry["name"]: entry
        for entry in manifest.get("commands", [])
    }

    runner = CliRunner()
    failures: list[TestFailure] = []
    tests_run = 0
    tests_passed = 0

    for command in app.get_tools():
        if command.hidden:
            continue
        if selected_names and command.name not in selected_names:
            continue

        meta = get_command_meta(command.callback)
        supports_dry = bool(meta.supports_dry_run)

        tool_payload = command_payloads.get(command.name, {})
        command_output_schema = tool_payload.get("outputSchema")

        def _record_failure(test_name: str, expected: Any, actual: Any, error: str) -> None:
            failures.append(
                {
                    "command": command.name,
                    "test": test_name,
                    "expected": expected,
                    "actual": actual,
                    "error": error,
                }
            )

        # 1) --schema should return command schema
        tests_run += 1
        schema_result = runner.invoke(app, [command.name, "--schema", "--text"], prog_name=prog_name)
        if schema_result.exit_code != 0:
            _record_failure("schema_accuracy", {"ok": True}, {"ok": False, "exit_code": schema_result.exit_code}, "Schema invocation failed")
        else:
            raw_schema = _safe_json_loads(schema_result.output)
            if raw_schema is None:
                _record_failure("schema_accuracy", "valid json", schema_result.output, "Schema output was not valid JSON")
            else:
                generated = generate_tool_schema(command.callback, name=command.name, required_scopes=list(meta.auth))
                if raw_schema.get("inputSchema") != generated.input_schema:
                    _record_failure(
                        "schema_accuracy",
                        generated.model_dump(exclude_none=True),
                        raw_schema,
                        "Schema payload did not match generated schema",
                    )
                else:
                    tests_passed += 1

        # 2) command output and envelope format
        invocation_args = _build_harness_args(app, command.name, include_dry_run=False)
        tests_run += 1
        run_result = runner.invoke(app, invocation_args, prog_name=prog_name)
        if run_result.exit_code == 0:
            payload = _safe_json_loads(run_result.output)
            if not isinstance(payload, dict) or not payload.get("ok"):
                _record_failure(
                    "output_format",
                    {"ok": True, "meta": Mapping[str, Any], "result": Any},
                    run_result.output,
                    "Command output was not structured JSON envelope",
                )
            else:
                mismatch = _validate_output_against_schema(payload, command_output_schema)
                if mismatch:
                    _record_failure("output_schema_conformance", command_output_schema, payload.get("result"), mismatch)
                else:
                    tests_passed += 1
        else:
            _record_failure("output_format", {"ok": True}, {"ok": False, "exit_code": run_result.exit_code}, f"Command invocation failed: {run_result.output[:140]}")

        # 3) error handling with unknown argument
        tests_run += 1
        error_result = runner.invoke(app, [command.name, "--tooli-does-not-exist"], prog_name=prog_name)
        if error_result.exit_code == 0:
            _record_failure(
                "error_handling",
                {"exit_code": "!=0"},
                {"exit_code": error_result.exit_code},
                "Unknown argument path did not produce error",
            )
        else:
            payload = _safe_json_loads(error_result.output)
            if not isinstance(payload, Mapping) or not bool(payload.get("ok")) is False:
                _record_failure(
                    "error_handling",
                    {"ok": False},
                    payload,
                    "Error output should be structured",
                )
            else:
                tests_passed += 1

        # 4) dry-run command, if supported.
        if supports_dry:
            tests_run += 1
            dry_args = _build_harness_args(app, command.name, include_dry_run=True)
            dry_result = runner.invoke(app, dry_args, prog_name=prog_name)
            if dry_result.exit_code != 0:
                _record_failure(
                    "dry_run",
                    {"ok": True},
                    {"ok": False, "exit_code": dry_result.exit_code},
                    "Dry-run invocation failed",
                )
            else:
                payload = _safe_json_loads(dry_result.output)
                if not isinstance(payload, dict) or not payload.get("ok"):
                    _record_failure(
                        "dry_run",
                        {"ok": True},
                        payload,
                        "Dry-run output missing structured envelope",
                    )
                else:
                    tests_passed += 1

    report = {
        "tool": tooli_name,
        "version": app.version,
        "tests_run": tests_run,
        "tests_passed": tests_passed,
        "tests_failed": len(failures),
        "failures": failures,
    }

    if output_path:
        Path(output_path).write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report
