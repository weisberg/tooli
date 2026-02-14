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

        # Register built-in commands
        self._register_builtins()

    def _register_builtins(self) -> None:
        @self.command(name="generate-skill", hidden=True)
        def generate_skill() -> None:
            """Generate SKILL.md for this application."""
            from tooli.docs.skill import generate_skill_md
            content = generate_skill_md(self)
            with open("SKILL.md", "w") as f:
                f.write(content)
            # Use click.echo as we are in a CLI context
            import click
            click.echo("Generated SKILL.md")

    def command(
        self,
        name: str | None = None,
        *,
        annotations: Any | None = None,
        examples: list[dict[str, Any]] | None = None,
        error_codes: dict[str, str] | None = None,
        timeout: float | None = None,
        cost_hint: str | None = None,
        human_in_the_loop: bool = False,
        auth: list[str] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Register a command using Tooli defaults and metadata.

        By default, Tooli uses TooliCommand to inject global flags and route
        return values through the output system.
        """

        kwargs.setdefault("cls", TooliCommand)
        decorator = super().command(name=name, **kwargs)

        def _wrap(func: Any) -> Any:
            # Attach app-level metadata to the callback for downstream use
            # (e.g., envelopes).
            setattr(func, "__tooli_app_name__", self.info.name or "tooli")
            setattr(func, "__tooli_app_version__", self.version)
            setattr(func, "__tooli_default_output__", self.default_output)

            # Attach command-level metadata
            setattr(func, "__tooli_annotations__", annotations)
            setattr(func, "__tooli_examples__", examples or [])
            setattr(func, "__tooli_error_codes__", error_codes or {})
            setattr(func, "__tooli_timeout__", timeout)
            setattr(func, "__tooli_cost_hint__", cost_hint)
            setattr(func, "__tooli_human_in_the_loop__", human_in_the_loop)
            setattr(func, "__tooli_auth__", auth or [])

            return decorator(func)

        return _wrap
