"""Tests for generated SKILL.md output."""

from __future__ import annotations

from pathlib import Path
import time
from pydantic import BaseModel
from typer.testing import CliRunner

from tooli import Tooli
from tooli.annotations import ReadOnly
from tooli.docs.skill import (
    estimate_skill_tokens,
    generate_skill_md,
    validate_skill_doc,
)
from tooli.manifest import generate_agent_manifest


class FileResult(BaseModel):
    path: str
    size: int


def test_generate_skill_includes_sections() -> None:
    """SKILL.md includes required v3 sections and frontmatter."""
    app = Tooli(name="skill-app")

    @app.command(annotations=ReadOnly, cost_hint="medium", human_in_the_loop=True)
    def inspect() -> list[str]:
        return ["ok"]

    content = generate_skill_md(app)
    assert content.startswith("---")
    assert "name: skill-app" in content
    assert "## Quick Reference" in content
    assert "## Installation" in content
    assert "## Commands" in content
    assert "## Global Flags" in content
    assert "## Output Envelope Format" in content
    assert "## Error Catalog" in content
    assert "## Workflow Patterns" in content
    assert "## Critical Rules" in content
    assert "### `inspect`" in content
    assert "**Behavior**: `read-only`" in content
    assert "**Cost Hint**: `medium`" in content
    assert "Always use `--json` when invoking from an agent." in content


def test_generate_skill_summary_mode() -> None:
    app = Tooli(name="skill-app")

    @app.command()
    def summarize() -> int:
        return 1

    content = generate_skill_md(app, detail_level="summary")
    assert "## Tier 2 summary" in content
    assert "| Command | Description |" in content
    assert "#### Parameters" not in content


def test_output_schema_for_return_annotation() -> None:
    app = Tooli(name="skill-app")

    @app.command()
    def find_files(pattern: str) -> list[FileResult]:
        return [FileResult(path="foo", size=12)]

    content = generate_skill_md(app, detail_level="full")
    assert '"type": "array"' in content
    assert '"path": {' in content or '"path":' in content
    assert '"size":' in content


def test_validate_skill_doc() -> None:
    app = Tooli(name="skill-app")

    @app.command()
    def ping() -> str:
        return "pong"

    content = generate_skill_md(app)
    result = validate_skill_doc(content)
    assert result["valid"] is True
    assert result["issues"] == []

    bad = "# missing frontmatter\n## Commands\n"
    bad_result = validate_skill_doc(bad)
    assert bad_result["valid"] is False
    assert any("frontmatter" in issue["message"] for issue in bad_result["issues"])


def test_skill_metadata_drives_triggers_and_rules() -> None:
    """Tool-level metadata appears in generated documentation."""
    app = Tooli(
        name="metadata-app",
        triggers=["build files", "check output"],
        anti_triggers=["delete", "network calls"],
        rules=["Use --json for automation."],
        env_vars={"METADATA_APP_TOKEN": {"required_for": ["analyze"], "description": "Auth token."}},
    )

    @app.command()
    def analyze(path: str) -> str:
        return path

    content = generate_skill_md(app, detail_level="full")
    assert "triggers:" in content
    assert "build files" in content
    assert "anti_triggers:" in content
    assert "delete" in content
    assert "Use --json for automation." in content
    assert "METADATA_APP_TOKEN" in content


def test_frontmatter_includes_trigger_expansion() -> None:
    """Frontmatter description auto-expands with trigger phrases."""
    app = Tooli(name="frontmatter-app", description="A file helper")

    @app.command()
    def find_files(pattern: str) -> str:
        """Find files matching patterns in a directory."""
        return pattern

    content = generate_skill_md(app)
    assert "name: frontmatter-app" in content
    assert "Useful for:" in content
    assert "find files" in content.lower()


def test_generate_skill_default_format_is_claude_skill(tmp_path: Path) -> None:
    """generate-skill defaults to the SKILL format while writing structured output."""
    app = Tooli(name="format-default")

    @app.command()
    def ping() -> str:
        return "pong"

    runner = CliRunner()
    path = tmp_path / "default-doc.md"
    result = runner.invoke(app, ["generate-skill", "--output-path", str(path)])
    assert result.exit_code == 0
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---")
    assert "## Quick Reference" in content


def test_skill_token_budget_benchmark_auto_summary_mode() -> None:
    """Large apps should auto-switch to summary mode and remain lower token footprint."""
    app = Tooli(name="token-budget-app")

    for index in range(24):

        def _make_command(cmd_index: int) -> None:
            @app.command(name=f"command-{cmd_index}", annotations=ReadOnly)
            def _command(path: str = ".") -> str:
                return path

        _make_command(index)

    auto = generate_skill_md(app, detail_level="auto")
    assert "## Tier 2 summary" in auto
    assert "#### Parameters" not in auto

    full = generate_skill_md(app, detail_level="full")
    summary_tokens = estimate_skill_tokens(auto)
    full_tokens = estimate_skill_tokens(full)

    assert summary_tokens < full_tokens
    assert summary_tokens > 0
    assert full_tokens >= summary_tokens


def test_skill_token_budget_targets() -> None:
    """Token estimation helper should support threshold checks for SKILL artifacts."""
    app = Tooli(name="small-token-app")

    @app.command()
    def hello(name: str) -> str:
        return name

    content = generate_skill_md(app, detail_level="full")
    token_count = estimate_skill_tokens(content)
    assert token_count > 0
    assert estimate_skill_tokens(content) <= 3000


def test_skill_benchmark_50_command_summary_stays_compact() -> None:
    app = Tooli(name="benchmark-app")

    for index in range(50):

        def _make_command(cmd_index: int) -> None:
            @app.command(name=f"command-{cmd_index}")
            def _command() -> dict[str, int]:
                return {"index": cmd_index}

        _make_command(index)

    start = time.perf_counter()
    manifest = generate_agent_manifest(app)
    duration_ms = (time.perf_counter() - start) * 1000
    assert duration_ms < 500.0
    assert len(manifest["commands"]) == 50

    auto = generate_skill_md(app, detail_level="auto")
    full = generate_skill_md(app, detail_level="full")
    assert "## Tier 2 summary" in auto
    assert "### `command-0`" in full
    assert estimate_skill_tokens(auto) <= 5000
    assert estimate_skill_tokens(full) > estimate_skill_tokens(auto)
