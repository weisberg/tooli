"""SmartInput system for Tooli: StdinOr[T] type and resolution."""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path
from typing import Any, Generic, TypeVar, Union

import click

from tooli.errors import InputError, ToolError

T = TypeVar("T")


class StdinOr(Generic[T]):
    """Type hint for parameters that can be populated from stdin or a file/URL."""

    pass


class StdinOrType(click.ParamType):
    """Click ParamType for StdinOr resolution."""

    name = "stdin_or"

    def __init__(self, inner_type: Any = str) -> None:
        self.inner_type = inner_type

    def convert(self, value: Any, param: click.Parameter | None, ctx: click.Context | None) -> Any:
        # 1. Explicit '-' means stdin
        if value == "-":
            return self._read_stdin()

        # 2. If it's a URL, try to fetch it
        if isinstance(value, str) and (value.startswith("http://") or value.startswith("https://")):
            return self._read_url(value)

        # 3. If no value provided, check if stdin is piped
        if value is None:
            if not sys.stdin.isatty():
                return self._read_stdin()
            else:
                raise InputError(
                    message=f"Missing input for parameter '{param.name if param else 'unknown'}'",
                    code="E1002",
                )

        # 4. Otherwise, treat as a path
        try:
            path = Path(value)
            if path.exists():
                if self.inner_type == Path:
                    return path
                return path.read_text()
            else:
                # If path doesn't exist, maybe it was meant to be raw string data?
                # But for StdinOr, we usually expect a source.
                # If inner_type is str and it doesn't look like a path, return as is?
                # No, better to be strict: if it's provided but not a file/URL/-, and we expect a source, fail.
                if self.inner_type == str:
                    return value
                raise InputError(
                    message=f"Input path does not exist: {value}",
                    code="E1003",
                )
        except Exception as e:
            if isinstance(e, ToolError):
                raise
            raise InputError(
                message=f"Failed to resolve input from '{value}': {e}",
                code="E1004",
            ) from e

    def _read_stdin(self) -> str:
        try:
            return sys.stdin.read()
        except Exception as e:
            raise InputError(
                message=f"Failed to read from stdin: {e}",
                code="E1005",
            ) from e

    def _read_url(self, url: str) -> str:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return response.read().decode("utf-8")
        except Exception as e:
            raise InputError(
                message=f"Failed to fetch URL '{url}': {e}",
                code="E1006",
            ) from e
