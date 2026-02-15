"""Tooli error hierarchy and structured error models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel

from tooli.exit_codes import ExitCode


def _default_exit_code(category: ErrorCategory) -> ExitCode:
    mapping = {
        ErrorCategory.INPUT: ExitCode.INVALID_INPUT,
        ErrorCategory.AUTH: ExitCode.AUTH_DENIED,
        ErrorCategory.STATE: ExitCode.STATE_ERROR,
        ErrorCategory.RUNTIME: ExitCode.INTERNAL_ERROR,
        ErrorCategory.INTERNAL: ExitCode.INTERNAL_ERROR,
    }
    return mapping[category]


class ErrorCategory(str, Enum):
    INPUT = "input"
    AUTH = "auth"
    STATE = "state"
    RUNTIME = "runtime"
    INTERNAL = "internal"


class Suggestion(BaseModel):
    action: str
    fix: str
    example: str | None = None
    applicability: str = "maybe_incorrect"


class ToolError(Exception):
    """Base error that agents can reason about."""

    def __init__(
        self,
        message: str,
        code: str,
        category: ErrorCategory = ErrorCategory.RUNTIME,
        suggestion: Suggestion | None = None,
        is_retryable: bool = False,
        details: dict[str, Any] | None = None,
        exit_code: ExitCode | int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.category = category
        self.suggestion = suggestion
        self.is_retryable = is_retryable
        self.details = details or {}
        resolved_exit_code = exit_code if exit_code is not None else _default_exit_code(category)
        if isinstance(resolved_exit_code, ExitCode):
            self.exit_code = int(resolved_exit_code)
        else:
            self.exit_code = resolved_exit_code

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "code": self.code,
            "category": self.category.value,
            "suggestion": self.suggestion.model_dump() if self.suggestion else None,
            "is_retryable": self.is_retryable,
            "details": self.details,
        }


class InputError(ToolError):
    """E1xxx: Input validation failures."""

    def __init__(
        self,
        message: str,
        code: str = "E1000",
        suggestion: Suggestion | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code,
            category=ErrorCategory.INPUT,
            suggestion=suggestion,
            details=details,
            exit_code=ExitCode.INVALID_INPUT,
        )


class AuthError(ToolError):
    """E2xxx: Authorization failures."""

    def __init__(
        self,
        message: str,
        code: str = "E2000",
        suggestion: Suggestion | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code,
            category=ErrorCategory.AUTH,
            suggestion=suggestion,
            details=details,
            exit_code=ExitCode.AUTH_DENIED,
        )


class StateError(ToolError):
    """E3xxx: Precondition or state failures."""

    def __init__(
        self,
        message: str,
        code: str = "E3000",
        suggestion: Suggestion | None = None,
        details: dict[str, Any] | None = None,
        exit_code: ExitCode | int = ExitCode.STATE_ERROR,
    ) -> None:
        super().__init__(
            message,
            code,
            category=ErrorCategory.STATE,
            suggestion=suggestion,
            details=details,
            exit_code=exit_code,
        )


class ToolRuntimeError(ToolError):
    """E4xxx: External dependency or runtime failures."""

    def __init__(
        self,
        message: str,
        code: str = "E4000",
        suggestion: Suggestion | None = None,
        details: dict[str, Any] | None = None,
        exit_code: int = 70,
    ) -> None:
        super().__init__(
            message,
            code,
            category=ErrorCategory.RUNTIME,
            suggestion=suggestion,
            details=details,
            exit_code=exit_code,
        )


class InternalError(ToolError):
    """E5xxx: Uncaught exceptions or framework failures."""

    def __init__(
        self,
        message: str,
        code: str = "E5000",
        suggestion: Suggestion | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code,
            category=ErrorCategory.INTERNAL,
            suggestion=suggestion,
            details=details,
            exit_code=ExitCode.INTERNAL_ERROR,
        )
