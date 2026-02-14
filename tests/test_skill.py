"""Tests for generated SKILL.md output."""

from __future__ import annotations

from tooli import Tooli
from tooli.annotations import ReadOnly
from tooli.docs.skill import generate_skill_md


def test_generate_skill_includes_governance_section() -> None:
    """SKILL.md generation should include per-command governance metadata."""
    app = Tooli(name="skill-app")

    @app.command(annotations=ReadOnly, cost_hint="medium", human_in_the_loop=True)
    def inspect() -> list[str]:
        return ["ok"]

    content = generate_skill_md(app)
    assert "### `inspect`" in content
    assert "#### Governance" in content
    assert "**Annotations**: `read-only`" in content
    assert "**Cost Hint**: `medium`" in content
    assert "**Human In The Loop**: `true`" in content

