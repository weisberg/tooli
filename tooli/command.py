"""Tooli command implementation: global flags and output routing."""

from __future__ import annotations

import ast
import inspect
import json
import os
import re
import signal
import sys
import tempfile
import time
import traceback
import types
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

import click
from typer.core import TyperCommand

from tooli.annotations import ToolAnnotation
from tooli.auth import AuthContext  # noqa: TC001
from tooli.command_meta import get_command_meta
from tooli.context import ToolContext
from tooli.envelope import Envelope, EnvelopeMeta
from tooli.errors import (
    AuthError,
    InputError,
    InternalError,
    Suggestion,
    ToolError,
    ToolRuntimeError,
)
from tooli.eval.recorder import InvocationRecorder  # noqa: TC001
from tooli.exit_codes import ExitCode
from tooli.idempotency import get_record, set_record
from tooli.input import is_secret_input, redact_secret_values, resolve_secret_value
from tooli.output import (
    OutputMode,
    ResponseFormat,
    parse_output_mode,
    parse_response_format,
    resolve_no_color,
    resolve_output_mode,
    resolve_response_format,
)
from tooli.pagination import PaginationParams
from tooli.security.policy import SecurityPolicy
from tooli.security.sanitizer import sanitize_output
from tooli.telemetry import duration_ms as otel_duration_ms
from tooli.telemetry import start_command_span
from tooli.telemetry_pipeline import TelemetryPipeline  # noqa: TC001


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
    meta = get_command_meta(callback)
    if meta.secret_params:
        return meta.secret_params

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
) -> tuple[str, str, str, TelemetryPipeline | None, InvocationRecorder | None, SecurityPolicy]:
    meta = get_command_meta(callback)
    security_policy = meta.security_policy
    if not isinstance(security_policy, SecurityPolicy):
        security_policy = SecurityPolicy.OFF
    return (
        str(meta.app_name),
        str(meta.app_version),
        str(meta.default_output),
        meta.telemetry_pipeline,
        meta.invocation_recorder,
        security_policy,
    )


def _serialize_arg_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None: # noqa: UP038
        return value
    if isinstance(value, dict):
        return {str(k): _serialize_arg_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)): # noqa: UP038
        return [_serialize_arg_value(item) for item in value]
    return str(value)


def _collect_invocation_args(ctx: click.Context) -> dict[str, Any]:
    params = getattr(ctx, "params", None)
    if not isinstance(params, dict):
        return {}
    return {str(name): _serialize_arg_value(value) for name, value in params.items()}


def _is_destructive_command(callback: Callable[..., Any] | None) -> bool:
    ann = get_command_meta(callback).annotations
    return bool(getattr(ann, "destructive", False))


def _is_idempotent_command(callback: Callable[..., Any] | None) -> bool:
    ann = get_command_meta(callback).annotations
    return bool(getattr(ann, "idempotent", False))


def _is_list_processing_command(callback: Callable[..., Any] | None) -> bool:
    return get_command_meta(callback).list_processing


def _is_paginated_command(callback: Callable[..., Any] | None) -> bool:
    return get_command_meta(callback).paginated


def _extract_annotation_hints(callback: Callable[..., Any] | None) -> dict[str, Any]:
    ann = get_command_meta(callback).annotations
    if not isinstance(ann, ToolAnnotation):
        return {}

    hints: dict[str, Any] = {}
    if ann.read_only:
        hints["readOnlyHint"] = True
    if ann.idempotent:
        hints["idempotentHint"] = True
    if ann.destructive:
        hints["destructiveHint"] = True
    if ann.open_world:
        hints["openWorldHint"] = True
    return hints


def _annotation_labels(callback: Callable[..., Any] | None) -> list[str]:
    ann = get_command_meta(callback).annotations
    if not isinstance(ann, ToolAnnotation):
        return []
    labels: list[str] = []
    if ann.read_only:
        labels.append("read-only")
    if ann.idempotent:
        labels.append("idempotent")
    if ann.destructive:
        labels.append("destructive")
    if ann.open_world:
        labels.append("open-world")
    return labels


def _is_agent_mode(
    ctx: click.Context | None = None,
    mode: OutputMode | None = None,
) -> bool:
    """Return True when structured JSON output should be preferred.

    This is used by both parser-level flows and command-level runtime flows.
    Uses the full detection module when available, with legacy fallbacks.
    """
    if os.getenv("TOOLI_AGENT_MODE", "").lower() in {"1", "true", "yes", "on"}:
        return True
    if os.getenv("TOOLI_OUTPUT", "").lower() in {OutputMode.JSON.value, OutputMode.JSONL.value}:
        return True
    if ctx is not None and mode is not None:
        return mode in {OutputMode.JSON, OutputMode.JSONL}
    from tooli.detect import CallerCategory, _get_context
    return _get_context().category != CallerCategory.HUMAN


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def _build_truncation_payload(*, full_path: str, full_output_lines: list[str], max_tokens: int) -> dict[str, Any]:
    head = full_output_lines[:50]
    tail = full_output_lines[-50:] if len(full_output_lines) > 50 else full_output_lines
    return {
        "truncated": True,
        "max_tokens": max_tokens,
        "artifact_path": full_path,
        "line_count": len(full_output_lines),
        "head": head,
        "tail": tail,
        "message": (
            "Output truncated. First 50 lines and last 50 lines shown. "
            f"Full output saved to {full_path}. Use 'tooli_read_page' to view more."
        ),
    }


