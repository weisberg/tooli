"""tooli — The agent-native CLI framework for Python."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

try:
    from typer import Argument, Option  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - exercised in optional backend setups
    from tooli.backends.native import Argument, Option

from tooli.app_native import Tooli as _NativeTooli
from tooli.dry_run import DryRunRecorder, dry_run_support, record_dry_action
from tooli.input import SecretInput, StdinOr
from tooli.versioning import VersionFilter, compare_versions

try:
    from tooli.app import Tooli as _TyperTooli  # type: ignore[import-not-found]
except ModuleNotFoundError:
    _TyperTooli: type | None = None


class Tooli:
    """Factory that selects Typer or native backend at construction time."""

    def __new__(cls, *args: Any, backend: str = "typer", **kwargs: Any):  # noqa: D401
        if backend == "native" or _TyperTooli is None:
            return _NativeTooli(*args, backend=backend, **kwargs)
        return _TyperTooli(*args, backend=backend, **kwargs)


__version__ = "2.0.0"
__all__ = [
    "Annotated",
    "Argument",
    "Option",
    "Tooli",
    "SecretInput",
    "StdinOr",
    "DryRunRecorder",
    "dry_run_support",
    "record_dry_action",
    "VersionFilter",
    "compare_versions",
]

if TYPE_CHECKING:
    from tooli.app import Tooli as AppTooli
    from tooli.app_native import Tooli as NativeTooli
