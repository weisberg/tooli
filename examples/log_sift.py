"""Streaming log filter example for Tooli.

`log-sift` is an agent-first log extractor. It keeps context usage predictable by
returning only line-level matches with optional neighboring context, instead of
pushing entire files through stdout.

Agent pain point solved:
- agents lose control when chaining shell pipelines and then re-parsing giant output,
- `grep` and ad-hoc parsers emit unstructured noise,
- `sed`/`awk`-style shell one-liners are fragile and hard to recover.

Communication contract:
- output is a list of deterministic records,
- every match can include `context_before`/`context_after`,
- machine output can be requested with `--output json` or `--output jsonl`,
- global `--dry-run` behavior stays untouched for read-only streaming.

Usage patterns:
- `python log_sift.py extract-errors /var/log/nginx/error.log`
- `journalctl -u nginx | python log_sift.py extract-errors - --pattern "ERROR|timeout"`
- `python log_sift.py extract-errors - --pattern "exception|traceback" --context 2 --max-matches 50`
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


def _collect_lines(source: StdinOr[Path] | str | None) -> list[tuple[int, str]]:
    if isinstance(source, Path):
        with source.open("r", encoding="utf-8", errors="replace") as handle:
            return [(line_num, line.rstrip("\n")) for line_num, line in enumerate(handle, 1)]

    if isinstance(source, str):
        return [(line_num, line.rstrip("\n")) for line_num, line in enumerate(source.splitlines(), 1)]

    raise InputError(
        message="No log source provided.",
        code="E1001",
        suggestion=Suggestion(
            action="provide source",
            fix="Pass a file path, URL, or '-' to read from stdin.",
            example="journalctl -u nginx | log-sift extract-errors - --pattern \"ERROR|exception\"",
        ),
    )


def _source_label(source: StdinOr[Path] | str | None) -> str:
    if isinstance(source, Path):
        return str(source)
    if source == "-":
        return "<stdin>"
    if isinstance(source, str):
        return "<inline>"
    return "<unknown>"


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
                "--context",
                "2",
                "--max-matches",
                "20",
            ],
            "description": "Pipe from another command and include context for triage.",
        },
    ],
    error_codes={
        "E1001": "No input source provided.",
        "E1002": "Pattern is invalid regex.",
        "E1003": "No matches in selected window.",
    },
)
def extract_errors(
    source: Annotated[
        StdinOr[Path],
        Argument(help="Log file path, URL, or '-' for stdin"),
    ],
    pattern: Annotated[str, Option(help="Regex pattern to match")]=r"(?i)error|fail|exception",
    context: Annotated[int, Option(help="Include n lines before/after each match", min=0)] = 0,
    max_matches: Annotated[int, Option(help="Maximum matches to return", min=1)] = 200,
) -> list[dict[str, Any]]:
    """Filter logs into deterministic JSON records for automation.

    Agent guidance:
    - run with `--output json` for a single envelope from MCP-driven loops,
    - run with `--output jsonl` for streaming one match per envelope,
    - use `--max-matches` to enforce hard boundaries,
    - pair with `tail -f` only when the file is bounded by command-level limits.
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
                example=r"\\b(ERROR|FAIL)\\b",
            ),
            details={"pattern": pattern},
        ) from exc

    source_label = _source_label(source)
    print(f"Scanning source: {source_label}", file=sys.stderr)

    lines = _collect_lines(source)
    matches: list[dict[str, Any]] = []

    for idx, (line_num, line) in enumerate(lines):
        if not matcher.search(line):
            continue

        before = lines[max(0, idx - context) : idx]
        after_end = min(idx + context + 1, len(lines))
        after = lines[idx + 1 : after_end]

        matches.append(
            {
                "match_index": len(matches) + 1,
                "line": line_num,
                "content": line,
                "pattern": pattern,
                "source": source_label,
                "context_before": [entry[1] for entry in before],
                "context_after": [entry[1] for entry in after],
            }
        )

        if len(matches) >= max_matches:
            break

    if not matches:
        raise InputError(
            message=f"No lines matched pattern '{pattern}' for the requested window.",
            code="E1003",
            suggestion=Suggestion(
                action="broaden pattern",
                fix="Use a broader pattern or increase --max-matches.",
                example=r'python log_sift.py extract-errors app.log --pattern "ERROR|WARN|FAIL"',
            ),
            details={"pattern": pattern, "source": source_label},
        )

    return [
        {
            **match,
            "truncated": match["match_index"] == max_matches and len(matches) == max_matches,
            "has_context": bool(context),
            "total_returned": len(matches),
        }
        for match in matches
    ]


if __name__ == "__main__":
    app()
