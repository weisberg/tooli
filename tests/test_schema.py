"""Tests for Tooli output schema generation."""

from __future__ import annotations

from pydantic import BaseModel

from tooli import Tooli
from tooli.schema import generate_tool_schema


class FileRecord(BaseModel):
    name: str
    size: int


def test_generate_tool_schema_includes_output_schema_from_return_type() -> None:
    app = Tooli(name="schema-app")

    @app.command()
    def list_files(pattern: str) -> list[FileRecord]:
        return [FileRecord(name="example", size=1)]

    schema = generate_tool_schema(list_files, name="list_files")
    assert schema.output_schema is not None
    assert schema.output_schema.get("type") == "array"
    assert schema.output_schema.get("items", {}).get("type") == "object"


def test_generate_tool_schema_uses_output_example_fallback() -> None:
    app = Tooli(name="schema-app")

    @app.command(output_example={"path": "src/main.py", "size": 17})
    def status(path: str) -> dict:
        return {"path": path}

    schema = generate_tool_schema(status, name="status")
    assert schema.output_schema is not None
    assert schema.output_schema.get("type") == "object"
    properties = schema.output_schema.get("properties", {})
    assert properties["path"]["type"] == "string"
    assert properties["size"]["type"] == "integer"
