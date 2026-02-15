"""SmartInput system for Tooli: StdinOr[T] type and resolution."""

from __future__ import annotations

import os
import sys
import urllib.request
import warnings
from collections.abc import Iterable  # noqa: TC003
from pathlib import Path
from typing import Any, Generic, TypeVar

import click

from tooli.errors import InputError, ToolError

T = TypeVar("T")


class StdinOr(Generic[T]):
    """Type hint for parameters that can be populated from stdin or a file/URL."""

    pass


class SecretInput(Generic[T]):
    """Marker type for parameters that carry secret material."""

    __tooli_secret_input__ = True

    def __class_getitem__(cls, item: Any) -> type[SecretInput[T]]:  # pragma: no cover - generic marker behavior
        return cls


def is_secret_input(annotation: Any) -> bool:
    """Return True when an annotation indicates a secret input."""
    import types
    from typing import Annotated, Union, get_args, get_origin
    from typing import Any as _AnyType

    if annotation is _AnyType:
        return False

    origin = get_origin(annotation)

    if origin is Annotated:
        base, *_meta = get_args(annotation)
        return is_secret_input(base)

    # Handle Optional[X] / Union[X, None] on Python 3.10+
    if origin is Union or origin is getattr(types, "UnionType", None):
        return any(is_secret_input(arg) for arg in get_args(annotation) if arg is not type(None))

    return getattr(annotation, "__tooli_secret_input__", False)


def secret_env_var(param_name: str) -> str:
    """Return the default environment variable for a secret parameter."""
    return f"TOOLI_SECRET_{param_name.upper()}"


def read_secret_value_from_file(path: str) -> str:
    """Read secret text from a file path."""
    file_path = Path(path)
    if not file_path.exists():
        raise InputError(
            message=f"Secret file not found: {path}",
            code="E1100",
            details={"path": path},
        )
    if not file_path.is_file():
        raise InputError(message=f"Secret source is not a file: {path}", code="E1101", details={"path": path})

    try:
        return file_path.read_text(encoding="utf-8").strip()
    except Exception as e:
        raise InputError(
            message=f"Failed to read secret file '{path}': {e}",
            code="E1102",
            details={"path": path},
        ) from e


def read_secret_value_from_stdin() -> str:
    """Read raw secret text from stdin."""
    try:
        value = sys.stdin.read()
    except Exception as e:
        raise InputError(message=f"Failed to read secret from stdin: {e}", code="E1103", details={}) from e

    value = value.strip()
    if not value:
        raise InputError(message="Secret stdin input was empty", code="E1104")
    return value


def resolve_secret_value(
    *,
    explicit_value: str | None,
    param_name: str,
    file_path: str | None = None,
    use_stdin: bool = False,
    use_env: bool = True,
) -> str | None:
    """Resolve the concrete secret using supported input channels."""
    if explicit_value is not None:
        return explicit_value

    if file_path is not None:
        return read_secret_value_from_file(file_path)

    if use_stdin:
        return read_secret_value_from_stdin()

    if use_env:
        env_key = secret_env_var(param_name)
        env_val = os.getenv(env_key)
        if env_val is not None:
            warnings.warn(
                f"Using {env_key} for secret input is deprecated due leakage risk. Use --{param_name}-secret-file or --{param_name}-secret-stdin instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return env_val.strip()

    return explicit_value


def redact_secret_values(value: Any, secret_values: Iterable[str]) -> Any:
    """Recursively replace known secret values with a redaction marker."""
    redact = "***REDACTED***"
    secret_set = {s for s in secret_values if isinstance(s, str)}
    if not secret_set:
        return value
    if "" in secret_set:
        secret_set.discard("")

    if isinstance(value, str):
        redacted = value
        for secret in sorted(secret_set, key=len, reverse=True):
            redacted = redacted.replace(secret, redact)
        return redacted

    if isinstance(value, dict):
        return {k: redact_secret_values(v, secret_set) for k, v in value.items()}

    if isinstance(value, list):
        return [redact_secret_values(item, secret_set) for item in value]

    if isinstance(value, tuple):
        return tuple(redact_secret_values(item, secret_set) for item in value)

    return value

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
                if self.inner_type is Path:
                    return path
                return path.read_text()
            else:
                # If path doesn't exist, maybe it was meant to be raw string data?
                # But for StdinOr, we usually expect a source.
                # If inner_type is str and it doesn't look like a path, return as is?
                # No, better to be strict: if it's provided but not a file/URL/-, and we expect a source, fail.
                if self.inner_type is str:
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
                return response.read().decode("utf-8")  # type: ignore[no-any-return]
        except Exception as e:
            raise InputError(
                message=f"Failed to fetch URL '{url}': {e}",
                code="E1006",
            ) from e
