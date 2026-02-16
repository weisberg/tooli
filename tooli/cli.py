"""Command-line launcher for Tooli applications."""

from __future__ import annotations

import importlib
import importlib.util
import uuid
from pathlib import Path
from typing import Any

import typer

from tooli.mcp.server import serve_mcp

cli = typer.Typer(no_args_is_help=True, help="tooli launcher")


@cli.callback()
def _launcher_callback() -> None:
    """Top-level Tooli launcher entrypoint."""


def _normalize_app_spec(raw: str) -> tuple[str, str | None]:
    """Split `<source>[:app]` into source path/module and optional app object name."""
    if ":" in raw:
        source, app_name = raw.split(":", 1)
        return source.strip(), app_name.strip() or None
    return raw.strip(), None


def _load_module_from_path(path: Path) -> Any:
    module_name = f"tooli_loader_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to create import spec for {path}.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_module(source: str) -> Any:
    """Load a module from a file path or import path."""
    source_path = Path(source)
    if source_path.exists():
        if not source_path.is_file():
            raise RuntimeError(f"Not a file: {source_path}")
        return _load_module_from_path(source_path)

    try:
        return importlib.import_module(source)
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"Could not import module '{source}'.") from exc


def _resolve_app_object(module: Any, app_name: str | None) -> Any:
    from tooli.app import Tooli

    if app_name is not None:
        app = getattr(module, app_name, None)
        if app is None:
            raise RuntimeError(
                f"Module '{module.__name__}' has no '{app_name}' attribute."
            )
        return app

    app_attr = getattr(module, "app", None)
    if app_attr is not None:
        return app_attr

    app_candidates = [
        value
        for value in vars(module).values()
        if isinstance(value, Tooli)
    ]
    if len(app_candidates) == 1:
        return app_candidates[0]

    if len(app_candidates) > 1:
        raise RuntimeError(
            "Module exposes multiple Tooli app instances. "
            "Pass an explicit app name via <module>:<app>."
        )

    raise RuntimeError(
        "Module does not define a Tooli app (expected `app` or explicit `:<app>` selector)."
    )


@cli.command()
def serve(
    app_path: str = typer.Argument(
        ...,
        help="Path to a .py module or import module containing a Tooli app.",
    ),
    transport: str = typer.Option("stdio", help="MCP transport: stdio|http|sse"),
    host: str = typer.Option("localhost", help="HTTP/SSE host"),
    port: int = typer.Option(8080, help="HTTP/SSE port"),
    defer_loading: bool = typer.Option(
        False,
        help="Expose deferred MCP discovery tools only.",
    ),
) -> None:
    """Run a Tooli app file as an MCP server."""
    try:
        source, requested_app = _normalize_app_spec(app_path)
        module = _load_module(source)
        app = _resolve_app_object(module, requested_app)
        serve_mcp(
            app,
            transport=transport,
            host=host,
            port=port,
            defer_loading=defer_loading,
        )
    except RuntimeError as exc:
        import click

        click.echo(f"Failed to load app: {exc}", err=True)
        raise SystemExit(1) from exc


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
