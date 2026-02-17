"""Native fallback implementation of the Tooli interface."""

from __future__ import annotations

import argparse
import inspect
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Annotated, get_args, get_origin, get_type_hints

from tooli.backends.native import Argument as NativeArgument, Option as NativeOption
from tooli.command_meta import CommandMeta
from tooli.envelope import Envelope, EnvelopeMeta
from tooli.errors import InternalError, InputError, ToolError
from tooli.transforms import ToolDef
from tooli.versioning import compare_versions


def _coerce_bool(raw: str) -> bool:
    lowered = raw.lower()
    if lowered in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise InputError(f"Invalid boolean value: {raw}")


def _strip_annotated(annotation: Any) -> tuple[Any, tuple[Any, ...]]:
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        return args[0], args[1:]
    return annotation, ()


def _coerce_value(raw: str, annotation: Any) -> Any:
    base_annotation, _metadata = _strip_annotated(annotation)
    if base_annotation is inspect.Signature.empty:
        return raw
    if base_annotation is bool:
        return _coerce_bool(str(raw))
    if base_annotation is int:
        return int(raw)
    if base_annotation is float:
        return float(raw)
    return raw


def _normalise_alias(name: str) -> str:
    return name.replace("_", "-")


def _native_marker_from_annotation(annotation: Any) -> NativeArgument | NativeOption | None:
    _, metadata = _strip_annotated(annotation)
    for extra in metadata:
        if isinstance(extra, (NativeArgument, NativeOption)):
            return extra
    return None


def _help_text(annotation: Any) -> str:
    _, metadata = _strip_annotated(annotation)
    for extra in metadata:
        help_text = getattr(extra, "help", None)
        if help_text:
            return str(help_text)
    return ""


def _yaml_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    try:
        return json.dumps(value)
    except Exception:
        return json.dumps(str(value))


def _format_help_param_type(annotation: Any) -> str:
    base_annotation, _metadata = _strip_annotated(annotation)
    if base_annotation is inspect.Signature.empty:
        return "any"
    if base_annotation is str:
        return "str"
    if base_annotation is int:
        return "int"
    if base_annotation is float:
        return "float"
    if base_annotation is bool:
        return "bool"
    if base_annotation is None:
        return "none"
    if hasattr(base_annotation, "__name__"):
        return str(base_annotation.__name__)
    return str(base_annotation)


@dataclass(slots=True)
class _NativeTooliConfig:
    name: str
    callback: Callable[..., Any]
    help_text: str
    hidden: bool = False


