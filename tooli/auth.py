"""Authorization context helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterable


def _parse_scopes(raw: str | None) -> frozenset[str]:
    if not raw:
        return frozenset()

    separators = (",", ";", " ")
    for separator in separators:
        raw = raw.replace(separator, ",")

    parts = {part.strip() for part in raw.split(",")}
    return frozenset(part for part in parts if part)


@dataclass(frozen=True)
class AuthContext:
    """Resolved authorization scopes for the current execution context."""

    scopes: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_env(cls, *, programmatic_scopes: Iterable[str] | None = None) -> "AuthContext":
        scopes = set(programmatic_scopes or ())
        scopes.update(_parse_scopes(os.getenv("TOOLI_AUTH_SCOPES")))
        return cls(frozenset(scopes))
