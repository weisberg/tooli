"""tooli — The agent-native CLI framework for Python."""

from __future__ import annotations

from typing import Annotated

from typer import Argument, Option

from tooli.app import Tooli
from tooli.dry_run import DryRunRecorder, dry_run_support, record_dry_action
from tooli.input import SecretInput, StdinOr
from tooli.versioning import VersionFilter, compare_versions

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
