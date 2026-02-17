"""Analyze and suggest metadata improvements for Tooli apps."""

from __future__ import annotations

from typing import Any

from tooli.command_meta import get_command_meta


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


def analyze_metadata(app: Any) -> dict[str, Any]:
    """Analyze app and return suggestions for metadata improvements."""
    tools = [t for t in app.get_tools() if not t.hidden]
    suggestions: list[dict[str, Any]] = []

    for tool_def in tools:
        meta = get_command_meta(tool_def.callback)
        cmd_suggestions: list[str] = []

        if not meta.examples:
            cmd_suggestions.append("Add examples for better agent understanding")

        if not meta.error_codes:
            cmd_suggestions.append("Declare error_codes for predictable error handling")

        if not _annotation_labels(tool_def.callback):
            cmd_suggestions.append("Add annotations (ReadOnly, Idempotent, Destructive, OpenWorld)")

        if not meta.when_to_use:
            cmd_suggestions.append("Add when_to_use for task-oriented SKILL.md")

        if not meta.task_group:
            cmd_suggestions.append("Add task_group for grouped command documentation")

        if meta.pipe_input is None and meta.pipe_output is None:
            cmd_suggestions.append("Add pipe_input/pipe_output for composition patterns")

        if not meta.recovery_playbooks and meta.error_codes:
            cmd_suggestions.append("Add recovery_playbooks for inline error guidance")

        if meta.output_example is None and not meta.expected_outputs:
            cmd_suggestions.append("Add output_example or expected_outputs for example rendering")

        if cmd_suggestions:
            suggestions.append({
                "command": tool_def.name,
                "suggestions": cmd_suggestions,
            })

    return {
        "total_commands": len(tools),
        "commands_with_suggestions": len(suggestions),
        "suggestions": suggestions,
    }


def generate_upgrade_stubs(app: Any) -> dict[str, str]:
    """Generate Python code stubs for missing metadata.

    Returns a dict mapping command names to suggested decorator kwargs.
    """
    tools = [t for t in app.get_tools() if not t.hidden]
    stubs: dict[str, str] = {}

    for tool_def in tools:
        meta = get_command_meta(tool_def.callback)
        parts: list[str] = []

        if not meta.when_to_use:
            help_text = (tool_def.help or tool_def.callback.__doc__ or "").strip()
            first_line = help_text.splitlines()[0] if help_text else tool_def.name
            parts.append(f'    when_to_use="{first_line}",')

        if not meta.task_group:
            parts.append('    task_group="General",')

        if not meta.recovery_playbooks and meta.error_codes:
            parts.append("    recovery_playbooks={},  # TODO: fill in")

        if parts:
            stubs[tool_def.name] = "\n".join(parts)

    return stubs
