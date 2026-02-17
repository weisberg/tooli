"""Tests for AGENTS.md generator."""

from __future__ import annotations

from tooli.annotations import Destructive, ReadOnly
from tooli.docs.agents_md import generate_agents_md


def _make_app():
    """Build a minimal Tooli app for testing."""
    from tooli import Tooli

    app = Tooli(
        name="test-app",
        help="A test application.",
        version="1.0.0",
        rules=["Never delete production data without confirmation."],
    )

    @app.command(
        "list-items",
        annotations=ReadOnly,
        examples=[{"args": ["--format", "json"], "description": "List all items"}],
    )
    def list_items(format: str = "json") -> list:
        """List all items in the store."""
        return []

    @app.command(
        "delete-item",
        annotations=Destructive,
        examples=[{"args": ["item-123"], "description": "Delete an item"}],
        supports_dry_run=True,
    )
    def delete_item(item_id: str) -> dict:
        """Delete an item by ID."""
        return {"deleted": item_id}

    return app


class TestGenerateAgentsMd:
    def test_contains_header(self):
        content = generate_agents_md(_make_app())
        assert "# AGENTS.md" in content

    def test_contains_project_overview(self):
        content = generate_agents_md(_make_app())
        assert "## Project Overview" in content
        assert "A test application." in content
        assert "test-app" in content
        assert "1.0.0" in content

    def test_all_commands_documented(self):
        content = generate_agents_md(_make_app())
        assert "### list-items" in content
        assert "### delete-item" in content

    def test_command_usage_shown(self):
        content = generate_agents_md(_make_app())
        assert "test-app list-items --json" in content
        assert "test-app delete-item <item_id> --json" in content

    def test_parameters_shown(self):
        content = generate_agents_md(_make_app())
        assert "`format` (optional" in content
        assert "`item_id` (required" in content

    def test_output_format_section_present(self):
        content = generate_agents_md(_make_app())
        assert "## Output Format" in content
        assert '"ok": true' in content
        assert '"ok": false' in content
        assert '"result"' in content
        assert '"error"' in content

    def test_important_rules_section_present(self):
        content = generate_agents_md(_make_app())
        assert "## Important Rules" in content
        assert "Always use `--json` flag when invoking programmatically." in content
        assert "Check the `ok` field before accessing `result`." in content
        assert "Use `--dry-run` before destructive commands." in content
        assert "Use `--yes` to skip confirmation prompts in automation." in content

    def test_app_specific_rules_included(self):
        content = generate_agents_md(_make_app())
        assert "Never delete production data without confirmation." in content

    def test_annotation_labels_shown(self):
        content = generate_agents_md(_make_app())
        assert "read-only" in content
        assert "destructive" in content

    def test_json_envelope_fields(self):
        content = generate_agents_md(_make_app())
        assert '"tool"' in content
        assert '"code"' in content
        assert '"message"' in content

    def test_available_commands_section(self):
        content = generate_agents_md(_make_app())
        assert "## Available Commands" in content


class TestBuiltinCommand:
    def test_generate_agents_md_command(self):
        from typer.testing import CliRunner

        app = _make_app()
        runner = CliRunner()
        result = runner.invoke(app, ["generate-agents-md", "--output", "-"])
        assert result.exit_code == 0
        assert "# AGENTS.md" in result.output
        assert "## Available Commands" in result.output

    def test_generate_skill_format_agents_md(self):
        from typer.testing import CliRunner

        app = _make_app()
        runner = CliRunner()
        result = runner.invoke(app, ["generate-skill", "--format", "agents-md", "--output", "-"])
        assert result.exit_code == 0
        assert "# AGENTS.md" in result.output
        assert "## Available Commands" in result.output
