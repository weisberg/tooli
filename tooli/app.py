"""Core Tooli application class extending Typer."""

from __future__ import annotations

from typing import Any

import typer


class Tooli(typer.Typer):
    """Agent-native CLI framework extending Typer.

    Tooli wraps Typer to produce CLI tools that are simultaneously
    human-friendly and machine-consumable by AI agents. The public API
    is Tooli-native — Typer is an implementation detail.
    """

    def __init__(
        self,
        *args: Any,
        version: str = "0.0.0",
        default_output: str = "auto",
        mcp_transport: str = "stdio",
        skill_auto_generate: bool = False,
        permissions: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)

        # Tooli-specific configuration
        self.version = version
        self.default_output = default_output
        self.mcp_transport = mcp_transport
        self.skill_auto_generate = skill_auto_generate
        self.permissions = permissions or {}
