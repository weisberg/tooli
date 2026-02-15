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
        from fastmcp import FastMCP  # type: ignore[import-not-found]
    except ImportError:
        import click
        click.echo("Error: fastmcp is not installed. Install it with 'pip install fastmcp'.", err=True)
        sys.exit(1)

    mcp = FastMCP(name=app.info.name or "tooli-app")

    # Register each Tooli command as an MCP tool
    for tool_def in app.get_tools():
        if tool_def.hidden:
            continue

        cmd_id = tool_def.name
        callback = tool_def.callback

        # Create a wrapper for FastMCP
        def _make_wrapper(cb: Any) -> Any:
            async def wrapper(**kwargs: Any) -> Any:
                # Execute the callback directly
                # FastMCP handles JSON serialization of the return value
                return cb(**kwargs)
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
