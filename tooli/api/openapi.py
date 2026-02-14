"""OpenAPI schema generation for Tooli apps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tooli.app import Tooli


def generate_openapi_schema(app: Tooli) -> dict[str, Any]:
    """Generate OpenAPI 3.1.0 schema for a Tooli application."""
    from tooli.schema import generate_tool_schema

    name = app.info.name or "tooli-app"
    description = app.info.help or "An agent-native CLI application."
    version = app.version or "0.0.0"

    paths: dict[str, Any] = {}

    for tool in app.get_tools():
        if tool.hidden:
            continue

        cmd_id = tool.name or tool.callback.__name__
        schema = generate_tool_schema(tool.callback, name=cmd_id)

        # We model every command as a POST request to avoid URL length issues
        # and to keep it simple for agent discovery.
        paths[f"/{cmd_id}"] = {
            "post": {
                "summary": schema.description.split("\n")[0],
                "description": schema.description,
                "operationId": cmd_id,
                "requestBody": {
                    "content": {"application/json": {"schema": schema.input_schema}},
                    "required": True,
                },
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Envelope"}
                            }
                        },
                    }
                },
                "tags": [name],
            }
        }

    return {
        "openapi": "3.1.0",
        "info": {"title": name, "description": description, "version": version},
        "paths": paths,
        "components": {
            "schemas": {
                "Envelope": {
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "result": {"type": "object", "nullable": True},
                        "meta": {
                            "type": "object",
                            "properties": {
                                "tool": {"type": "string"},
                                "version": {"type": "string"},
                                "duration_ms": {"type": "integer", "minimum": 0},
                                "warnings": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["tool", "version", "duration_ms", "warnings"],
                        },
                        "error": {
                            "type": "object",
                            "nullable": True,
                            "properties": {
                                "message": {"type": "string"},
                                "code": {"type": "string"},
                                "category": {"type": "string"},
                                "suggestion": {"type": "object", "nullable": True},
                                "details": {"type": "object"},
                            },
                        },
                    },
                    "required": ["ok", "meta"],
                }
            }
        },
    }
