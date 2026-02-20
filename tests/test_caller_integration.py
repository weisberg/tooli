"""Integration tests for the caller-aware agent runtime.

Tests that the detection module is properly wired into the envelope,
telemetry, recorder, manifest, and builtin command pipeline.
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tooli import Tooli
from tooli.detect import reset_cache


@pytest.fixture(autouse=True)
def clear_detect_cache():
    reset_cache()
    yield
    reset_cache()


def _make_app() -> Tooli:
    app = Tooli(name="test-tool", version="1.0.0")

    @app.command()
    def greet(name: str = "world") -> dict[str, str]:
        """Say hello."""
        return {"greeting": f"Hello, {name}!"}

    return app


# ---------------------------------------------------------------------------
# Envelope includes caller fields
# ---------------------------------------------------------------------------


class TestEnvelopeCallerFields:

    def test_envelope_includes_caller_id_when_set(self):
        app = _make_app()
        runner = CliRunner()
        with patch.dict(os.environ, {"TOOLI_CALLER": "aider", "TOOLI_CALLER_VERSION": "0.82.1"}, clear=False):
            result = runner.invoke(app, ["greet", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["meta"]["caller_id"] == "aider"
            assert data["meta"]["caller_version"] == "0.82.1"

    def test_envelope_caller_fields_null_when_not_set(self):
        app = _make_app()
        runner = CliRunner()
        result = runner.invoke(app, ["greet", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["meta"]["caller_id"] is None
        assert data["meta"]["caller_version"] is None
        assert data["meta"]["session_id"] is None

    def test_envelope_includes_session_id(self):
        app = _make_app()
        runner = CliRunner()
        env = {"TOOLI_CALLER": "crewai", "TOOLI_SESSION_ID": "run-xyz-123"}
        with patch.dict(os.environ, env, clear=False):
            result = runner.invoke(app, ["greet", "--json"])
            data = json.loads(result.output)
            assert data["meta"]["session_id"] == "run-xyz-123"


# ---------------------------------------------------------------------------
# _is_agent_mode uses detection
# ---------------------------------------------------------------------------


class TestIsAgentModeDetection:

    def test_agent_mode_with_tooli_caller(self):
        from tooli.command import _is_agent_mode
        with patch.dict(os.environ, {"TOOLI_CALLER": "cursor"}, clear=False):
            assert _is_agent_mode() is True

    def test_agent_mode_legacy_flag(self):
        from tooli.command import _is_agent_mode
        with patch.dict(os.environ, {"TOOLI_AGENT_MODE": "true"}, clear=False):
            assert _is_agent_mode() is True


# ---------------------------------------------------------------------------
# detect-context builtin command
# ---------------------------------------------------------------------------


class TestDetectContextCommand:

    def test_detect_context_json(self):
        app = _make_app()
        runner = CliRunner()
        env = {"TOOLI_CALLER": "claude-code", "TOOLI_CALLER_VERSION": "1.5.0"}
        with patch.dict(os.environ, env, clear=False):
            result = runner.invoke(app, ["detect-context", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["result"]["category"] == "ai_agent"
            assert data["result"]["caller_id"] == "claude-code"
            assert data["result"]["confidence"] == 1.0
            assert data["result"]["is_agent"] is True

    def test_detect_context_without_caller(self):
        app = _make_app()
        runner = CliRunner()
        result = runner.invoke(app, ["detect-context", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        # In test runner (non-interactive), should detect as some form of automation
        assert data["result"]["category"] in ("unknown_automation", "ai_agent", "human")


# ---------------------------------------------------------------------------
# Manifest includes caller_convention
# ---------------------------------------------------------------------------


class TestManifestCallerConvention:

    def test_manifest_has_caller_convention(self):
        from tooli.manifest import generate_agent_manifest
        app = _make_app()
        manifest = generate_agent_manifest(app)
        assert "caller_convention" in manifest
        conv = manifest["caller_convention"]
        assert conv["env_var"] == "TOOLI_CALLER"
        assert conv["version_var"] == "TOOLI_CALLER_VERSION"
        assert conv["session_var"] == "TOOLI_SESSION_ID"
        assert conv["detect_command"] == "detect-context"

    def test_manifest_global_flags_include_schema(self):
        from tooli.manifest import generate_agent_manifest
        app = _make_app()
        manifest = generate_agent_manifest(app)
        assert "--schema" in manifest["global_flags"]


# ---------------------------------------------------------------------------
# InvocationRecord includes caller fields
# ---------------------------------------------------------------------------


class TestRecorderCallerFields:

    def test_invocation_record_with_caller(self):
        from tooli.eval.recorder import SCHEMA_VERSION, InvocationRecord
        record = InvocationRecord(
            schema_version=SCHEMA_VERSION,
            recorded_at="2026-01-01T00:00:00Z",
            command="test.greet",
            args={"name": "world"},
            status="success",
            duration_ms=10,
            error_code=None,
            exit_code=0,
            caller_id="aider",
            session_id="sess-123",
        )
        d = record.to_dict()
        assert d["caller_id"] == "aider"
        assert d["session_id"] == "sess-123"
        assert d["schema_version"] == 2

    def test_invocation_record_without_caller(self):
        from tooli.eval.recorder import SCHEMA_VERSION, InvocationRecord
        record = InvocationRecord(
            schema_version=SCHEMA_VERSION,
            recorded_at="2026-01-01T00:00:00Z",
            command="test.greet",
            args={},
            status="success",
            duration_ms=5,
            error_code=None,
            exit_code=0,
        )
        d = record.to_dict()
        assert "caller_id" not in d
        assert "session_id" not in d


# ---------------------------------------------------------------------------
# OTel span caller attributes
# ---------------------------------------------------------------------------


class TestTelemetryCallerAttributes:

    def test_noop_span_set_caller_is_safe(self):
        from tooli.telemetry import _NoopCommandSpan
        span = _NoopCommandSpan()
        span.set_caller(caller_id="test", caller_version="1.0", session_id="s1")

    def test_active_span_set_caller(self):
        from unittest.mock import MagicMock

        from tooli.telemetry import _ActiveCommandSpan
        mock_span = MagicMock()
        span = _ActiveCommandSpan(command="test", span=mock_span)
        span.set_caller(caller_id="claude-code", caller_version="1.5", session_id="sess-1")
        mock_span.set_attribute.assert_any_call("tooli.caller_id", "claude-code")
        mock_span.set_attribute.assert_any_call("tooli.caller_version", "1.5")
        mock_span.set_attribute.assert_any_call("tooli.session_id", "sess-1")

    def test_active_span_set_caller_skips_none(self):
        from unittest.mock import MagicMock

        from tooli.telemetry import _ActiveCommandSpan
        mock_span = MagicMock()
        span = _ActiveCommandSpan(command="test", span=mock_span)
        mock_span.reset_mock()
        span.set_caller(caller_id=None, caller_version=None, session_id=None)
        # No caller-related set_attribute calls should have been made
        for c in mock_span.set_attribute.call_args_list:
            assert "caller" not in str(c)
            assert "session" not in str(c)


# ---------------------------------------------------------------------------
# SKILL.md Agent Integration section
# ---------------------------------------------------------------------------


class TestSkillAgentIntegration:

    def test_skill_md_contains_agent_integration(self):
        from tooli.docs.skill_v4 import generate_skill_md
        app = _make_app()
        content = generate_skill_md(app)
        assert "## Agent Integration" in content
        assert "TOOLI_CALLER" in content
        assert "detect-context" in content


# ---------------------------------------------------------------------------
# CLAUDE.md TOOLI_CALLER hints
# ---------------------------------------------------------------------------


class TestClaudeMdCallerHints:

    def test_claude_md_v2_mentions_tooli_caller(self):
        from tooli.docs.claude_md_v2 import generate_claude_md_v2
        app = _make_app()
        content = generate_claude_md_v2(app)
        assert "TOOLI_CALLER" in content
        assert "caller_id" in content


# ---------------------------------------------------------------------------
# Adaptive confirmation
# ---------------------------------------------------------------------------


class TestAdaptiveConfirmation:

    def test_agent_with_yes_skips_confirmation(self):
        from tooli.command import _needs_human_confirmation
        from tooli.security.policy import SecurityPolicy
        result = _needs_human_confirmation(
            SecurityPolicy.STANDARD,
            is_destructive=True,
            requires_approval=False,
            has_human_in_the_loop=False,
            force=False,
            yes_override=True,
            is_agent_caller=True,
        )
        assert result is False

    def test_human_without_yes_needs_confirmation(self):
        from tooli.command import _needs_human_confirmation
        from tooli.security.policy import SecurityPolicy
        result = _needs_human_confirmation(
            SecurityPolicy.STANDARD,
            is_destructive=True,
            requires_approval=False,
            has_human_in_the_loop=False,
            force=False,
            yes_override=False,
            is_agent_caller=False,
        )
        assert result is True
