"""CLI entrypoint for standalone Tooli framework export generation."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import uuid
from pathlib import Path
from typing import Any

from tooli.export import ExportMode, ExportTarget, generate_export


def _normalize_app_spec(raw: str) -> tuple[str, str | None]:
    if ":" in raw:
        source, app_name = raw.split(":", 1)
        return source.strip(), app_name.strip() or None
    return raw.strip(), None


def _load_module_from_path(path: Path) -> Any:
    module_name = f"tooli_export_loader_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to create import spec for {path}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_module(source: str) -> Any:
    source_path = Path(source)
    if source_path.exists():
        if not source_path.is_file():
            raise RuntimeError(f"Not a file: {source_path}")
        return _load_module_from_path(source_path)
    try:
        return importlib.import_module(source)
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"Could not import module '{source}'.") from exc


def _looks_like_tooli_app(value: Any) -> bool:
    return callable(getattr(value, "get_tools", None)) and hasattr(value, "info")


def _resolve_app_object(module: Any, app_name: str | None) -> Any:
    if app_name is not None:
        app = getattr(module, app_name, None)
        if app is None:
            raise RuntimeError(f"Module '{module.__name__}' has no '{app_name}' attribute.")
        if not _looks_like_tooli_app(app):
            raise RuntimeError(f"Attribute '{app_name}' is not a Tooli app instance.")
        return app

    app_attr = getattr(module, "app", None)
    if app_attr is not None and _looks_like_tooli_app(app_attr):
        return app_attr

    app_candidates = [value for value in vars(module).values() if _looks_like_tooli_app(value)]
    if len(app_candidates) == 1:
        return app_candidates[0]
    if len(app_candidates) > 1:
        raise RuntimeError("Module exposes multiple Tooli apps. Use <module>:<app>.")
    raise RuntimeError("Module does not expose a Tooli app.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tooli-export")
    subparsers = parser.add_subparsers(dest="target", required=True)
    for target in ("openai", "langchain", "adk", "python"):
        sub = subparsers.add_parser(target)
        sub.add_argument("app", help="App module spec: module[:app] or path/to/app.py[:app]")
        sub.add_argument("--command", default=None, help="Export only one command by name.")
        sub.add_argument("--mode", default="subprocess", choices=["subprocess", "import"])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        source, app_name = _normalize_app_spec(args.app)
        module = _load_module(source)
        app = _resolve_app_object(module, app_name)
        payload = generate_export(
            app,
            target=ExportTarget(args.target),
            command=args.command,
            mode=ExportMode(args.mode),
        )
        print(payload, end="")
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"tooli-export: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
