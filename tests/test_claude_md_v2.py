"""Tests for enhanced CLAUDE.md v2 generator."""

from __future__ import annotations

from tooli.annotations import ReadOnly
from tooli.docs.claude_md_v2 import generate_claude_md_v2


def _make_app():
    from tooli import Tooli

    app = Tooli(name="claude-test", help="A test app.", version="2.0.0")

    @app.command(
        "search",
        annotations=ReadOnly,
        examples=[{"args": ["--query", "test"], "description": "Search items"}],
    )
    def search(query: str = "") -> list:
        """Search for items."""
        return []

    return app


class TestClaudeMdV2:
    def test_contains_build_section(self):
        content = generate_claude_md_v2(_make_app())
        assert "## Build & Test" in content
        assert "pip install claude-test" in content

    def test_contains_architecture(self):
        content = generate_claude_md_v2(_make_app())
        assert "## Architecture" in content
        assert "Tooli v4" in content
        assert "2.0.0" in content

    def test_contains_agent_invocation(self):
        content = generate_claude_md_v2(_make_app())
        assert "## Agent Invocation" in content
        assert "--json" in content

    def test_contains_key_commands(self):
        content = generate_claude_md_v2(_make_app())
        assert "## Key Commands" in content
        assert "claude-test search" in content

    def test_contains_key_patterns(self):
        content = generate_claude_md_v2(_make_app())
        assert "## Key Patterns" in content
        assert "--agent-bootstrap" in content

    def test_contains_dev_workflow(self):
        content = generate_claude_md_v2(_make_app())
        assert "## Development Workflow" in content

    def test_annotation_labels_shown(self):
        content = generate_claude_md_v2(_make_app())
        assert "[read-only]" in content
