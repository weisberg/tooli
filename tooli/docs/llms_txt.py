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

    for tool_def in app.get_tools():
        if tool_def.hidden:
            continue
        short_help = (tool_def.help or tool_def.callback.__doc__ or "").split("\n")[0]
        lines.append(f"- [{tool_def.name}](llms-full.txt#{tool_def.name}): {short_help}")

    lines.append("")
    lines.append("Optional: [Full Documentation](llms-full.txt)")
    return "\n".join(lines)


def generate_llms_full_txt(app: Tooli) -> str:
    """Generate expanded llms-full.txt content."""
    # For now, we can reuse SKILL.md logic as it's already quite detailed
    from tooli.docs.skill import generate_skill_md

    return generate_skill_md(app)
