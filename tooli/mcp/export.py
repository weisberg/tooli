"""MCP tool definition export for Tooli."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from tooli.app import Tooli


class MCPToolDefinition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str
    input_schema: dict[str, Any] = Field(alias="inputSchema")
    annotations: dict[str, Any] | None = None


def export_mcp_tools(
    app: Tooli,
    *,
    defer_loading: bool = False,
    include_resources: bool = False,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Export all registered commands as MCP tool definitions."""
    from tooli.annotations import ToolAnnotation
    from tooli.command_meta import get_command_meta
    from tooli.schema import generate_tool_schema

    if defer_loading:
        return [
            {
                "name": "search_tools",
                "description": "Find command names and signatures that match a query.",
                "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
            },
            {
                "name": "run_tool",
                "description": "Execute an existing Tooli command by name.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "arguments": {"type": "object", "additionalProperties": True},
                    },
                    "required": ["name"],
                },
                "annotations": {"readOnlyHint": False},
            },
        ]

    # Preserve backwards-compatibility for callers that expect only tool payloads.
    tools: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    prompts: list[dict[str, Any]] = []

    for tool_def in app.get_tools():
        if tool_def.hidden:
            continue

        callback = tool_def.callback
        schema = generate_tool_schema(callback, name=tool_def.name)
        meta = get_command_meta(callback)

        mcp_tool = {
            "name": tool_def.name,
            "description": tool_def.help or schema.description,
            "inputSchema": schema.input_schema,
            "version": schema.version,
        }

        if schema.deprecated:
            mcp_tool["deprecated"] = True  # type: ignore[assignment]
            if schema.deprecated_message:
                mcp_tool["deprecatedMessage"] = schema.deprecated_message

        if required_scopes := meta.auth:
            mcp_tool["auth"] = list(required_scopes)  # type: ignore[assignment]

        # Add behavioral annotations as MCP hints
        annotations = meta.annotations
        if isinstance(annotations, ToolAnnotation):
            hints = {}
            if annotations.read_only:
                hints["readOnlyHint"] = True
            if annotations.idempotent:
                hints["idempotentHint"] = True
            if annotations.destructive:
                hints["destructiveHint"] = True
            if annotations.open_world:
                hints["openWorldHint"] = True
            if hints:
                mcp_tool["annotations"] = hints

        tools.append(mcp_tool)

    for callback, meta in app.get_resources():
        if meta.hidden:
            continue

        resource = {
            "uri": meta.uri,
            "name": meta.name or callback.__name__,
            "description": (meta.description or ""),
            "mimeType": meta.mime_type,
            "meta": {
                "annotations": {"readOnlyHint": True},
                "tags": list(meta.tags),
            },
        }
        resources.append({k: v for k, v in resource.items() if v not in (None, "", [])})

    for callback, meta in app.get_prompts():
        if meta.hidden:
            continue

        prompt = {
            "name": meta.name,
            "description": meta.description or "",
            "meta": {
                "callback": getattr(callback, "__name__", "prompt"),
            },
        }
        prompts.append(prompt)

    if not include_resources:
        return tools

    return {
        "tools": tools,
        "resources": [entry for entry in resources if entry is not None],
        "prompts": [entry for entry in prompts if entry is not None],
    }
