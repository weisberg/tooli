"""Tests for TooliResult and TooliError types."""

from __future__ import annotations

import pytest

from tooli.errors import (
    AuthError,
    InputError,
    InternalError,
    StateError,
    Suggestion,
    ToolError,
    ToolRuntimeError,
)
from tooli.python_api import TooliError as TooliErr
from tooli.python_api import TooliResult

# ---------------------------------------------------------------------------
# TooliResult construction
# ---------------------------------------------------------------------------


class TestTooliResultConstruction:

    def test_success_result(self):
        result = TooliResult(ok=True, result={"count": 42})
        assert result.ok is True
        assert result.result == {"count": 42}
        assert result.error is None
        assert result.meta is None

    def test_success_with_meta(self):
        meta = {"tool": "test.greet", "version": "1.0.0", "duration_ms": 10}
        result = TooliResult(ok=True, result="hello", meta=meta)
        assert result.ok is True
        assert result.result == "hello"
        assert result.meta["tool"] == "test.greet"

    def test_failure_result(self):
        err = TooliErr(code="E1000", category="input", message="bad input")
        result = TooliResult(ok=False, error=err)
        assert result.ok is False
        assert result.result is None
        assert result.error is err

    def test_success_factory(self):
        result = TooliResult.success([1, 2, 3], meta={"tool": "t"})
        assert result.ok is True
        assert result.result == [1, 2, 3]
        assert result.meta == {"tool": "t"}

    def test_failure_factory(self):
        err = TooliErr(code="E3001", category="state", message="not found")
        result = TooliResult.failure(err)
        assert result.ok is False
        assert result.error is err

    def test_from_tool_error_factory(self):
        exc = InputError("bad pattern", code="E1003")
        result = TooliResult.from_tool_error(exc, field="pattern")
        assert result.ok is False
        assert result.error.code == "E1003"
        assert result.error.category == "input"
        assert result.error.field == "pattern"

    def test_result_is_frozen(self):
        result = TooliResult(ok=True, result="x")
        with pytest.raises(AttributeError):
            result.ok = False  # type: ignore[misc]

    def test_success_with_none_result(self):
        result = TooliResult(ok=True, result=None)
        assert result.ok is True
        assert result.result is None

    def test_success_with_list_result(self):
        data = [{"path": "a.py"}, {"path": "b.py"}]
        result = TooliResult.success(data)
        assert result.result == data
        assert len(result.result) == 2


# ---------------------------------------------------------------------------
# TooliResult.unwrap()
# ---------------------------------------------------------------------------


class TestTooliResultUnwrap:

    def test_unwrap_success(self):
        result = TooliResult(ok=True, result={"greeting": "hello"})
        assert result.unwrap() == {"greeting": "hello"}

    def test_unwrap_success_list(self):
        result = TooliResult.success([1, 2, 3])
        assert result.unwrap() == [1, 2, 3]

    def test_unwrap_success_none(self):
        result = TooliResult(ok=True, result=None)
        assert result.unwrap() is None

    def test_unwrap_failure_raises_tool_error(self):
        err = TooliErr(code="E1000", category="input", message="bad input")
        result = TooliResult(ok=False, error=err)
        with pytest.raises(InputError) as exc_info:
            result.unwrap()
        assert exc_info.value.message == "bad input"
        assert exc_info.value.code == "E1000"

    def test_unwrap_failure_no_error_raises_internal(self):
        result = TooliResult(ok=False)
        with pytest.raises(InternalError):
            result.unwrap()

    def test_unwrap_failure_with_suggestion(self):
        err = TooliErr(
            code="E3001",
            category="state",
            message="not found",
            suggestion={"action": "check", "fix": "verify the path"},
        )
        result = TooliResult(ok=False, error=err)
        with pytest.raises(StateError) as exc_info:
            result.unwrap()
        assert exc_info.value.suggestion is not None
        assert exc_info.value.suggestion.action == "check"


# ---------------------------------------------------------------------------
# TooliError construction
# ---------------------------------------------------------------------------


class TestTooliErrorConstruction:

    def test_basic_error(self):
        err = TooliErr(code="E1000", category="input", message="bad")
        assert err.code == "E1000"
        assert err.category == "input"
        assert err.message == "bad"
        assert err.suggestion is None
        assert err.is_retryable is False
        assert err.field is None
        assert err.details == {}

    def test_error_with_all_fields(self):
        err = TooliErr(
            code="E3001",
            category="state",
            message="not found",
            suggestion={"action": "retry", "fix": "wait and retry"},
            is_retryable=True,
            field="resource_id",
            details={"attempted_id": "abc-123"},
        )
        assert err.is_retryable is True
        assert err.field == "resource_id"
        assert err.details["attempted_id"] == "abc-123"
        assert err.suggestion["action"] == "retry"

    def test_error_is_frozen(self):
        err = TooliErr(code="E1000", category="input", message="bad")
        with pytest.raises(AttributeError):
            err.code = "E2000"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TooliError.to_exception()
# ---------------------------------------------------------------------------


