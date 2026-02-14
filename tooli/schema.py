"""Schema generation pipeline for Tooli commands."""

from __future__ import annotations

import inspect
from collections.abc import Callable  # noqa: TC003
from typing import (
    Annotated,
    Any,
    get_args,
    get_origin,
)

from pydantic import BaseModel, Field, create_model

from tooli.command_meta import get_command_meta


class ToolSchema(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    cost_hint: str | None = None
    version: str | None = None
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] = Field(default_factory=dict)
    auth: list[str] = Field(default_factory=list)
    examples: list[dict[str, Any]] = Field(default_factory=list)
    deprecated: bool = False
    deprecated_message: str | None = None


def _dereference_refs(schema: dict[str, Any], root_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """Recursively inline $ref entries."""
    if root_schema is None:
        root_schema = schema

    if isinstance(schema, dict):
        if "$ref" in schema:
            ref_path = schema["$ref"]
            if ref_path.startswith("#/$defs/"):
                def_name = ref_path.split("/")[-1]
                ref_content = root_schema.get("$defs", {}).get(def_name, {})
                # Recursively dereference the content
                return _dereference_refs(ref_content, root_schema)

        return {k: _dereference_refs(v, root_schema) for k, v in schema.items() if k != "$defs"}

    if isinstance(schema, list):
        return [_dereference_refs(item, root_schema) for item in schema]

    return schema


def generate_tool_schema(
    func: Callable[..., Any], name: str | None = None, required_scopes: list[str] | None = None
) -> ToolSchema:
    """Generate MCP-compatible tool schema from a function signature."""
    sig = inspect.signature(func)

    fields: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        # Skip self/cls for methods
        if param_name in ("self", "cls"):
            continue

        annotation = param.annotation
        if annotation is inspect.Parameter.empty:
            annotation = Any

        # Extract help text from Annotated metadata (Typer Option/Argument)
        description = ""
        if get_origin(annotation) is Annotated:
            annotated_args = get_args(annotation)
            for meta in annotated_args[1:]:
                help_text = getattr(meta, "help", None)
                if help_text:
                    description = help_text
                    break

        default = ... if param.default is inspect.Parameter.empty else param.default

        fields[param_name] = (annotation, Field(default=default, description=description))

    # Create dynamic model
    model_name = f"{name or func.__name__}_input"
    DynamicModel = create_model(model_name, **fields)

    raw_schema = DynamicModel.model_json_schema()
    input_schema = _dereference_refs(raw_schema)

    meta = get_command_meta(func)
    return ToolSchema(
        name=name or func.__name__,
        description=func.__doc__ or "",
        input_schema=input_schema,
        version=meta.version,
        deprecated=meta.deprecated,
        deprecated_message=meta.deprecated_message,
        auth=required_scopes or list(meta.auth),
    )