def _write_token_protection_artifact(full_output: str) -> Path:
    log_dir = Path(tempfile.gettempdir()) / "tooli_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix="tooli_output_",
        suffix=".json",
        dir=log_dir,
        mode="w",
        encoding="utf-8",
        delete=False,
    ) as handle:
        handle.write(full_output)
        return Path(handle.name)


def _maybe_emit_token_limited_json(
    *,
    result: Any,
    mode: OutputMode,
    ctx: click.Context,
    app_version: str,
    duration_ms: int,
    annotation_hints: dict[str, Any] | None,
    pagination_meta: dict[str, Any],
    max_tokens: int | None,
) -> Any | None:
    if max_tokens is None or max_tokens <= 0:
        return None

    if mode not in {OutputMode.JSON, OutputMode.JSONL}:
        return None

    if not _is_agent_mode(ctx, mode):
        return None

    payload = Envelope(
        ok=True,
        result=result,
        meta=_build_envelope_meta(
            ctx,
            app_version=app_version,
            duration_ms=duration_ms,
            annotations=annotation_hints,
            truncated=bool(pagination_meta.get("truncated", False)),
            next_cursor=pagination_meta.get("next_cursor"),
            truncation_message=pagination_meta.get("truncation_message"),
        ),
    ).model_dump()
    full_output = _json_dumps(payload)
    if _estimate_tokens(full_output) <= max_tokens:
        return None

    artifact_path = _write_token_protection_artifact(full_output)
    lines = full_output.splitlines()
    truncation_payload = _build_truncation_payload(
        full_path=str(artifact_path),
        full_output_lines=lines,
        max_tokens=max_tokens,
    )
    return {
        "mode": "token_limit",
        "result": truncation_payload,
        "meta": {
            "tool": _get_tool_id(ctx),
            "version": app_version,
            "duration_ms": duration_ms,
            "dry_run": bool(getattr(ctx.obj, "dry_run", False)),
            "warnings": payload["meta"]["warnings"],
            "annotations": annotation_hints,
            "truncated": True,
            "next_cursor": pagination_meta.get("next_cursor"),
            "truncation_message": pagination_meta.get("truncation_message")
            or f"Output token estimate exceeded {max_tokens}.",
        },
    }


def _extract_pagination_flags(ctx: click.Context, *, paginated: bool) -> PaginationParams:
    if not paginated:
        return PaginationParams()

    return PaginationParams.from_flags(
        limit=ctx.meta.get("tooli_flag_limit"),
        cursor=ctx.meta.get("tooli_flag_cursor"),
        fields=ctx.meta.get("tooli_flag_fields"),
        filter=ctx.meta.get("tooli_flag_filter"),
        max_items=ctx.meta.get("tooli_flag_max_items"),
        select=ctx.meta.get("tooli_flag_select"),
    )


def _apply_field_filter(value: Any, fields: list[str]) -> Any:
    if not fields:
        return value

    if isinstance(value, dict):
        return {name: value[name] for name in fields if name in value}

    if isinstance(value, list):
        return [_apply_field_filter(item, fields) for item in value]

    return value


def _apply_filter(value: list[Any], key: str, expected: str) -> list[Any]:
    filtered: list[Any] = []
    for item in value:
        if not isinstance(item, dict):
            filtered.append(item)
            continue
        if str(item.get(key)) == expected:
            filtered.append(item)
    return filtered


def _apply_pagination(
    value: Any,
    params: PaginationParams,
) -> tuple[Any, dict[str, Any]]:
    if not isinstance(value, list):
        return _apply_field_filter(value, params.fields), {}

    items = value
    filtered_items = items
    filter_expr = params.filter_expr()
    if filter_expr is not None:
        filter_key, filter_value = filter_expr
        filtered_items = _apply_filter(filtered_items, filter_key, filter_value)

    if params.should_filter_fields():
        filtered_items = _apply_field_filter(filtered_items, params.fields)

    start = params.cursor
    if start > len(filtered_items):
        start = len(filtered_items)

    limit = params.limit
    max_items = params.max_items
    if limit is None and max_items is None:
        page = filtered_items[start:]
        return page, {"truncated": False}

    if limit is None: # noqa: SIM108
        page_size = max_items
    else:
        page_size = limit

    if max_items is not None:
        page_size = min(page_size, max_items)  # type: ignore[type-var]

    end = start + page_size  # type: ignore[operator]
    page = filtered_items[start:end]
    truncated = len(filtered_items) > end
    meta: dict[str, Any] = {
        "truncated": truncated,
        "next_cursor": str(end) if truncated else None,
        "truncation_message": (
            f"Use --cursor {end} to fetch the next page." if truncated else None
        ),
    }
    return page, meta


def _strip_annotated(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is not None and getattr(origin, "__name__", None) == "Annotated":
        args = get_args(annotation)
        if args:
            return args[0]
    return annotation


def _is_list_annotation(annotation: Any) -> bool:
    annotation = _strip_annotated(annotation)
    if annotation is inspect.Parameter.empty:
        return False

    if annotation in (list, tuple, set, Iterable):
        return True

    origin = get_origin(annotation)
    if origin in (list, tuple, set):
        return True

    if origin in (types.UnionType, getattr(types, "UnionType", object)) or str(origin).endswith(".Union'>"):
        optional_args = [arg for arg in get_args(annotation) if arg is not None]
        return any(_is_list_annotation(arg) for arg in optional_args)

    return False


def _is_list_value_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, set)): # noqa: UP038
        return len(value) == 0
    return False


