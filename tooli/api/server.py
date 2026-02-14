"""HTTP API server for Tooli apps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tooli.app import Tooli


def build_app(app: Tooli) -> Any:
    """Build a Starlette application for the Tooli app."""
    try:
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
    except ImportError as exc:
        raise ImportError("Starlette is required for HTTP serving. Install it with 'pip install starlette'.") from exc

    from tooli.api.openapi import generate_openapi_schema

    async def openapi_endpoint(request: Any) -> JSONResponse:
        return JSONResponse(generate_openapi_schema(app))

    routes = [
        Route("/openapi.json", openapi_endpoint, methods=["GET"]),
    ]

    # Create an endpoint for each command
    for tool in app.get_tools():
        if tool.hidden:
            continue

        cmd_id = tool.name or tool.callback.__name__

        async def make_handler(command: Any) -> Any:
            async def handler(request: Any) -> JSONResponse:
                try:
                    body = await request.json()
                except Exception:
                    body = {}

                # We need to invoke the command.
                # For simplicity in this implementation, we call the callback directly.
                # In a real implementation, we'd want to handle Click context etc.
                try:
                    # Capture duration
                    import time
                    start = time.perf_counter()

                    # Tooli commands usually return a value.
                    # If it's async, we await it.
                    import inspect
                    if inspect.iscoroutinefunction(command.callback):
                        result = await command.callback(**body)
                    else:
                        result = command.callback(**body)

                    duration_ms = int((time.perf_counter() - start) * 1000)

                    # Wrap in envelope
                    from tooli.envelope import Envelope, EnvelopeMeta
                    meta = EnvelopeMeta(
                        tool=command.name or command.callback.__name__,
                        version=app.version or "0.0.0",
                        duration_ms=duration_ms,
                    )
                    env = Envelope(ok=True, result=result, meta=meta)
                    return JSONResponse(env.model_dump())
                except Exception as e:
                    # Handle errors
                    from tooli.errors import InternalError, ToolError
                    if not isinstance(e, ToolError):
                        e = InternalError(message=str(e))

                    from tooli.envelope import Envelope, EnvelopeMeta
                    meta = EnvelopeMeta(
                        tool=command.name or command.callback.__name__,
                        version=app.version or "0.0.0",
                        duration_ms=0,
                    )
                    env = Envelope(ok=False, result=None, meta=meta)
                    out = env.model_dump()
                    out["error"] = e.to_dict()
                    return JSONResponse(out, status_code=getattr(e, "exit_code", 500))

            return handler

        routes.append(Route(f"/{cmd_id}", make_handler(tool), methods=["POST"]))

    return Starlette(debug=True, routes=routes)


def serve_api(app: Tooli, host: str = "localhost", port: int = 8000) -> None:
    """Run the Tooli app as an HTTP API server."""
    try:
        import uvicorn
    except ImportError:
        import sys

        import click
        click.echo("Error: uvicorn is not installed. Install it with 'pip install uvicorn'.", err=True)
        sys.exit(1)

    starlette_app = build_app(app)
    uvicorn.run(starlette_app, host=host, port=port)
