"""Tests for capabilities (#158), handoffs (#159), and error field mapping (#160)."""

from __future__ import annotations

from tooli.annotations import Destructive, ReadOnly
from tooli.command_meta import CommandMeta, get_command_meta
from tooli.errors import (
    AuthError,
    InputError,
    InternalError,
    StateError,
    ToolError,
    ToolRuntimeError,
)
from tooli.python_api import TooliError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(backend: str = "typer"):
    from tooli import Tooli

    app = Tooli(name="test-app", help="Test app", version="1.0.0")

    @app.command(
        annotations=ReadOnly,
        capabilities=["fs:read", "net:read"],
        handoffs=[
            {"command": "process", "when": "After finding files to analyze"},
            {"command": "rename-files", "when": "To rename matched files"},
        ],
        delegation_hint="Use an agent with filesystem access",
    )
    def find_files(pattern: str, root: str = ".") -> list:
        """Find files matching a pattern."""
        return [{"path": f"{root}/{pattern}"}]

    @app.command(
        annotations=Destructive,
        capabilities=["fs:write", "fs:delete"],
    )
    def delete_item(item_id: str) -> dict:
        """Delete an item by ID."""
        return {"deleted": item_id}

    @app.command()
    def simple() -> str:
        """A simple command with no capabilities."""
        return "ok"

    @app.command()
    def fail_with_field(value: str) -> dict:
        """Command that raises with field info."""
        raise InputError(
            message=f"Invalid pattern: {value}",
            code="E1003",
            field="value",
        )

    return app


# ---------------------------------------------------------------------------
# #158 — Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_capabilities_stored_on_meta(self):
        app = _make_app()
        cb = app.get_command("find-files")
        meta = get_command_meta(cb)
        assert meta.capabilities == ["fs:read", "net:read"]

    def test_capabilities_empty_by_default(self):
        app = _make_app()
        cb = app.get_command("simple")
        meta = get_command_meta(cb)
        assert meta.capabilities == []

    def test_capabilities_in_manifest(self):
        from tooli.manifest import generate_agent_manifest

        app = _make_app()
        manifest = generate_agent_manifest(app)
        find_cmd = next(c for c in manifest["commands"] if c["name"] == "find_files" or "find" in c["name"])
        assert "capabilities" in find_cmd
        assert "fs:read" in find_cmd["capabilities"]

    def test_capabilities_not_in_manifest_when_empty(self):
        from tooli.manifest import generate_agent_manifest

        app = _make_app()
        manifest = generate_agent_manifest(app)
        simple_cmd = next(c for c in manifest["commands"] if c["name"] == "simple")
        assert "capabilities" not in simple_cmd

    def test_capabilities_in_schema(self):
        from tooli.schema import generate_tool_schema

        app = _make_app()
        cb = app.get_command("find-files")
        schema = generate_tool_schema(cb, name="find-files")
        assert schema.capabilities == ["fs:read", "net:read"]

    def test_capabilities_in_skill_md(self):
        from tooli.docs.skill_v4 import SkillV4Generator

        app = _make_app()
        content = SkillV4Generator(app).generate()
        assert "fs:read" in content

    def test_capabilities_in_agents_md(self):
        from tooli.docs.agents_md import generate_agents_md

        app = _make_app()
        content = generate_agents_md(app)
        assert "fs:read" in content

    def test_capabilities_in_claude_md(self):
        from tooli.docs.claude_md_v2 import generate_claude_md_v2

        app = _make_app()
        content = generate_claude_md_v2(app)
        assert "fs:read" in content

    def test_capabilities_native_backend(self):
        from tooli import Tooli

        app = Tooli(name="native-test", version="1.0.0", backend="native")

        @app.command(capabilities=["fs:read"])
        def read_file(path: str) -> str:
            return "content"

        meta = get_command_meta(read_file)
        assert meta.capabilities == ["fs:read"]


# ---------------------------------------------------------------------------
# #159 — Handoffs
# ---------------------------------------------------------------------------


