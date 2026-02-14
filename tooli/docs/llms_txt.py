"""llms.txt and llms-full.txt generation for Tooli apps."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tooli.app import Tooli


def generate_llms_txt(app: Tooli) -> str:
    """Generate curated llms.txt content."""
    lines: list[str] = []
    name = app.info.name or "tooli-app"
    description = app.info.help or "An agent-native CLI application."

    lines.append(f"# {name}")
    lines.append("")
    lines.append(f"> {description}")
    lines.append("")
    lines.append("## Commands")
    lines.append("")

    for cmd in app.registered_commands:
        if cmd.hidden:
            continue
        cmd_name = cmd.name or cmd.callback.__name__
        help_text = cmd.help or cmd.callback.__doc__ or ""
        short_help = help_text.split("\n")[0]
        lines.append(f"- [{cmd_name}](llms-full.txt#{cmd_name}): {short_help}")

    lines.append("")
    lines.append("Optional: [Full Documentation](llms-full.txt)")
    return "\n".join(lines)


def generate_llms_full_txt(app: Tooli) -> str:
    """Generate expanded llms-full.txt content."""
    # For now, we can reuse SKILL.md logic as it's already quite detailed
    from tooli.docs.skill import generate_skill_md

    return generate_skill_md(app)
