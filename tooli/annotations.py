"""Behavioral annotations for Tooli commands."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolAnnotation:
    """Behavioral hint for agents."""

    read_only: bool = False
    idempotent: bool = False
    destructive: bool = False
    open_world: bool = False

    def __or__(self, other: ToolAnnotation) -> ToolAnnotation:
        return ToolAnnotation(
            read_only=self.read_only or other.read_only,
            idempotent=self.idempotent or other.idempotent,
            destructive=self.destructive or other.destructive,
            open_world=self.open_world or other.open_world,
        )


ReadOnly = ToolAnnotation(read_only=True)
Idempotent = ToolAnnotation(idempotent=True)
Destructive = ToolAnnotation(destructive=True)
OpenWorld = ToolAnnotation(open_world=True)