class TestHandoffs:
    def test_handoffs_stored_on_meta(self):
        app = _make_app()
        cb = app.get_command("find-files")
        meta = get_command_meta(cb)
        assert len(meta.handoffs) == 2
        assert meta.handoffs[0]["command"] == "process"
        assert meta.handoffs[0]["when"] == "After finding files to analyze"

    def test_handoffs_empty_by_default(self):
        app = _make_app()
        cb = app.get_command("simple")
        meta = get_command_meta(cb)
        assert meta.handoffs == []

    def test_delegation_hint_stored(self):
        app = _make_app()
        cb = app.get_command("find-files")
        meta = get_command_meta(cb)
        assert meta.delegation_hint == "Use an agent with filesystem access"

    def test_delegation_hint_none_by_default(self):
        app = _make_app()
        cb = app.get_command("simple")
        meta = get_command_meta(cb)
        assert meta.delegation_hint is None

    def test_handoffs_in_manifest(self):
        from tooli.manifest import generate_agent_manifest

        app = _make_app()
        manifest = generate_agent_manifest(app)
        find_cmd = next(c for c in manifest["commands"] if "find" in c["name"])
        assert "handoffs" in find_cmd
        assert len(find_cmd["handoffs"]) == 2

    def test_delegation_hint_in_manifest(self):
        from tooli.manifest import generate_agent_manifest

        app = _make_app()
        manifest = generate_agent_manifest(app)
        find_cmd = next(c for c in manifest["commands"] if "find" in c["name"])
        assert find_cmd["delegation_hint"] == "Use an agent with filesystem access"

    def test_handoffs_not_in_manifest_when_empty(self):
        from tooli.manifest import generate_agent_manifest

        app = _make_app()
        manifest = generate_agent_manifest(app)
        simple_cmd = next(c for c in manifest["commands"] if c["name"] == "simple")
        assert "handoffs" not in simple_cmd
        assert "delegation_hint" not in simple_cmd

    def test_handoffs_in_skill_md(self):
        from tooli.docs.skill_v4 import SkillV4Generator

        app = _make_app()
        content = SkillV4Generator(app).generate()
        assert "process" in content
        assert "Handoff" in content

    def test_handoffs_in_agents_md(self):
        from tooli.docs.agents_md import generate_agents_md

        app = _make_app()
        content = generate_agents_md(app)
        assert "process" in content
        assert "Next steps" in content

    def test_handoffs_in_schema(self):
        from tooli.schema import generate_tool_schema

        app = _make_app()
        cb = app.get_command("find-files")
        schema = generate_tool_schema(cb, name="find-files")
        assert len(schema.handoffs) == 2
        assert schema.delegation_hint == "Use an agent with filesystem access"


# ---------------------------------------------------------------------------
# #160 — Error field mapping
# ---------------------------------------------------------------------------


class TestErrorField:
    def test_tool_error_field_attribute(self):
        err = ToolError("bad input", code="E1000", field="pattern")
        assert err.field == "pattern"

    def test_tool_error_field_none_by_default(self):
        err = ToolError("bad input", code="E1000")
        assert err.field is None

    def test_input_error_field(self):
        err = InputError("bad value", field="value")
        assert err.field == "value"

    def test_auth_error_field(self):
        err = AuthError("no access", field="token")
        assert err.field == "token"

    def test_state_error_field(self):
        err = StateError("not found", field="item_id")
        assert err.field == "item_id"

    def test_runtime_error_field(self):
        err = ToolRuntimeError("timeout", field="url")
        assert err.field == "url"

    def test_internal_error_field(self):
        err = InternalError("crash", field="config")
        assert err.field == "config"

    def test_to_dict_includes_field(self):
        err = InputError("bad pattern", code="E1003", field="pattern")
        d = err.to_dict()
        assert d["field"] == "pattern"

    def test_to_dict_excludes_field_when_none(self):
        err = InputError("bad pattern", code="E1003")
        d = err.to_dict()
        assert "field" not in d

    def test_tooli_error_from_tool_error_preserves_field(self):
        err = InputError("bad pattern", code="E1003", field="pattern")
        tooli_err = TooliError.from_tool_error(err)
        assert tooli_err.field == "pattern"

    def test_tooli_error_field_override(self):
        err = InputError("bad pattern", code="E1003")
        tooli_err = TooliError.from_tool_error(err, field="pattern")
        assert tooli_err.field == "pattern"

    def test_field_in_python_api_result(self):
        app = _make_app()
        result = app.call("fail-with-field", value="[invalid")
        assert result.ok is False
        assert result.error.field == "value"

    def test_field_in_unwrap_exception(self):
        import pytest

        app = _make_app()
        result = app.call("fail-with-field", value="[invalid")
        with pytest.raises(InputError) as exc_info:
            result.unwrap()
        assert exc_info.value.field == "value"

    def test_commandmeta_default_has_no_field(self):
        """Verify CommandMeta doesn't break — field is on errors, not meta."""
        meta = CommandMeta()
        assert meta.capabilities == []
        assert meta.handoffs == []
        assert meta.delegation_hint is None
