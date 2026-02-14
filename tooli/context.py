"""Context object for Tooli command execution."""

from __future__ import annotations

from dataclasses import dataclass, field


from typing import Any


@dataclass(frozen=True)
class ToolContext:
    """Standard context accessible via click.Context.obj."""

    quiet: bool = False
    verbose: int = 0
    dry_run: bool = False
    yes: bool = False
    timeout: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)
