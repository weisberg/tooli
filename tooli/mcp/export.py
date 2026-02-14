"""MCP tool definition export for Tooli."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:
    from tooli.app import Tooli


class MCPToolDefinition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str
    input_schema: dict[str, Any] = Field(alias="inputSchema")
    annotations: dict[str, Any] | None = None


def export_mcp_tools(app: Tooli) -> list[dict[str, Any]]:
    """Export all registered commands as MCP tool definitions."""
    from tooli.schema import generate_tool_schema
    from tooli.annotations import ToolAnnotation
    
    tools = []
    for cmd in app.registered_commands:
        cmd_id = cmd.name or cmd.callback.__name__
        schema = generate_tool_schema(cmd.callback, name=cmd_id)
        
        mcp_tool = {
            "name": cmd_id,
            "description": schema.description,
            "inputSchema": schema.input_schema,
        }
        
        # Add behavioral annotations as MCP hints
        annotations = getattr(cmd.callback, "__tooli_annotations__", None)
        if isinstance(annotations, ToolAnnotation):
            hints = {}
            if annotations.read_only: hints["readOnlyHint"] = True
            if annotations.idempotent: hints["idempotentHint"] = True
            if annotations.destructive: hints["destructiveHint"] = True
            if annotations.open_world: hints["openWorldHint"] = True
            if hints:
                mcp_tool["annotations"] = hints
        
        tools.append(mcp_tool)
        
    return tools
