"""Central exit-code taxonomy for Tooli."""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """CLI exit codes used across Tooli.

    The full set is kept for future growth, even when only a subset is used
    by the current implementation.
    """

    SUCCESS = 0
    INVALID_INPUT = 2
    STATE_ERROR = 10
    INPUT_MISSING = 20
    AUTH_DENIED = 30
    RUNTIME_UNAVAILABLE = 40
    TIMEOUT_EXPIRED = 50
    GENERIC_FAILURE = 65
    INTERNAL_ERROR = 70
    PARTIAL_FAILURE = 75
    HUMAN_HANDOFF_REQUIRED = 101
