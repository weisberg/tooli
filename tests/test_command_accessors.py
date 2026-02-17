"""Tests for command accessor methods (#149) and CallerCategory.PYTHON_API (#150)."""

from __future__ import annotations

from tooli.detect import CallerCategory, ExecutionContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(backend: str = "typer"):
    from tooli import Tooli

    app = Tooli(name="test-app", version="1.0.0", backend=backend)

    @app.command()
    def greet(name: str) -> dict:
        """Greet someone."""
        return {"message": f"Hello, {name}!"}

    @app.command(name="find-files")
    def find_files(pattern: str) -> list:
        """Find files."""
        return [{"path": pattern}]

    @app.command()
    def no_args() -> str:
        return "ok"

    return app


# ---------------------------------------------------------------------------
# get_command()
# ---------------------------------------------------------------------------


class TestGetCommand:
    def test_get_command_by_name(self):
        app = _make_app()
        cb = app.get_command("greet")
        assert cb is not None
        assert callable(cb)

    def test_get_command_hyphen_name(self):
        app = _make_app()
        cb = app.get_command("find-files")
        assert cb is not None

    def test_get_command_underscore_name(self):
        app = _make_app()
        cb = app.get_command("find_files")
        assert cb is not None

    def test_get_command_not_found(self):
        app = _make_app()
        cb = app.get_command("nonexistent")
        assert cb is None

    def test_get_command_native_backend(self):
        app = _make_app(backend="native")
        cb = app.get_command("greet")
        assert cb is not None

    def test_get_command_callback_works(self):
        app = _make_app()
        cb = app.get_command("greet")
        result = cb(name="World")
        assert result == {"message": "Hello, World!"}


# ---------------------------------------------------------------------------
# list_commands()
# ---------------------------------------------------------------------------


class TestListCommands:
    def test_list_commands_includes_registered(self):
        app = _make_app()
        cmds = app.list_commands()
        assert "greet" in cmds
        assert "find-files" in cmds or "find_files" in cmds

    def test_list_commands_sorted(self):
        app = _make_app()
        cmds = app.list_commands()
        assert cmds == sorted(cmds)

    def test_list_commands_native_backend(self):
        app = _make_app(backend="native")
        cmds = app.list_commands()
        assert "greet" in cmds


# ---------------------------------------------------------------------------
# CallerCategory.PYTHON_API (#150)
# ---------------------------------------------------------------------------


class TestCallerCategoryPythonAPI:
    def test_python_api_in_enum(self):
        assert CallerCategory.PYTHON_API == "python_api"

    def test_is_agent_false_for_python_api(self):
        ctx = ExecutionContext(
            category=CallerCategory.PYTHON_API,
            agent_name=None,
            confidence=1.0,
            signals=[],
            is_interactive=False,
        )
        assert ctx.is_agent is False

    def test_is_human_false_for_python_api(self):
        ctx = ExecutionContext(
            category=CallerCategory.PYTHON_API,
            agent_name=None,
            confidence=1.0,
            signals=[],
            is_interactive=False,
        )
        assert ctx.is_human is False

    def test_call_sets_caller_id(self):
        app = _make_app()
        result = app.call("greet", name="World")
        assert result.meta["caller_id"] == "python-api"

    def test_acall_meta_caller_id(self):
        """Verify acall also sets caller_id in meta."""
        import asyncio

        app = _make_app()
        result = asyncio.run(app.acall("greet", name="World"))
        assert result.meta["caller_id"] == "python-api"
