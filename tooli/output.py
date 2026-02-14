"""Output mode detection and resolution for Tooli."""

from __future__ import annotations

import os
import sys
from enum import Enum

import click


class OutputMode(str, Enum):
    AUTO = "auto"
    JSON = "json"
    JSONL = "jsonl"
    TEXT = "text"
    PLAIN = "plain"


class ResponseFormat(str, Enum):
    CONCISE = "concise"
    DETAILED = "detailed"


def is_tty() -> bool:
    """Return True if stdout is an interactive terminal.

    This wrapper exists to make TTY behavior testable.
    """

    try:
        return bool(sys.stdout.isatty())
    except Exception:
        return False


def parse_output_mode(value: str) -> OutputMode:
    normalized = value.strip().lower()
    for mode in OutputMode:
        if normalized == mode.value:
            return mode
    raise click.BadParameter(f"Invalid output mode: {value!r}")


def resolve_output_mode(ctx: click.Context) -> OutputMode:
    """Resolve output mode for the current invocation.

    Precedence:
    1) explicit CLI flags captured into ctx.meta (last flag wins)
    2) auto-detection (TTY -> AUTO, non-TTY -> JSON)
    3) TOOLI_OUTPUT env var override
    """

    explicit: OutputMode | None = ctx.meta.get("tooli_output_override")
    if explicit is not None:
        return explicit

    mode = OutputMode.AUTO if is_tty() else OutputMode.JSON

    env = os.getenv("TOOLI_OUTPUT")
    if env:
        mode = parse_output_mode(env)

    return mode


def resolve_no_color(ctx: click.Context) -> bool:
    """Return True if color/markup should be disabled."""

    if bool(ctx.meta.get("tooli_no_color")):
        return True
    return bool(os.getenv("NO_COLOR"))


def parse_response_format(value: str) -> ResponseFormat:
    normalized = value.strip().lower()
    for response_format in ResponseFormat:
        if normalized == response_format.value:
            return response_format
    raise click.BadParameter(f"Invalid response format: {value!r}")


def resolve_response_format(ctx: click.Context) -> ResponseFormat:
    """Return response format from CLI override or default."""

    explicit = ctx.meta.get("tooli_response_format")
    if isinstance(explicit, ResponseFormat):
        return explicit
    if isinstance(explicit, str):
        return parse_response_format(explicit)
    return ResponseFormat.CONCISE
