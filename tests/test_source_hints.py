"""Tests for source-level agent hint generation and parsing."""

from __future__ import annotations

from tooli.annotations import Destructive, ReadOnly
from tooli.docs.source_hints import (
    generate_source_hints,
    insert_source_hints,
    parse_source_hints,
)


def _make_app():
    from tooli import Tooli

    app = Tooli(name="hint-test", help="Hint test app", version="1.0.0")

    @app.command("list-items", annotations=ReadOnly, task_group="Query")
    def list_items() -> list:
        """List items."""
        return []

    @app.command("delete-item", annotations=Destructive, task_group="Mutation")
    def delete_item(item_id: str) -> dict:
        """Delete item."""
        return {"deleted": item_id}

    return app


class TestGenerateHints:
    def test_basic_structure(self):
        app = _make_app()
        hints = generate_source_hints(app)
        assert hints.startswith("# tooli:agent\n")
        assert hints.strip().endswith("# tooli:end")

    def test_contains_app_info(self):
        app = _make_app()
        hints = generate_source_hints(app)
        assert "# app: hint-test" in hints
        assert "# description: Hint test app" in hints

    def test_contains_commands(self):
        app = _make_app()
        hints = generate_source_hints(app)
        assert "# cmd: list-items [read-only] group=Query" in hints
        assert "# cmd: delete-item [destructive] group=Mutation" in hints


class TestInsertHints:
    def test_insert_before_imports(self):
        source = '"""Module docstring."""\n\nimport os\nimport sys\n'
        hints = "# tooli:agent\n# cmd: test\n# tooli:end\n"
        result = insert_source_hints(source, hints)
        assert result.index("# tooli:agent") < result.index("import os")

    def test_replace_existing_block(self):
        source = (
            '"""Doc."""\n\n'
            "# tooli:agent\n# old content\n# tooli:end\n\n"
            "import os\n"
        )
        hints = "# tooli:agent\n# new content\n# tooli:end\n"
        result = insert_source_hints(source, hints)
        assert "# old content" not in result
        assert "# new content" in result
        # Should only have one block
        assert result.count("# tooli:agent") == 1

    def test_insert_when_no_imports(self):
        source = '"""Just a doc."""\n\nx = 1\n'
        hints = "# tooli:agent\n# cmd: test\n# tooli:end\n"
        result = insert_source_hints(source, hints)
        assert "# tooli:agent" in result


class TestParseHints:
    def test_parse_full_block(self):
        source = (
            "# tooli:agent\n"
            "# app: my-app v1.0.0\n"
            "# description: My application\n"
            "# cmd: hello [read-only]\n"
            "# cmd: delete [destructive] group=Mutation\n"
            "# tooli:end\n"
        )
        parsed = parse_source_hints(source)
        assert parsed is not None
        assert parsed["app"] == "my-app v1.0.0"
        assert parsed["description"] == "My application"
        assert len(parsed["commands"]) == 2
        assert "hello [read-only]" in parsed["commands"]

    def test_parse_no_block(self):
        source = "import os\n"
        assert parse_source_hints(source) is None
