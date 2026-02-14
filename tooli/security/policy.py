"""Security policy resolution for Tooli command execution."""

from __future__ import annotations

import os
from enum import Enum


class SecurityPolicy(str, Enum):
    """Policy levels for destructive command execution."""

    OFF = "off"
    STANDARD = "standard"
    STRICT = "strict"


def resolve_security_policy(value: str | None = None) -> SecurityPolicy:
    """Resolve security mode from explicit value or `TOOLI_SECURITY_POLICY`."""

    candidate = (value or os.getenv("TOOLI_SECURITY_POLICY") or SecurityPolicy.STANDARD.value).strip().lower()
    if candidate in {SecurityPolicy.STANDARD.value, SecurityPolicy.STRICT.value, SecurityPolicy.OFF.value}:
        return SecurityPolicy(candidate)

    return SecurityPolicy.STANDARD
