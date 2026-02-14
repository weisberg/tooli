"""Tooli command implementation: global flags and output routing."""

from __future__ import annotations

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


def _get_tool_id(ctx: click.Context) -> str:
    # click uses command_path like "file-tools find-files".
    return ctx.command_path.replace(" ", ".")


def _get_app_meta_from_callback(
    callback: Callable[..., Any] | None,
) -> tuple[str, str, str]:
    if callback is None:
        return ("tooli", "0.0.0", "auto")
    name = getattr(callback, "__tooli_app_name__", "tooli")
    version = getattr(callback, "__tooli_app_version__", "0.0.0")
    default_output = getattr(callback, "__tooli_default_output__", "auto")
    return (str(name), str(version), str(default_output))


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
        _, app_version, app_default_output = _get_app_meta_from_callback(self.callback)

        # Initialize ToolContext and store in ctx.obj for callback access.
        ctx.obj = ToolContext(
            quiet=bool(ctx.meta.get("tooli_flag_quiet", False)),
            verbose=int(ctx.meta.get("tooli_flag_verbose", 0)),
            dry_run=bool(ctx.meta.get("tooli_flag_dry_run", False)),
            yes=bool(ctx.meta.get("tooli_flag_yes", False)),
            timeout=ctx.meta.get("tooli_flag_timeout"),
            response_format=resolve_response_format(ctx),
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
        start = time.perf_counter()
        timer_active = False

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

        try:
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
            return self._handle_tool_error(ctx, app_version, start, e, mode, no_color)
        except SystemExit as e:
            raise SystemExit(_normalize_system_exit(e.code))
        finally:
            if timer_active:
                signal.setitimer(signal.ITIMER_REAL, 0)

        duration_ms = int((time.perf_counter() - start) * 1000)

        if result is None:
            return None

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
            meta = EnvelopeMeta(
                tool=_get_tool_id(ctx),
                version=app_version or "0.0.0",
                duration_ms=duration_ms,
                warnings=[],
            )
            env = Envelope(ok=True, result=result, meta=meta)
            click.echo(_json_dumps(env.model_dump()))
            return result

        if mode == OutputMode.JSONL:
            meta = EnvelopeMeta(
                tool=_get_tool_id(ctx),
                version=app_version or "0.0.0",
                duration_ms=duration_ms,
                warnings=[],
            )
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
        if mode in (OutputMode.JSON, OutputMode.JSONL, OutputMode.AUTO) and not click.get_text_stream("stdout").isatty():
            meta = EnvelopeMeta(
                tool=_get_tool_id(ctx),
                version=app_version,
                duration_ms=int((time.perf_counter() - start) * 1000),
            )
            env = Envelope(ok=False, result=None, meta=meta)
            out = env.model_dump()
            out["error"] = error.to_dict()
            click.echo(_json_dumps(out))
        else:
            if not no_color:
                try:
                    from rich.console import Console

                    console = Console(stderr=True)
                    console.print(f"[bold red]Error:[/bold red] {error.message}")
                    if error.suggestion:
                        console.print(f"[bold blue]Suggestion:[/bold blue] {error.suggestion.fix}")
                except Exception:
                    click.echo(f"Error: {error.message}", err=True)
            else:
                click.echo(f"Error: {error.message}", err=True)

        if error.exit_code is not None:
            raise SystemExit(_normalize_system_exit(error.exit_code))

        raise SystemExit(int(ExitCode.INTERNAL_ERROR))
