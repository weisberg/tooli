"""Optional opt-in telemetry collection for Tooli command invocations."""

from __future__ import annotations

import contextlib
import datetime
import json
import os
import random
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Generator  # noqa: TC003
from dataclasses import dataclass
from io import TextIOWrapper  # noqa: TC003
from pathlib import Path
from typing import Any

try:
    import fcntl as _fcntl
except ImportError:
    _fcntl = None  # type: ignore[assignment]

try:
    import msvcrt as _msvcrt
except ImportError:
    _msvcrt = None  # type: ignore[assignment]


@contextlib.contextmanager
def _file_lock(f: TextIOWrapper) -> Generator[None, None, None]:
    """Acquire an exclusive file lock, cross-platform."""
    if _fcntl is not None:
        _fcntl.flock(f, _fcntl.LOCK_EX)
        try:
            yield
        finally:
            _fcntl.flock(f, _fcntl.LOCK_UN)
    elif _msvcrt is not None:
        _msvcrt.locking(f.fileno(), _msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            _msvcrt.locking(f.fileno(), _msvcrt.LK_UNLCK, 1)
    else:
        yield

DEFAULT_TELEMETRY_DIR = Path.home() / ".config" / "tooli" / "telemetry"
DEFAULT_TELEMETRY_FILE = "events.jsonl"
DEFAULT_RETENTION_DAYS = 30
SCHEMA_VERSION = 1


def _parse_bool_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _utc_now() -> float:
    return time.time()


def _to_timestamp(value: float) -> str:
    return datetime.datetime.fromtimestamp(value, tz=datetime.timezone.utc).isoformat()


def _parse_recorded_at(value: Any) -> float:
    if not isinstance(value, str):
        raise ValueError("Invalid recorded_at value")

    # timezone-naive iso strings are treated as UTC for compatibility.
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.datetime.fromisoformat(value).timestamp()


def _default_telemetry_endpoint() -> str | None:
    return os.getenv("TOOLI_TELEMETRY_ENDPOINT")


def should_enable_telemetry(explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    return _parse_bool_env(os.getenv("TOOLI_TELEMETRY"))


def resolve_telemetry_endpoint(explicit: str | None) -> str | None:
    if explicit is not None:
        return explicit
    return _default_telemetry_endpoint()


@dataclass
class TelemetryRecord:
    """Telemetry payload emitted per command execution."""

    schema_version: int
    recorded_at: str
    app: str
    command: str
    success: bool
    duration_ms: int
    exit_code: int | None = None
    error_code: str | None = None
    error_category: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "recorded_at": self.recorded_at,
            "app": self.app,
            "command": self.command,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "exit_code": self.exit_code,
            "error_code": self.error_code,
            "error_category": self.error_category,
        }


class TelemetryPipeline:
    """Writes anonymous usage events for Tooli command execution."""

    def __init__(
        self,
        *,
        app_name: str,
        enabled: bool,
        endpoint: str | None = None,
        storage_dir: Path | None = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        clock: Callable[[], float] = _utc_now,
    ) -> None:
        self.app_name = app_name
        self.enabled = enabled
        self.endpoint = endpoint
        self.storage_dir = storage_dir
        self.retention_days = retention_days
        self.clock = clock

    @property
    def storage_root(self) -> Path:
        return self.storage_dir or DEFAULT_TELEMETRY_DIR

    @property
    def events_file(self) -> Path:
        return self.storage_root / DEFAULT_TELEMETRY_FILE

    def record(
        self,
        *,
        command: str,
        success: bool,
        duration_ms: int,
        exit_code: int | None = None,
        error_code: str | None = None,
        error_category: str | None = None,
    ) -> None:
        if not self.enabled:
            return

        record = TelemetryRecord(
            schema_version=SCHEMA_VERSION,
            recorded_at=_to_timestamp(self.clock()),
            app=self.app_name,
            command=command,
            success=success,
            duration_ms=duration_ms,
            exit_code=exit_code,
            error_code=error_code,
            error_category=error_category,
        )

        self._write_local_event(record)
        if self.endpoint:
            self._send_remote(record)

    def _write_local_event(self, record: TelemetryRecord) -> None:
        try:
            path = self.events_file
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as file: # noqa: SIM117
                with _file_lock(file):
                    file.write(json.dumps(record.to_dict(), sort_keys=True))
                    file.write("\n")

            # Prune ~1% of the time to avoid O(n) overhead on every write.
            if random.random() < 0.01:
                self._prune_retained_events(path)
        except OSError:
            return

    def _prune_retained_events(self, path: Path) -> None:
        if self.retention_days <= 0:
            return
        cutoff = self.clock() - (self.retention_days * 24 * 60 * 60)
        try:
            with path.open("r+", encoding="utf-8") as file, _file_lock(file):
                    lines = file.read().splitlines()
                    kept_lines: list[str] = []
                    for line in lines:
                        try:
                            payload = json.loads(line)
                            recorded_at = payload.get("recorded_at")
                            if _parse_recorded_at(recorded_at) < cutoff:
                                continue
                        except (json.JSONDecodeError, ValueError, TypeError):
                            kept_lines.append(line)
                            continue
                        kept_lines.append(line)

                    if len(kept_lines) != len(lines):
                        file.seek(0)
                        file.truncate()
                        if kept_lines:
                            file.write("\n".join(kept_lines) + "\n")
        except OSError:
            return

    def _send_remote(self, record: TelemetryRecord) -> None:
        payload = json.dumps(record.to_dict(), ensure_ascii=False).encode("utf-8")
        headers: dict[str, str] = {"Content-Type": "application/json"}
        token = os.getenv("TOOLI_TELEMETRY_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                if response.status < 200 or response.status >= 300:
                    return
        except (urllib.error.URLError, OSError):
            return


def build_telemetry_pipeline(
    *,
    app_name: str,
    telemetry: bool | None,
    endpoint: str | None = None,
    storage_dir: Path | None = None,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    clock: Callable[[], float] = _utc_now,
) -> TelemetryPipeline:
    return TelemetryPipeline(
        app_name=app_name,
        enabled=should_enable_telemetry(telemetry),
        endpoint=resolve_telemetry_endpoint(endpoint),
        storage_dir=storage_dir,
        retention_days=retention_days,
        clock=clock,
    )
