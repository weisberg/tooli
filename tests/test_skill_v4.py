"""Tests for v4 SKILL.md generator and new metadata fields."""

from __future__ import annotations

from tooli.annotations import Destructive, ReadOnly  # noqa: F401
from tooli.command_meta import CommandMeta, get_command_meta
from tooli.docs.skill_v4 import (
    estimate_skill_tokens,
    generate_skill_md,
    validate_skill_doc,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(**kwargs):
    """Build a minimal Tooli app for testing."""
    from tooli import Tooli

    app = Tooli(name="test-app", help="A test application.", version="1.0.0", **kwargs)
    return app


def _make_app_with_commands(*, task_groups=False, when_to_use=False, expected_outputs=False):
    app = _make_app()

    expected = []
    if expected_outputs:
        expected = [{"items": ["a", "b"], "count": 2}]

    @app.command(
        "list-items",
        annotations=ReadOnly,
        examples=[{"args": ["--format", "json"], "description": "List all items"}],
        error_codes={"E3001": "No items found -> Use broader filter"},
        task_group="Query" if task_groups else None,
        when_to_use="Use when you need to enumerate available items" if when_to_use else None,
        expected_outputs=expected,
    )
    def list_items(format: str = "json") -> dict:
        """List all items in the store."""
        return {"items": [], "count": 0}

    @app.command(
        "delete-item",
        annotations=Destructive,
        examples=[{"args": ["item-123"], "description": "Delete an item"}],
        error_codes={"E3002": "Item not found -> Verify item ID"},
        task_group="Mutation" if task_groups else None,
        when_to_use="Use when you need to remove an item permanently" if when_to_use else None,
        supports_dry_run=True,
    )
    def delete_item(item_id: str) -> dict:
        """Delete an item by ID."""
        return {"deleted": item_id}

    return app


# ---------------------------------------------------------------------------
# CommandMeta v4 fields
# ---------------------------------------------------------------------------

class TestCommandMetaV4Fields:
    def test_new_fields_default_values(self):
        meta = CommandMeta()
        assert meta.when_to_use is None
        assert meta.expected_outputs == []
        assert meta.task_group is None

    def test_new_fields_stored_on_callback(self):
        app = _make_app()

        @app.command(
            "test-cmd",
            when_to_use="Use for testing",
            task_group="Testing",
            expected_outputs=[{"result": "ok"}],
        )
        def test_cmd() -> str:
            """Test command."""
            return "ok"

        meta = get_command_meta(test_cmd)
        assert meta.when_to_use == "Use for testing"
        assert meta.task_group == "Testing"
        assert meta.expected_outputs == [{"result": "ok"}]


# ---------------------------------------------------------------------------
# Task-oriented grouping
# ---------------------------------------------------------------------------

class TestTaskGrouping:
    def test_groups_present_in_output(self):
        app = _make_app_with_commands(task_groups=True)
        content = generate_skill_md(app)
        assert "### Query" in content
        assert "### Mutation" in content

    def test_no_groups_when_all_general(self):
        app = _make_app_with_commands(task_groups=False)
        content = generate_skill_md(app)
        # Should not have group headings when all commands are "General"
        assert "### General" not in content


# ---------------------------------------------------------------------------
# When to use
# ---------------------------------------------------------------------------

class TestWhenToUse:
    def test_explicit_when_to_use(self):
        app = _make_app_with_commands(when_to_use=True)
        content = generate_skill_md(app)
        assert "Use when you need to enumerate available items" in content
        assert "Use when you need to remove an item permanently" in content

    def test_auto_synthesized_when_to_use(self):
        app = _make_app_with_commands(when_to_use=False)
        content = generate_skill_md(app)
        # Auto-synthesis should include docstring first line
        assert "List all items in the store" in content


# ---------------------------------------------------------------------------
# Expected outputs
# ---------------------------------------------------------------------------

class TestExpectedOutputs:
    def test_expected_output_rendered(self):
        app = _make_app_with_commands(expected_outputs=True)
        content = generate_skill_md(app)
        assert "Expected output:" in content
        assert '"count": 2' in content


# ---------------------------------------------------------------------------
# Trigger synthesis
# ---------------------------------------------------------------------------

class TestTriggerSynthesis:
    def test_enhanced_trigger_template(self):
        app = _make_app(triggers=["item management", "inventory"])
        @app.command("noop")
        def noop() -> None:
            """No-op command."""
        content = generate_skill_md(app)
        assert "Use this skill whenever" in content
        assert "Triggers include:" in content

    def test_anti_triggers_in_frontmatter(self):
        app = _make_app(anti_triggers=["database admin", "deployment"])
        @app.command("noop")
        def noop() -> None:
            """No-op."""
        content = generate_skill_md(app)
        assert "Do NOT use for" in content


# ---------------------------------------------------------------------------
# Composition patterns
# ---------------------------------------------------------------------------

class TestCompositionPatterns:
    def test_readonly_destructive_preview_pair(self):
        app = _make_app_with_commands()
        content = generate_skill_md(app)
        assert "Preview then execute" in content

    def test_dry_run_pattern(self):
        app = _make_app_with_commands()
        content = generate_skill_md(app)
        assert "Safe execution: delete-item" in content


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_valid_v4_doc(self):
        app = _make_app_with_commands()
        content = generate_skill_md(app)
        result = validate_skill_doc(content)
        assert result["valid"] is True, f"Issues: {result.get('issues')}"

    def test_all_prd_sections_present(self):
        app = _make_app_with_commands()
        content = generate_skill_md(app)
        required = [
            "## Quick Reference",
            "## Installation",
            "## Commands",
            "## Composition Patterns",
            "## Global Flags",
            "## Output Format",
            "## Exit Codes",
            "## Critical Rules",
        ]
        for section in required:
            assert section in content, f"Missing section: {section}"

    def test_missing_sections_detected(self):
        result = validate_skill_doc("# Just a title\n\nNo sections here.\n")
        assert result["valid"] is False
        assert len(result["issues"]) > 0


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_v3_app_generates_valid_v4(self):
        """An app with no v4 fields should still produce valid SKILL.md."""
        app = _make_app()

        @app.command("hello")
        def hello(name: str = "world") -> str:
            """Say hello."""
            return f"Hello, {name}!"

        content = generate_skill_md(app)
        result = validate_skill_doc(content)
        assert result["valid"] is True, f"Issues: {result.get('issues')}"


# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------

class TestTokenBudget:
    def test_10_commands_under_4000_tokens(self):
        app = _make_app()
        for i in range(10):
            @app.command(f"cmd-{i}")
            def _cmd(x: str = "default") -> str:
                """A simple command."""
                return x
            # Re-register with unique name by using the loop
        content = generate_skill_md(app)
        tokens = estimate_skill_tokens(content)
        assert tokens <= 4000, f"10-command doc used {tokens} tokens (max 4000)"

    def test_50_commands_summary_under_5000_tokens(self):
        app = _make_app()
        for i in range(50):
            @app.command(f"cmd-{i}")
            def _cmd(x: str = "default") -> str:
                """A simple command."""
                return x
        content = generate_skill_md(app, detail_level="summary")
        tokens = estimate_skill_tokens(content)
        assert tokens <= 5000, f"50-command summary used {tokens} tokens (max 5000)"


# ---------------------------------------------------------------------------
# Claude Code target
# ---------------------------------------------------------------------------

class TestClaudeCodeTarget:
    def test_claude_code_rules(self):
        app = _make_app_with_commands()
        content = generate_skill_md(app, target="claude-code")
        assert "Use Bash tool to invoke CLI commands" in content
