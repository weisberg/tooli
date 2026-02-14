"""Output sanitization helpers for security modes."""

from __future__ import annotations

import re
from typing import Any

ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
INJECTION_PATTERN = re.compile(r"\$\([^)]*\)|`[^`]+`")


def sanitize_text(value: str) -> str:
    """Strip control content and obvious injection-like shell patterns."""

    sanitized = ANSI_ESCAPE_PATTERN.sub("", value)
    sanitized = CONTROL_CHAR_PATTERN.sub("", sanitized)
    sanitized = INJECTION_PATTERN.sub("[redacted]", sanitized)
    return sanitized


def sanitize_output(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, dict):
        return {str(key): sanitize_output(val) for key, val in value.items()}
    if isinstance(value, list):
        return [sanitize_output(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_output(item) for item in value)
    if isinstance(value, set):
        return tuple(sanitize_output(item) for item in sorted(value, key=repr))
    return value
