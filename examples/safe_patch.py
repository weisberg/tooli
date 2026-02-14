"""Self-healing file edit example for Tooli.

`safe-patch` demonstrates a deterministic editing workflow for agents that must avoid
free-form shell text operations.

Agent pain points solved:
- `sed`/`perl` edits fail with opaque errors,
- exact-match mistakes go unchecked until downstream context shows drift,
- large files can be damaged by broad replacement commands.

Communication contract:
- every failure returns `ToolError` with a concrete fix hint,
- `--dry-run` plan can be reviewed before write operations,
- JSON output is stable (`status`, `file`, `matches`, `changed`).

Workflow examples:
- `python safe_patch.py replace-text README.md --search "TODO" --replace "DONE"`
- `python safe_patch.py replace-text README.md --search "old" --replace "new" --max-replacements 1`
- `python safe_patch.py replace-text - --help` to inspect all available switches.
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


def _validate_search_term(search: str) -> str:
    stripped = search.strip()
    if not stripped:
        raise InputError(
            message="search cannot be empty",
            code="E1000",
            suggestion=Suggestion(
                action="provide search text",
                fix="Pass a non-empty --search value with exact spacing.",
                example='safe-patch replace-text notes.txt --search "TODO" --replace "DONE"',
            ),
        )
    return search


def _build_close_matches(content: str, target: str) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    closest = difflib.get_close_matches(target.strip(), lines, n=3, cutoff=0.6)
    if not closest:
        return "No close text matches were found."
    if len(closest) == 1:
        return f"Did you mean: {closest[0]!r}?"
    return "Did you mean: " + ", ".join(repr(entry) for entry in closest) + "?"


def _build_previews(content: str, needle: str, context_lines: int) -> dict[str, Any]:
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        if needle in line:
            start = max(idx - context_lines, 0)
            end = min(idx + context_lines + 1, len(lines))
            return {
                "line": idx + 1,
                "before": lines[start:idx],
                "match": line,
                "after": lines[idx + 1:end],
            }

    return {
        "line": None,
        "before": [],
        "match": None,
        "after": [],
    }


def _format_preview(lines: dict[str, Any]) -> str:
    if not lines["match"]:
        return "No snippet available."

    before = "\n".join(lines["before"])
    after = "\n".join(lines["after"])
    return "\n".join(part for part in [before, lines["match"], after] if part)


def _ensure_file_access(file_path: str) -> Path:
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

    if not os.access(str(target), os.R_OK):
        raise InputError(
            message=f"File is not readable: {file_path}",
            code="E1003",
            suggestion=Suggestion(
                action="fix read permissions",
                fix="Grant read permissions to the current user.",
                example=f"chmod +r {file_path}",
            ),
            details={"path": file_path},
        )

    if not os.access(str(target), os.W_OK):
        raise InputError(
            message=f"File is not writable: {file_path}",
            code="E1003",
            suggestion=Suggestion(
                action="fix write permissions",
                fix="Ensure the file is writable before applying the patch.",
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
                fix=f"Double-check exact spacing/newlines. {_build_close_matches(original, search)}",
                example="safe-patch replace-text app.py --search \"actual string\" --replace \"replacement\"",
            ),
            details={"target": search},
        )

    if max_replacements is None:
        new_text = original.replace(search, replace)
        return new_text, original.count(search)

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

    before = original.count(search)
    updated = original.replace(search, replace, max_replacements)
    return updated, min(before, max_replacements)


def _build_action_plan(
    *,
    file_path: str,
    search: str,
    replace: str,
    requested: int | None,
    matches: int,
    preview: dict[str, Any],
) -> dict[str, Any]:
    planned = min(matches, requested or matches)
    return {
        "status": "planned",
        "file": file_path,
        "mode": "replace",
        "search": search,
        "replace": replace,
        "requested_replacements": requested,
        "planned_replacements": planned,
        "snippet": {
            "first_match_line": preview["line"],
            "context": {
                "before": preview["before"],
                "match": preview["match"],
                "after": preview["after"],
            },
            "preview": _format_preview(preview),
        },
    }


@app.command(
    annotations=Destructive,
    human_in_the_loop=True,
    cost_hint="medium",
    examples=[
        {
            "args": [
                "replace-text",
                "config.py",
                "--search",
                "old_flag = False",
                "--replace",
                "old_flag = True",
            ],
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
            "description": "Replace only first match",
        },
    ],
    error_codes={
        "E1000": "search was empty.",
        "E1001": "File path is invalid or missing.",
        "E1002": "Path is not a file.",
        "E1003": "File access denied.",
        "E1004": "search string not found.",
        "E1005": "Invalid max_replacements value.",
        "E1006": "Write step failed.",
        "E1007": "Failed to read source file.",
    },
)
def replace_text(
    ctx: Any,
    file_path: Annotated[str, Argument(help="File to modify")],
    search: Annotated[str, Option(help="Exact text to find")],
    replace: Annotated[str, Option(help="Text to replace with")],
    max_replacements: Annotated[int | None, Option(help="Maximum replacements to apply")] = None,
    context_lines: Annotated[int, Option(help="Preview context lines around first match", min=0)] = 2,
) -> dict[str, Any]:
    """Replace exact text with strict preconditions and actionable hints.

    Agent guidance:
    - keep `search` exact (including indentation and whitespace),
    - prefer `--max-replacements` for narrow edits,
    - keep global `--dry-run` enabled first for auditability,
    - use `--output json` to consume results automatically.

    Output contract:
    - `status` is `planned` while dry-run is active,
    - `status` is `applied` when write succeeds,
    - `planned_replacements` reflects the actual number of edits requested.
    """

    file_path_validated = _ensure_file_access(file_path)

    _validate_search_term(search)
    preview = _build_previews(file_path_validated.read_text(encoding="utf-8"), search, context_lines)

    try:
        original = file_path_validated.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(
            message=f"Unable to read file: {file_path}",
            code="E1007",
            suggestion=Suggestion(
                action="fix file access",
                fix="Ensure the file is readable and retry.",
                example=f"python safe_patch.py replace-text {file_path} --search \"TODO\" --replace \"DONE\"",
            ),
            details={"path": file_path},
        ) from exc

    updated, replacements = _replace_content(original, search, replace, max_replacements)

    if bool(getattr(ctx.obj, "dry_run", False)):
        return _build_action_plan(
            file_path=file_path,
            search=search,
            replace=replace,
            requested=max_replacements,
            matches=original.count(search),
            preview=preview,
        )

    action_plan = _build_action_plan(
        file_path=file_path,
        search=search,
        replace=replace,
        requested=max_replacements,
        matches=replacements,
        preview=preview,
    )

    try:
        file_path_validated.write_text(updated, encoding="utf-8")
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
        **action_plan,
        "status": "applied",
        "applied_replacements": replacements,
        "changed": replacements > 0,
    }


if __name__ == "__main__":
    app()