def _parse_null_delimited_input() -> list[str]:
    if sys.stdin.isatty():
        return []

    raw = sys.stdin.read()
    if not raw:
        return []

    return [entry for entry in raw.split("\0") if entry]


def _extract_validation_details(message: str) -> dict[str, Any]:
    """Return machine-oriented fields for CLI parser failures."""
    normalized = (message or "").strip()
    lowered = normalized.lower()
    details: dict[str, Any] = {
        "expected": [],
        "received": [],
        "retry_hint": "Check argument names and required values, then rerun.",
    }

    def _normalize_token(value: str) -> str:
        return value.strip(" '\"").lstrip("-")

    missing_argument = re.search(r"Missing argument '?([A-Za-z0-9_\\-]+)'?", normalized)
    if missing_argument:
        details["expected"] = [_normalize_token(missing_argument.group(1)).lower()]
        details["retry_hint"] = f"Provide required argument(s): {missing_argument.group(1)}."
        return details

    missing_option = re.search(r"Missing option '?(-{1,2}[A-Za-z0-9_\\-]+)'?", normalized)
    if missing_option:
        details["expected"] = [_normalize_token(missing_option.group(1))]
        details["retry_hint"] = f"Provide the {missing_option.group(1)} option."
        return details

    option_value = re.search(r"Missing parameter for option (?P<option>.+)", normalized)
    if option_value:
        details["expected"] = [option_value.group("option")]
        details["retry_hint"] = f"Provide a value for {option_value.group('option')}."
        return details

    unknown_option = re.search(r"No such option: ([^\\n]+)", normalized)
    if unknown_option:
        details["expected"] = "valid option"
        details["retry_hint"] = f"Remove or replace unsupported option {unknown_option.group(1)}."
        return details

    unexpected = re.search(r"Unexpected extra argument(.*)", normalized)
    if unexpected:
        extra = unexpected.group(1).strip(" :") or ""
        if extra:
            details["received"] = [extra]
        details["retry_hint"] = "Remove extra positional arguments and rerun."
        return details

    if lowered.startswith("invalid value for"):
        details["retry_hint"] = "Correct the value format and rerun."

    if lowered.startswith("got unexpected extra argument"):
        details["retry_hint"] = "Remove unsupported trailing arguments."

    return details


def _build_validation_input_error(message: str) -> InputError:
    """Build deterministic InputError for parser/validation failures."""
    details = _extract_validation_details(message)
    return InputError(
        message=message,
        code="E1001",
        suggestion=Suggestion(
            action="fix_argument_or_option",
            fix="Check required arguments and option names against --help output.",
            example="my-tool command --help",
        ),
        details=details,
    )


def _evaluate_python_payload(code: str, *, command_name: str) -> dict[str, Any]:
    stripped = code.strip()
    if not stripped:
        return {}

    try:
        tree = ast.parse(stripped, mode="eval")
    except SyntaxError as e:
        raise InputError(
            message=(
                f"{command_name}: python-eval input must be a valid expression."
            ),
            code="E1005",
            details={"error": str(e)},
        ) from e

    allowed_builtins = {
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "len": len,
        "list": list,
        "dict": dict,
        "min": min,
        "max": max,
        "sum": sum,
        "sorted": sorted,
    }

    try:
        value = eval(compile(tree, filename="<agent-python-eval>", mode="eval"), {"__builtins__": allowed_builtins}, {})
    except Exception as e:
        raise InputError(
            message=f"{command_name}: failed to evaluate python-eval payload.",
            code="E1006",
            details={"error": str(e)},
        ) from e

    if not isinstance(value, dict):
        raise InputError(
            message=f"{command_name}: python-eval payload must evaluate to a mapping.",
            code="E1007",
            details={"value_type": type(value).__name__},
        )

    return value


def _resolve_null_input_arg(ctx: click.Context) -> str | None:
    command = getattr(ctx, "command", None)
    if command is None:
        return None

    params = getattr(ctx, "params", {})
    if not isinstance(params, dict):
        return None

    callback = getattr(command, "callback", None)
    if not _is_list_processing_command(callback):
        return None

    if callback is None:
        return None

    for name, param in inspect.signature(callback).parameters.items():
        if name not in params:
            continue
        if name in ("ctx", "self", "cls"):
            continue
        if _is_list_annotation(param.annotation) and _is_list_value_empty(params[name]):
            return name

    return None


def _apply_python_eval_inputs(
    callback: Callable[..., Any],
    ctx: click.Context,
    *,
    command_name: str,
    allow_python_eval: bool,
) -> None:
    if not allow_python_eval or sys.stdin.isatty():
        return

    if not ctx.meta.get("tooli_flag_python_eval", False):
        return

    payload = _evaluate_python_payload(sys.stdin.read(), command_name=command_name)
    if not payload:
        return

    signature = inspect.signature(callback)
    for param_name, param in signature.parameters.items():
        if param_name in ("ctx", "self", "cls"):
            continue
        if param_name in payload:
            value = payload[param_name]
            ctx.params[param_name] = value
        elif param_name in ctx.params and param.default is inspect.Parameter.empty:
            # Let invocation-time validation surface missing required values.
            continue

