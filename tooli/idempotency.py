"""Simple process-local idempotency tracking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IdempotencyRecord:
    has_cached_result: bool
    result: Any = None


class IdempotencyStore:
    """In-memory idempotency registry for the current process."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], IdempotencyRecord] = {}

    def get(self, *, command: str, idempotency_key: str) -> IdempotencyRecord | None:
        return self._records.get((command, idempotency_key))

    def put(
        self,
        *,
        command: str,
        idempotency_key: str,
        has_cached_result: bool,
        result: Any = None,
    ) -> None:
        self._records[(command, idempotency_key)] = IdempotencyRecord(
            has_cached_result=has_cached_result,
            result=result,
        )

    def clear(self) -> None:
        self._records.clear()


_global_store = IdempotencyStore()


def get_record(*, command: str, idempotency_key: str) -> IdempotencyRecord | None:
    """Return any stored idempotency entry for a command/key pair."""

    if not idempotency_key:
        return None
    return _global_store.get(command=command, idempotency_key=idempotency_key)


def set_record(
    *,
    command: str,
    idempotency_key: str,
    has_cached_result: bool,
    result: Any = None,
) -> None:
    """Persist execution outcome metadata for a command/key pair."""

    if not idempotency_key:
        return
    _global_store.put(
        command=command,
        idempotency_key=idempotency_key,
        has_cached_result=has_cached_result,
        result=result,
    )


def clear_records() -> None:
    """Clear the in-memory idempotency cache."""

    _global_store.clear()