class TestTooliErrorToException:

    @pytest.mark.parametrize(
        ("category", "expected_cls"),
        [
            ("input", InputError),
            ("auth", AuthError),
            ("state", StateError),
            ("runtime", ToolRuntimeError),
            ("internal", InternalError),
        ],
    )
    def test_category_mapping(self, category: str, expected_cls: type[ToolError]):
        err = TooliErr(code="E0000", category=category, message="test")
        exc = err.to_exception()
        assert isinstance(exc, expected_cls)
        assert exc.message == "test"
        assert exc.code == "E0000"

    def test_unknown_category_falls_back_to_runtime(self):
        err = TooliErr(code="E9999", category="unknown_category", message="mystery")
        exc = err.to_exception()
        assert isinstance(exc, ToolRuntimeError)

    def test_suggestion_preserved(self):
        err = TooliErr(
            code="E1003",
            category="input",
            message="invalid pattern",
            suggestion={
                "action": "fix",
                "fix": "escape brackets",
                "example": 'find "*.py"',
            },
        )
        exc = err.to_exception()
        assert exc.suggestion is not None
        assert exc.suggestion.action == "fix"
        assert exc.suggestion.fix == "escape brackets"
        assert exc.suggestion.example == 'find "*.py"'

    def test_suggestion_none_preserved(self):
        err = TooliErr(code="E1000", category="input", message="bad")
        exc = err.to_exception()
        assert exc.suggestion is None

    def test_details_preserved(self):
        err = TooliErr(
            code="E5000",
            category="internal",
            message="crash",
            details={"traceback": "..."},
        )
        exc = err.to_exception()
        assert exc.details == {"traceback": "..."}

    def test_empty_details_passed_as_none(self):
        err = TooliErr(code="E1000", category="input", message="bad", details={})
        exc = err.to_exception()
        # Empty dict → None in ToolError constructor
        assert exc.details == {}


# ---------------------------------------------------------------------------
# TooliError.from_tool_error()
# ---------------------------------------------------------------------------


class TestTooliErrorFromToolError:

    def test_from_input_error(self):
        exc = InputError("invalid input", code="E1001")
        err = TooliErr.from_tool_error(exc)
        assert err.code == "E1001"
        assert err.category == "input"
        assert err.message == "invalid input"
        assert err.is_retryable is False
        assert err.field is None

    def test_from_error_with_suggestion(self):
        suggestion = Suggestion(action="fix", fix="try again")
        exc = StateError("not found", code="E3001", suggestion=suggestion)
        err = TooliErr.from_tool_error(exc)
        assert err.suggestion is not None
        assert err.suggestion["action"] == "fix"
        assert err.suggestion["fix"] == "try again"

    def test_from_error_with_field(self):
        exc = InputError("bad value", code="E1005")
        err = TooliErr.from_tool_error(exc, field="start_date")
        assert err.field == "start_date"

    def test_from_retryable_error(self):
        exc = ToolRuntimeError("timeout", code="E4001")
        exc.is_retryable = True
        err = TooliErr.from_tool_error(exc)
        assert err.is_retryable is True

    def test_from_error_with_details(self):
        exc = InternalError("crash", code="E5000", details={"trace": "..."})
        err = TooliErr.from_tool_error(exc)
        assert err.details == {"trace": "..."}

    def test_roundtrip_input(self):
        """from_tool_error → to_exception produces equivalent error."""
        original = InputError("bad input", code="E1001")
        err = TooliErr.from_tool_error(original)
        restored = err.to_exception()
        assert isinstance(restored, InputError)
        assert restored.message == original.message
        assert restored.code == original.code

    def test_roundtrip_with_suggestion(self):
        suggestion = Suggestion(action="check", fix="verify path", example="ls /tmp")
        original = StateError("not found", code="E3001", suggestion=suggestion)
        err = TooliErr.from_tool_error(original)
        restored = err.to_exception()
        assert isinstance(restored, StateError)
        assert restored.suggestion.action == "check"
        assert restored.suggestion.fix == "verify path"
        assert restored.suggestion.example == "ls /tmp"


# ---------------------------------------------------------------------------
# TooliError.from_dict()
# ---------------------------------------------------------------------------


class TestTooliErrorFromDict:

    def test_from_full_dict(self):
        data = {
            "code": "E1003",
            "category": "input",
            "message": "invalid pattern",
            "suggestion": {"action": "fix", "fix": "escape brackets"},
            "is_retryable": True,
            "field": "pattern",
            "details": {"raw": "["},
        }
        err = TooliErr.from_dict(data)
        assert err.code == "E1003"
        assert err.category == "input"
        assert err.message == "invalid pattern"
        assert err.suggestion["action"] == "fix"
        assert err.is_retryable is True
        assert err.field == "pattern"
        assert err.details["raw"] == "["

    def test_from_minimal_dict(self):
        data = {"code": "E0000", "message": "something"}
        err = TooliErr.from_dict(data)
        assert err.code == "E0000"
        assert err.category == "internal"  # default
        assert err.message == "something"
        assert err.suggestion is None
        assert err.is_retryable is False
        assert err.field is None

    def test_from_empty_dict(self):
        err = TooliErr.from_dict({})
        assert err.code == "E0000"
        assert err.category == "internal"
        assert err.message == "Unknown error"

    def test_from_dict_to_exception(self):
        data = {"code": "E2001", "category": "auth", "message": "denied"}
        err = TooliErr.from_dict(data)
        exc = err.to_exception()
        assert isinstance(exc, AuthError)
        assert exc.message == "denied"


# ---------------------------------------------------------------------------
# Exports from tooli package
# ---------------------------------------------------------------------------


class TestExports:

    def test_tooli_result_importable(self):
        from tooli import TooliResult as TR
        assert TR is TooliResult

    def test_tooli_error_importable(self):
        from tooli import TooliError as TE
        assert TE is TooliErr
