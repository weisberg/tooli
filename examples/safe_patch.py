"""Self-healing text replacement example for Tooli."""

from __future__ import annotations

import difflib
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


@app.command(annotations=Destructive, human_in_the_loop=True)
def replace_text(
    ctx: Any,
    file_path: Annotated[str, Argument(help="File to modify")],
    search: Annotated[str, Option(help="Exact text to find")],
    replace: Annotated[str, Option(help="Text to replace with")],
) -> dict[str, Any]:
    """Replace exact text safely with actionable validation and dry-run support."""

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

    try:
        original = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(
            message=f"Unable to read file: {file_path}",
            code="E1003",
            suggestion=Suggestion(
                action="fix file access",
                fix="Ensure the file is readable and retry.",
                example=f"cat {file_path}",
            ),
            details={"path": file_path},
        ) from exc

    if search not in original:
        raise InputError(
            message=f"Exact search string was not found in '{file_path}'.",
            code="E1004",
            suggestion=Suggestion(
                action="adjust search text",
                fix=f"Double-check exact spacing/newlines. {_build_hint(original, search)}",
                example="safe-patch replace-text app.py --search \"actual string\" --replace \"replacement\"",
            ),
        )

    replacements = original.count(search)
    updated = original.replace(search, replace)

    if bool(getattr(ctx.obj, "dry_run", False)):
        return {
            "status": "planned",
            "file": str(target),
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
            code="E1005",
            suggestion=Suggestion(
                action="retry with writable path",
                fix="Check write permissions and ensure destination file is not read-only.",
                example=f"safe-patch replace-text {file_path} --search \"...\" --replace \"...\"",
            ),
            details={"path": file_path},
        ) from exc

    return {"status": "applied", "file": str(target), "matches": replacements}


if __name__ == "__main__":
    app()
