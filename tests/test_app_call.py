"""Tests for app.call() — synchronous Python API."""

from __future__ import annotations

import pytest

from tooli.errors import InputError, StateError
from tooli.python_api import TooliResult

# ---------------------------------------------------------------------------
# Helpers — build a minimal Tooli app for testing
# ---------------------------------------------------------------------------


def _make_app(backend: str = "typer"):
    """Create a test Tooli app with a few commands."""
    from tooli import Tooli

    app = Tooli(name="test-app", version="1.0.0", backend=backend)

    @app.command()
    def greet(name: str, greeting: str = "Hello") -> dict:
        """Greet someone."""
        return {"message": f"{greeting}, {name}!"}

    @app.command()
    def fail_input(value: str) -> dict:
        """Always raises InputError."""
        raise InputError(message=f"Bad value: {value}", code="E1001")

    @app.command()
    def fail_state() -> dict:
        """Always raises StateError."""
        raise StateError(message="Resource not found", code="E3001")

    @app.command()
    def fail_unexpected() -> dict:
        """Always raises an unexpected exception."""
        msg = "boom"
        raise ValueError(msg)

    @app.command(name="find-files")
    def find_files(pattern: str, root: str = ".") -> list:
        """Find files matching a pattern."""
        return [{"path": f"{root}/{pattern}", "matched": True}]

    @app.command()
    def no_args() -> str:
        """Command with no arguments."""
        return "ok"

    return app


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


class TestCallSuccess:
    def test_basic_call(self):
        app = _make_app()
        result = app.call("greet", name="World")
        assert isinstance(result, TooliResult)
        assert result.ok is True
        assert result.result == {"message": "Hello, World!"}

    def test_call_with_kwargs(self):
        app = _make_app()
        result = app.call("greet", name="Alice", greeting="Hi")
        assert result.ok is True
        assert result.result == {"message": "Hi, Alice!"}

    def test_meta_fields(self):
        app = _make_app()
        result = app.call("greet", name="Bob")
        assert result.meta is not None
        assert result.meta["tool"] == "test-app.greet"
        assert result.meta["version"] == "1.0.0"
        assert result.meta["duration_ms"] >= 0
        assert result.meta["caller_id"] == "python-api"

    def test_hyphen_command_name(self):
        app = _make_app()
        result = app.call("find-files", pattern="*.py")
        assert result.ok is True
        assert result.result == [{"path": "./*.py", "matched": True}]

    def test_underscore_command_name(self):
        app = _make_app()
        result = app.call("find_files", pattern="*.py")
        assert result.ok is True
        assert result.result == [{"path": "./*.py", "matched": True}]

    def test_no_args_command(self):
        app = _make_app()
        result = app.call("no-args")
        assert result.ok is True
        assert result.result == "ok"

    def test_unwrap_success(self):
        app = _make_app()
        result = app.call("greet", name="World")
        assert result.unwrap() == {"message": "Hello, World!"}

    def test_list_result(self):
        app = _make_app()
        result = app.call("find-files", pattern="*.md", root="/docs")
        assert result.ok is True
        assert len(result.result) == 1
        assert result.result[0]["path"] == "/docs/*.md"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestCallErrors:
    def test_unknown_command(self):
        app = _make_app()
        result = app.call("nonexistent")
        assert result.ok is False
        assert result.error is not None
        assert result.error.code == "E1001"
        assert "Unknown command" in result.error.message

    def test_unknown_kwargs(self):
        app = _make_app()
        result = app.call("greet", name="World", bogus="value")
        assert result.ok is False
        assert result.error is not None
        assert "bogus" in result.error.message

    def test_tool_error_input(self):
        app = _make_app()
        result = app.call("fail-input", value="bad")
        assert result.ok is False
        assert result.error is not None
        assert result.error.code == "E1001"
        assert result.error.category == "input"
        assert "Bad value" in result.error.message

    def test_tool_error_state(self):
        app = _make_app()
        result = app.call("fail-state")
        assert result.ok is False
        assert result.error.category == "state"
        assert result.error.code == "E3001"

    def test_unexpected_exception(self):
        app = _make_app()
        result = app.call("fail-unexpected")
        assert result.ok is False
        assert result.error is not None
        assert result.error.category == "internal"
        assert "boom" in result.error.message

    def test_unwrap_raises(self):
        app = _make_app()
        result = app.call("fail-input", value="bad")
        with pytest.raises(InputError) as exc_info:
            result.unwrap()
        assert exc_info.value.code == "E1001"

    def test_error_meta_present(self):
        app = _make_app()
        result = app.call("fail-input", value="x")
        assert result.meta is not None
        assert "test-app." in result.meta["tool"]
        assert "fail" in result.meta["tool"]
        assert result.meta["duration_ms"] >= 0


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


class TestCallDryRun:
    def test_dry_run_kwarg(self):
        app = _make_app()
        result = app.call("greet", name="World", dry_run=True)
        assert result.ok is True
        assert result.result["dry_run"] is True
        assert result.result["command"] == "greet"
        assert result.result["arguments"]["name"] == "World"

    def test_dry_run_does_not_execute(self):
        app = _make_app()
        result = app.call("fail-unexpected", dry_run=True)
        # Should NOT raise because dry_run skips execution
        assert result.ok is True
        assert result.result["dry_run"] is True


# ---------------------------------------------------------------------------
# Native backend
# ---------------------------------------------------------------------------


class TestCallNativeBackend:
    def test_basic_call(self):
        app = _make_app(backend="native")
        result = app.call("greet", name="Native")
        assert result.ok is True
        assert result.result == {"message": "Hello, Native!"}

    def test_unknown_command(self):
        app = _make_app(backend="native")
        result = app.call("nonexistent")
        assert result.ok is False
        assert "Unknown command" in result.error.message

    def test_error_handling(self):
        app = _make_app(backend="native")
        result = app.call("fail-input", value="bad")
        assert result.ok is False
        assert result.error.category == "input"

    def test_dry_run(self):
        app = _make_app(backend="native")
        result = app.call("greet", name="Test", dry_run=True)
        assert result.ok is True
        assert result.result["dry_run"] is True
