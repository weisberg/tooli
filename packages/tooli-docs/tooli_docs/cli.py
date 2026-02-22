"""CLI entrypoint for standalone Tooli documentation generation."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import uuid
from pathlib import Path
from typing import Any


def _normalize_app_spec(raw: str) -> tuple[str, str | None]:
    if ":" in raw:
        source, app_name = raw.split(":", 1)
        return source.strip(), app_name.strip() or None
    return raw.strip(), None


def _load_module_from_path(path: Path) -> Any:
    module_name = f"tooli_docs_loader_{uuid.uuid4().hex}"
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


def _load_schema(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Failed to read schema file '{path}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Schema file '{path}' is not valid JSON: {exc}") from exc


def _schema_tools(schema: Any) -> list[dict[str, Any]]:
    if isinstance(schema, list):
        return [item for item in schema if isinstance(item, dict)]
    if not isinstance(schema, dict):
        return []
    if isinstance(schema.get("tools"), list):
        return [item for item in schema["tools"] if isinstance(item, dict)]
    if "name" in schema and ("input_schema" in schema or "inputSchema" in schema):
        return [schema]
    return []


def _render_skill_from_schema(schema: Any) -> str:
    tools = _schema_tools(schema)
    lines = ["# SKILL.md", "", "## Available Commands", ""]
    for tool in tools:
        name = str(tool.get("name", "unknown"))
        description = str(tool.get("description", "")).strip() or "No description."
        lines.extend([f"### {name}", "", description, ""])
        input_schema = tool.get("input_schema") or tool.get("inputSchema") or {}
        props = input_schema.get("properties", {}) if isinstance(input_schema, dict) else {}
        required = set(input_schema.get("required", [])) if isinstance(input_schema, dict) else set()
        if isinstance(props, dict) and props:
            lines.append("Parameters:")
            for key, value in props.items():
                if not isinstance(value, dict):
                    continue
                p_type = value.get("type", "any")
                p_desc = value.get("description", "")
                req = "required" if key in required else "optional"
                lines.append(f"- `{key}` ({p_type}, {req}) {p_desc}".rstrip())
            lines.append("")
    if not tools:
        lines.extend(["No commands found in schema.", ""])
    return "\n".join(lines).rstrip() + "\n"


def _render_agents_from_schema(schema: Any) -> str:
    tools = _schema_tools(schema)
    lines = ["# AGENTS.md", "", "## Available Commands", ""]
    for tool in tools:
        name = str(tool.get("name", "unknown"))
        description = str(tool.get("description", "")).strip() or "No description."
        lines.extend([f"### {name}", "", description, ""])
    if not tools:
        lines.extend(["No commands found in schema.", ""])
    return "\n".join(lines).rstrip() + "\n"


def _render_claude_from_schema(schema: Any) -> str:
    tools = _schema_tools(schema)
    lines = ["# CLAUDE.md", "", "## Command Summary", ""]
    for tool in tools:
        name = str(tool.get("name", "unknown"))
        description = str(tool.get("description", "")).strip() or "No description."
        lines.append(f"- `{name}`: {description}")
    if not tools:
        lines.append("No commands found in schema.")
    lines.append("")
    return "\n".join(lines)


def _generate_for_app(kind: str, app: Any) -> str:
    if kind == "skill":
        from tooli.docs.skill_v4 import generate_skill_md

        return generate_skill_md(app)
    if kind == "claude-md":
        from tooli.docs.claude_md_v2 import generate_claude_md_v2

        return generate_claude_md_v2(app)
    if kind == "agents-md":
        from tooli.docs.agents_md import generate_agents_md

        return generate_agents_md(app)
    raise RuntimeError(f"Unsupported docs kind: {kind}")


def _generate_from_schema(kind: str, schema: Any) -> str:
    if kind == "skill":
        return _render_skill_from_schema(schema)
    if kind == "claude-md":
        return _render_claude_from_schema(schema)
    if kind == "agents-md":
        return _render_agents_from_schema(schema)
    raise RuntimeError(f"Unsupported docs kind: {kind}")


def _write_output(content: str, output_path: str) -> None:
    if output_path == "-":
        print(content, end="")
        return
    Path(output_path).write_text(content, encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tooli-docs")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for cmd in ("skill", "claude-md", "agents-md"):
        sub = subparsers.add_parser(cmd)
        sub.add_argument("app", nargs="?", help="App module spec: module[:app] or path/to/app.py[:app]")
        sub.add_argument("--from-schema", dest="from_schema", help="Generate docs from a JSON schema file.")
        sub.add_argument("--output", default="-", help="Output path, or '-' for stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.from_schema:
            schema = _load_schema(args.from_schema)
            content = _generate_from_schema(args.command, schema)
        else:
            if not args.app:
                raise RuntimeError("Provide <app> or --from-schema.")
            source, app_name = _normalize_app_spec(args.app)
            module = _load_module(source)
            app = _resolve_app_object(module, app_name)
            content = _generate_for_app(args.command, app)
        _write_output(content, args.output)
        return 0
    except RuntimeError as exc:
        print(f"tooli-docs: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
