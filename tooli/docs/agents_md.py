"""AGENTS.md generator for GitHub Copilot and OpenAI Codex compatibility."""

from __future__ import annotations

import inspect
from typing import Any, get_args, get_origin

from tooli.command_meta import get_command_meta


def _readable_type(annotation: Any) -> str:
    """Return a human-readable type string from a type annotation."""
    if annotation is inspect.Signature.empty:
        return "any"
    if annotation is Any:
        return "any"
    if isinstance(annotation, str):
        return annotation
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        name = getattr(origin, "__name__", str(origin))
        if args:
            return f"{name}[{', '.join(_readable_type(a) for a in args)}]"
        return name
    if hasattr(annotation, "__name__"):
        return str(annotation.__name__)
    return str(annotation)


def _annotation_labels(callback: Any) -> list[str]:
    """Extract annotation labels (read-only, idempotent, etc.) from a callback."""
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


def _command_params(callback: Any) -> list[tuple[str, Any, Any, str]]:
    """Extract parameter info from a callback function signature."""
    try:
        type_hints = inspect.get_annotations(callback)
    except Exception:
        type_hints = {}
    params: list[tuple[str, Any, Any, str]] = []
    for param in inspect.signature(callback).parameters.values():
        if param.kind in {inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL}:
            continue
        if param.name in {"ctx", "context"}:
            continue
        annotation = type_hints.get(param.name, param.annotation)
        # Try to extract help text from Annotated metadata
        description = ""
        if get_origin(annotation) is not None:
            args = get_args(annotation)
            if args:
                for meta_item in args[1:]:
                    help_text = getattr(meta_item, "help", None)
                    if help_text:
                        description = str(help_text)
                        break
        params.append((param.name, annotation, param.default, description))
    return params


def _is_required(default: Any) -> bool:
    return default is inspect.Signature.empty or default is Ellipsis


def _collect_visible_commands(app: Any) -> list[Any]:
    """Collect non-hidden commands from a Tooli app."""
    return [tool_def for tool_def in app.get_tools() if not tool_def.hidden]


def generate_agents_md(app: Any) -> str:
    """Generate an AGENTS.md document from a Tooli app.

    AGENTS.md is the documentation format read by GitHub Copilot and
    OpenAI Codex for repository-level agent instructions.
    """
    app_name = app.info.name or "tooli-app"
    app_help = (app.info.help or "An agent-native CLI application.").strip()
    version = getattr(app, "version", "0.0.0")

    lines: list[str] = []

    # Header
    lines.extend([
        "# AGENTS.md",
        "",
        "## Project Overview",
        "",
        f"{app_help}",
        "",
        f"- **Name**: {app_name}",
        f"- **Version**: {version}",
        "- **Framework**: Tooli (agent-native CLI)",
        "",
    ])

    # Available Commands
    lines.extend(["## Available Commands", ""])

    tools = _collect_visible_commands(app)
    for tool_def in tools:
        callback = tool_def.callback
        help_text = (tool_def.help or callback.__doc__ or "").strip()
        short_help = help_text.splitlines()[0] if help_text else tool_def.name

        lines.extend([f"### {tool_def.name}", "", short_help, ""])

        # Usage
        params = _command_params(callback)
        required_args = [
            f"<{name}>"
            for name, _ann, default, _desc in params
            if _is_required(default)
        ]
        arg_str = " " + " ".join(required_args) if required_args else ""
        lines.extend([
            "**Usage:**",
            "",
            "```bash",
            f"{app_name} {tool_def.name}{arg_str} --json",
            "```",
            "",
        ])

        # Parameters
        lines.append("**Parameters:**")
        if params:
            for name, annotation, default, description in params:
                required_str = "required" if _is_required(default) else "optional"
                type_str = _readable_type(annotation)
                desc_str = f": {description}" if description else ""
                if not _is_required(default) and default is not None:
                    desc_str += f" (default: {default})"
                lines.append(f"- `{name}` ({required_str}, {type_str}){desc_str}")
        else:
            lines.append("- None")
        lines.append("")

        # Output
        lines.append("**Output:** JSON envelope with `ok`, `result`, `meta` fields.")
        lines.append("")

        # Behavior annotations
        labels = _annotation_labels(callback)
        if labels:
            lines.append(f"**Behavior:** {', '.join(labels)}")
            lines.append("")

    # Output Format
    lines.extend([
        "## Output Format",
        "",
        "All commands support `--json` for structured output:",
        "",
        "```json",
        '{',
        '  "ok": true,',
        '  "result": [...],',
        '  "meta": ' + '{' + f'"tool": "{app_name}.<cmd>", "version": "{version}", "duration_ms": 34' + '}',
        '}',
        "```",
        "",
        "On error:",
        "",
        "```json",
        '{',
        '  "ok": false,',
        '  "error": ' + '{' + '"code": "E3001", "message": "...", "suggestion": ' + '{' + '...' + '}' + '}',
        '}',
        "```",
        "",
    ])

    # Important Rules
    rules = [
        "Always use `--json` flag when invoking programmatically.",
        "Check the `ok` field before accessing `result`.",
        "Use `--dry-run` before destructive commands.",
        "Use `--yes` to skip confirmation prompts in automation.",
    ]
    app_rules = list(getattr(app, "rules", []) or [])
    for rule in app_rules:
        if rule not in rules:
            rules.append(rule)

    lines.extend(["## Important Rules", ""])
    for rule in rules:
        lines.append(f"- {rule}")
    lines.append("")

    return "\n".join(lines)
