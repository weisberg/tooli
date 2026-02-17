"""Enhanced CLAUDE.md generator with richer agent-facing sections."""

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


def generate_claude_md_v2(app: Any) -> str:
    """Generate a richer CLAUDE.md with architecture and workflow sections."""
    app_name = app.info.name or "tooli-app"
    app_help = (app.info.help or "An agent-native CLI application.").strip()
    version = getattr(app, "version", "0.0.0")

    lines = [
        f"# {app_name}",
        "",
        f"{app_help}",
        "",
    ]

    # Build & Test
    lines.extend([
        "## Build & Test",
        "",
        "```bash",
        f"pip install {app_name}",
        f"{app_name} --help",
        "```",
        "",
    ])

    # Architecture
    lines.extend([
        "## Architecture",
        "",
        "- **Framework**: Tooli v4 (agent-native CLI)",
        f"- **Version**: {version}",
        "- **Output**: All commands support `--json` for machine-readable output",
        "- **Error handling**: Structured errors with codes, categories, and suggestions",
        "",
    ])

    # Agent invocation
    lines.extend([
        "## Agent Invocation",
        "",
        "Set `TOOLI_CALLER` to identify your agent before invoking commands:",
        "",
        f"```bash\nTOOLI_CALLER=claude-code {app_name} <command> --json\n```",
        "",
        "This gives the tool 100% confidence in agent detection (no heuristic probing),",
        "and populates `caller_id`, `caller_version`, `session_id` in the envelope `meta`.",
        "",
        "Use `--json` for all agent invocations. The envelope format is:",
        "",
        '```json\n{"ok": true, "result": ..., "meta": {"tool": "...", "version": "...", "caller_id": "..."}}\n```',
        "",
    ])

    # Key commands
    lines.extend(["## Key Commands", ""])
    tools = [t for t in app.get_tools() if not t.hidden]

    for tool_def in tools:
        meta = get_command_meta(tool_def.callback)
        labels = _annotation_labels(tool_def.callback)
        label_str = f" [{', '.join(labels)}]" if labels else ""

        cap_str = f" needs:{','.join(meta.capabilities)}" if meta.capabilities else ""

        examples = meta.examples
        if examples:
            first = examples[0]
            args = first.get("args", [])
            if isinstance(args, list):
                arg_text = " ".join(str(a) for a in args if a is not None)
                lines.append(f"- `{app_name} {tool_def.name} {arg_text}`{label_str}{cap_str}")
            else:
                lines.append(f"- `{app_name} {tool_def.name}`{label_str}{cap_str}")
        else:
            lines.append(f"- `{app_name} {tool_def.name}`{label_str}{cap_str}")

    lines.append("")

    # Key Patterns
    lines.extend([
        "## Key Patterns",
        "",
        "- Always check `ok` before reading `result`.",
        "- Use `--json` for machine-readable output.",
        "- Use `--dry-run` before destructive operations.",
        "- Use `--schema` to inspect parameters and output contracts.",
        "- Use `--agent-bootstrap` to regenerate SKILL.md.",
        "",
    ])

    # Development Workflow
    lines.extend([
        "## Development Workflow",
        "",
        "1. Use `--schema` to understand command parameters.",
        "2. Use `--dry-run` to preview destructive operations.",
        "3. Use `--json` for all agent interactions.",
        "4. Check `meta.truncated` and paginate with `--cursor` when needed.",
        "5. Use `eval analyze` for invocation summaries.",
        "",
    ])

    # Skill docs reference
    lines.extend([
        "## Skill and Protocol Docs",
        "",
        "- See `SKILL.md` for full command-level documentation.",
        "- Use `--help-agent` for per-command structured metadata.",
        "- Use `--agent-manifest` for machine-readable manifest.",
    ])

    return "\n".join(lines) + "\n"
