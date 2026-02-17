"""Framework export code generation for Tooli apps."""

from __future__ import annotations

import inspect
import keyword
import types
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Union, get_args, get_origin, get_type_hints

from tooli.command_meta import get_command_meta
from tooli.input import StdinOr


class ExportTarget(str, Enum):
    """Supported export targets."""

    OPENAI = "openai"
    LANGCHAIN = "langchain"
    ADK = "adk"
    PYTHON = "python"


class ExportMode(str, Enum):
    """Wrapper generation mode."""

    SUBPROCESS = "subprocess"
    IMPORT = "import"


@dataclass(frozen=True)
class _ExportParam:
    name: str
    cli_name: str
    required: bool
    is_option: bool
    default: Any
    help_text: str
    annotation: Any


@dataclass(frozen=True)
class _ExportCommand:
    name: str
    callback: Any
    description: str
    params: list[_ExportParam]
    return_annotation: Any
    annotation_notes: list[str]


def _sanitize_identifier(name: str) -> str:
    value = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name.replace("-", "_"))
    if not value:
        value = "tool"
    if value[0].isdigit():
        value = f"tool_{value}"
    if keyword.iskeyword(value):
        value = f"{value}_cmd"
    return value


def _strip_annotated(annotation: Any) -> Any:
    value = annotation
    while get_origin(value) is Annotated:
        args = get_args(value)
        value = args[0] if args else Any
    return value


def _annotation_metadata(annotation: Any) -> tuple[Any, tuple[Any, ...]]:
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        if not args:
            return Any, ()
        return args[0], tuple(args[1:])
    return annotation, ()


def _is_optional(annotation: Any) -> tuple[bool, Any]:
    stripped = _strip_annotated(annotation)
    origin = get_origin(stripped)
    if origin not in {Union, types.UnionType}:
        return False, stripped

    args = [arg for arg in get_args(stripped) if arg is not type(None)]
    if len(args) == len(get_args(stripped)):
        return False, stripped
    if len(args) == 1:
        return True, args[0]
    return True, args[0] if args else Any


