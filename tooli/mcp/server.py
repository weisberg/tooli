"""MCP server implementation for Tooli."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tooli.app import Tooli


def serve_mcp(
    app: Tooli,
    transport: str = "stdio",
    host: str = "localhost",
    port: int = 8080,
) -> None:
    """Run the Tooli app as an MCP server."""
    if transport not in {"stdio", "http", "sse"}:
        raise ValueError(f"Unsupported MCP transport: {transport}")

    try:
        from fastmcp import FastMCP
    except ImportError:
        print("Error: fastmcp is not installed. Install it with 'pip install fastmcp'.")
        sys.exit(1)

    mcp = FastMCP(name=app.info.name or "tooli-app")

    # Register each Tooli command as an MCP tool
    for cmd in app.registered_commands:
        if cmd.hidden:
            continue

        cmd_id = cmd.name or cmd.callback.__name__
        
        # behavioral hints
        from tooli.annotations import ToolAnnotation
        annotations = getattr(cmd.callback, "__tooli_annotations__", None)
        is_read_only = False
        if isinstance(annotations, ToolAnnotation):
            is_read_only = annotations.read_only

        # Create a wrapper for FastMCP
        def _make_wrapper(callback: Any) -> Any:
            async def wrapper(**kwargs: Any) -> Any:
                # Execute the callback directly
                # FastMCP handles JSON serialization of the return value
                return callback(**kwargs)
            return wrapper

        mcp.tool(name=cmd_id, description=cmd.help or cmd.callback.__doc__ or "")(_make_wrapper(cmd.callback))

    # Strict stdout discipline for stdio transport
    if transport == "stdio":
        # Redirect logging to stderr
        logging.basicConfig(level=logging.INFO, stream=sys.stderr)
        mcp.run(transport="stdio")
    else:
        # HTTP / SSE transport (Phase 2, Issue #18)
        # FastMCP 2.x supports http/sse
        mcp.run(transport=transport, host=host, port=port)
