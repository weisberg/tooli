"""tooli -- The lean agent-native CLI framework for Python."""

from __future__ import annotations

from typing import Annotated

from tooli.backends.native import Argument, Option

from tooli.app_native import Tooli
from tooli.detect import CallerCategory, ExecutionContext, detect_execution_context
from tooli.dry_run import DryRunRecorder, dry_run_support, record_dry_action
from tooli.input import SecretInput, StdinOr
from tooli.python_api import TooliError, TooliResult
from tooli.versioning import VersionFilter, compare_versions

__version__ = "6.5.0"
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
    "CallerCategory",
    "ExecutionContext",
    "detect_execution_context",
    "TooliResult",
    "TooliError",
]
