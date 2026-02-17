"""Generate ``# tooli:agent`` source-level hint blocks."""

from __future__ import annotations

import re
from typing import Any

from tooli.command_meta import get_command_meta


def generate_source_hints(app: Any) -> str:
    """Produce a ``# tooli:agent ... # tooli:end`` comment block.

    The block summarises command names, annotations, and key metadata
    so that LLMs reading source code can orient themselves quickly.
    """
    lines = ["# tooli:agent"]
    name = app.info.name or "tooli-app"
    lines.append(f"# app: {name} v{getattr(app, 'version', '0.0.0')}")
    lines.append(f"# description: {(app.info.help or '').strip()}")

    visible = [t for t in app.get_tools() if not t.hidden]
    for tool_def in visible:
        meta = get_command_meta(tool_def.callback)
        ann = meta.annotations
        labels: list[str] = []
        if ann is not None:
            if getattr(ann, "read_only", False):
                labels.append("read-only")
            if getattr(ann, "idempotent", False):
                labels.append("idempotent")
            if getattr(ann, "destructive", False):
                labels.append("destructive")
            if getattr(ann, "open_world", False):
                labels.append("open-world")
        ann_text = f" [{', '.join(labels)}]" if labels else ""
        group_text = f" group={meta.task_group}" if meta.task_group else ""
        lines.append(f"# cmd: {tool_def.name}{ann_text}{group_text}")
    lines.append("# tooli:end")
    return "\n".join(lines) + "\n"


def insert_source_hints(source: str, hints: str) -> str:
    """Insert or replace a ``# tooli:agent`` block in Python source.

    The block is placed after the module docstring and before the first
    import.  If a block already exists it is replaced.
    """
    # Remove existing block
    source = re.sub(
        r"^# tooli:agent\n.*?^# tooli:end\n?",
        "",
        source,
        flags=re.MULTILINE | re.DOTALL,
    )

    # Find insertion point: after module docstring, before first import
    match = re.search(r'^(from |import )', source, flags=re.MULTILINE)
    if match:
        insert_at = match.start()
        return source[:insert_at] + hints + "\n" + source[insert_at:]

    # No imports found; append
    return source.rstrip() + "\n\n" + hints


def parse_source_hints(source: str) -> dict[str, Any] | None:
    """Parse an existing ``# tooli:agent`` block from source text."""
    match = re.search(
        r"^# tooli:agent\n(.*?)^# tooli:end",
        source,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        return None

    result: dict[str, Any] = {"commands": []}
    for line in match.group(1).splitlines():
        line = line.lstrip("# ").strip()
        if line.startswith("app:"):
            result["app"] = line[4:].strip()
        elif line.startswith("description:"):
            result["description"] = line[12:].strip()
        elif line.startswith("cmd:"):
            result["commands"].append(line[4:].strip())
    return result
