"""Optional OpenTelemetry instrumentation for command execution."""

from __future__ import annotations

import importlib
import json
import os
import time
from typing import Any


def _parse_bool_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _load_opentelemetry_trace() -> Any:
    return importlib.import_module("opentelemetry.trace")


def _is_enabled() -> bool:
    return _parse_bool_env(os.getenv("TOOLI_OTEL_ENABLED"))


def _serialize_arguments(arguments: dict[str, Any] | None) -> str:
    if not arguments:
        return "{}"

    return json.dumps(arguments, sort_keys=True, default=str, ensure_ascii=False, separators=(",", ":"))


class _NoopCommandSpan:
    """Safe-op span handle used when OTel is disabled or unavailable."""

    def set_arguments(self, arguments: dict[str, Any] | None) -> None:
        del arguments

    def set_outcome(self, *, exit_code: int, error_category: str | None, duration_ms: int) -> None:
        del exit_code, error_category, duration_ms


class _ActiveCommandSpan:
    def __init__(self, command: str, span: Any) -> None:
        self._span = span
        self._ended = False
        self._span.set_attribute("tooli.command", command)

    def set_arguments(self, arguments: dict[str, Any] | None) -> None:
        self._span.set_attribute("tooli.arguments", _serialize_arguments(arguments))

    def set_outcome(self, *, exit_code: int, error_category: str | None, duration_ms: int) -> None:
        if self._ended:
            return

        self._span.set_attribute("tooli.duration_ms", duration_ms)
        self._span.set_attribute("tooli.exit_code", exit_code)
        self._span.set_attribute("tooli.error_category", error_category or "none")

        if exit_code != 0:
            try:
                from opentelemetry.trace import (  # type: ignore[import-not-found]
                    Status,
                    StatusCode,
                )

                self._span.set_status(Status(StatusCode.ERROR, f"exit_code={exit_code}"))
            except Exception:
                # API may vary across versions; keep telemetry best effort.
                self._span.set_attribute("tooli.status", "error")

        self._span.end()
        self._ended = True


def start_command_span(*, command: str, arguments: dict[str, Any] | None = None) -> _NoopCommandSpan | _ActiveCommandSpan:
    """Create and return an OpenTelemetry span handle for a command execution."""

    if not _is_enabled():
        return _NoopCommandSpan()

    try:
        trace = _load_opentelemetry_trace()
        tracer = trace.get_tracer("tooli")
        raw_span = tracer.start_span("tooli.command")
        span = _ActiveCommandSpan(command=command, span=raw_span)
        span.set_arguments(arguments)
        return span
    except Exception:
        return _NoopCommandSpan()


def duration_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