def _render_list_output(values: Iterable[Any], *, delimiter: str) -> str:
    return delimiter.join(str(item) for item in values)


def _needs_human_confirmation(
    policy: SecurityPolicy,
    *,
    is_destructive: bool,
    requires_approval: bool,
    has_human_in_the_loop: bool,
    force: bool,
    yes_override: bool,
    is_agent_caller: bool = False,
) -> bool:
    if not is_destructive and not requires_approval:
        return False
    if force:
        return False
    if requires_approval:
        return True
    if policy == SecurityPolicy.OFF:
        return False
    if policy == SecurityPolicy.STRICT and has_human_in_the_loop:
        return True
    # When an agent is calling and --yes was passed, skip confirmation
    if is_agent_caller and yes_override:
        return False
    return not yes_override


def _enforce_authorization(
    *,
    auth_context: AuthContext | None,
    required_scopes: list[str],
) -> None:
    if not required_scopes:
        return

    active_scopes = set(auth_context.scopes if auth_context is not None else [])
    missing_scopes = [scope for scope in required_scopes if scope not in active_scopes]
    if missing_scopes:
        raise AuthError(
            message="Missing required scopes for command.",
            code="E2001",
            details={
                "required_scopes": required_scopes,
                "missing_scopes": missing_scopes,
                "active_scopes": sorted(active_scopes),
            },
        )


def _audit_security_event(ctx: click.Context, *, event: str, details: dict[str, Any]) -> None:
    payload = {
        "event": "tooli.security",
        "type": event,
        "command": _get_tool_id(ctx),
        "details": details,
    }
    click.echo(json.dumps(payload, sort_keys=True), err=True)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _build_parser_error_payload(
    *,
    command_name: str,
    app_version: str,
    start_time: float,
    error: InputError,
) -> str:
    meta = EnvelopeMeta(
        tool=command_name,
        version=app_version,
        duration_ms=max(1, int((time.perf_counter() - start_time) * 1000)),
        warnings=[],
    )
    envelope = Envelope(ok=False, result=None, meta=meta)
    payload = envelope.model_dump()
    payload["error"] = error.to_dict()
    return _json_dumps(payload)


def _emit_parser_error(
    message: str,
    *,
    command_name: str,
    app_version: str,
    start_time: float,
    code: str,
) -> None:
    if code == "E1001":
        error = _build_validation_input_error(message)
    else:
        error = InputError(
            message=message,
            code=code,
            details=_extract_validation_details(message),
        )
    click.echo(_build_parser_error_payload(
        command_name=command_name,
        app_version=app_version,
        start_time=start_time,
        error=error,
    ))


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


def _build_envelope_meta(
    ctx: click.Context,
    *,
    app_version: str,
    duration_ms: int,
    annotations: dict[str, Any] | None = None,
    truncated: bool = False,
    next_cursor: str | None = None,
    truncation_message: str | None = None,
    output_schema: dict[str, Any] | None = None,
) -> EnvelopeMeta:
    warnings: list[str] = []
    command = getattr(ctx, "command", None)
    if command is not None:
        callback_obj = getattr(command, "callback", None)
        meta = get_command_meta(callback_obj)
        if meta.deprecated:
            if meta.deprecated_message:
                warnings.append(str(meta.deprecated_message))
            else:
                warnings.append("This command is deprecated.")

    from tooli.detect import _get_context
    detection = _get_context()

    return EnvelopeMeta(
        tool=_get_tool_id(ctx),
        version=app_version,
        duration_ms=duration_ms,
        dry_run=bool(getattr(getattr(ctx, "obj", None), "dry_run", False)),
        warnings=warnings,
        annotations=annotations,
        truncated=truncated,
        next_cursor=next_cursor,
        truncation_message=truncation_message,
        caller_id=detection.caller_id,
        caller_version=detection.caller_version,
        session_id=detection.session_id,
        output_schema=output_schema,
    )


