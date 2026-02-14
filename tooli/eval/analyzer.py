"""Analysis helpers for invocation logs."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _read_records(log_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return records

    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(payload, dict):
            continue
        records.append(payload)

    return records


def _invocation_key(payload: dict[str, Any]) -> tuple[str, str]:
    command = str(payload.get("command") or "")
    args = payload.get("args", {})
    if not isinstance(args, dict):
        args = {}
    return command, json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)


def _is_invalid_parameter_error(payload: dict[str, Any]) -> bool:
    code = payload.get("error_code")
    if isinstance(code, str) and code.startswith("E1"):
        return True
    return payload.get("exit_code") == 2


def analyze_invocations(log_path: str | Path) -> dict[str, Any]:
    """Load and analyze invocation logs from a JSONL file."""

    path = Path(log_path)
    records = _read_records(path)

    if not records:
        return {
            "total_invocations": 0,
            "invocations_per_command": {},
            "invalid_parameter_rate": {},
            "most_common_error_codes": [],
            "duplicate_invocations": [],
            "average_duration_ms_per_command": {},
        }

    invocations_per_command: dict[str, int] = Counter()
    invalid_counts: dict[str, int] = Counter()
    error_counts: dict[str, int] = Counter()
    durations: dict[str, list[int]] = defaultdict(list)
    duplicate_counts: dict[tuple[str, str], int] = Counter()

    for payload in records:
        command = str(payload.get("command") or "")
        invocations_per_command[command] += 1

        duration = payload.get("duration_ms")
        if isinstance(duration, int):
            durations[command].append(duration)

        if _is_invalid_parameter_error(payload):
            invalid_counts[command] += 1

        error_code = payload.get("error_code")
        if isinstance(error_code, str):
            error_counts[error_code] += 1

        duplicate_counts[_invocation_key(payload)] += 1

    average_duration = {}
    for command, values in durations.items():
        if values:
            average_duration[command] = sum(values) / len(values)
        else:
            average_duration[command] = 0.0

    invalid_rates = {
        command: (invalid_counts[command] / total) if total else 0.0
        for command, total in invocations_per_command.items()
    }

    duplicate_invocations = [
        {
            "command": command,
            "args": json.loads(args_key),
            "count": count,
        }
        for (command, args_key), count in duplicate_counts.items()
        if count > 1
    ]

    return {
        "total_invocations": sum(invocations_per_command.values()),
        "invocations_per_command": dict(invocations_per_command),
        "invalid_parameter_rate": invalid_rates,
        "most_common_error_codes": [
            {"code": code, "count": count}
            for code, count in sorted(error_counts.items(), key=lambda item: item[1], reverse=True)
        ],
        "duplicate_invocations": sorted(duplicate_invocations, key=lambda item: item["count"], reverse=True),
        "average_duration_ms_per_command": average_duration,
    }
