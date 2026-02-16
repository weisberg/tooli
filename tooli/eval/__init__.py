"""Utilities for recording and analyzing Tooli command invocations."""

from __future__ import annotations

from tooli.eval.analyzer import analyze_invocations
from tooli.eval.agent_test import run_agent_tests
from tooli.eval.recorder import (
    DEFAULT_EVAL_DIR,
    DEFAULT_EVAL_FILE,
    SCHEMA_VERSION,
    InvocationRecord,
    InvocationRecorder,
    build_invocation_recorder,
)

__all__ = [
    "analyze_invocations",
    "InvocationRecord",
    "InvocationRecorder",
    "SCHEMA_VERSION",
    "DEFAULT_EVAL_DIR",
    "DEFAULT_EVAL_FILE",
    "build_invocation_recorder",
    "run_agent_tests",
]
