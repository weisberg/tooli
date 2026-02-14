"""Core Tooli application class extending Typer."""

from __future__ import annotations

from typing import Any

import typer

from tooli.command import TooliCommand


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

    def command(self, *args: Any, **kwargs: Any) -> Any:
        """Register a command using Tooli defaults.

        By default, Tooli uses TooliCommand to inject global flags and route
        return values through the output system.
        """

        kwargs.setdefault("cls", TooliCommand)
        decorator = super().command(*args, **kwargs)

        def _wrap(func: Any) -> Any:
            # Attach app-level metadata to the callback for downstream use
            # (e.g., envelopes).
            setattr(func, "__tooli_app_name__", self.info.name or "tooli")
            setattr(func, "__tooli_app_version__", self.version)
            setattr(func, "__tooli_default_output__", self.default_output)
            return decorator(func)

        return _wrap
