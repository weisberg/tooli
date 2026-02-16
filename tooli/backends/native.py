"""Native backend primitives for Tooli command metadata.

The v3 roadmap introduces a native parser backend so Tooli can eventually work
without Typer/Click. During the v3 transition this module provides backend-agnostic
`Argument` and `Option` marker classes that remain API-compatible with Typer-style
annotations when used with `Annotated`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeVar


_AnnotationValue = TypeVar("_AnnotationValue")


@dataclass(frozen=True, init=False)
class _BaseMarker:
    """Shared metadata holder for Argument/Option annotations."""

    args: tuple[Any, ...] = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        object.__setattr__(self, "args", args)
        object.__setattr__(self, "kwargs", kwargs)


@dataclass(frozen=True, init=False)
class Argument(_BaseMarker):
    """Backend-agnostic marker for positional arguments.

    This intentionally stores the same metadata used by Typer's `Argument` helper
    so we can translate when a Typer backend is active.
    """

    def as_typer(self) -> Any:
        try:
            from typer import Argument as _TyperArgument
        except Exception as exc:  # pragma: no cover - exercised in optional backend tests
            raise RuntimeError("Typer backend is not available.") from exc
        return _TyperArgument(*self.args, **self.kwargs)


@dataclass(frozen=True, init=False)
class Option(_BaseMarker):
    """Backend-agnostic marker for command options."""

    def as_typer(self) -> Any:
        try:
            from typer import Option as _TyperOption
        except Exception as exc:  # pragma: no cover - exercised in optional backend tests
            raise RuntimeError("Typer backend is not available.") from exc
        return _TyperOption(*self.args, **self.kwargs)


# Backward-compatible names used by Tooli internals during backend migration.
NativeArgument = Argument
NativeOption = Option


def translate_marker(marker: object) -> object:
    """Return Typer-compatible metadata when a marker is Tooli-native."""
    if isinstance(marker, Argument):
        return marker.as_typer()
    if isinstance(marker, Option):
        return marker.as_typer()
    return marker
