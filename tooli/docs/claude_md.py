"""Generate CLAUDE.md files optimized for Claude Code workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tooli.command_meta import get_command_meta

if TYPE_CHECKING:
    from tooli.app import Tooli


def _line_for_command(tooli_name: str, command_name: str | None, callback: object) -> str:
    examples = get_command_meta(callback).examples
    if examples:
        first = examples[0]
        args = first.get("args", [])
        if isinstance(args, list):
            arg_text = " ".join(str(arg) for arg in args if arg is not None)
            return f"- `{tooli_name} {command_name} {arg_text}`"

    return f"- `{tooli_name} {command_name}`"


def generate_claude_md(app: "Tooli") -> str:
    """Generate concise CLAUDE.md content for the CLI app."""
    app_name = app.info.name or "tooli-app"
    app_help = app.info.help or "An agent-native CLI application."
    lines = [
        f"# CLAUDE.md — {app_name}",
        "",
        "## Project overview",
        "",
        f"{app_help}",
        "",
        "This project is built with Tooli and should be used through machine-friendly outputs.",
        "",
        "## Key commands",
        "",
    ]

    for tool_def in app.get_tools():
        if tool_def.hidden:
            continue
        lines.append(_line_for_command(app_name, tool_def.name, tool_def.callback))

    lines.extend(
        [
            "",
            "## Important patterns",
            "",
            "- Always check `ok` before reading `result`.",
            "- Use `--json` for machine-readable output.",
            "- Use `--dry-run` before destructive operations.",
            "- Use `--schema` to inspect parameters and output contracts.",
            "",
            "## Testing",
            "",
            "Run `eval analyze` for invocation summaries and `eval agent-test` for agent-facing validation.",
            "",
            "## Skill and protocol docs",
            "",
            "- See `SKILL.md` for full command-level documentation.",
            "- Use `--help-agent` for per-command structured metadata.",
        ]
    )
    return "\n".join(lines)