class Tooli:
    """Minimal Tooli-compatible implementation used when Typer is unavailable."""

    def __init__(
        self,
        *args: Any,  # noqa: ARG002
        backend: str = "native",
        description: str | None = None,
        version: str = "0.0.0",
        name: str = "tooli",
        help: str | None = None,
        callbacks: list[Callable[..., Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        del args
        if backend == "typer":
            raise RuntimeError("Typer backend requested but Typer is unavailable.")

        if callbacks is not None:
            raise TypeError("callbacks is not supported in the native backend fallback.")

        default_output = kwargs.pop("default_output", "auto")
        self.default_output = default_output
        if kwargs:
            # Keep call sites compatible with Typer style signatures by allowing a
            # small subset of common arguments and rejecting unsupported options.
            unsupported = ", ".join(sorted(kwargs))
            raise RuntimeError(f"Unsupported options for native backend: {unsupported}")

        self.version = version
        self.backend = backend
        self.name = name
        if help is None:
            help = description if description is not None else "An agent-native CLI application."
        self.help = help
        self.info = SimpleNamespace(name=name, help=self.help)

        self._commands: list[_NativeTooliConfig] = []
        self._versioned_commands_latest: dict[str, str] = {}
        self._transforms: list[Any] = []
        self._resources: list[tuple[Callable[..., Any], Any]] = []
        self._prompts: list[tuple[Callable[..., Any], Any]] = []

    def command(
        self,
        name: str | None = None,
        *,
        annotations: Any | None = None,
        list_processing: bool = False,
        paginated: bool = False,
        examples: list[dict[str, Any]] | None = None,
        error_codes: dict[str, str] | None = None,
        timeout: float | None = None,
        cost_hint: str | None = None,
        human_in_the_loop: bool = False,
        auth: list[str] | None = None,
        max_tokens: int | None = None,
        supports_dry_run: bool = False,
        requires_approval: bool = False,
        danger_level: str | None = None,
        allow_python_eval: bool = False,
        output_example: Any | None = None,
        version: str | None = None,
        deprecated: bool = False,
        deprecated_message: str | None = None,
        pipe_input: dict[str, Any] | None = None,
        pipe_output: dict[str, Any] | None = None,
        when_to_use: str | None = None,
        expected_outputs: list[dict[str, Any]] | None = None,
        recovery_playbooks: dict[str, list[str]] | None = None,
        task_group: str | None = None,
        **kwargs: Any,
    ) -> Any:
        _ = list_processing
        _ = paginated
        _ = examples
        _ = error_codes
        _ = timeout
        _ = cost_hint
        _ = human_in_the_loop
        _ = auth
        _ = max_tokens
        _ = supports_dry_run
        _ = requires_approval
        _ = danger_level
        _ = allow_python_eval
        _ = output_example
        _ = deprecated
        _ = deprecated_message
        _ = pipe_input
        _ = pipe_output
        _ = when_to_use
        _ = expected_outputs
        _ = recovery_playbooks
        _ = task_group
        version_kwargs = kwargs

        def _configure_callback(func: Any) -> None:
            try:
                annotations_by_param = dict(get_type_hints(func, include_extras=True))
            except Exception:
                annotations_by_param = dict(func.__annotations__)

            func.__annotations__ = annotations_by_param
            meta = CommandMeta(
                app=self,
                app_name=self.info.name,
                app_version=self.version,
                default_output=self.default_output,
                annotations=annotations,
                list_processing=False,
                paginated=False,
                version=None if version is None else str(version),
                output_example=output_example,
                cost_hint=cost_hint,
                human_in_the_loop=human_in_the_loop,
                timeout=timeout,
                auth=auth or [],
                max_tokens=max_tokens,
                supports_dry_run=supports_dry_run,
                requires_approval=requires_approval,
                danger_level=danger_level,
                allow_python_eval=allow_python_eval,
                deprecated=deprecated,
                deprecated_message=deprecated_message,
                error_codes=error_codes or {},
                pipe_input=pipe_input,
                pipe_output=pipe_output,
                when_to_use=when_to_use,
                expected_outputs=expected_outputs or [],
                recovery_playbooks=recovery_playbooks or {},
                task_group=task_group,
            )
            func.__tooli_meta__ = meta

        if version is None:
            def _wrap(callback: Any) -> Any:
                _configure_callback(callback)
                self._add_command(name or callback.__name__.replace("_", "-"), callback, hidden=False)
                return callback
            return _wrap

        def _wrap(callback: Any) -> Any:  # type: ignore[no-redef]
            _configure_callback(callback)

            base_name = name or callback.__name__.replace("_", "-")
            is_hidden = bool(version_kwargs.get("hidden", False))
            version_value = version
            if version_value is None:
                version_value = "0.0.0"
            version_suffix = version_value
            if not str(version_suffix).startswith("v"):
                versioned_alias = f"{base_name}-v{version_suffix}"
            else:
                versioned_alias = f"{base_name}-{version_suffix}"

            self._add_command(base_name, callback, hidden=is_hidden)
            self._add_command(versioned_alias, callback, hidden=True)

            latest_version = self._versioned_commands_latest.get(base_name)
            if latest_version is None or compare_versions(str(version_value), latest_version) >= 0:
                self._versioned_commands_latest[base_name] = str(version_value)
                # Keep the latest alias visible and hide older ones.
                for entry in self._commands:
                    if entry.name == base_name and entry.callback is not callback:
                        entry.hidden = True
                return callback

            # Older command version was declared first; keep latest as primary.
            for entry in self._commands:
                if entry.name == base_name and entry.callback is callback:
                    entry.hidden = True
            return callback

        return _wrap

    def _add_command(self, name: str, callback: Callable[..., Any], *, hidden: bool = False) -> None:
        self._commands.append(
            _NativeTooliConfig(name=name, callback=callback, help_text=(callback.__doc__ or ""), hidden=hidden)
        )

    def add_typer(self, *_args: Any, **_kwargs: Any) -> None:
        # Nested command groups are unsupported in fallback mode.
        return None

    def register_callback(self, _callback: Any) -> Any:
        # Kept for Typer compatibility; command decorator already registers itself.
        return _callback

    def resource(self, *_args: Any, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def _wrap(callback: Callable[..., Any]) -> Callable[..., Any]:
            self._resources.append((callback, None))
            return callback
        return _wrap

    def prompt(self, *_args: Any, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def _wrap(callback: Callable[..., Any]) -> Callable[..., Any]:
            self._prompts.append((callback, None))
            return callback
        return _wrap

    def with_transforms(self, *transforms: Any) -> "Tooli":
        clone = self.__class__(
            backend="native",
            version=self.version,
            name=self.name,
            help=self.help,
        )
        clone._commands = list(self._commands)
        clone._versioned_commands_latest = dict(self._versioned_commands_latest)
        clone._resources = list(self._resources)
        clone._prompts = list(self._prompts)
        clone._transforms = list(transforms)
        return clone

    def get_tools(self) -> list[ToolDef]:
        commands = list(self._commands)
        for transform in self._transforms:
            commands = transform.apply(commands)
        return [ToolDef(name=entry.name, callback=entry.callback, help=entry.help_text, hidden=entry.hidden) for entry in commands]

    def get_resources(self) -> list[tuple[Callable[..., Any], Any]]:
        return list(self._resources)

    def get_prompts(self) -> list[tuple[Callable[..., Any], Any]]:
        return list(self._prompts)

    @property
    def registered_commands(self) -> list[_NativeTooliConfig]:
        return list(self._commands)

    def list_commands(self, _ctx: Any | None = None) -> list[str]:
        return sorted(command.name for command in self._commands if not command.hidden)

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog=self.info.name, add_help=True)
        parser.add_argument("--version", action="version", version=self.version)
        parser.add_argument("--help-agent", action="store_true", help="Emit YAML help metadata.")
        subparsers = parser.add_subparsers(dest="command", required=False)

        for command in self._commands:
            if command.hidden:
                continue
            cb = command.callback
            spec = inspect.signature(cb)
            sp = subparsers.add_parser(command.name, help=command.help_text)
            for parameter in spec.parameters.values():
                if parameter.name in {"ctx", "context"}:
                    continue
                if parameter.kind in {inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL}:
                    continue

                annotation = cb.__annotations__.get(parameter.name, parameter.annotation)
                marker = _native_marker_from_annotation(annotation)

                if isinstance(marker, NativeOption):
                    option_names = [str(value) for value in marker.args if str(value).startswith("-")]
                    if not option_names:
                        option_names = [f"--{_normalise_alias(parameter.name)}"]
                    opt_kwargs = dict(marker.kwargs)
                    default = parameter.default
                    if parameter.default is inspect.Signature.empty:
                        default = None

                    if opt_kwargs.get("help"):
                        help_text = str(opt_kwargs["help"])
                    else:
                        help_text = _help_text(annotation)

                    raw_type = cb.__annotations__.get(parameter.name, parameter.annotation)
                    base_type, _meta = _strip_annotated(raw_type)
                    is_flag = bool(opt_kwargs.get("is_flag", False))
                    if base_type is bool:
                        action = "store_false" if default is True else "store_true"
                        sp.add_argument(
                            *option_names,
                            action=action,
                            help=help_text,
                            default=bool(default),
                        )
                    elif is_flag:
                        sp.add_argument(*option_names, action="store_true", help=help_text, default=False)
                    else:
                        sp.add_argument(
                            *option_names,
                            default=default,
                            type=base_type if base_type not in (bool, inspect.Signature.empty, Any) else None,
                            help=help_text,
                        )
                    continue

                if isinstance(marker, NativeArgument):
                    # NativeArgument currently uses positional semantics; ignore all metadata.
                    if parameter.default is inspect.Signature.empty:
                        sp.add_argument(parameter.name, help=_help_text(annotation))
                    else:
                        sp.add_argument(parameter.name, nargs="?", default=parameter.default, help=_help_text(annotation))
                else:
                    if parameter.default is inspect.Signature.empty:
                        sp.add_argument(parameter.name, help=_help_text(annotation))
                    else:
                        option_name = f"--{_normalise_alias(parameter.name)}"
                        raw_type = cb.__annotations__.get(parameter.name, parameter.annotation)
                        base, _meta = _strip_annotated(raw_type)
                        is_flag = base is bool
                        if is_flag:
                            sp.add_argument(option_name, action="store_true", default=bool(parameter.default))
                        else:
                            sp.add_argument(option_name, default=parameter.default, type=base if base is not bool else None)

            # command-local json/schema flags
            sp.add_argument("--json", action="store_true", help="Emit machine JSON output.")
            sp.add_argument("--schema", action="store_true", help="Print command schema and exit.")
            sp.add_argument("--dry-run", action="store_true", help="Preview without mutation.")
            sp.add_argument("--help-agent", action="store_true", help="Emit YAML help metadata.")
            # parse callback name for routing.
            sp.set_defaults(_tooli_command=command)

        return parser

    def _emit_schema(self, callback: Callable[..., Any]) -> None:
        from tooli.schema import generate_tool_schema

        schema = generate_tool_schema(callback, name=callback.__name__)
        print(json.dumps(schema.model_dump(), indent=2))

    def _emit_help_agent(self, callback: Callable[..., Any]) -> None:
        from tooli.command_meta import get_command_meta
        from tooli.schema import generate_tool_schema

        signature = inspect.signature(callback)
        lines = [
            f"command: {callback.__name__}",
            f"description: {(callback.__doc__ or '').strip()}",
        ]

        lines.append("params:")
        for parameter in signature.parameters.values():
            if parameter.name in {"ctx", "context"}:
                continue
            if parameter.kind in {inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL}:
                continue

            annotation = callback.__annotations__.get(parameter.name, parameter.annotation)
            marker = _native_marker_from_annotation(annotation)

            base_annotation, _ = _strip_annotated(annotation)
            param_type = _format_help_param_type(base_annotation)

            if isinstance(marker, NativeOption):
                option_names = [str(value) for value in marker.args if str(value).startswith("-")]
                if not option_names:
                    option_names = [f"--{_normalise_alias(parameter.name)}"]
                name = ", ".join(sorted(set(option_names)))
                is_required = parameter.default is inspect.Signature.empty
            elif isinstance(marker, NativeArgument):
                name = parameter.name
                is_required = parameter.default is inspect.Signature.empty
            else:
                if parameter.default is inspect.Signature.empty:
                    name = parameter.name
                    is_required = True
                else:
                    name = f"--{_normalise_alias(parameter.name)}"
                    is_required = False

            lines.append(f"  - name: {name}")
            lines.append(f"    type: {param_type}")
            lines.append(f"    required: {'true' if is_required else 'false'}")

            if parameter.default is not inspect.Signature.empty:
                lines.append(f"    default: {_yaml_value(parameter.default)}")

            help_text = _help_text(annotation)
            if help_text:
                lines.append(f"    help: {_yaml_value(help_text)}")

        meta = get_command_meta(callback)
        if meta.auth:
            lines.append("auth:")
            for item in meta.auth:
                lines.append(f"  - {item}")

        if meta.cost_hint is not None:
            lines.append(f"cost_hint: {_yaml_value(str(meta.cost_hint))}")

        if meta.max_tokens is not None:
            lines.append(f"max_tokens: {meta.max_tokens}")

        if meta.requires_approval:
            lines.append("requires_approval: true")

        if meta.danger_level:
            lines.append(f"danger_level: {_yaml_value(str(meta.danger_level))}")

        if meta.human_in_the_loop:
            lines.append("human_in_the_loop: true")

        if meta.allow_python_eval:
            lines.append("allow_python_eval: true")

        if meta.error_codes:
            lines.append("errors:")
            for code, _message in sorted(meta.error_codes.items(), key=lambda item: item[0]):
                lines.append(f"  - {code}")

        if meta.examples:
            example_args = meta.examples[0].get("args", [])
            if isinstance(example_args, list):
                example_text = " ".join(str(arg) for arg in example_args if arg is not None).strip()
                if example_text:
                    lines.append(f"example: {json.dumps(example_text)}")

        schema = generate_tool_schema(callback, name=callback.__name__)
        lines.append("output: " + json.dumps(schema.output_schema))

        print("\n".join(lines))

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.main(*args, **kwargs)

    def main(self, args: list[str] | None = None, prog_name: str | None = None, **_kwargs: Any) -> int:
        del prog_name
        cli_args = list(args if args is not None else sys.argv[1:])
        parser = self._build_parser()

        start_time = time.perf_counter()
        parsed = parser.parse_args(cli_args)
        ns = vars(parsed)
        if not ns:
            parser.print_help()
            return 1

        command = ns.pop("_tooli_command", None)
        if command is None:
            parser.print_help()
            return 1

        callback = command.callback
        show_schema = bool(ns.pop("schema", False))
        if show_schema:
            self._emit_schema(callback)
            return 0
        if bool(ns.pop("help_agent", False)):
            self._emit_help_agent(callback)
            return 0

        if bool(ns.pop("dry_run", False)):
            payload = {
                "tool": f"{self.info.name}.{command.name}",
                "dry_run": True,
                "command": command.name,
                "arguments": ns,
            }
            print(json.dumps(payload, sort_keys=True))
            return 0

        callback_kwargs: dict[str, Any] = {}
        signature = inspect.signature(callback)
        for parameter in signature.parameters.values():
            if parameter.name in {"ctx", "context"}:
                continue
            if parameter.kind in {inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL}:
                continue
            value = ns.pop(parameter.name, parameter.default if parameter.default is not inspect.Signature.empty else None)
            if isinstance(value, str):
                annotation = callback.__annotations__.get(parameter.name, parameter.annotation)
                if get_origin(annotation) is not None or isinstance(value, str):
                    marker = _native_marker_from_annotation(annotation)
                    base_annotation = _strip_annotated(annotation)[0]
                    if base_annotation is inspect.Signature.empty:
                        base_annotation = str
                    if base_annotation not in (str, Any, inspect.Parameter.empty):
                        value = _coerce_value(value, annotation)
            callback_kwargs[parameter.name] = value

        output_json = bool(ns.pop("json", False))
        use_text_mode = not output_json

        try:
            result = callback(**callback_kwargs)
            if use_text_mode and not isinstance(result, str):
                print(json.dumps(result, indent=2))
            elif use_text_mode:
                print(result)
            else:
                payload = Envelope(
                    ok=True,
                    result=result,
                    meta=EnvelopeMeta(
                        tool=f"{self.info.name}.{command.name}",
                        version=self.version,
                        duration_ms=max(1, int((time.perf_counter() - start_time) * 1000)),
                        dry_run=False,
                        warnings=[],
                    ),
                )
                print(json.dumps(payload.model_dump(), indent=2))
            return 0
        except ToolError as exc:
            if output_json:
                payload = {
                    "ok": False,
                    "error": exc.to_dict(),
                    "meta": {
                        "tool": f"{self.info.name}.{command.name}",
                        "version": self.version,
                        "duration_ms": max(1, int((time.perf_counter() - start_time) * 1000)),
                        "dry_run": False,
                        "warnings": [],
                    },
                }
                print(json.dumps(payload, indent=2))
            else:
                print(f"Error: {exc.code}: {exc.message}")
            return int(getattr(exc, "exit_code", 1))
        except InternalError as exc:
            if output_json:
                payload = {
                    "ok": False,
                    "error": exc.to_dict(),
                    "meta": {
                        "tool": f"{self.info.name}.{command.name}",
                        "version": self.version,
                        "duration_ms": max(1, int((time.perf_counter() - start_time) * 1000)),
                        "dry_run": False,
                        "warnings": [],
                    },
                }
                print(json.dumps(payload, indent=2))
            else:
                print(f"Error: {exc.code}: {exc.message}")
            return int(exc.exit_code)
        except Exception as exc:
            if output_json:
                payload = {
                    "ok": False,
                    "error": {
                        "code": "E5000",
                        "message": str(exc),
                        "category": "runtime",
                    },
                    "meta": {
                        "tool": f"{self.info.name}.{command.name}",
                        "version": self.version,
                        "duration_ms": max(1, int((time.perf_counter() - start_time) * 1000)),
                        "dry_run": False,
                        "warnings": [],
                    },
                }
                print(json.dumps(payload, indent=2))
            else:
                print(f"Error: {exc}")
            return 1