def _is_list_of_string(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin not in {list, set, tuple}:
        return False
    args = get_args(annotation)
    return bool(args and args[0] is str)


def _is_stdin_or(annotation: Any) -> bool:
    origin = get_origin(annotation)
    return annotation is StdinOr or origin is StdinOr


def _render_python_type(annotation: Any) -> str:
    annotation = _strip_annotated(annotation)
    if annotation is inspect.Signature.empty:
        return "Any"
    if annotation is Any:
        return "Any"
    if annotation is None or annotation is type(None):
        return "None"
    if annotation in {str, int, float, bool, dict, list, tuple, set}:
        return annotation.__name__

    origin = get_origin(annotation)
    if origin is None:
        if hasattr(annotation, "__name__"):
            return str(annotation.__name__)
        return str(annotation).replace("typing.", "")

    # Optional/Union.
    if origin in {Union, types.UnionType}:
        items = [_render_python_type(arg) for arg in get_args(annotation)]
        return " | ".join(items)

    args = get_args(annotation)
    if not args:
        return str(origin).replace("typing.", "")
    rendered_args = ", ".join(_render_python_type(arg) for arg in args)
    origin_name = getattr(origin, "__name__", str(origin).replace("typing.", ""))
    return f"{origin_name}[{rendered_args}]"


def _render_wrapper_type(annotation: Any, *, default: Any) -> str:
    optional, base = _is_optional(annotation)
    annotation = _strip_annotated(base)

    if _is_stdin_or(annotation):
        rendered = "str"
    elif annotation is Path:
        rendered = "str"
    elif _is_list_of_string(annotation):
        rendered = "str"
    elif annotation in {str, int, float, bool}:
        rendered = annotation.__name__
    else:
        rendered = "str"

    if optional or default is None:
        return f"{rendered} | None"
    return rendered


def _render_default(value: Any, *, preserve_path: bool = False) -> str:
    if value is inspect.Signature.empty:
        return ""
    if isinstance(value, Path):
        if preserve_path:
            return f"Path({str(value)!r})"
        return repr(str(value))
    if isinstance(value, Enum):
        return repr(value.value)
    return repr(value)


def _annotation_notes(callback: Any) -> list[str]:
    meta = get_command_meta(callback)
    ann = meta.annotations
    if ann is None:
        return []
    notes: list[str] = []
    if getattr(ann, "read_only", False):
        notes.append("read-only")
    if getattr(ann, "idempotent", False):
        notes.append("idempotent")
    if getattr(ann, "destructive", False):
        notes.append("destructive")
    if getattr(ann, "open_world", False):
        notes.append("open-world")
    return notes


def _parameter_note(annotation: Any) -> str | None:
    optional, base = _is_optional(annotation)
    del optional
    raw = _strip_annotated(base)
    if raw is Path:
        return "Path values are exported as string paths."
    if _is_list_of_string(raw):
        return "list[str] values are exported as comma-separated strings."
    if _is_stdin_or(raw):
        return "StdinOr values can be a file path, URL, or '-' for stdin."
    return None


def _help_text(annotation: Any) -> str:
    _, metadata = _annotation_metadata(annotation)
    for item in metadata:
        text = getattr(item, "help", None)
        if text:
            return str(text)
    return ""


def _is_option(annotation: Any, default: Any) -> bool:
    _, metadata = _annotation_metadata(annotation)
    for item in metadata:
        cls_name = item.__class__.__name__.lower()
        if "argument" in cls_name:
            return False
        if "option" in cls_name:
            return True
    return default is not inspect.Signature.empty


def _collect_commands(app: Any, command: str | None = None) -> list[_ExportCommand]:
    commands: list[_ExportCommand] = []
    for tool in sorted(app.get_tools(), key=lambda item: item.name):
        if tool.hidden:
            continue
        callback = tool.callback
        signature = inspect.signature(callback)
        try:
            hints = get_type_hints(callback, include_extras=True)
        except Exception:
            hints = dict(callback.__annotations__)

        params: list[_ExportParam] = []
        for param_name, param in signature.parameters.items():
            if param_name in {"self", "cls", "ctx"}:
                continue

            annotation = hints.get(param_name, param.annotation)
            default = param.default
            params.append(
                _ExportParam(
                    name=param_name,
                    cli_name=param_name.replace("_", "-"),
                    required=default is inspect.Signature.empty,
                    is_option=_is_option(annotation, default),
                    default=default,
                    help_text=_help_text(annotation),
                    annotation=annotation,
                )
            )

        return_annotation = hints.get("return", signature.return_annotation)
        commands.append(
            _ExportCommand(
                name=tool.name,
                callback=callback,
                description=(tool.help or callback.__doc__ or "").strip(),
                params=params,
                return_annotation=return_annotation,
                annotation_notes=_annotation_notes(callback),
            )
        )

    if command is None:
        return commands

    wanted = command.strip()
    for item in commands:
        if item.name == wanted:
            return [item]

    available = ", ".join(sorted(cmd.name for cmd in commands))
    raise ValueError(f"Unknown command '{wanted}'. Available commands: {available}")


def _header(app: Any, *, target: ExportTarget, mode: ExportMode) -> list[str]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    app_name = app.info.name or "tooli-app"
    return [
        f'"""Auto-generated {target.value} integration for {app_name}.',
        "Generated by tooli - https://github.com/weisberg/tooli",
        f"Generated at {now}",
        f"Export mode: {mode.value}",
        '"""',
    ]


def _signature_for_wrapper(command: _ExportCommand) -> str:
    parts: list[str] = []
    for param in command.params:
        wrapper_type = _render_wrapper_type(param.annotation, default=param.default)
        if param.required:
            parts.append(f"{param.name}: {wrapper_type}")
            continue
        parts.append(f"{param.name}: {wrapper_type} = {_render_default(param.default)}")
    return ", ".join(parts)


def _docstring_lines(command: _ExportCommand) -> list[str]:
    lines: list[str] = []
    summary = command.description or f"Wrapper for `{command.name}`."
    lines.extend(summary.splitlines())
    arg_lines: list[str] = []
    for param in command.params:
        help_text = param.help_text or "No description."
        arg_lines.append(f"{param.name}: {help_text}")
        note = _parameter_note(param.annotation)
        if note:
            arg_lines.append(f"{param.name} note: {note}")
    if arg_lines:
        lines.append("")
        lines.append("Args:")
        lines.extend(arg_lines)
    if command.annotation_notes:
        lines.append("")
        lines.append(f"Annotations: {', '.join(command.annotation_notes)}")
    return lines


def _emit_subprocess_call(lines: list[str], command: _ExportCommand, *, app_name: str, caller: str) -> None:
    lines.append(f"    cmd = [{app_name!r}, {command.name!r}]")
    for param in command.params:
        if not param.is_option:
            lines.append(f"    cmd.append(str({param.name}))")
            continue
        if _render_wrapper_type(param.annotation, default=param.default).startswith("bool"):
            lines.append(f"    if {param.name}:")
            lines.append(f"        cmd.append('--{param.cli_name}')")
            continue
        lines.append(f"    if {param.name} is not None:")
        lines.append(f"        cmd.extend(['--{param.cli_name}', str({param.name})])")
    lines.append("    cmd.append('--json')")
    lines.append("    result = subprocess.run(")
    lines.append("        cmd,")
    lines.append("        capture_output=True,")
    lines.append("        text=True,")
    lines.append("        check=False,")
    lines.append(f"        env={{**os.environ, 'TOOLI_CALLER': {caller!r}}},")
    lines.append("    )")


def _generate_openai(app: Any, commands: list[_ExportCommand], *, mode: ExportMode) -> str:
    app_name = app.info.name or "tooli-app"
    module_name = _sanitize_identifier(str(app_name))
    out = _header(app, target=ExportTarget.OPENAI, mode=mode)
    out.extend(["from __future__ import annotations", "", "import json", "import os"])
    if mode == ExportMode.SUBPROCESS:
        out.append("import subprocess")
    else:
        out.append(f"from {module_name} import app")
    out.extend(["from agents import function_tool", ""])

    for command in commands:
        fn_name = _sanitize_identifier(command.name)
        out.append("@function_tool")
        out.append(f"def {fn_name}({_signature_for_wrapper(command)}) -> str:")
        out.append('    """')
        for line in _docstring_lines(command):
            out.append(f"    {line}")
        out.append('    """')
        if mode == ExportMode.SUBPROCESS:
            _emit_subprocess_call(out, command, app_name=app_name, caller="openai-agents-sdk")
            out.append("    return result.stdout")
        else:
            out.append("    os.environ['TOOLI_CALLER'] = 'openai-agents-sdk'")
            kwargs = ", ".join(f"{param.name}={param.name}" for param in command.params)
            if kwargs:
                out.append(f"    result = app.call({command.name!r}, {kwargs})")
            else:
                out.append(f"    result = app.call({command.name!r})")
            out.append("    error_payload = None")
            out.append("    if result.error is not None:")
            out.append("        error_payload = {")
            out.append("            'code': result.error.code,")
            out.append("            'category': result.error.category,")
            out.append("            'message': result.error.message,")
            out.append("        }")
            out.append("    return json.dumps({'ok': result.ok, 'result': result.result, 'error': error_payload, 'meta': result.meta})")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _generate_langchain(app: Any, commands: list[_ExportCommand], *, mode: ExportMode) -> str:
    app_name = app.info.name or "tooli-app"
    module_name = _sanitize_identifier(str(app_name))
    out = _header(app, target=ExportTarget.LANGCHAIN, mode=mode)
    out.extend(["from __future__ import annotations", "", "import json", "import os", "from typing import Any"])
    if mode == ExportMode.SUBPROCESS:
        out.append("import subprocess")
    else:
        out.append(f"from {module_name} import app")
    out.extend(["from langchain_core.tools import tool", ""])

    for command in commands:
        fn_name = _sanitize_identifier(command.name)
        out.append("@tool")
        out.append(f"def {fn_name}({_signature_for_wrapper(command)}) -> dict[str, Any]:")
        out.append('    """')
        for line in _docstring_lines(command):
            out.append(f"    {line}")
        out.append('    """')
        if mode == ExportMode.SUBPROCESS:
            _emit_subprocess_call(out, command, app_name=app_name, caller="langchain")
            out.append("    try:")
            out.append("        payload = json.loads(result.stdout)")
            out.append("    except json.JSONDecodeError as exc:")
            out.append("        raise ValueError(f'Invalid tooli JSON output: {result.stdout or result.stderr}') from exc")
            out.append("    if not payload.get('ok', False):")
            out.append("        error = payload.get('error') or {}")
            out.append("        raise ValueError(str(error.get('message', 'Tool invocation failed')))")
            out.append("    return payload.get('result', {})")
        else:
            out.append("    os.environ['TOOLI_CALLER'] = 'langchain'")
            kwargs = ", ".join(f"{param.name}={param.name}" for param in command.params)
            if kwargs:
                out.append(f"    result = app.call({command.name!r}, {kwargs})")
            else:
                out.append(f"    result = app.call({command.name!r})")
            out.append("    if not result.ok:")
            out.append("        message = result.error.message if result.error is not None else 'Tool invocation failed'")
            out.append("        raise ValueError(message)")
            out.append("    return result.result if isinstance(result.result, dict) else {'value': result.result}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _generate_adk(app: Any, commands: list[_ExportCommand], *, mode: ExportMode) -> str:
    del commands, mode
    app_name = str(app.info.name or "tooli-app")
    description = (app.info.help or "").strip() or "agent-native CLI workflows"
    lines = [
        f"# Auto-generated Google ADK agent config for {app_name}",
        "# Generated by tooli",
        "",
        f"name: {app_name}-agent",
        "model: gemini-2.0-flash",
        "instruction: |",
        f"  You are an agent that uses the {app_name} CLI for {description}.",
        "  Always pass --json for structured output.",
        '  Check the "ok" field before accessing "result".',
        "",
        "tools:",
        "  - mcp_tool:",
        f"      server_command: {app_name} mcp serve --transport stdio",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _generate_python(app: Any, commands: list[_ExportCommand], *, mode: ExportMode) -> str:
    del mode
    app_name = str(app.info.name or "tooli-app")
    module_name = _sanitize_identifier(app_name)
    lines = _header(app, target=ExportTarget.PYTHON, mode=ExportMode.IMPORT)
    needs_path = False
    needs_any = False
    needs_stdin_or = False
    for command in commands:
        return_type = _render_python_type(command.return_annotation)
        if "Path" in return_type:
            needs_path = True
        if "Any" in return_type:
            needs_any = True
        if "StdinOr" in return_type:
            needs_stdin_or = True
        for param in command.params:
            rendered_type = _render_python_type(param.annotation)
            if "Path" in rendered_type:
                needs_path = True
            if "Any" in rendered_type:
                needs_any = True
            if "StdinOr" in rendered_type:
                needs_stdin_or = True
            if isinstance(param.default, Path):
                needs_path = True

    lines.extend(["from __future__ import annotations", ""])
    if needs_path:
        lines.append("from pathlib import Path")
    if needs_any:
        lines.append("from typing import Any")
    if needs_stdin_or:
        lines.append("from tooli import StdinOr")
    if needs_path or needs_any or needs_stdin_or:
        lines.append("")
    lines.extend([f"from {module_name} import app", ""])

    for command in commands:
        fn_name = _sanitize_identifier(command.name)
        args: list[str] = []
        for param in command.params:
            rendered_type = _render_python_type(param.annotation)
            if param.required:
                args.append(f"{param.name}: {rendered_type}")
            else:
                args.append(f"{param.name}: {rendered_type} = {_render_default(param.default, preserve_path=True)}")
        return_type = _render_python_type(command.return_annotation)
        lines.append(f"def {fn_name}({', '.join(args)}) -> {return_type}:")
        lines.append('    """')
        for line in _docstring_lines(command):
            lines.append(f"    {line}")
        lines.append('    """')
        kwargs = ", ".join(f"{param.name}={param.name}" for param in command.params)
        if kwargs:
            lines.append(f"    return app.call({command.name!r}, {kwargs}).unwrap()")
        else:
            lines.append(f"    return app.call({command.name!r}).unwrap()")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate_export(
    app: Any,
    *,
    target: ExportTarget,
    command: str | None = None,
    mode: ExportMode = ExportMode.SUBPROCESS,
) -> str:
    """Generate framework-specific wrapper code for a Tooli app."""
    commands = _collect_commands(app, command=command)
    if target is ExportTarget.OPENAI:
        return _generate_openai(app, commands, mode=mode)
    if target is ExportTarget.LANGCHAIN:
        return _generate_langchain(app, commands, mode=mode)
    if target is ExportTarget.ADK:
        return _generate_adk(app, commands, mode=mode)
    if target is ExportTarget.PYTHON:
        return _generate_python(app, commands, mode=mode)
    raise ValueError(f"Unsupported export target: {target}")
