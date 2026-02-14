"""Invocation recording for command executions."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


DEFAULT_EVAL_DIR = Path.home() / ".config" / "tooli" / "eval"
DEFAULT_EVAL_FILE = "invocations.jsonl"
SCHEMA_VERSION = 1


def _parse_record_path(value: str | None) -> Path | None:
    """Resolve the TOOLI_RECORD value to a JSONL file path."""

    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    return Path(candidate).expanduser()


def _default_record_path() -> Path:
    return DEFAULT_EVAL_DIR / DEFAULT_EVAL_FILE


def _resolve_record_path(record: bool | str | None) -> Path | None:
    if isinstance(record, str):
        return Path(record).expanduser()
    if isinstance(record, bool):
        return _default_record_path() if record else None
    return _parse_record_path(os.getenv("TOOLI_RECORD"))


def _utc_now() -> float:
    return time.time()


def _to_timestamp(value: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(value))


def _to_serializable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


@dataclass
class InvocationRecord:
    """Serialized payload for a single command invocation."""

    schema_version: int
    recorded_at: str
    command: str
    args: dict[str, Any]
    status: str
    duration_ms: int
    error_code: str | None
    exit_code: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "recorded_at": self.recorded_at,
            "command": self.command,
            "args": self.args,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "error_code": self.error_code,
            "exit_code": self.exit_code,
        }


class InvocationRecorder:
    """Append-only JSONL logging for command invocations."""

    def __init__(
        self,
        *,
        path: Path,
        clock: Callable[[], float] = _utc_now,
    ) -> None:
        self.path = Path(path).expanduser()
        self.clock = clock

    def record(
        self,
        *,
        command: str,
        args: dict[str, Any],
        status: str,
        duration_ms: int,
        error_code: str | None,
        exit_code: int | None,
    ) -> None:
        payload = InvocationRecord(
            schema_version=SCHEMA_VERSION,
            recorded_at=_to_timestamp(self.clock()),
            command=command,
            args={k: _to_serializable(v) for k, v in args.items()},
            status=status,
            duration_ms=duration_ms,
            error_code=error_code,
            exit_code=exit_code,
        )

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(payload.to_dict(), sort_keys=True))
                file.write("\n")
        except OSError:
            return


def build_invocation_recorder(
    *,
    record: bool | str | None = None,
) -> InvocationRecorder | None:
    path = _resolve_record_path(record)
    if path is None:
        return None
    return InvocationRecorder(path=path)
