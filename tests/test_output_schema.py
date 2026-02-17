"""Tests for output schema in envelope meta (#163)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from tooli import Tooli


def _make_app():
    app = Tooli(name="schema-app", version="1.0.0")

    @app.command()
    def greet(name: str) -> dict:
        """Greet someone."""
        return {"message": f"Hello, {name}!"}

    @app.command()
    def count(n: int) -> list:
        """Count to n."""
        return list(range(n))

    @app.command()
    def no_return(name: str):
        """Command with no return type."""
        pass

    return app


class TestOutputSchemaInEnvelope:
    def test_concise_mode_omits_schema(self):
        app = _make_app()
        runner = CliRunner()
        result = runner.invoke(app, ["greet", "World", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["meta"].get("output_schema") is None

    def test_detailed_mode_includes_schema(self):
        app = _make_app()
        runner = CliRunner()
        result = runner.invoke(app, ["greet", "World", "--json", "--response-format", "detailed"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        schema = data["meta"].get("output_schema")
        assert schema is not None
        assert schema.get("type") is not None

    def test_env_var_includes_schema(self, monkeypatch):
        monkeypatch.setenv("TOOLI_INCLUDE_SCHEMA", "true")
        app = _make_app()
        runner = CliRunner()
        result = runner.invoke(app, ["greet", "World", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        schema = data["meta"].get("output_schema")
        assert schema is not None

    def test_env_var_1_includes_schema(self, monkeypatch):
        monkeypatch.setenv("TOOLI_INCLUDE_SCHEMA", "1")
        app = _make_app()
        runner = CliRunner()
        result = runner.invoke(app, ["count", "3", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        schema = data["meta"].get("output_schema")
        assert schema is not None

    def test_schema_infer_returns_correct_type(self):
        """Verify the inferred schema matches the return type."""
        app = _make_app()
        runner = CliRunner()
        result = runner.invoke(app, ["count", "3", "--json", "--response-format", "detailed"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        schema = data["meta"].get("output_schema")
        assert schema is not None
        # list return type should produce array schema
        assert schema.get("type") == "array"

    def test_text_mode_unaffected(self):
        app = _make_app()
        runner = CliRunner()
        result = runner.invoke(app, ["greet", "World", "--text", "--response-format", "detailed"])
        assert result.exit_code == 0
        # Text mode doesn't use envelope at all
        assert "output_schema" not in result.output

    def test_envelope_meta_model_has_output_schema_field(self):
        from tooli.envelope import EnvelopeMeta
        meta = EnvelopeMeta(tool="test", version="1.0.0", duration_ms=1, output_schema={"type": "object"})
        d = meta.model_dump()
        assert d["output_schema"] == {"type": "object"}

    def test_envelope_meta_output_schema_none_by_default(self):
        from tooli.envelope import EnvelopeMeta
        meta = EnvelopeMeta(tool="test", version="1.0.0", duration_ms=1)
        d = meta.model_dump()
        assert d["output_schema"] is None
