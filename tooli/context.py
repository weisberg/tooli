"""Context object for Tooli command execution."""

from __future__ import annotations

import builtins
import io  # noqa: TC003
import os
from dataclasses import dataclass, field
from typing import Any

import click

from tooli.auth import AuthContext  # noqa: TC001
from tooli.errors import InputError, Suggestion


@dataclass(frozen=True)
class ToolContext:
    """Standard context accessible via click.Context.obj."""

    quiet: bool = False
    verbose: int = 0
    dry_run: bool = False
    force: bool = False
    yes: bool = False
    idempotency_key: str | None = None
    timeout: float | None = None
    response_format: str = "concise"
    auth: AuthContext | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def confirm(self, message: str, *, default: bool = False, allow_yes_override: bool = True) -> bool:
        """Request a confirmation in interactive mode.

        If --yes was provided, confirmation is automatically accepted.
        When stdin is not a TTY, read from the platform's tty/console device.
        """

        if allow_yes_override and self.yes:
            return True

        if click.get_text_stream("stdin").isatty():
            return click.confirm(message, default=default)

        prompt_stream = _open_tty_prompt_stream()
        if prompt_stream is None:
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

        with prompt_stream:
            return _read_confirmation_response(message, prompt_stream, default=default)


def _prompt_device_path() -> str:
    """Return the platform-specific prompt device."""

    if os.name == "nt":
        return "CON"
    return "/dev/tty"


def _open_tty_prompt_stream() -> io.TextIOBase | None:
    """Open the tty/console stream for confirmation prompts.

    Returns ``None`` when the platform prompt device cannot be opened.
    """

    path = _prompt_device_path()
    try:
        return _open(path, "r+", encoding="utf-8")
    except OSError:
        return None


# Module-level alias used by _open_tty_prompt_stream so tests can monkeypatch it.
_open = builtins.open


def _read_confirmation_response(message: str, stream: io.TextIOBase, *, default: bool) -> bool:
    """Read and parse a yes/no confirmation answer from the stream."""

    response = stream.readline()
    if response == "":
        return default

    value = response.strip().lower()
    if value == "":
        return default
    if value in {"y", "yes"}:
        return True
    if value in {"n", "no"}:
        return False

    raise InputError(
        message=f"Invalid confirmation response: {response.strip()}",
        code="E1008",
        suggestion=Suggestion(
            action="provide a valid confirmation answer",
            fix="Type y or n.",
            example=f"{message} [y/N] y",
        ),
        details={
            "prompt": message,
            "response": response.strip(),
            "valid_values": ["y", "yes", "n", "no"],
        },
    )
