"""Bootstrap logic for --agent-bootstrap flag."""

from __future__ import annotations

import os
from typing import Any


def _detect_target() -> str:
    """Auto-detect the best target format from environment."""
    if os.getenv("CLAUDE_CODE"):
        return "claude-code"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "claude-skill"
    return "generic-skill"


def generate_bootstrap(app: Any, *, target: str = "auto") -> str:
    """Produce a complete, deployable SKILL.md."""
    from tooli.docs.skill_v4 import generate_skill_md

    if target == "auto":
        target = _detect_target()
    return generate_skill_md(app, target=target)  # type: ignore[arg-type]
