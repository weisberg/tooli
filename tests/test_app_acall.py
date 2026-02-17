"""Tests for app.acall() — async Python API."""

from __future__ import annotations

import asyncio

import pytest

from tooli.errors import InputError
from tooli.python_api import TooliResult

# ---------------------------------------------------------------------------
# Helpers — build a minimal Tooli app for testing
# ---------------------------------------------------------------------------


def _make_app(backend: str = "typer"):
    """Create a test Tooli app with sync and async commands."""
    from tooli import Tooli

    app = Tooli(name="test-app", version="1.0.0", backend=backend)

    @app.command()
    def greet(name: str, greeting: str = "Hello") -> dict:
        """Greet someone (sync)."""
        return {"message": f"{greeting}, {name}!"}

    @app.command()
    async def greet_async(name: str, greeting: str = "Hello") -> dict:
        """Greet someone (async)."""
        await asyncio.sleep(0)  # yield to event loop
        return {"message": f"{greeting}, {name}!"}

    @app.command()
    def fail_input(value: str) -> dict:
        """Always raises InputError."""
        raise InputError(message=f"Bad value: {value}", code="E1001")

    @app.command()
    async def fail_async() -> dict:
        """Async command that raises."""
        await asyncio.sleep(0)
        msg = "async boom"
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
# Async success paths
# ---------------------------------------------------------------------------


class TestAcallSuccess:
    @pytest.mark.asyncio
    async def test_sync_command_via_acall(self):
        app = _make_app()
        result = await app.acall("greet", name="World")
        assert isinstance(result, TooliResult)
        assert result.ok is True
        assert result.result == {"message": "Hello, World!"}

    @pytest.mark.asyncio
    async def test_async_command_via_acall(self):
        app = _make_app()
        result = await app.acall("greet-async", name="World")
        assert result.ok is True
        assert result.result == {"message": "Hello, World!"}

    @pytest.mark.asyncio
    async def test_async_command_with_kwargs(self):
        app = _make_app()
        result = await app.acall("greet-async", name="Alice", greeting="Hi")
        assert result.ok is True
        assert result.result == {"message": "Hi, Alice!"}

    @pytest.mark.asyncio
    async def test_meta_fields(self):
        app = _make_app()
        result = await app.acall("greet", name="Bob")
        assert result.meta is not None
        assert "test-app." in result.meta["tool"]
        assert result.meta["version"] == "1.0.0"
        assert result.meta["duration_ms"] >= 0
        assert result.meta["caller_id"] == "python-api"

    @pytest.mark.asyncio
    async def test_hyphen_command_name(self):
        app = _make_app()
        result = await app.acall("find-files", pattern="*.py")
        assert result.ok is True

    @pytest.mark.asyncio
    async def test_underscore_command_name(self):
        app = _make_app()
        result = await app.acall("find_files", pattern="*.py")
        assert result.ok is True

    @pytest.mark.asyncio
    async def test_no_args_command(self):
        app = _make_app()
        result = await app.acall("no-args")
        assert result.ok is True
        assert result.result == "ok"

    @pytest.mark.asyncio
    async def test_unwrap_success(self):
        app = _make_app()
        result = await app.acall("greet-async", name="World")
        assert result.unwrap() == {"message": "Hello, World!"}


# ---------------------------------------------------------------------------
# Async error paths
# ---------------------------------------------------------------------------


class TestAcallErrors:
    @pytest.mark.asyncio
    async def test_unknown_command(self):
        app = _make_app()
        result = await app.acall("nonexistent")
        assert result.ok is False
        assert "Unknown command" in result.error.message

    @pytest.mark.asyncio
    async def test_unknown_kwargs(self):
        app = _make_app()
        result = await app.acall("greet", name="World", bogus="value")
        assert result.ok is False
        assert "bogus" in result.error.message

    @pytest.mark.asyncio
    async def test_sync_error_via_acall(self):
        app = _make_app()
        result = await app.acall("fail-input", value="bad")
        assert result.ok is False
        assert result.error.category == "input"

    @pytest.mark.asyncio
    async def test_async_unexpected_error(self):
        app = _make_app()
        result = await app.acall("fail-async")
        assert result.ok is False
        assert result.error.category == "internal"
        assert "async boom" in result.error.message

    @pytest.mark.asyncio
    async def test_unwrap_raises(self):
        app = _make_app()
        result = await app.acall("fail-input", value="bad")
        with pytest.raises(InputError):
            result.unwrap()


# ---------------------------------------------------------------------------
# Async dry run
# ---------------------------------------------------------------------------


class TestAcallDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_sync_command(self):
        app = _make_app()
        result = await app.acall("greet", name="World", dry_run=True)
        assert result.ok is True
        assert result.result["dry_run"] is True

    @pytest.mark.asyncio
    async def test_dry_run_async_command(self):
        app = _make_app()
        result = await app.acall("greet-async", name="World", dry_run=True)
        assert result.ok is True
        assert result.result["dry_run"] is True

    @pytest.mark.asyncio
    async def test_dry_run_does_not_execute(self):
        app = _make_app()
        result = await app.acall("fail-async", dry_run=True)
        assert result.ok is True


# ---------------------------------------------------------------------------
# Native backend
# ---------------------------------------------------------------------------


class TestAcallNativeBackend:
    @pytest.mark.asyncio
    async def test_sync_command(self):
        app = _make_app(backend="native")
        result = await app.acall("greet", name="Native")
        assert result.ok is True
        assert result.result == {"message": "Hello, Native!"}

    @pytest.mark.asyncio
    async def test_async_command(self):
        app = _make_app(backend="native")
        result = await app.acall("greet-async", name="Native")
        assert result.ok is True
        assert result.result == {"message": "Hello, Native!"}

    @pytest.mark.asyncio
    async def test_unknown_command(self):
        app = _make_app(backend="native")
        result = await app.acall("nonexistent")
        assert result.ok is False

    @pytest.mark.asyncio
    async def test_dry_run(self):
        app = _make_app(backend="native")
        result = await app.acall("greet-async", name="Test", dry_run=True)
        assert result.ok is True
        assert result.result["dry_run"] is True
