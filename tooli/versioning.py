"""Tool versioning helpers for Tooli commands."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import zip_longest
import re
from typing import Any


_VERSION_SEPARATORS = re.compile(r"[.+-]")


def _normalize_version_part(part: str) -> tuple[int, str | int]:
    part = part.strip().lower()
    if not part:
        return (0, 0)
    if part.isdigit():
        return (0, int(part))
    return (1, part)


def normalize_version(version: str) -> tuple[tuple[int, str | int], ...]:
    """Normalize a version string into a comparable tuple."""

    if not version:
        return ()

    parts: list[tuple[int, str | int]] = []
    for raw_part in _VERSION_SEPARATORS.split(version):
        part = _normalize_version_part(raw_part)
        parts.append(part)
    return tuple(parts)


def compare_versions(left: str | None, right: str | None) -> int:
    """Compare two version strings.

    Returns:
        -1 if left < right
         0 if equal
         1 if left > right
    """

    if left is None and right is None:
        return 0
    if left is None:
        return -1
    if right is None:
        return 1

    left_parts = normalize_version(left)
    right_parts = normalize_version(right)
    max_len = max(len(left_parts), len(right_parts))

    for i in range(max_len):
        left_part = left_parts[i] if i < len(left_parts) else (0, 0)
        right_part = right_parts[i] if i < len(right_parts) else (0, 0)
        if left_part == right_part:
            continue
        if left_part > right_part:
            return 1
        return -1

    return 0


def is_version_in_range(version: str, *, min_version: str | None = None, max_version: str | None = None) -> bool:
    """Return True if version is within the inclusive [min, max] range."""

    if min_version is not None and compare_versions(version, min_version) < 0:
        return False
    if max_version is not None and compare_versions(version, max_version) > 0:
        return False
    return True


def _command_version(command: Any) -> str | None:
    callback = getattr(command, "callback", None)
    if callback is None:
        return None
    from tooli.command_meta import get_command_meta
    raw = get_command_meta(callback).version
    return None if raw is None else str(raw)


@dataclass(frozen=True)
class VersionFilter:
    """Filter Tooli command registrations by inclusive version window."""

    min_version: str | None = None
    max_version: str | None = None

    def apply(self, commands: list[Any]) -> list[Any]:
        if self.min_version is None and self.max_version is None:
            return list(commands)

        return [
            command
            for command in commands
            if (version := _command_version(command)) is not None
            and is_version_in_range(
                version,
                min_version=self.min_version,
                max_version=self.max_version,
            )
        ]
