"""Context object for Tooli command execution."""

from __future__ import annotations

from dataclasses import dataclass, field

import click
from typing import Any

from tooli.errors import InputError, Suggestion


@dataclass(frozen=True)
class ToolContext:
    """Standard context accessible via click.Context.obj."""

    quiet: bool = False
    verbose: int = 0
    dry_run: bool = False
    yes: bool = False
    timeout: float | None = None
    response_format: str = "concise"
    extra: dict[str, Any] = field(default_factory=dict)

    def confirm(self, message: str, *, default: bool = False) -> bool:
        """Request a confirmation in interactive mode.

        If --yes was provided, confirmation is automatically accepted.
        In non-TTY environments without --yes, raises an InputError instead of
        waiting on stdin.
        """

        if self.yes:
            return True

        stdin_is_tty = click.get_text_stream("stdin").isatty()
        if not stdin_is_tty:
            raise InputError(
                message=(
                    f"{message}. Add --yes to run without interactive confirmation "
                    "in non-interactive mode."
                ),
                code="E1007",
                suggestion=Suggestion(
                    action="provide yes flag",
                    fix="Re-run with --yes.",
                    example="mytool cleanup --yes",
                ),
                details={"prompt": message},
            )

        return click.confirm(message, default=default)
