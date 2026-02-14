"""Tooli command implementation: global flags and output routing."""

from __future__ import annotations

import inspect
import json
import signal
import traceback
import time
from collections.abc import Callable
from typing import Any, Iterable

import click
from typer.core import TyperCommand

from tooli.context import ToolContext
from tooli.envelope import Envelope, EnvelopeMeta
from tooli.errors import InputError, InternalError, RuntimeError, ToolError
from tooli.exit_codes import ExitCode
from tooli.input import is_secret_input, redact_secret_values, resolve_secret_value
from tooli.eval.recorder import InvocationRecorder
from tooli.telemetry_pipeline import TelemetryPipeline
from tooli.output import (
    OutputMode,
    parse_output_mode,
    parse_response_format,
    ResponseFormat,
    resolve_no_color,
    resolve_output_mode,
    resolve_response_format,
)


def _set_output_override(mode: OutputMode) -> Callable[[click.Context, click.Parameter, Any], Any]:
    def _cb(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
        # Only apply when the option is explicitly provided.
        if value is None or value is False:
            return value
        ctx.meta["tooli_output_override"] = mode
        return value

    return _cb


def _set_output_override_from_string(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
    if value is None:
        return value
    ctx.meta["tooli_output_override"] = parse_output_mode(str(value))
    return value


def _set_no_color(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
    if value:
        ctx.meta["tooli_no_color"] = True
    return value


def _set_response_format(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
    if value is None:
        return value
    mode = parse_response_format(str(value))
    ctx.meta["tooli_response_format"] = mode
    return value


def _capture_tooli_flags(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
    if value is not None and value is not False:
        ctx.meta[f"tooli_flag_{param.name}"] = value
    return value


def _detect_secret_parameter_names(callback: Callable[..., Any] | None) -> list[str]:
    """Return callback parameters annotated with SecretInput."""
    secret_params = getattr(callback, "__tooli_secret_params__", None)
    if isinstance(secret_params, list):
        return secret_params

    if callback is None:
        return []

    names: list[str] = []
    for name, param in inspect.signature(callback).parameters.items():
        if is_secret_input(param.annotation):
            names.append(name)
    return names


def _capture_secret_file_path(ctx: click.Context, param: click.Parameter, value: Any, *, secret_name: str) -> Any:
    if value is not None:
        ctx.meta[f"tooli_secret_file_{secret_name}"] = value
    return value


def _capture_secret_stdin_flag(ctx: click.Context, param: click.Parameter, value: Any, *, secret_name: str) -> Any:
    if value:
        ctx.meta[f"tooli_secret_stdin_{secret_name}"] = True
    return value


def _capture_default_secret_file_path(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
    if value is not None:
        ctx.meta["tooli_secret_file"] = value
    return value


def _capture_default_secret_stdin_flag(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
    if value:
        ctx.meta["tooli_secret_stdin_default"] = True
    return value


def _get_tool_id(ctx: click.Context) -> str:
    # click uses command_path like "file-tools find-files".
    return ctx.command_path.replace(" ", ".")


def _get_app_meta_from_callback(
    callback: Callable[..., Any] | None,
) -> tuple[str, str, str, TelemetryPipeline | None, InvocationRecorder | None]:
    if callback is None:
        return ("tooli", "0.0.0", "auto", None, None)
    name = getattr(callback, "__tooli_app_name__", "tooli")
    version = getattr(callback, "__tooli_app_version__", "0.0.0")
    default_output = getattr(callback, "__tooli_default_output__", "auto")
    telemetry_pipeline = getattr(callback, "__tooli_telemetry_pipeline__", None)
    invocation_recorder = getattr(callback, "__tooli_invocation_recorder__", None)
    return (str(name), str(version), str(default_output), telemetry_pipeline, invocation_recorder)


def _serialize_arg_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _serialize_arg_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize_arg_value(item) for item in value]
    return str(value)


def _collect_invocation_args(ctx: click.Context) -> dict[str, Any]:
    params = getattr(ctx, "params", None)
    if not isinstance(params, dict):
        return {}
    return {str(name): _serialize_arg_value(value) for name, value in params.items()}


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _normalize_system_exit(code: object | None) -> int:
    if code is None:
        return int(ExitCode.SUCCESS)
    if isinstance(code, ExitCode):
        return int(code.value)
    if isinstance(code, int):
        return code
    if isinstance(code, bool):
        return int(code)
    if isinstance(code, str) and code.isdigit():
        return int(code)
    return 1


def _build_envelope_meta(ctx: click.Context, *, app_version: str, duration_ms: int) -> EnvelopeMeta:
    warnings: list[str] = []
    callback = getattr(ctx, "command", None)
    if callback is not None:
        callback_obj = getattr(callback, "callback", None)
        if callback_obj is not None and getattr(callback_obj, "__tooli_deprecated__", False):
            deprecated_message = getattr(callback_obj, "__tooli_deprecated_message__", None)
            if deprecated_message:
                warnings.append(str(deprecated_message))
            else:
                warnings.append("This command is deprecated.")

    return EnvelopeMeta(
        tool=_get_tool_id(ctx),
        version=app_version,
        duration_ms=duration_ms,
        dry_run=bool(getattr(getattr(ctx, "obj", None), "dry_run", False)),
        warnings=warnings,
    )


class TooliCommand(TyperCommand):
    """TyperCommand subclass with Tooli global flags and output routing."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        params = list(kwargs.get("params") or [])

        # Global flags injected into every command. expose_value=False prevents passing into callbacks.
        params.extend(
            [
                click.Option(
                    ["--output", "-o"],
                    metavar="MODE",
                    type=click.Choice([m.value for m in OutputMode], case_sensitive=False),
                    help="Output mode: auto|json|jsonl|text|plain",
                    expose_value=False,
                    callback=_set_output_override_from_string,
                ),
                click.Option(
                    ["--json"],
                    is_flag=True,
                    help="Alias for --output json",
                    expose_value=False,
                    callback=_set_output_override(OutputMode.JSON),
                ),
                click.Option(
                    ["--jsonl"],
                    is_flag=True,
                    help="Alias for --output jsonl",
                    expose_value=False,
                    callback=_set_output_override(OutputMode.JSONL),
                ),
                click.Option(
                    ["--text"],
                    is_flag=True,
                    help="Alias for --output text",
                    expose_value=False,
                    callback=_set_output_override(OutputMode.TEXT),
                ),
                click.Option(
                    ["--plain"],
                    is_flag=True,
                    help="Alias for --output plain",
                    expose_value=False,
                    callback=_set_output_override(OutputMode.PLAIN),
                ),
                click.Option(
                    ["--no-color"],
                    is_flag=True,
                    help="Disable colored/pretty output (also respects NO_COLOR).",
                    expose_value=False,
                    callback=_set_no_color,
                ),
                click.Option(
                    ["--quiet", "-q"],
                    is_flag=True,
                    help="Suppress non-essential output.",
                    expose_value=False,
                    callback=_capture_tooli_flags,
                ),
                click.Option(
                    ["--verbose", "-v"],
                    count=True,
                    help="Increase verbosity (e.g., -vv).",
                    expose_value=False,
                    callback=_capture_tooli_flags,
                ),
                click.Option(
                    ["--dry-run"],
                    is_flag=True,
                    help="Show planned actions without executing.",
                    expose_value=False,
                    callback=_capture_tooli_flags,
                ),
                click.Option(
                    ["--yes", "-y"],
                    is_flag=True,
                    help="Skip interactive confirmation prompts.",
                    expose_value=False,
                    callback=_capture_tooli_flags,
                ),
                click.Option(
                    ["--timeout"],
                    type=float,
                    help="Maximum execution time in seconds.",
                    expose_value=False,
                    callback=_capture_tooli_flags,
                ),
                click.Option(
                    ["--response-format"],
                    type=click.Choice([m.value for m in ResponseFormat], case_sensitive=False),
                    help="Response format for command return values.",
                    expose_value=False,
                    callback=_set_response_format,
                ),
                click.Option(
                    ["--schema"],
                    is_flag=True,
                    help="Output JSON Schema for this command and exit.",
                    expose_value=False,
                    callback=_capture_tooli_flags,
                ),
                click.Option(
                    ["--help-agent"],
                    is_flag=True,
                    help="Emit compact, token-efficient command help.",
                    expose_value=False,
                    callback=_capture_tooli_flags,
                ),
            ]
        )

        self._tooli_secret_params = _detect_secret_parameter_names(kwargs.get("callback"))
        secret_params = self._tooli_secret_params

        for secret_name in secret_params:
            option_name = secret_name.replace("_", "-")
            params.extend(
                [
                    click.Option(
                        [f"--{option_name}-secret-file"],
                        type=click.Path(dir_okay=False),
                        help="Read secret value from a file.",
                        expose_value=False,
                        hidden=True,
                        callback=lambda ctx, param, value, secret_name=secret_name: _capture_secret_file_path(
                            ctx,
                            param,
                            value,
                            secret_name=secret_name,
                        ),
                    ),
                    click.Option(
                        [f"--{option_name}-secret-stdin"],
                        is_flag=True,
                        help="Read secret value from stdin.",
                        expose_value=False,
                        hidden=True,
                        callback=lambda ctx, param, value, secret_name=secret_name: _capture_secret_stdin_flag(
                            ctx,
                            param,
                            value,
                            secret_name=secret_name,
                        ),
                    ),
                ]
            )

            if len(secret_params) == 1:
                params.extend(
                    [
                        click.Option(
                            ["--secret-file"],
                            type=click.Path(dir_okay=False),
                            help="Read secret value from a file.",
                            expose_value=False,
                            hidden=True,
                            callback=_capture_default_secret_file_path,
                        ),
                        click.Option(
                            ["--secret-stdin"],
                            is_flag=True,
                            help="Read secret value from stdin.",
                            expose_value=False,
                            hidden=True,
                            callback=_capture_default_secret_stdin_flag,
                        ),
                    ]
                )
        kwargs["params"] = params
        super().__init__(*args, **kwargs)

    @staticmethod
    def _format_param_for_help_agent(parameter: click.Parameter) -> str:
        names: Iterable[str]
        if isinstance(parameter, click.Option):
            if parameter.opts or parameter.secondary_opts:
                names = parameter.opts + parameter.secondary_opts
            elif parameter.name:
                names = (parameter.name,)
            else:
                names = ("option",)
            signature = "/".join(names)
        else:
            signature = parameter.name or "arg"

        if isinstance(parameter.type, click.Choice):
            type_name = f"choice[{','.join(map(str, parameter.type.choices))}]"
        elif parameter.type and parameter.type.name:
            type_name = parameter.type.name
        else:
            type_name = "unknown"

        parts = [signature, type_name]
        if parameter.default is not None and not isinstance(parameter, click.Argument):
            parts.append(f"default={parameter.default}")
        if getattr(parameter, "required", False):
            parts.append("required")
        return ":".join(parts)

    @staticmethod
    def _render_help_agent_output(ctx: click.Context) -> str:
        if ctx.command is None:
            return ""

        command = ctx.command
        lines = [
            f"command {command.name or ctx.info_name or 'tooli'}:",
            f"help={command.help or command.get_short_help_str(100) or ''}",
        ]

        params = [p for p in command.params if p.expose_value]
        if params:
            lines.append("params=" + "|".join(TooliCommand._format_param_for_help_agent(p) for p in params))

        return "\n".join(lines)

    def invoke(self, ctx: click.Context) -> Any:
        _, app_version, app_default_output, telemetry_pipeline, invocation_recorder = _get_app_meta_from_callback(
            self.callback
        )

        # Initialize ToolContext and store in ctx.obj for callback access.
        ctx.obj = ToolContext(
            quiet=bool(ctx.meta.get("tooli_flag_quiet", False)),
            verbose=int(ctx.meta.get("tooli_flag_verbose", 0)),
            dry_run=bool(ctx.meta.get("tooli_flag_dry_run", False)),
            yes=bool(ctx.meta.get("tooli_flag_yes", False)),
            timeout=ctx.meta.get("tooli_flag_timeout"),
            response_format=resolve_response_format(ctx).value,
        )

        if bool(ctx.meta.get("tooli_flag_help_agent", False)):
            click.echo(self._render_help_agent_output(ctx))
            return None

        if bool(ctx.meta.get("tooli_flag_schema", False)):
            from tooli.schema import generate_tool_schema

            schema = generate_tool_schema(self.callback, name=_get_tool_id(ctx))
            if self.callback:
                annotations = getattr(self.callback, "__tooli_annotations__", None)
                from tooli.annotations import ToolAnnotation

                if isinstance(annotations, ToolAnnotation):
                    hints = []
                    if annotations.read_only:
                        hints.append("read-only")
                    if annotations.idempotent:
                        hints.append("idempotent")
                    if annotations.destructive:
                        hints.append("destructive")
                    if annotations.open_world:
                        hints.append("open-world")
                    schema.annotations = hints

                schema.examples = getattr(self.callback, "__tooli_examples__", [])

            click.echo(_json_dumps(schema.model_dump(exclude_none=True)))
            ctx.exit(int(ExitCode.SUCCESS))

        # Apply Tooli.default_output as a baseline when no explicit override was provided.
        if "tooli_output_override" not in ctx.meta:
            try:
                parsed = parse_output_mode(app_default_output)
            except click.BadParameter:
                parsed = OutputMode.AUTO
            ctx.meta["tooli_output_override"] = parsed

        result: Any | None = None

        mode = resolve_output_mode(ctx)
        no_color = resolve_no_color(ctx)
        command_name = _get_tool_id(ctx)
        start = time.perf_counter()
        timer_active = False
        ctx.meta.setdefault("tooli_secret_values", [])

        # Handle timeout if specified.
        def _timeout_handler(signum: int, frame: Any) -> None:
            del signum, frame
            raise RuntimeError(
                message=f"Command timed out after {ctx.obj.timeout} seconds",
                code="E4001",
                exit_code=ExitCode.TIMEOUT_EXPIRED,
            )

        if ctx.obj.timeout and ctx.obj.timeout > 0:
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, ctx.obj.timeout)
            timer_active = True

        def _emit_telemetry(*, success: bool, error: ToolError | None = None, exit_code: int | None = None) -> None:
            if telemetry_pipeline is None:
                return
            telemetry_pipeline.record(
                command=command_name,
                success=success,
                duration_ms=int((time.perf_counter() - start) * 1000),
                exit_code=exit_code,
                error_code=None if error is None else error.code,
                error_category=None if error is None else error.category.value,
            )

        def _emit_invocation(*, status: str, error_code: str | None = None, exit_code: int | None = None) -> None:
            if invocation_recorder is None:
                return

            args = redact_secret_values(_collect_invocation_args(ctx), ctx.meta.get("tooli_secret_values", []))
            invocation_recorder.record(
                command=command_name,
                args=args,
                status=status,
                duration_ms=int((time.perf_counter() - start) * 1000),
                error_code=error_code,
                exit_code=exit_code,
            )

        try:
            # Resolve secret arguments before invoking the callback.
            for secret_name in getattr(self, "_tooli_secret_params", []):
                explicit_value = ctx.params.get(secret_name)
                file_path = ctx.meta.pop(f"tooli_secret_file_{secret_name}", None)
                if file_path is None and len(getattr(self, "_tooli_secret_params", [])) == 1:
                    file_path = ctx.meta.pop("tooli_secret_file", None)

                use_stdin = bool(ctx.meta.pop(f"tooli_secret_stdin_{secret_name}", False))
                if not use_stdin and len(getattr(self, "_tooli_secret_params", [])) == 1:
                    use_stdin = bool(ctx.meta.pop("tooli_secret_stdin_default", False))

                resolved = resolve_secret_value(
                    explicit_value=explicit_value,
                    param_name=secret_name,
                    file_path=file_path,
                    use_stdin=use_stdin,
                    use_env=True,
                )

                if resolved is not None:
                    ctx.params[secret_name] = resolved
                    if isinstance(ctx.meta.get("tooli_secret_values"), list):
                        ctx.meta["tooli_secret_values"].append(resolved)

            try:
                result = super().invoke(ctx)
            except ToolError:
                raise
            except click.UsageError as e:
                # Map Click usage errors to InputError (exit code 2).
                raise InputError(message=str(e), code="E1001") from e
            except click.ClickException as e:
                raise InputError(message=e.format_message(), code="E1002") from e
            except Exception as e:
                details = {}
                if ctx.obj.verbose > 0:
                    details["traceback"] = traceback.format_exc()
                raise InternalError(
                    message=f"Internal error: {e}",
                    details=details,
                ) from e
        except ToolError as e:
            _emit_invocation(
                status="error",
                error_code=e.code,
                exit_code=_normalize_system_exit(e.exit_code),
            )
            _emit_telemetry(
                success=False,
                error=e,
                exit_code=_normalize_system_exit(e.exit_code),
            )
            return self._handle_tool_error(ctx, app_version, start, e, mode, no_color)
        except SystemExit as e:
            exit_code = _normalize_system_exit(e.code)
            _emit_invocation(status="error", exit_code=exit_code)
            _emit_telemetry(success=(exit_code == 0), exit_code=exit_code)
            raise SystemExit(exit_code)
        finally:
            if timer_active:
                signal.setitimer(signal.ITIMER_REAL, 0)

        duration_ms = int((time.perf_counter() - start) * 1000)

        if result is None:
            _emit_invocation(status="success", exit_code=0)
            _emit_telemetry(success=True, exit_code=0)
            return None

        result = redact_secret_values(result, ctx.meta.get("tooli_secret_values", []))
        _emit_invocation(status="success", exit_code=0)
        _emit_telemetry(success=True, exit_code=0)

        if mode == OutputMode.AUTO:
            if click.get_text_stream("stdout").isatty() and not no_color and not ctx.obj.quiet:
                try:
                    from rich import print as rich_print

                    rich_print(result)
                except Exception:
                    click.echo(str(result))
                return result

            mode = OutputMode.JSON
            # Continue through envelope path for machine-readable output.

        if mode in (OutputMode.TEXT, OutputMode.PLAIN):
            click.echo(str(result))
            return result

        if mode == OutputMode.JSON:
            meta = _build_envelope_meta(ctx, app_version=app_version or "0.0.0", duration_ms=duration_ms)
            env = Envelope(ok=True, result=result, meta=meta)
            click.echo(_json_dumps(env.model_dump()))
            return result

        if mode == OutputMode.JSONL:
            meta = _build_envelope_meta(ctx, app_version=app_version or "0.0.0", duration_ms=duration_ms)
            if isinstance(result, list):
                for item in result:
                    env = Envelope(ok=True, result=item, meta=meta)
                    click.echo(_json_dumps(env.model_dump()))
            else:
                env = Envelope(ok=True, result=result, meta=meta)
                click.echo(_json_dumps(env.model_dump()))
            return result

        click.echo(str(result))
        return result

    def _handle_tool_error(
        self,
        ctx: click.Context,
        app_version: str,
        start: float,
        error: ToolError,
        mode: OutputMode,
        no_color: bool,
    ) -> None:
        secret_values = ctx.meta.get("tooli_secret_values", [])
        if mode in (OutputMode.JSON, OutputMode.JSONL, OutputMode.AUTO) and not click.get_text_stream("stdout").isatty():
            meta = _build_envelope_meta(
                ctx,
                app_version=app_version,
                duration_ms=int((time.perf_counter() - start) * 1000),
            )
            env = Envelope(ok=False, result=None, meta=meta)
            out = env.model_dump()
            out["error"] = redact_secret_values(error.to_dict(), secret_values)
            click.echo(_json_dumps(out))
        else:
            message = redact_secret_values(error.message, secret_values)
            suggestion = ""
            if error.suggestion:
                suggestion = redact_secret_values(error.suggestion.fix, secret_values)
            if not no_color:
                try:
                    from rich.console import Console

                    console = Console(stderr=True)
                    console.print(f"[bold red]Error:[/bold red] {message}")
                    if error.suggestion:
                        console.print(f"[bold blue]Suggestion:[/bold blue] {suggestion}")
                except Exception:
                    click.echo(f"Error: {message}", err=True)
            else:
                click.echo(f"Error: {message}", err=True)

        if error.exit_code is not None:
            raise SystemExit(_normalize_system_exit(error.exit_code))

        raise SystemExit(int(ExitCode.INTERNAL_ERROR))