class TooliCommand(TyperCommand):
    """TyperCommand subclass with Tooli global flags and output routing."""

    def main(  # type: ignore[override]
        self,
        args: list[str] | None = None,
        prog_name: str | None = None,
        complete_var: str | None = None,
        standalone_mode: bool = True,
        windows_expand_args: bool = True,
        **extra: Any,
    ) -> Any:
        start_time = time.perf_counter()
        try:
            return super().main(
                args=args,
                prog_name=prog_name,
                complete_var=complete_var,
                standalone_mode=False,
                windows_expand_args=windows_expand_args,
                **extra,
            )
        except click.UsageError as exc:
            if not standalone_mode:
                raise

            if not _is_agent_mode():
                exc.show()
                raise SystemExit(_normalize_system_exit(exc.exit_code)) from exc

            cb_meta = get_command_meta(self.callback)
            _emit_parser_error(
                exc.format_message(),
                command_name=self.name or "tooli",
                app_version=cb_meta.app_version or "0.0.0",
                start_time=start_time,
                code="E1001",
            )
            raise SystemExit(_normalize_system_exit(exc.exit_code)) from exc
        except click.ClickException as exc:
            if not standalone_mode:
                raise

            if not _is_agent_mode():
                exc.show()
                raise SystemExit(_normalize_system_exit(exc.exit_code)) from exc

            cb_meta = get_command_meta(self.callback)
            _emit_parser_error(
                exc.format_message(),
                command_name=self.name or "tooli",
                app_version=cb_meta.app_version or "0.0.0",
                start_time=start_time,
                code="E1002",
            )
            raise SystemExit(_normalize_system_exit(exc.exit_code)) from exc

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
                    ["--print0"],
                    is_flag=True,
                    help="Emit NUL-delimited output for list results in text/plain modes.",
                    expose_value=False,
                    callback=_capture_tooli_flags,
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
                    ["--force"],
                    is_flag=True,
                    help="Force execution of destructive commands.",
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
                    ["--idempotency-key"],
                    type=str,
                    help="Idempotency key for safe retries.",
                    expose_value=False,
                    callback=_capture_tooli_flags,
                ),
                click.Option(
                    ["--null"],
                    is_flag=True,
                    help="Parse null-delimited stdin lists for list-processing commands.",
                    expose_value=False,
                    callback=_capture_tooli_flags,
                ),
                click.Option(
                    ["--python-eval"],
                    is_flag=True,
                    help="Evaluate stdin as a Python expression and inject the returned mapping as arguments.",
                    expose_value=False,
                    hidden=True,
                    callback=_capture_tooli_flags,
                ),
            ]
        )

        if _is_paginated_command(kwargs.get("callback")):
            params.extend(
                [
                    click.Option(
                        ["--limit"],
                        type=click.IntRange(min=1),
                        help="Maximum number of items to return.",
                        expose_value=False,
                        callback=_capture_tooli_flags,
                    ),
                    click.Option(
                        ["--cursor"],
                        type=str,
                        help="Cursor token for the next page.",
                        expose_value=False,
                        callback=_capture_tooli_flags,
                    ),
                    click.Option(
                        ["--fields", "--select"],
                        type=str,
                        help="Comma-separated list of top-level output fields.",
                        expose_value=False,
                        callback=_capture_tooli_flags,
                    ),
                    click.Option(
                        ["--filter"],
                        type=str,
                        help="Filter list items using key=value.",
                        expose_value=False,
                        callback=_capture_tooli_flags,
                    ),
                    click.Option(
                        ["--max-items"],
                        type=click.IntRange(min=1),
                        help="Maximum number of list items to emit.",
                        expose_value=False,
                        callback=_capture_tooli_flags,
                    ),
                ]
            )

        params.extend(
            [
                click.Option(
                    ["--agent-manifest"],
                    is_flag=True,
                    help="Emit agent manifest JSON payload.",
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
    def _yaml_value(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        return json.dumps(str(value))

    @staticmethod
    def _render_help_agent_output(ctx: click.Context) -> str:
        if ctx.command is None:
            return ""

        from tooli.schema import generate_tool_schema

        command = ctx.command
        lines = [
            f"command: {command.name or ctx.info_name or 'tooli'}",
            f"description: {(command.help or command.get_short_help_str(100) or '').strip()}",
        ]

        params = [p for p in command.params if p.expose_value]
        lines.append("params:")
        for param in params:
            if isinstance(param, click.Option):
                names = param.opts + param.secondary_opts if (param.opts or param.secondary_opts) else [param.name or "option"]
                names = [name.replace("--", "") for name in names]
            else:
                names = [param.name or "arg"]

            if isinstance(param.type, click.Choice):
                param_type = "choice"
            elif param.type and param.type.name:
                param_type = str(param.type.name)
            else:
                param_type = "unknown"

            lines.append("  - name: " + ", ".join(sorted(set(names))))
            lines.append(f"    type: {param_type}")
            lines.append(f"    required: {TooliCommand._yaml_value(bool(getattr(param, 'required', False)))}")

            if not isinstance(param, click.Argument):
                lines.append(f"    default: {TooliCommand._yaml_value(param.default)}")

            if getattr(param, "help", None):
                lines.append(f"    help: {TooliCommand._yaml_value(param.help)}")

        if params:
            lines.append("")

        callback = getattr(ctx.command, "callback", None)
        cb_meta = get_command_meta(callback)

        if cb_meta.auth:
            lines.append("auth:")
            for item in cb_meta.auth:
                lines.append(f"  - {item}")

        labels = _annotation_labels(callback)
        if labels:
            lines.append("behavior:")
            for item in labels:
                lines.append(f"  - {item}")

        schema = generate_tool_schema(callback, name=ctx.command.name or "command") if callback else None
        if schema and schema.output_schema:
            lines.append("output: " + TooliCommand._yaml_value(json.dumps(schema.output_schema, separators=(",", ":"))))

        if cb_meta.cost_hint:
            lines.append(f"cost_hint: {TooliCommand._yaml_value(str(cb_meta.cost_hint))}")

        if cb_meta.max_tokens is not None:
            lines.append(f"max_tokens: {TooliCommand._yaml_value(cb_meta.max_tokens)}")

        if cb_meta.requires_approval:
            lines.append("requires_approval: true")

        if cb_meta.danger_level:
            lines.append(f"danger_level: {TooliCommand._yaml_value(str(cb_meta.danger_level))}")

        if cb_meta.human_in_the_loop:
            lines.append("human_in_the_loop: true")

        if cb_meta.allow_python_eval:
            lines.append("allow_python_eval: true")

        if cb_meta.error_codes:
            lines.append("errors:")
            for code, message in sorted(cb_meta.error_codes.items(), key=lambda item: item[0]):
                lines.append(f"  - \"{code}\"")

        if cb_meta.examples:
            example = cb_meta.examples[0]
            example_args = example.get("args", [])
            example_text = ""
            if isinstance(example_args, list):
                example_text = " ".join(str(arg) for arg in example_args if arg is not None).strip()
            if example_text:
                lines.append(f"example: {TooliCommand._yaml_value(example_text)}")

        return "\n".join(lines)

    def _append_behavior_help_line(self, lines: list[str], command: click.Command) -> None:
        labels = _annotation_labels(getattr(command, "callback", None))
        if not labels:
            return
        lines.append(f"Behavior: [{', '.join(labels)}]")

    def get_help(self, ctx: click.Context) -> str:
        if ctx.command is None:
            return super().get_help(ctx)

        # When an identified agent requests --help, prefer structured output
        from tooli.detect import _get_context
        detection = _get_context()
        if detection.is_agent and detection.identified_via_convention:
            return self._render_help_agent_output(ctx)

        lines = super().get_help(ctx).splitlines()
        self._append_behavior_help_line(lines, ctx.command)
        return "\n".join(lines)

    def invoke(self, ctx: click.Context) -> Any:
        _, app_version, app_default_output, telemetry_pipeline, invocation_recorder, security_policy = _get_app_meta_from_callback(
            self.callback
        )
        cb_meta = get_command_meta(self.callback)
        required_scopes = list(cb_meta.auth)
        max_tokens = cb_meta.max_tokens
        auth_context = cb_meta.auth_context
        requires_approval = bool(cb_meta.requires_approval)
        danger_level = cb_meta.danger_level
        allow_python_eval = bool(cb_meta.allow_python_eval)

        # Initialize ToolContext and store in ctx.obj for callback access.
        ctx.obj = ToolContext(
            quiet=bool(ctx.meta.get("tooli_flag_quiet", False)),
            verbose=int(ctx.meta.get("tooli_flag_verbose", 0)),
            dry_run=bool(ctx.meta.get("tooli_flag_dry_run", False)),
            force=bool(ctx.meta.get("tooli_flag_force", False)),
            yes=bool(ctx.meta.get("tooli_flag_yes", False)),
            timeout=ctx.meta.get("tooli_flag_timeout"),
            auth=auth_context,
            idempotency_key=ctx.meta.get("tooli_flag_idempotency_key"),
            response_format=resolve_response_format(ctx).value,
        )

        if bool(ctx.meta.get("tooli_flag_help_agent", False)):
            click.echo(self._render_help_agent_output(ctx))
            return None

        if bool(ctx.meta.get("tooli_flag_agent_manifest", False)):
            cb_meta = get_command_meta(self.callback)
            app = cb_meta.app
            if app is None:
                raise click.ClickException("Unable to resolve application metadata for --agent-manifest.")

            from tooli.manifest import generate_agent_manifest

            click.echo(json.dumps(generate_agent_manifest(app), indent=2))
            ctx.exit(int(ExitCode.SUCCESS))

        if bool(ctx.meta.get("tooli_flag_schema", False)):
            from tooli.schema import generate_tool_schema

            schema = generate_tool_schema(self.callback, name=_get_tool_id(ctx), required_scopes=required_scopes)  # type: ignore[arg-type]
            if self.callback:
                schema.annotations = _extract_annotation_hints(self.callback)
                if cb_meta.cost_hint:
                    schema.cost_hint = str(cb_meta.cost_hint)
                schema.examples = list(cb_meta.examples)

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
        used_cached_result = False

        mode = resolve_output_mode(ctx)
        no_color = resolve_no_color(ctx)
        command_name = _get_tool_id(ctx)
        idempotency_key = ctx.meta.get("tooli_flag_idempotency_key")
        list_processing = _is_list_processing_command(self.callback)
        print0_output = bool(ctx.meta.get("tooli_flag_print0", False))
        is_idempotent = _is_idempotent_command(self.callback)
        paginated = _is_paginated_command(self.callback)
        pagination_params = _extract_pagination_flags(ctx, paginated=paginated)
        start = time.perf_counter()
        timer_active = False
        ctx.meta.setdefault("tooli_secret_values", [])
        annotation_hints = _extract_annotation_hints(self.callback)

        def _observation_args() -> dict[str, Any]:
            args = _collect_invocation_args(ctx)
            for secret_name in getattr(self, "_tooli_secret_params", []):
                if secret_name in args:
                    args[secret_name] = "********"
            if idempotency_key:
                args["idempotency_key"] = idempotency_key
            return args

        command_span = start_command_span(command=command_name, arguments=_observation_args())

        def _enforce_security_policy() -> None:
            if security_policy == SecurityPolicy.OFF and not requires_approval:
                return

            is_destructive = _is_destructive_command(self.callback)
            if not is_destructive and not requires_approval:
                return

            confirmation_label = "high-risk" if requires_approval else "destructive"
            if danger_level:
                confirmation_label = f"{danger_level} risk"

            has_human_in_the_loop = cb_meta.human_in_the_loop
            from tooli.detect import _get_context as _detect_ctx
            confirm_needed = _needs_human_confirmation(
                policy=security_policy,
                is_destructive=True,
                requires_approval=requires_approval,
                has_human_in_the_loop=has_human_in_the_loop,
                force=ctx.obj.force,
                yes_override=ctx.obj.yes,
                is_agent_caller=_detect_ctx().is_agent,
            )

            if not confirm_needed:
                if ctx.obj.force:
                    _audit_security_event(
                        ctx,
                        event="destructive_override",
                        details={"policy": security_policy.value, "override": "force"},
                    )
                elif ctx.obj.yes:
                    _audit_security_event(
                        ctx,
                        event="destructive_override",
                        details={"policy": security_policy.value, "override": "yes"},
                    )
                else:
                    _audit_security_event(
                        ctx,
                        event="destructive_confirmed",
                        details={"policy": security_policy.value},
                    )
                return

            _audit_security_event(
                ctx,
                event="destructive_confirmation_required",
                details={
                    "policy": security_policy.value,
                    "human_in_the_loop": has_human_in_the_loop,
                    "reason": confirmation_label,
                },
            )
            if security_policy == SecurityPolicy.STRICT and has_human_in_the_loop:
                confirm = ctx.obj.confirm(
                    message=f"This command is {confirmation_label} and requires manual confirmation.",
                    default=False,
                    allow_yes_override=False,
                )
            else:
                confirm = ctx.obj.confirm(
                    message=f"This command is {confirmation_label} and requires manual confirmation.",
                    default=False,
                )

            if not confirm:
                _audit_security_event(ctx, event="destructive_denied", details={"policy": security_policy.value})
                raise InputError(message="Destructive command not confirmed.", code="E2003")

        def _authorize() -> None:
            _enforce_authorization(auth_context=auth_context, required_scopes=required_scopes)

        def _enforce_capabilities() -> None:
            if security_policy != SecurityPolicy.STRICT:
                return
            capabilities = list(cb_meta.capabilities)
            if not capabilities:
                return
            allowed_raw = os.environ.get("TOOLI_ALLOWED_CAPABILITIES", "")
            if not allowed_raw:
                return  # No allowlist set — skip enforcement
            allowed = {c.strip() for c in allowed_raw.split(",") if c.strip()}
            denied = [c for c in capabilities if c not in allowed and not any(c.startswith(a.rstrip(":*") + ":") for a in allowed if a.endswith(":*"))]
            if denied:
                _audit_security_event(
                    ctx,
                    event="capability_violation",
                    details={"denied": denied, "required": capabilities, "allowed": sorted(allowed)},
                )
                raise AuthError(
                    message=f"Capability not allowed: {', '.join(denied)}",
                    code="E2002",
                    details={"denied_capabilities": denied, "required_capabilities": capabilities},
                )

        def _check_idempotency() -> None:
            nonlocal result, used_cached_result
            if not idempotency_key:
                return

            record = get_record(command=command_name, idempotency_key=str(idempotency_key))
            if record is None:
                return

            if is_idempotent and record.has_cached_result:
                used_cached_result = True
                result = record.result
                return

            raise InputError(
                message="Duplicate idempotency key requires command to be marked idempotent.",
                code="E1004",
                details={"command": command_name, "idempotency_key": idempotency_key},
            )

        # Handle timeout if specified.
        def _timeout_handler(signum: int, frame: Any) -> None:
            del signum, frame
            raise ToolRuntimeError(
                message=f"Command timed out after {ctx.obj.timeout} seconds",
                code="E4001",
                exit_code=ExitCode.TIMEOUT_EXPIRED,
            )

        if ctx.obj.timeout and ctx.obj.timeout > 0 and hasattr(signal, "SIGALRM"):
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, ctx.obj.timeout)
            timer_active = True

        def _emit_telemetry(*, success: bool, error: ToolError | None = None, exit_code: int | None = None) -> None:
            elapsed_ms = otel_duration_ms(start)
            if telemetry_pipeline is None:
                command_span.set_outcome(
                    exit_code=0 if exit_code is None else exit_code,
                    error_category=None if error is None else error.category.value,
                    duration_ms=elapsed_ms,
                )
                return

            telemetry_pipeline.record(
                command=command_name,
                success=success,
                duration_ms=elapsed_ms,
                exit_code=exit_code,
                error_code=None if error is None else error.code,
                error_category=None if error is None else error.category.value,
            )
            command_span.set_outcome(
                exit_code=0 if exit_code is None else exit_code,
                error_category=None if error is None else error.category.value,
                duration_ms=elapsed_ms,
            )

        from tooli.detect import _get_context as _detect_get_context
        _detection = _detect_get_context()
        command_span.set_caller(
            caller_id=_detection.caller_id,
            caller_version=_detection.caller_version,
            session_id=_detection.session_id,
        )

        def _emit_invocation(*, status: str, error_code: str | None = None, exit_code: int | None = None) -> None:
            if invocation_recorder is None:
                return

            args = redact_secret_values(_collect_invocation_args(ctx), ctx.meta.get("tooli_secret_values", []))
            if idempotency_key:
                args["idempotency_key"] = idempotency_key
            invocation_recorder.record(
                command=command_name,
                args=args,
                status=status,
                duration_ms=int((time.perf_counter() - start) * 1000),
                error_code=error_code,
                exit_code=exit_code,
                caller_id=_detection.caller_id,
                session_id=_detection.session_id,
            )

        try:
            _check_idempotency()
            if ctx.meta.get("tooli_flag_null"):
                list_arg = _resolve_null_input_arg(ctx)
                if list_arg is not None:
                    parsed = _parse_null_delimited_input()  # type: ignore[assignment]
                    if parsed:
                        ctx.params[list_arg] = parsed  # type: ignore[assignment]

            if not used_cached_result:
                _apply_python_eval_inputs(
                    self.callback,  # type: ignore[arg-type]
                    ctx,
                    command_name=command_name,
                    allow_python_eval=allow_python_eval,
                )
                _authorize()
                _enforce_capabilities()
                _enforce_security_policy()

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

                command_span.set_arguments(
                    redact_secret_values(_collect_invocation_args(ctx), ctx.meta.get("tooli_secret_values", []))
                )

                try:
                    result = super().invoke(ctx)
                except ToolError:
                    raise
                except click.UsageError as e:
                    # Map Click usage errors to InputError (exit code 2).
                    raise _build_validation_input_error(str(e)) from e
                except click.ClickException as e:
                    message = e.format_message()
                    details = _extract_validation_details(message)
                    raise InputError(
                        message=message,
                        code="E1002",
                        details=details,
                    ) from e
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
            return self._handle_tool_error(
                ctx,
                app_version,
                start,
                e,
                mode,
                no_color,
                security_policy=security_policy,
            )
        except SystemExit as e:
            exit_code = _normalize_system_exit(e.code)
            _emit_invocation(status="error", exit_code=exit_code)
            _emit_telemetry(success=(exit_code == 0), exit_code=exit_code)
            raise SystemExit(exit_code) from e
        finally:
            if timer_active:
                signal.setitimer(signal.ITIMER_REAL, 0)

        if idempotency_key and not used_cached_result:
            set_record(
                command=command_name,
                idempotency_key=str(idempotency_key),
                has_cached_result=is_idempotent,
                result=result,
            )

        duration_ms = int((time.perf_counter() - start) * 1000)

        if result is None:
            _emit_invocation(status="success", exit_code=0)
            _emit_telemetry(success=True, exit_code=0)
            return None

        result = redact_secret_values(result, ctx.meta.get("tooli_secret_values", []))
        if security_policy != SecurityPolicy.OFF:
            result = sanitize_output(result)

        pagination_meta: dict[str, Any] = {}
        if paginated:
            result, pagination_meta = _apply_pagination(result, pagination_params)

        _emit_invocation(status="success", exit_code=0)
        _emit_telemetry(success=True, exit_code=0)
        truncated_envelope = _maybe_emit_token_limited_json(
            result=result,
            mode=mode,
            ctx=ctx,
            app_version=app_version or "0.0.0",
            duration_ms=duration_ms,
            annotation_hints=annotation_hints,
            pagination_meta=pagination_meta,
            max_tokens=max_tokens,
        )

        if truncated_envelope is not None:
            click.echo(_json_dumps(truncated_envelope))
            return result

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
            if list_processing and isinstance(result, Iterable) and not isinstance(result, (dict, str, bytes, bytearray)): # noqa: UP038
                delimiter = "\0" if print0_output else "\n"
                click.echo(_render_list_output(result, delimiter=delimiter), nl=not print0_output)
            else:
                click.echo(str(result))
            return result

        if mode in (OutputMode.JSON, OutputMode.JSONL):
            # Include output schema in detailed mode or when explicitly requested
            _output_schema: dict[str, Any] | None = None
            _include_schema = (
                resolve_response_format(ctx) == ResponseFormat.DETAILED
                or os.environ.get("TOOLI_INCLUDE_SCHEMA", "").lower() in {"1", "true", "yes"}
            )
            if _include_schema:
                _output_schema = cb_meta.output_schema
                if _output_schema is None:
                    # Infer from return annotation
                    import inspect as _inspect

                    from tooli.schema import _infer_output_schema
                    try:
                        _hints = get_type_hints(self.callback, include_extras=True)  # type: ignore[arg-type]
                    except Exception:
                        _hints = {}
                    _sig = _inspect.signature(self.callback)  # type: ignore[arg-type]
                    _return_ann = _hints.get("return", _sig.return_annotation)
                    _output_schema = _infer_output_schema(_return_ann, cb_meta.output_example)

            meta = _build_envelope_meta(
                ctx,
                app_version=app_version or "0.0.0",
                duration_ms=duration_ms,
                annotations=annotation_hints,
                truncated=bool(pagination_meta.get("truncated", False)),
                next_cursor=pagination_meta.get("next_cursor"),
                truncation_message=pagination_meta.get("truncation_message"),
                output_schema=_output_schema,
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
        *,
        security_policy: SecurityPolicy = SecurityPolicy.OFF,
    ) -> None:
        annotations = _extract_annotation_hints(getattr(ctx.command, "callback", None))
        secret_values = ctx.meta.get("tooli_secret_values", [])
        if mode in (OutputMode.JSON, OutputMode.JSONL, OutputMode.AUTO) and not click.get_text_stream("stdout").isatty():
            meta = _build_envelope_meta(
                ctx,
                app_version=app_version,
                duration_ms=int((time.perf_counter() - start) * 1000),
                annotations=annotations,
            )
            env = Envelope(ok=False, result=None, meta=meta)
            out = env.model_dump()
            out["error"] = redact_secret_values(error.to_dict(), secret_values)
            if security_policy != SecurityPolicy.OFF:
                out = sanitize_output(out)
            click.echo(_json_dumps(out))
        else:
            message = redact_secret_values(error.message, secret_values)
            suggestion = ""
            if error.suggestion:
                suggestion = redact_secret_values(error.suggestion.fix, secret_values)
            if security_policy != SecurityPolicy.OFF:
                message = sanitize_output(message)
                suggestion = sanitize_output(suggestion)
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
