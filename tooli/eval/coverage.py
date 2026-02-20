"""Metadata coverage reporter for Tooli apps."""

from __future__ import annotations

from typing import Any

from tooli.command_meta import get_command_meta
from tooli.docs.skill_v4 import estimate_skill_tokens


def _annotation_labels(callback: Any) -> list[str]:
    meta = get_command_meta(callback).annotations
    if meta is None:
        return []
    labels: list[str] = []
    if getattr(meta, "read_only", False):
        labels.append("read-only")
    if getattr(meta, "idempotent", False):
        labels.append("idempotent")
    if getattr(meta, "destructive", False):
        labels.append("destructive")
    if getattr(meta, "open_world", False):
        labels.append("open-world")
    return labels


def eval_coverage(app: Any) -> dict[str, Any]:
    """Report metadata coverage across all visible commands.

    Returns a dict with per-command details and aggregate statistics.
    """
    tools = [t for t in app.get_tools() if not t.hidden]
    commands: list[dict[str, Any]] = []
    warnings: list[str] = []

    total = len(tools)
    with_examples = 0
    with_output_schema = 0
    with_error_codes = 0
    with_annotations = 0
    with_help_text = 0
    with_when_to_use = 0
    with_task_group = 0
    with_pipe_contracts = 0

    for tool_def in tools:
        meta = get_command_meta(tool_def.callback)
        entry: dict[str, Any] = {"name": tool_def.name, "issues": []}

        has_examples = bool(meta.examples)
        has_error_codes = bool(meta.error_codes)
        has_annotations = bool(_annotation_labels(tool_def.callback))
        has_help = bool((tool_def.help or tool_def.callback.__doc__ or "").strip())
        has_when_to_use = bool(meta.when_to_use)
        has_task_group = bool(meta.task_group)
        has_pipes = False  # pipe contracts removed in v6.0

        if has_examples:
            with_examples += 1
        else:
            entry["issues"].append("missing examples")

        # Check output schema
        try:
            from tooli.schema import generate_tool_schema
            schema = generate_tool_schema(tool_def.callback, name=tool_def.name)
            has_output_schema = schema.output_schema is not None
        except Exception:
            has_output_schema = False

        if has_output_schema:
            with_output_schema += 1
        else:
            entry["issues"].append("missing output schema")
            if meta.output_example is None:
                warnings.append(f"{tool_def.name}: dict return without output_example")

        if has_error_codes:
            with_error_codes += 1
        else:
            entry["issues"].append("missing error codes")

        if has_annotations:
            with_annotations += 1
        else:
            entry["issues"].append("missing annotations")

        if has_help:
            with_help_text += 1
        else:
            entry["issues"].append("missing help text")

        if has_when_to_use:
            with_when_to_use += 1

        if has_task_group:
            with_task_group += 1

        if has_pipes:
            with_pipe_contracts += 1

        entry["coverage"] = {
            "examples": has_examples,
            "output_schema": has_output_schema,
            "error_codes": has_error_codes,
            "annotations": has_annotations,
            "help_text": has_help,
            "when_to_use": has_when_to_use,
            "task_group": has_task_group,
            "pipe_contracts": has_pipes,
        }
        commands.append(entry)

    # Estimate token count
    try:
        from tooli.docs.skill_v4 import generate_skill_md
        skill_content = generate_skill_md(app)
        token_estimate = estimate_skill_tokens(skill_content)
    except Exception:
        token_estimate = 0

    return {
        "total_commands": total,
        "coverage": {
            "examples": with_examples,
            "output_schema": with_output_schema,
            "error_codes": with_error_codes,
            "annotations": with_annotations,
            "help_text": with_help_text,
            "when_to_use": with_when_to_use,
            "task_group": with_task_group,
            "pipe_contracts": with_pipe_contracts,
        },
        "token_estimate": token_estimate,
        "commands": commands,
        "warnings": warnings,
    }
