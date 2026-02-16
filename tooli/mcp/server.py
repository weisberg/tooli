"""MCP server implementation for Tooli."""

from __future__ import annotations

import inspect
import logging
import sys
from typing import TYPE_CHECKING, Any

from tooli.schema import generate_tool_schema  # type: ignore[import-not-found]

if TYPE_CHECKING:
    from tooli.app import Tooli
    from tooli.transforms import ToolDef


def _build_tool_map(app: Tooli) -> dict[str, ToolDef]:
    """Build a stable map of visible tool names to definitions."""
    return {tool.name: tool for tool in app.get_tools() if not tool.hidden}


def _annotation_hints_from_callback(callback: Any) -> dict[str, Any]:
    from tooli.command_meta import get_command_meta

    annotations: dict[str, Any] = {}
    try:
        meta = get_command_meta(callback)
    except Exception:
        return annotations

    tool_ann = meta.annotations
    if tool_ann is None:
        return annotations

    if getattr(tool_ann, "read_only", False):
        annotations["readOnlyHint"] = True
    if getattr(tool_ann, "idempotent", False):
        annotations["idempotentHint"] = True
    if getattr(tool_ann, "destructive", False):
        annotations["destructiveHint"] = True
    if getattr(tool_ann, "open_world", False):
        annotations["openWorldHint"] = True

    return annotations


def _run_callable(callback: Any, arguments: dict[str, Any]) -> Any:
    sig = inspect.signature(callback)
    kwargs: dict[str, Any] = {}
    accepts_var_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in sig.parameters.values()
    )

    for name, param in sig.parameters.items():
        if name in ("ctx", "self", "cls"):
            kwargs[name] = None
            continue

        if name in arguments:
            kwargs[name] = arguments[name]
            continue

        if (
            param.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
            and param.default is inspect.Parameter.empty
        ):
            raise ValueError(f"Missing required tool argument: {name}")

    for key in arguments:
        if key not in sig.parameters and not accepts_var_kwargs:
            raise ValueError(f"Unknown argument for tool call: {key}")

    if inspect.iscoroutinefunction(callback):
        import asyncio

        return asyncio.run(callback(**kwargs))

    return callback(**kwargs)


def _search_tools(app: Tooli, query: str = "", limit: int = 10) -> list[dict[str, Any]]:
    if limit < 1:
        raise ValueError("limit must be at least 1")

    tools = _build_tool_map(app)
    normalized = query.strip().lower()
    matches: list[tuple[float, dict[str, Any]]] = []

    for tool_def in tools.values():
        tool_name = tool_def.name
        description = tool_def.help or ""
        if (
            normalized
            and normalized not in tool_name.lower()
            and normalized not in description.lower()
        ):
            continue

        schema = generate_tool_schema(tool_def.callback, name=tool_name)
        match_score = 0.0
        if tool_name.lower() == normalized:
            match_score = 10.0
        elif tool_name.lower().startswith(normalized):
            match_score = 5.0
        elif normalized and normalized in tool_name.lower():
            match_score = 3.0
        else:
            match_score = 1.0 if normalized else 0.0

        matches.append(
            (
                match_score,
                {
                    "name": tool_def.name,
                    "description": description,
                    "version": schema.version,
                    "inputSchema": schema.input_schema,
                    "annotations": _annotation_hints_from_callback(tool_def.callback),
                },
            )
        )

    if normalized:
        matches.sort(key=lambda item: item[0], reverse=True)

    return [entry for _, entry in matches[:limit]]


def _build_run_tool(app: Tooli) -> Any:
    tool_map = _build_tool_map(app)

    def run_tool(name: str, arguments: dict[str, Any] | None = None) -> Any:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name is required")

        tool = tool_map.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")

        if arguments is None:
            return _run_callable(tool.callback, {})

        if not isinstance(arguments, dict):
            raise ValueError("arguments must be an object")

        return _run_callable(tool.callback, arguments)

    return run_tool


def serve_mcp(
    app: Tooli,
    transport: str = "stdio",
    host: str = "localhost",
    port: int = 8080,
    defer_loading: bool = False,
) -> None:
    """Run the Tooli app as an MCP server."""
    if transport not in {"stdio", "http", "sse"}:
        raise ValueError(f"Unsupported MCP transport: {transport}")

    try:
        from fastmcp import FastMCP  # type: ignore[import-not-found]
    except ImportError:
        import click
        click.echo("Error: fastmcp is not installed. Install it with 'pip install fastmcp'.", err=True)
        sys.exit(1)

    mcp = FastMCP(name=app.info.name or "tooli-app")

    if defer_loading:
        mcp.tool(
            name="search_tools",
            description="Find matching commands and return their schemas.",
        )(_search_tools)
        mcp.tool(
            name="run_tool",
            description="Execute a registered Tooli command by name.",
        )(_build_run_tool(app))
    else:
        # Register each Tooli command as an MCP tool
        for tool_def in app.get_tools():
            if tool_def.hidden:
                continue

            cmd_id = tool_def.name
            callback = tool_def.callback

            # Create a wrapper for FastMCP
            def _make_wrapper(cb: Any) -> Any:
                async def wrapper(**kwargs: Any) -> Any:
                    result = _run_callable(cb, kwargs)
                    return result

                return wrapper

            description = tool_def.help or tool_def.callback.__doc__ or ""
            mcp.tool(name=cmd_id, description=description)(_make_wrapper(callback))

    # Strict stdout discipline for stdio transport
    if transport == "stdio":
        # Redirect logging to stderr
        logging.basicConfig(level=logging.INFO, stream=sys.stderr)
        mcp.run(transport="stdio")
    else:
        # HTTP / SSE transport (Phase 2, Issue #18)
        # FastMCP 2.x supports http/sse
        mcp.run(transport=transport, host=host, port=port)  # type: ignore[arg-type]
