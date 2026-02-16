"""Programmatic orchestration helpers for Tooli commands."""

from __future__ import annotations

import ast
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tooli.app import Tooli


_ORCHESTRATION_BUILTINS: dict[str, Any] = {
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "len": len,
    "list": list,
    "dict": dict,
    "min": min,
    "max": max,
    "sum": sum,
    "sorted": sorted,
}


def _coerce_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("Plan payload must be a list of tool-call steps.")
    if not payload:
        return []
    return [step for step in payload]


def _parse_python_plan(raw: str, *, command_name: str) -> list[dict[str, Any]]:
    stripped = raw.strip()
    if not stripped:
        return []

    try:
        tree = ast.parse(stripped, mode="eval")
    except SyntaxError as exc:
        raise ValueError(
            f"{command_name}: python plan input must be a valid Python expression."
        ) from exc

    try:
        value = eval(compile(tree, filename="<tooli-orchestrate>", mode="eval"), {"__builtins__": _ORCHESTRATION_BUILTINS}, {})
    except Exception as exc:
        raise ValueError(
            f"{command_name}: failed to evaluate python plan payload."
        ) from exc

    if not isinstance(value, list):
        raise ValueError(f"{command_name}: python payload must evaluate to a list.")

    return _coerce_payload(value)


def parse_plan_payload(raw: str, *, command_name: str, allow_python: bool) -> list[dict[str, Any]]:
    """Parse orchestration steps from JSON or Python expression payload."""
    stripped = raw.strip()
    if not stripped:
        return []

    if allow_python:
        return _parse_python_plan(stripped, command_name=command_name)

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{command_name}: plan must be valid JSON (or use --python)."
        ) from exc

    return _coerce_payload(parsed)


def _validate_step(index: int, step: Any, command_name: str) -> tuple[str, dict[str, Any]]:
    if not isinstance(step, dict):
        raise ValueError(
            f"{command_name}: plan step {index} must be an object with command and arguments."
        )

    command = step.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError(
            f"{command_name}: step {index} is missing a valid command string."
        )

    arguments = step.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError(
            f"{command_name}: step {index} arguments must be an object."
        )

    return command, arguments


def run_tool_plan(
    app: Tooli,
    steps: list[dict[str, Any]] | list[Any],
    *,
    max_steps: int,
    continue_on_error: bool = False,
) -> dict[str, Any]:
    """Execute an orchestration plan against a Tooli app.

    Args:
        app: Tooli app containing the target commands.
        steps: Ordered list of tool-call dictionaries.
        max_steps: Maximum number of steps to execute.
        continue_on_error: Continue executing after a step failure when True.
    """
    from tooli.mcp.server import _build_run_tool

    plan = _coerce_payload(steps)
    if max_steps <= 0:
        raise ValueError("max_steps must be greater than zero.")
    if len(plan) > max_steps:
        raise ValueError(f"Plan has {len(plan)} steps, which exceeds max_steps={max_steps}.")

    run_tool = _build_run_tool(app)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for index, step in enumerate(plan):
        try:
            command, arguments = _validate_step(index, step, app.info.name or "orchestrate")
            result = run_tool(name=command, arguments=arguments)
        except Exception as exc:  # broad catch: orchestration errors are user-facing payloads
            failures.append(
                {
                    "index": index,
                    "command": (
                        step.get("command")
                        if isinstance(step, dict)
                        else None
                    ),
                    "error": str(exc),
                }
            )
            if not continue_on_error:
                break
            continue

        results.append({"index": index, "command": command, "result": result})

    ok = not failures
    return {
        "ok": ok,
        "steps_executed": len(results),
        "steps_total": len(plan),
        "results": results,
        "errors": failures,
        "summary": {
            "ok": ok,
            "executed": len(results),
            "failed": len(failures),
            "failed_step": failures[0]["index"] if failures else None,
        },
    }
