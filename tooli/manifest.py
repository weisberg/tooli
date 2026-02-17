"""Generate machine-readable tool manifest payloads for agents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tooli.app import Tooli

from tooli.command_meta import get_command_meta
from tooli.schema import generate_tool_schema

ExitCodesType = list[dict[str, str]]

GLOBAL_FLAGS: dict[str, str] = {
    "--json": "Output as JSON envelope.",
    "--jsonl": "Output as newline-delimited JSON.",
    "--plain": "Unformatted text for downstream parsing.",
    "--quiet": "Suppress non-essential output.",
    "--dry-run": "Preview actions without executing.",
    "--schema": "Print command schema and exit.",
    "--help-agent": "Emit structured YAML help metadata.",
    "--agent-manifest": "Emit machine-readable agent manifest.",
    "--timeout": "Maximum execution time in seconds.",
    "--yes": "Skip interactive prompts.",
}


def _annotation_hints(meta: Any) -> dict[str, bool]:
    ann = meta.annotations
    if ann is None:
        return {}

    hints: dict[str, bool] = {}
    if getattr(ann, "read_only", False):
        hints["readOnlyHint"] = True
    if getattr(ann, "idempotent", False):
        hints["idempotentHint"] = True
    if getattr(ann, "destructive", False):
        hints["destructiveHint"] = True
    if getattr(ann, "open_world", False):
        hints["openWorldHint"] = True
    return hints


def _command_error_catalog_entries(tool_name: str, meta: Any) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for code, message in sorted(meta.error_codes.items(), key=lambda item: item[0]):
        entries.append({
            "code": code,
            "message": message,
            "command": tool_name,
        })
    return entries


def _command_input_output_schema(callback: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
    schema = generate_tool_schema(callback, name=getattr(callback, "__name__", "tool"))
    input_schema = schema.input_schema
    output_schema = schema.output_schema
    return input_schema, output_schema


def generate_agent_manifest(app: "Tooli") -> dict[str, Any]:
    """Build the v3 agent manifest from a Tooli app instance."""
    name = app.info.name or "tooli"
    tool = {
        "name": name,
        "version": app.version,
        "description": app.info.help or "",
        "install": f"pip install {name}",
        "python_requires": ">=3.10",
        "triggers": list(getattr(app, "triggers", []) or []),
        "anti_triggers": list(getattr(app, "anti_triggers", []) or []),
    }

    commands: list[dict[str, Any]] = []
    error_entries: list[dict[str, str]] = []
    for tool_def in app.get_tools():
        if tool_def.hidden:
            continue

        callback = tool_def.callback
        meta = get_command_meta(callback)

        input_schema, output_schema = _command_input_output_schema(callback)
        annotations = _annotation_hints(meta)

        entry: dict[str, Any] = {
            "name": tool_def.name,
            "description": tool_def.help or (callback.__doc__ or ""),
            "annotations": annotations,
            "inputSchema": input_schema,
            "outputSchema": output_schema,
            "examples": list(meta.examples),
            "error_codes": meta.error_codes,
            "cost_hint": meta.cost_hint,
            "supports_dry_run": bool(meta.supports_dry_run),
        }
        if meta.pipe_input is not None:
            entry["pipe_input"] = meta.pipe_input
        if meta.pipe_output is not None:
            entry["pipe_output"] = meta.pipe_output
        if meta.task_group is not None:
            entry["task_group"] = meta.task_group
        if meta.when_to_use is not None:
            entry["when_to_use"] = meta.when_to_use
        commands.append(entry)
        error_entries.extend(_command_error_catalog_entries(tool_def.name, meta))

    manifest: dict[str, Any] = {
        "manifest_version": "3.0",
        "tool": tool,
        "commands": commands,
        "global_flags": GLOBAL_FLAGS,
        "envelope_schema": {
            "success": {
                "ok": True,
                "result": "<command-specific-data>",
                "meta": {
                    "tool": f"{name}.<command>",
                    "version": app.version,
                    "duration_ms": 0,
                    "dry_run": False,
                    "truncated": False,
                    "next_cursor": None,
                    "warnings": [],
                },
            },
            "failure": {
                "ok": False,
                "error": {
                    "code": "E0000",
                    "category": "runtime",
                    "message": "See command output for details.",
                },
                "meta": {
                    "tool": f"{name}.<command>",
                    "version": app.version,
                    "duration_ms": 0,
                    "dry_run": False,
                    "truncated": False,
                    "next_cursor": None,
                    "warnings": [],
                },
            },
        },
        "error_catalog": error_entries,
        "exit_codes": {
            "0": "Success",
            "2": "Invalid usage / validation error",
            "10": "Not found / state error",
            "30": "Permission denied",
            "50": "Timeout / temporary external delay",
            "70": "Internal or runtime error",
            "101": "Human handoff required",
        },
        "workflows": list(getattr(app, "workflows", []) or []),
        "env_vars": getattr(app, "env_vars", {}),
        "rules": list(getattr(app, "rules", []) or []),
        "mcp": {
            "supported": True,
            "transports": ["stdio", "http", "sse"],
            "serve_command": f"{name} mcp serve --transport stdio",
        },
    }

    return manifest


def manifest_as_json(app: "Tooli", indent: int = 2) -> str:
    import json

    return json.dumps(generate_agent_manifest(app), indent=indent)
