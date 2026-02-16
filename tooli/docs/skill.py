"""Backward-compatible skill generation entrypoints."""

from __future__ import annotations

from tooli.docs.skill_v3 import (
    DetailLevel,
    SkillGenerator,
    estimate_skill_tokens,
    generate_skill_md,
    validate_skill_doc,
)

__all__ = [
    "DetailLevel",
    "SkillGenerator",
    "estimate_skill_tokens",
    "generate_skill_md",
    "validate_skill_doc",
]
