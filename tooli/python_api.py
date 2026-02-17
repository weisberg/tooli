"""Typed result types for the tooli Python API.

``TooliResult`` mirrors the CLI JSON envelope (``{ok, result, error, meta}``)
as a typed Python object.  ``TooliError`` is the Python-side representation of
a structured error, convertible back to the appropriate ``ToolError`` exception
subclass via ``to_exception()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Generic, TypeVar

from tooli.errors import (
    AuthError,
    ErrorCategory,
    InputError,
    InternalError,
    StateError,
    Suggestion,
    ToolError,
    ToolRuntimeError,
)

T = TypeVar("T")

_CATEGORY_TO_CLASS: dict[str, type[ToolError]] = {
    ErrorCategory.INPUT.value: InputError,
    ErrorCategory.AUTH.value: AuthError,
    ErrorCategory.STATE.value: StateError,
    ErrorCategory.RUNTIME.value: ToolRuntimeError,
    ErrorCategory.INTERNAL.value: InternalError,
}


@dataclass(frozen=True)
class TooliError:
    """Structured error from a tooli command invocation.

    Mirrors the JSON envelope ``error`` object.  Use ``to_exception()`` to
    convert back to the matching ``ToolError`` subclass when you need to raise.
    """

    code: str
    category: str
    message: str
    suggestion: dict[str, Any] | None = None
    is_retryable: bool = False
    field: str | None = None
    details: dict[str, Any] = dc_field(default_factory=dict)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def to_exception(self) -> ToolError:
        """Convert to the appropriate ``ToolError`` subclass."""
        suggestion_obj: Suggestion | None = None
        if self.suggestion is not None:
            suggestion_obj = Suggestion(**self.suggestion)

        cls = _CATEGORY_TO_CLASS.get(self.category, ToolRuntimeError)
        return cls(
            message=self.message,
            code=self.code,
            suggestion=suggestion_obj,
            details=self.details if self.details else None,
            field=self.field,
        )

    @classmethod
    def from_tool_error(cls, err: ToolError, *, field: str | None = None) -> TooliError:
        """Create a ``TooliError`` from a ``ToolError`` exception."""
        suggestion_dict: dict[str, Any] | None = None
        if err.suggestion is not None:
            suggestion_dict = err.suggestion.model_dump()
        return cls(
            code=err.code,
            category=err.category.value,
            message=err.message,
            suggestion=suggestion_dict,
            is_retryable=err.is_retryable,
            field=field or err.field,
            details=err.details,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TooliError:
        """Create a ``TooliError`` from an envelope error dict."""
        return cls(
            code=data.get("code", "E0000"),
            category=data.get("category", "internal"),
            message=data.get("message", "Unknown error"),
            suggestion=data.get("suggestion"),
            is_retryable=data.get("is_retryable", False),
            field=data.get("field"),
            details=data.get("details", {}),
        )


@dataclass(frozen=True)
class TooliResult(Generic[T]):
    """Structured result from a tooli command invocation.

    This is the Python equivalent of the CLI JSON envelope::

        {"ok": true, "result": ..., "meta": {...}}

    Use ``unwrap()`` to get the result value directly, raising on error.

    Example::

        result = app.call("find-files", pattern="*.py")
        if result.ok:
            for f in result.result:
                print(f["path"])

        # Or, raise on error:
        files = result.unwrap()
    """

    ok: bool
    result: T | None = None
    error: TooliError | None = None
    meta: dict[str, Any] | None = None

    def unwrap(self) -> T:
        """Return the result value, or raise the corresponding ``ToolError``.

        Raises
        ------
        ToolError
            The appropriate subclass (``InputError``, ``StateError``, etc.)
            when ``ok`` is ``False``.
        """
        if not self.ok:
            if self.error is not None:
                raise self.error.to_exception()
            raise InternalError("Result is not ok but no error was provided")
        return self.result  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def success(cls, result: T, meta: dict[str, Any] | None = None) -> TooliResult[T]:
        """Create a successful result."""
        return cls(ok=True, result=result, meta=meta)

    @classmethod
    def failure(
        cls,
        error: TooliError,
        meta: dict[str, Any] | None = None,
    ) -> TooliResult[Any]:
        """Create a failed result."""
        return cls(ok=False, error=error, meta=meta)

    @classmethod
    def from_tool_error(
        cls,
        err: ToolError,
        meta: dict[str, Any] | None = None,
        *,
        field: str | None = None,
    ) -> TooliResult[Any]:
        """Create a failed result from a ``ToolError`` exception."""
        return cls.failure(TooliError.from_tool_error(err, field=field), meta=meta)
