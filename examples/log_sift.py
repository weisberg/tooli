"""Streaming log filter example for Tooli.

This example demonstrates Universal I/O and structured output for downstream agents:
- accept file paths, URLs, and piped stdin through `StdinOr`,
- keep command output token-efficient with predictable JSON fields,
- support `--output json` and `--output jsonl` in non-interactive contexts.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Annotated, Any

from tooli import Argument, Option, Tooli
from tooli.annotations import Idempotent, ReadOnly
from tooli.errors import InputError, Suggestion
from tooli.input import StdinOr  # noqa: TC001

app = Tooli(name="log-sift", description="Extract matching log lines from files or stdin")


def _iter_lines(source: StdinOr[Path] | str | None) -> list[tuple[int, str]]:
    """Extract lines as (line_number, text) tuples."""
    lines: list[tuple[int, str]] = []
    if isinstance(source, Path):
        with source.open("r", encoding="utf-8", errors="replace") as handle:
            for line_num, line in enumerate(handle, 1):
                lines.append((line_num, line.rstrip("\n")))
        return lines

    if isinstance(source, str):
        for line_num, line in enumerate(source.splitlines(), 1):
            lines.append((line_num, line.rstrip("\n")))
        return lines

    raise InputError(
        message="No log source provided.",
        code="E1001",
        suggestion=Suggestion(
            action="provide source",
            fix="Pass a file path, URL, or '-' to read from stdin.",
            example="journalctl -u nginx | log-sift extract-errors - --pattern \"ERROR|exception\"",
        ),
    )


@app.command(
    annotations=ReadOnly | Idempotent,
    list_processing=True,
    paginated=True,
    cost_hint="low",
    examples=[
        {
            "args": ["extract-errors", "app.log"],
            "description": "Scan a local file for error-like lines.",
        },
        {
            "args": [
                "extract-errors",
                "-",
                "--pattern",
                "(?i)timeout|exception|error",
            ],
            "description": "Pipe streaming input from another command.",
        },
    ],
    error_codes={
        "E1001": "No input source provided.",
        "E1002": "Pattern is invalid regex.",
    },
)
def extract_errors(
    source: Annotated[
        StdinOr[Path],
        Argument(help="Log file path, URL, or '-' for stdin", default=None),
    ] = None,
    pattern: Annotated[str, Option(help="Regex pattern to match")] = r"(?i)error|fail|exception",
    max_matches: Annotated[int, Option(help="Maximum matches to collect", min=1)] = 200,
) -> list[dict[str, Any]]:
    """Filter logs into deterministic JSON objects for downstream steps.

    Agent guidance:
    - use `--output json` or `--json` for direct automation,
    - use `--output jsonl` when streaming each result as separate envelope records,
    - use `--limit` for bounded pagination in very long inputs.
    """

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

    source_label = "<stdin>" if not isinstance(source, Path) else str(source)
    print(f"Scanning source: {source_label}", file=sys.stderr)

    matches: list[dict[str, Any]] = []
    for line_num, line in _iter_lines(source):
        if matcher.search(line):
            matches.append({"line": line_num, "content": line})
            if len(matches) >= max_matches:
                break

    return [
        {
            "match_index": idx,
            "line": entry["line"],
            "source": source_label,
            "content": entry["content"],
            "pattern": pattern,
        }
        for idx, entry in enumerate(matches, 1)
    ]


if __name__ == "__main__":
    app()
