"""LogSlicer: Turn nasty logs into queryable events."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated

from tooli import Argument, Option, StdinOr, Tooli
from tooli.annotations import ReadOnly

if TYPE_CHECKING:
    from collections.abc import Iterable

app = Tooli(
    name="logslicer",
    help="Parses logs into structured events; supports stdin/file parity.",
    version="0.1.0",
)

@app.command(
    annotations=ReadOnly,
    list_processing=True,
    examples=[
        {"args": ["parse", "app.log"], "description": "Parse a log file"},
        {"args": ["parse", "-"], "description": "Parse from stdin"},
    ],
)
def parse(
    source: Annotated[StdinOr[str], Argument(help="Log source (file, URL, or '-')")],
    format: Annotated[str, Option(help="Log format: json|plain")] = "auto",
) -> Iterable[dict]:
    """Parse log entries into structured JSON objects."""
    # Demo superpower: StdinOr resolves content automatically
    content = str(source)
    lines = content.splitlines()

    for i, line in enumerate(lines):
        # Very simple parser
        try:
            if format == "json" or (format == "auto" and line.startswith("{")):
                yield {"line": i, "event": json.loads(line)}
            else:
                yield {"line": i, "raw": line, "type": "info"}
        except Exception:
            # Demonstration of how to handle malformed entries in a stream
            yield {"line": i, "error": "parse_failure", "raw": line}

@app.command(
    annotations=ReadOnly,
)
def stats(
    source: Annotated[StdinOr[str], Argument(help="Log source")],
) -> dict:
    """Summarize log statistics."""
    content = str(source)
    lines = content.splitlines()

    return {
        "total_entries": len(lines),
        "levels": {"INFO": 80, "ERROR": 5, "WARN": 15}, # Mock data
        "top_errors": ["ConnectionTimeout", "AuthFailure"]
    }

if __name__ == "__main__":
    app()
