"""Streaming local log filtering example for Tooli."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Annotated, Any

from tooli import Argument, Option, Tooli
from tooli.annotations import ReadOnly
from tooli.errors import InputError, Suggestion
from tooli.input import StdinOr  # noqa: TC001

app = Tooli(name="log-sift", description="Extract matching log lines from files or stdin")


def _iter_lines(source: StdinOr[Path] | str | None):
    if isinstance(source, Path):
        with source.open("r", encoding="utf-8", errors="replace") as handle:
            for line_num, line in enumerate(handle, 1):
                yield line_num, line.rstrip("\n")
        return

    if isinstance(source, str):
        for line_num, line in enumerate(source.splitlines(), 1):
            yield line_num, line.rstrip("\n")
        return

    raise InputError(
        message="No log source provided.",
        code="E1001",
        suggestion=Suggestion(
            action="provide source",
            fix="Pass a file path, URL, or '-' to read from stdin.",
            example="journalctl -u nginx | log-sift extract-errors - --pattern \"ERROR|exception\"",
        ),
    )


@app.command(annotations=ReadOnly)
def extract_errors(
    source: Annotated[
        StdinOr[Path],
        Argument(help="Log file path, URL, or '-' for stdin", default=None),
    ] = None,
    pattern: Annotated[str, Option(help="Regex pattern to match")] = r"(?i)error|fail|exception",
    max_matches: Annotated[int, Option(help="Maximum matching lines to return", min=1)] = 200,
) -> list[dict[str, Any]]:
    """Extract matching lines and emit JSON-friendly structured results."""

    try:
        matcher = re.compile(pattern)
    except re.error as exc:
        raise InputError(
            message=f"Invalid regular expression pattern: {pattern}",
            code="E1002",
            suggestion=Suggestion(
                action="fix regex",
                fix="Use a valid Python regex pattern.",
                example=r'\\bERROR\\b',
            ),
            details={"pattern": pattern},
        ) from exc

    print(
        f"Scanning source: {'<stdin>' if not isinstance(source, Path) else source}",
        file=sys.stderr,
    )

    matches: list[dict[str, Any]] = []
    for line_num, line in _iter_lines(source):
        if matcher.search(line):
            matches.append({"line": line_num, "content": line})
            if len(matches) >= max_matches:
                break

    return matches


if __name__ == "__main__":
    app()
