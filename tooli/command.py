"""Tooli command implementation: global flags + return-value routing."""

from __future__ import annotations

import json
import os
import signal
import time
from typing import Any, Callable, Optional

import click
from typer.core import TyperCommand

from tooli.context import ToolContext
from tooli.envelope import Envelope, EnvelopeMeta
from tooli.errors import InternalError, ToolError, RuntimeError, InputError
from tooli.output import OutputMode, resolve_no_color, resolve_output_mode, parse_output_mode


def _set_output_override(mode: OutputMode) -> Callable[[click.Context, click.Parameter, Any], Any]:
    def _cb(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
        # Only apply when the option is explicitly provided / truthy.
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


def _capture_tooli_flags(ctx: click.Context, param: click.Parameter, value: Any) -> Any:
    if value is not None and value is not False:
        ctx.meta[f"tooli_flag_{param.name}"] = value
    return value


def _get_tool_id(ctx: click.Context) -> str:
    # click uses command_path like "file-tools find-files"
    return ctx.command_path.replace(" ", ".")


def _get_app_meta_from_callback(callback: Optional[Callable[..., Any]]) -> tuple[str, str, str]:
    if callback is None:
        return ("tooli", "0.0.0", "auto")
    name = getattr(callback, "__tooli_app_name__", "tooli")
    version = getattr(callback, "__tooli_app_version__", "0.0.0")
    default_output = getattr(callback, "__tooli_default_output__", "auto")
    return (str(name), str(version), str(default_output))


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


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
                    ["--schema"],
                    is_flag=True,
                    help="Output JSON Schema for this command and exit.",
                    expose_value=False,
                    callback=_capture_tooli_flags,
                ),
            ]
        )

        kwargs["params"] = params
        super().__init__(*args, **kwargs)

    def invoke(self, ctx: click.Context) -> Any:
        app_name, app_version, app_default_output = _get_app_meta_from_callback(self.callback)

        # Initialize ToolContext and store in ctx.obj
        ctx.obj = ToolContext(
            quiet=bool(ctx.meta.get("tooli_flag_quiet", False)),
            verbose=int(ctx.meta.get("tooli_flag_verbose", 0)),
            dry_run=bool(ctx.meta.get("tooli_flag_dry_run", False)),
            yes=bool(ctx.meta.get("tooli_flag_yes", False)),
            timeout=ctx.meta.get("tooli_flag_timeout"),
        )

        if bool(ctx.meta.get("tooli_flag_schema", False)):
            from tooli.schema import generate_tool_schema
            
            schema = generate_tool_schema(self.callback, name=_get_tool_id(ctx)) # type: ignore
            
            # Enrich schema with Tooli-specific metadata
            if self.callback:
                annotations = getattr(self.callback, "__tooli_annotations__", None)
                if annotations:
                    # Map ToolAnnotation to strings for JSON
                    from tooli.annotations import ToolAnnotation
                    if isinstance(annotations, ToolAnnotation):
                        hints = []
                        if annotations.read_only: hints.append("read-only")
                        if annotations.idempotent: hints.append("idempotent")
                        if annotations.destructive: hints.append("destructive")
                        if annotations.open_world: hints.append("open-world")
                        schema.annotations = hints
                
                schema.examples = getattr(self.callback, "__tooli_examples__", [])

            click.echo(_json_dumps(schema.model_dump(exclude_none=True)))
            ctx.exit(0)

        # Apply Tooli.default_output as a baseline when no explicit override was provided.
        if "tooli_output_override" not in ctx.meta:
            try:
                ctx.meta["tooli_output_override"] = parse_output_mode(app_default_output)
            except click.BadParameter:
                # Ignore invalid defaults; fall back to auto detection.
                pass

        mode = resolve_output_mode(ctx)
        no_color = resolve_no_color(ctx)

        # Handle timeout if specified
        def _timeout_handler(signum: int, frame: Any) -> None:
            raise RuntimeError(
                message=f"Command timed out after {ctx.obj.timeout} seconds",
                code="E4001",
                exit_code=50,
            )

        if ctx.obj.timeout and ctx.obj.timeout > 0:
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, ctx.obj.timeout)

        start = time.perf_counter()
        try:
            try:
                result = super().invoke(ctx)
            except ToolError:
                raise
            except click.UsageError as e:
                # Map Click usage errors to InputError (exit code 2)
                raise InputError(message=str(e), code="E1001") from e
            except Exception as e:
                # Wrap unexpected errors
                details = {}
                if ctx.obj.verbose > 0:
                    import traceback

                    details["traceback"] = traceback.format_exc()
                raise InternalError(
                    message=f"Internal error: {e}",
                    details=details,
                ) from e
        except ToolError as e:
            # Handle structured error output
            if mode in (OutputMode.JSON, OutputMode.JSONL, OutputMode.AUTO) and not click.get_text_stream("stdout").isatty():
                meta = EnvelopeMeta(
                    tool=_get_tool_id(ctx),
                    version=app_version,
                    duration_ms=int((time.perf_counter() - start) * 1000),
                )
                env = Envelope(ok=False, result=None, meta=meta)
                # Merge error info into a single object for the agent
                out = env.model_dump()
                out["error"] = e.to_dict()
                click.echo(_json_dumps(out))
            else:
                # Human-readable error to stderr
                if not no_color:
                    try:
                        from rich.console import Console

                        console = Console(stderr=True)
                        console.print(f"[bold red]Error:[/bold red] {e.message}")
                        if e.suggestion:
                            console.print(f"[bold blue]Suggestion:[/bold blue] {e.suggestion.fix}")
                    except Exception:
                        click.echo(f"Error: {e.message}", err=True)
                else:
                    click.echo(f"Error: {e.message}", err=True)

            # Re-disable timer
            if ctx.obj.timeout:
                signal.setitimer(signal.ITIMER_REAL, 0)

            ctx.exit(e.exit_code)
        finally:
            if ctx.obj.timeout:
                signal.setitimer(signal.ITIMER_REAL, 0)

        duration_ms = int((time.perf_counter() - start) * 1000)

        if result is None:
            return None

        tool_id = _get_tool_id(ctx)

        if mode == OutputMode.AUTO:
            # AUTO renders "human" output on TTY, otherwise JSON.
            if click.get_text_stream("stdout").isatty() and not no_color:
                try:
                    from rich import print as rich_print

                    rich_print(result)
                except Exception:
                    click.echo(str(result))
                return result
            mode = OutputMode.JSON

        if mode in (OutputMode.TEXT, OutputMode.PLAIN):
            click.echo(str(result))
            return result

        meta = EnvelopeMeta(
            tool=tool_id,
            version=app_version or "0.0.0",
            duration_ms=duration_ms,
            warnings=[],
        )

        if mode == OutputMode.JSON:
            env = Envelope(ok=True, result=result, meta=meta)
            click.echo(_json_dumps(env.model_dump()))
            return result

        if mode == OutputMode.JSONL:
            if isinstance(result, list):
                for item in result:
                    env = Envelope(ok=True, result=item, meta=meta)
                    click.echo(_json_dumps(env.model_dump()))
            else:
                env = Envelope(ok=True, result=result, meta=meta)
                click.echo(_json_dumps(env.model_dump()))
            return result

        # Fallback: behave as text.
        click.echo(str(result))
        return result
