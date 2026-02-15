"""Dry-run support helpers for Tooli commands."""

from __future__ import annotations

from collections.abc import Callable  # noqa: TC003
from contextvars import ContextVar
from functools import wraps
from typing import Any

import click

from tooli.context import ToolContext

_DRY_RUN_RECORDER: ContextVar[DryRunRecorder | None] = ContextVar(
    "_tooli_dry_run_recorder",
    default=None,
)


def current_dry_run_recorder() -> DryRunRecorder | None:
    """Return the active dry-run recorder, if any."""

    return _DRY_RUN_RECORDER.get()


def record_dry_action(action: str, target: str, details: dict[str, Any] | None = None) -> None:
    """Append an action to the active dry-run recorder when available."""

    recorder = current_dry_run_recorder()
    if recorder is None:
        return
    recorder.record(action=action, target=target, details=details or {})


class DryRunRecorder:
    """Collects planned actions during dry-run execution."""

    def __init__(self) -> None:
        self.actions: list[dict[str, Any]] = []

    def record(self, *, action: str, target: str, details: dict[str, Any] | None = None) -> None:
        self.actions.append(
            {
                "action": action,
                "target": target,
                "details": details or {},
            }
        )

    def to_list(self) -> list[dict[str, Any]]:
        return list(self.actions)


def _find_tooli_context(args: tuple[Any, ...], kwargs: dict[str, Any]) -> click.Context | None:
    """Best-effort extraction of click context from callback arguments."""

    ctx = kwargs.get("ctx")
    if isinstance(ctx, click.Context):
        return ctx

    for value in args:
        if isinstance(value, click.Context):
            return value

    context = click.get_current_context(silent=True)
    if isinstance(context, click.Context):
        return context
    return None


def dry_run_support(callback: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator for commands that should return a dry-run action plan.

    The command runs with an active recorder. When `ctx.obj.dry_run` is True,
    the recorder output is returned as the command result.
    """

    if not callable(callback):
        raise TypeError("dry_run_support must decorate a callable")

    @wraps(callback)
    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        ctx = _find_tooli_context(args, kwargs)
        if ctx is None or ctx.obj is None:
            return callback(*args, **kwargs)

        recorder = DryRunRecorder()
        token = _DRY_RUN_RECORDER.set(recorder)
        try:
            result = callback(*args, **kwargs)
        finally:
            _DRY_RUN_RECORDER.reset(token)

        if isinstance(ctx.obj, ToolContext) and getattr(ctx.obj, "dry_run", False):
            return recorder.to_list()
        return result

    return _wrapped
