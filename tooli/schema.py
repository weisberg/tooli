"""Schema generation pipeline for Tooli commands."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping  # noqa: TC003
from typing import Annotated, Any, get_args, get_origin, get_type_hints

from pydantic import BaseModel, Field, TypeAdapter, create_model

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
    capabilities: list[str] = Field(default_factory=list)
    handoffs: list[dict[str, str]] = Field(default_factory=list)
    delegation_hint: str | None = None


def _dereference_refs(schema: dict[str, Any], root_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """Recursively inline `$ref` entries."""
    if root_schema is None:
        root_schema = schema

    if isinstance(schema, dict):
        if "$ref" in schema:
            ref_path = schema["$ref"]
            if ref_path.startswith("#/$defs/"):
                def_name = ref_path.split("/")[-1]
                ref_content = root_schema.get("$defs", {}).get(def_name, {})
                # Recursively dereference the content.
                return _dereference_refs(ref_content, root_schema)

        return {k: _dereference_refs(v, root_schema) for k, v in schema.items() if k != "$defs"}

    if isinstance(schema, list):
        return [_dereference_refs(item, root_schema) for item in schema]

    return schema


def _infer_schema_from_example(value: Any) -> dict[str, Any]:
    """Infer a JSON schema from a concrete sample value."""
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, list):
        if value:
            item_schema = _infer_schema_from_example(value[0])
        else:
            item_schema = {"type": "string"}
        return {"type": "array", "items": item_schema}
    if isinstance(value, Mapping):
        properties: dict[str, Any] = {}
        required: list[str] = []
        for key, raw in value.items():
            property_name = str(key)
            properties[property_name] = _infer_schema_from_example(raw)
            required.append(property_name)
        payload: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            payload["required"] = required
        return payload
    if isinstance(value, tuple):
        return {"type": "array", "items": _infer_schema_from_example(list(value))}
    return {"type": "string"}


def _infer_output_schema(annotation: Any, output_example: Any) -> dict[str, Any] | None:
    """Build output schema from return annotation or fallback example.

    Return annotations are preferred for tool-driven integrations. `output_example`
    can override inference for primitive and dynamic payloads.
    """
    if output_example is not None:
        return _infer_schema_from_example(output_example)
    if annotation is inspect.Signature.empty or annotation is Any:
        return None

    try:
        adapter = TypeAdapter(annotation)
        return _dereference_refs(adapter.json_schema())
    except Exception:
        try:
            model = create_model(
                "tooli_output_schema_model",
                value=(annotation, ...),
            )
            payload = model.model_json_schema()
            return _dereference_refs(payload.get("properties", {}).get("value", {}))
        except Exception:
            return None


def generate_tool_schema(
    func: Callable[..., Any], name: str | None = None, required_scopes: list[str] | None = None
) -> ToolSchema:
    """Generate MCP-compatible tool schema from a function signature."""
    sig = inspect.signature(func)
    try:
        resolved_annotations = get_type_hints(func, include_extras=True)
    except Exception:
        resolved_annotations = {}

    fields: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        # Skip self/cls for methods
        if param_name in {"self", "cls"}:
            continue

        annotation = resolved_annotations.get(param_name, param.annotation)
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
    dynamic_model = create_model(model_name, **fields)

    raw_schema = dynamic_model.model_json_schema()
    input_schema = _dereference_refs(raw_schema)

    meta = get_command_meta(func)
    return_annotation = resolved_annotations.get("return", sig.return_annotation)
    output_schema = _infer_output_schema(return_annotation, meta.output_example)
    return ToolSchema(
        name=name or func.__name__,
        description=func.__doc__ or "",
        input_schema=input_schema,
        output_schema=output_schema,
        version=meta.version,
        deprecated=meta.deprecated,
        deprecated_message=meta.deprecated_message,
        auth=required_scopes or list(meta.auth),
        capabilities=list(meta.capabilities),
        handoffs=list(meta.handoffs),
        delegation_hint=meta.delegation_hint,
    )
