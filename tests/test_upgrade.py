"""Tests for upgrade-metadata analysis."""

from __future__ import annotations

from tooli.annotations import ReadOnly
from tooli.upgrade import analyze_metadata, generate_upgrade_stubs


def _make_app(*, with_metadata=False):
    from tooli import Tooli

    app = Tooli(name="upgrade-test", help="Upgrade test", version="1.0.0")

    kwargs = {}
    if with_metadata:
        kwargs = {
            "annotations": ReadOnly,
            "examples": [{"args": ["--all"]}],
            "error_codes": {"E1": "Error"},
            "when_to_use": "List items",
            "task_group": "Query",
            "pipe_output": {"format": "json"},
            "recovery_playbooks": {"E1": ["Fix it"]},
            "expected_outputs": [{"items": []}],
        }

    @app.command("cmd", **kwargs)
    def cmd() -> list:
        """A command."""
        return []

    return app


class TestAnalyzeMetadata:
    def test_bare_command_has_suggestions(self):
        report = analyze_metadata(_make_app())
        assert report["commands_with_suggestions"] == 1
        suggestions = report["suggestions"][0]["suggestions"]
        assert any("examples" in s for s in suggestions)
        assert any("when_to_use" in s for s in suggestions)

    def test_fully_annotated_has_no_suggestions(self):
        report = analyze_metadata(_make_app(with_metadata=True))
        assert report["commands_with_suggestions"] == 0

    def test_total_commands_correct(self):
        report = analyze_metadata(_make_app())
        assert report["total_commands"] == 1


class TestGenerateStubs:
    def test_stubs_for_bare_command(self):
        stubs = generate_upgrade_stubs(_make_app())
        assert "cmd" in stubs
        assert "when_to_use" in stubs["cmd"]
        assert "task_group" in stubs["cmd"]

    def test_no_stubs_for_complete_command(self):
        stubs = generate_upgrade_stubs(_make_app(with_metadata=True))
        assert "cmd" not in stubs
