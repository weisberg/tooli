"""Self-healing text replacement example for Tooli.

This tool shows how an agent can perform deterministic, reversible file edits:
- validate target content before writing,
- give actionable recovery hints when edits fail,
- honor global `--dry-run` and produce machine-readable envelopes.
"""

from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import Annotated, Any

from tooli import Argument, Option, Tooli
from tooli.annotations import Destructive
from tooli.errors import InputError, Suggestion

app = Tooli(name="safe-patch", description="Agent-safe local file replacements")


def _build_hint(content: str, target: str) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    closest = difflib.get_close_matches(target.strip(), lines, n=3, cutoff=0.6)
    if not closest:
        return "No close text matches were found."
    if len(closest) == 1:
        return f"Did you mean: {closest[0]!r}?"
    return "Did you mean: " + ", ".join(repr(entry) for entry in closest) + "?"


def _ensure_file_exists(file_path: str) -> Path:
    target = Path(file_path)
    if not target.exists():
        raise InputError(
            message=f"File not found: {file_path}",
            code="E1001",
            suggestion=Suggestion(
                action="pass valid file path",
                fix="Use a path that points to an existing writable file.",
                example="safe-patch replace-text notes.txt --search \"old\" --replace \"new\"",
            ),
            details={"path": file_path},
        )

    if not target.is_file():
        raise InputError(
            message=f"Expected a file, got a directory: {file_path}",
            code="E1002",
            suggestion=Suggestion(
                action="pass file path",
                fix="Pass a concrete file path, not a directory.",
                example="safe-patch replace-text data/config.toml --search x --replace y",
            ),
            details={"path": file_path},
        )

    if not os.access(str(target), os.W_OK):
        raise InputError(
            message=f"File is not writable: {file_path}",
            code="E1003",
            suggestion=Suggestion(
                action="fix file permissions",
                fix="Ensure target file is writable before patching.",
                example=f"chmod +w {file_path}",
            ),
            details={"path": file_path},
        )

    return target


def _replace_content(
    original: str,
    search: str,
    replace: str,
    max_replacements: int | None,
) -> tuple[str, int]:
    if search not in original:
        raise InputError(
            message="Exact search string was not found in source.",
            code="E1004",
            suggestion=Suggestion(
                action="adjust search text",
                fix=f"Double-check exact spacing/newlines. {_build_hint(original, search)}",
                example="safe-patch replace-text app.py --search \"actual string\" --replace \"replacement\"",
            ),
            details={"target": search},
        )

    if max_replacements is None:
        return original.replace(search, replace), original.count(search)

    if max_replacements <= 0:
        raise InputError(
            message="max-replacements must be greater than zero when provided.",
            code="E1005",
            suggestion=Suggestion(
                action="set max-replacements",
                fix="Set --max-replacements to a positive integer or omit for full replace.",
                example="safe-patch replace-text app.py --search \"old\" --replace \"new\" --max-replacements 2",
            ),
        )

    updated = original.replace(search, replace, max_replacements)
    matches = original.count(search)
    applied = min(matches, max_replacements)
    return updated, applied


@app.command(
    annotations=Destructive,
    human_in_the_loop=True,
    cost_hint="medium",
    examples=[
        {
            "args": ["replace-text", "config.py", "--search", "old_flag = False", "--replace", "old_flag = True"],
            "description": "Single-pass exact string replacement",
        },
        {
            "args": [
                "replace-text",
                "README.md",
                "--search",
                "TODO",
                "--replace",
                "DONE",
                "--max-replacements",
                "1",
            ],
            "description": "Only replace the first match",
        },
    ],
    error_codes={
        "E1001": "File path is invalid or file missing.",
        "E1003": "File not writable.",
        "E1004": "Search string not found.",
        "E1005": "Invalid max-replacements value.",
        "E1006": "Write step failed.",
        "E1007": "Could not read file.",
    },
)
def replace_text(
    ctx: Any,
    file_path: Annotated[str, Argument(help="File to modify")],
    search: Annotated[str, Option(help="Exact text to find")],
    replace: Annotated[str, Option(help="Text to replace with")],
    max_replacements: Annotated[int | None, Option(help="Maximum replacements to apply")] = None,
) -> dict[str, Any]:
    """Replace exact text with strict preconditions and actionable hints.

    Agent guidance:
    - keep `search` exact (including indentation and whitespace),
    - prefer `--max-replacements` in narrow edits,
    - use global `--dry-run` to plan changes before writing.
    """

    target = _ensure_file_exists(file_path)

    if search == "":
        raise InputError(
            message="search must not be empty.",
            code="E1007",
            suggestion=Suggestion(
                action="provide search text",
                fix='Provide a non-empty --search value (example: "--search \"TODO\"").',
                example="safe-patch replace-text notes.txt --search \"TODO\" --replace \"DONE\"",
            ),
        )

    try:
        original = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(
            message=f"Unable to read file: {file_path}",
            code="E1007",
            suggestion=Suggestion(
                action="fix file access",
                fix="Ensure the file is readable and retry.",
                example=f"cat {file_path}",
            ),
            details={"path": file_path},
        ) from exc

    updated, replacements = _replace_content(original, search, replace, max_replacements)

    if bool(getattr(ctx.obj, "dry_run", False)):
        return {
            "status": "planned",
            "file": str(target),
            "requested_replacements": max_replacements,
            "matches": replacements,
            "search": search,
            "replacement": replace,
            "dry_run": True,
        }

    try:
        target.write_text(updated, encoding="utf-8")
    except OSError as exc:
        raise InputError(
            message=f"Failed to write updated file: {file_path}",
            code="E1006",
            suggestion=Suggestion(
                action="retry with writable path",
                fix="Check write permissions and ensure destination file is not read-only.",
                example=f"safe-patch replace-text {file_path} --search \"...\" --replace \"...\"",
            ),
            details={"path": file_path},
        ) from exc

    return {
        "status": "applied",
        "file": str(target),
        "matches": replacements,
        "requested_replacements": max_replacements,
            "changed": True,
        }


if __name__ == "__main__":
    app()
