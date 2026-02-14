"""Tooli command implementation: global flags + return-value routing."""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Callable, Optional

import click
from typer.core import TyperCommand

from tooli.envelope import Envelope, EnvelopeMeta
from tooli.output import OutputMode, resolve_no_color, resolve_output_mode, parse_output_mode


@dataclass(frozen=True)
class _TooliAppMeta:
    name: str
    version: str
    default_output: str


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


def _get_tool_id(ctx: click.Context) -> str:
    # click uses command_path like "file-tools find-files"
    return ctx.command_path.replace(" ", ".")


def _get_app_meta_from_callback(callback: Optional[Callable[..., Any]]) -> _TooliAppMeta:
    if callback is None:
        return _TooliAppMeta(name="tooli", version="0.0.0", default_output="auto")
    name = getattr(callback, "__tooli_app_name__", "tooli")
    version = getattr(callback, "__tooli_app_version__", "0.0.0")
    default_output = getattr(callback, "__tooli_default_output__", "auto")
    return _TooliAppMeta(name=str(name), version=str(version), default_output=str(default_output))


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
            ]
        )

        kwargs["params"] = params
        super().__init__(*args, **kwargs)

    def invoke(self, ctx: click.Context) -> Any:
        app_meta = _get_app_meta_from_callback(self.callback)

        # Apply Tooli.default_output as a baseline when no explicit override was provided.
        if "tooli_output_override" not in ctx.meta:
            try:
                ctx.meta["tooli_output_override"] = parse_output_mode(app_meta.default_output)
            except click.BadParameter:
                # Ignore invalid defaults; fall back to auto detection.
                pass

        mode = resolve_output_mode(ctx)
        no_color = resolve_no_color(ctx)

        start = time.perf_counter()
        result = super().invoke(ctx)
        duration_ms = int((time.perf_counter() - start) * 1000)

        if result is None:
            return None

        tool_id = _get_tool_id(ctx)

        if mode == OutputMode.AUTO:
            # AUTO renders "human" output on TTY, otherwise JSON.
            if click.get_text_stream("stdout").isatty() and not no_color:
                try:
                    from rich import print as rich_print  # type: ignore[import-not-found]

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
            version=app_meta.version or "0.0.0",
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

