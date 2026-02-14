"""SKILL.md generation from Tooli app introspection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tooli.app import Tooli


def generate_skill_md(app: Tooli) -> str:
    """Generate SKILL.md content for a Tooli application."""
    lines = []
    
    name = app.info.name or "tooli-app"
    description = app.info.help or "An agent-native CLI application."
    
    lines.append(f"# {name}")
    lines.append("")
    lines.append(description)
    lines.append("")
    
    lines.append("## Commands")
    lines.append("")
    
    # Typer commands are stored in app.registered_commands
    for cmd in app.registered_commands:
        cmd_name = cmd.name or cmd.callback.__name__
        help_text = cmd.help or cmd.callback.__doc__ or ""
        short_help = help_text.split("
")[0]
        lines.append(f"* **{cmd_name}**: {short_help}")
    
    lines.append("")
    
    for cmd in app.registered_commands:
        cmd_name = cmd.name or cmd.callback.__name__
        help_text = cmd.help or cmd.callback.__doc__ or ""
        
        lines.append(f"### `{cmd_name}`")
        lines.append("")
        lines.append(help_text)
        lines.append("")
        
        # Behavioral annotations
        annotations = getattr(cmd.callback, "__tooli_annotations__", None)
        if annotations:
            from tooli.annotations import ToolAnnotation
            if isinstance(annotations, ToolAnnotation):
                hints = []
                if annotations.read_only: hints.append("read-only")
                if annotations.idempotent: hints.append("idempotent")
                if annotations.destructive: hints.append("destructive")
                if annotations.open_world: hints.append("open-world")
                if hints:
                    lines.append(f"**Behavior**: `[{', '.join(hints)}]`")
                    lines.append("")

        # Examples
        examples = getattr(cmd.callback, "__tooli_examples__", [])
        if examples:
            lines.append("**Examples**:")
            lines.append("")
            for ex in examples:
                args = " ".join(ex.get("args", []))
                desc = ex.get("description", "")
                lines.append(f"```bash
{name} {cmd_name} {args}
```")
                if desc:
                    lines.append(f"> {desc}")
                lines.append("")

    lines.append("## Exit Codes")
    lines.append("")
    lines.append("| Code | Meaning |")
    lines.append("|---|---|")
    lines.append("| 0 | Success |")
    lines.append("| 2 | Invalid usage / validation error |")
    lines.append("| 10 | Not found |")
    lines.append("| 30 | Permission denied |")
    lines.append("| 50 | Timeout |")
    lines.append("| 70 | Internal error |")
    lines.append("| 101 | Human handoff required |")
    
    return "
".join(lines)
