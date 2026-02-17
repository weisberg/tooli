"""Tests for v4 SKILL.md generator, bootstrap, and new metadata fields."""

from __future__ import annotations

import os
from unittest import mock

from tooli.annotations import Destructive, ReadOnly  # noqa: F401
from tooli.command_meta import CommandMeta, get_command_meta
from tooli.docs.skill_v4 import (
    estimate_skill_tokens,
    generate_skill_md,
    validate_skill_doc,
)
from tooli.pipes import PipeContract, pipe_contracts_compatible

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(**kwargs):
    """Build a minimal Tooli app for testing."""
    from tooli import Tooli

    app = Tooli(name="test-app", help="A test application.", version="1.0.0", **kwargs)
    return app


def _make_app_with_commands(*, task_groups=False, when_to_use=False, recovery=False, pipes=False, expected_outputs=False):
    app = _make_app()

    pipe_input = None
    pipe_output = None
    if pipes:
        pipe_output = PipeContract(format="json", description="List of items").to_dict()
        pipe_input = PipeContract(format="json", description="Items to process").to_dict()

    recovery_playbooks: dict[str, list[str]] = {}
    if recovery:
        recovery_playbooks = {
            "File not found": ["Check the path exists", "Use --root to set base directory"],
        }

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
        pipe_output=pipe_output,
        expected_outputs=expected,
        recovery_playbooks=recovery_playbooks,
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
        pipe_input=pipe_input,
        supports_dry_run=True,
        recovery_playbooks={"Permission denied": ["Check your API key", "Verify scopes"]} if recovery else {},
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
        assert meta.pipe_input is None
        assert meta.pipe_output is None
        assert meta.when_to_use is None
        assert meta.expected_outputs == []
        assert meta.recovery_playbooks == {}
        assert meta.task_group is None

    def test_new_fields_stored_on_callback(self):
        app = _make_app()
        pipe_out = PipeContract(format="json", description="test").to_dict()

        @app.command(
            "test-cmd",
            pipe_output=pipe_out,
            when_to_use="Use for testing",
            task_group="Testing",
            recovery_playbooks={"E1": ["Step 1"]},
            expected_outputs=[{"result": "ok"}],
        )
        def test_cmd() -> str:
            """Test command."""
            return "ok"

        meta = get_command_meta(test_cmd)
        assert meta.pipe_output == pipe_out
        assert meta.when_to_use == "Use for testing"
        assert meta.task_group == "Testing"
        assert meta.recovery_playbooks == {"E1": ["Step 1"]}
        assert meta.expected_outputs == [{"result": "ok"}]


# ---------------------------------------------------------------------------
# PipeContract
# ---------------------------------------------------------------------------

class TestPipeContract:
    def test_to_dict_and_from_dict(self):
        contract = PipeContract(format="json", schema={"type": "array"}, description="Items", example='[{"id": 1}]')
        d = contract.to_dict()
        assert d["format"] == "json"
        assert d["schema"] == {"type": "array"}
        assert d["description"] == "Items"
        assert d["example"] == '[{"id": 1}]'

        restored = PipeContract.from_dict(d)
        assert restored.format == "json"
        assert restored.schema == {"type": "array"}

    def test_minimal_to_dict(self):
        contract = PipeContract(format="text")
        d = contract.to_dict()
        assert d == {"format": "text"}

    def test_compatibility(self):
        out = PipeContract(format="json").to_dict()
        inp = PipeContract(format="json").to_dict()
        assert pipe_contracts_compatible(out, inp) is True

    def test_incompatibility(self):
        out = PipeContract(format="json").to_dict()
        inp = PipeContract(format="csv").to_dict()
        assert pipe_contracts_compatible(out, inp) is False

    def test_none_contracts(self):
        assert pipe_contracts_compatible(None, None) is False
        assert pipe_contracts_compatible({"format": "json"}, None) is False


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
# Error recovery sections
# ---------------------------------------------------------------------------

class TestErrorRecovery:
    def test_inline_recovery_playbooks(self):
        app = _make_app_with_commands(recovery=True)
        content = generate_skill_md(app)
        assert "If Something Goes Wrong" in content
        assert "Check the path exists" in content
        assert "Use --root to set base directory" in content

    def test_error_codes_in_recovery(self):
        app = _make_app_with_commands(recovery=True)
        content = generate_skill_md(app)
        assert "E3001" in content
        assert "E3002" in content


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
    def test_pipe_contract_composition(self):
        app = _make_app_with_commands(pipes=True)
        content = generate_skill_md(app)
        assert "## Composition Patterns" in content
        assert "Pipe list-items into delete-item" in content

    def test_readonly_destructive_preview_pair(self):
        app = _make_app_with_commands()
        content = generate_skill_md(app)
        assert "Preview then execute" in content

    def test_dry_run_pattern(self):
        app = _make_app_with_commands()
        content = generate_skill_md(app)
        assert "Safe execution: delete-item" in content


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

class TestBootstrap:
    def test_agent_bootstrap_produces_skill(self):
        from tooli.bootstrap import generate_bootstrap

        app = _make_app_with_commands()
        result = generate_bootstrap(app)
        assert result.startswith("---\n")
        assert "## Commands" in result

    def test_auto_target_detection_claude_code(self):
        from tooli.bootstrap import _detect_target

        with mock.patch.dict(os.environ, {"CLAUDE_CODE": "1"}):
            assert _detect_target() == "claude-code"

    def test_auto_target_detection_anthropic(self):
        from tooli.bootstrap import _detect_target

        env = {"ANTHROPIC_API_KEY": "sk-ant-test"}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_CODE", None)
            assert _detect_target() in ("claude-skill", "generic-skill")

    def test_auto_target_detection_generic(self):
        from tooli.bootstrap import _detect_target

        with mock.patch.dict(os.environ, {}, clear=True):
            assert _detect_target() == "generic-skill"


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
