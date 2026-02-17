"""RepoLens: Explain this codebase to an agent."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from tooli import Argument, Option, Tooli
from tooli.annotations import ReadOnly
from tooli.errors import InputError, Suggestion

app = Tooli(
    name="repolens",
    help="Locally scans a repo and emits a structured inventory.",
    version="0.1.0",
)

@app.command(
    annotations=ReadOnly,
    examples=[
        {"args": ["summary", "."], "description": "Summarize the current directory"},
    ],
    when_to_use="Get a high-level overview of a codebase including file counts, sizes, and key files",
    task_group="Analysis",
    pipe_output={"format": "json"},
)
def summary(
    root: Annotated[Path, Argument(help="Root directory to scan")] = Path("."),
) -> dict:
    """Get high-level statistics about the codebase."""
    if not root.is_dir():
        raise InputError(
            message=f"Path '{root}' is not a directory.",
            code="E1001",
            suggestion=Suggestion(action="fix_path", fix="Provide a valid directory path.")
        )

    # Simple check for git repo
    is_git = (root / ".git").is_dir()
    if not is_git:
        # Fun demo moment: structured error for non-git repo
        raise InputError(
            message="Not a git repository.",
            code="E1002",
            suggestion=Suggestion(
                action="run_in_repo",
                fix="Run this command inside a git repository or pass a valid repo root."
            )
        )

    # Basic inventory
    files = list(root.rglob("*"))
    extensions = {}
    total_size = 0

    for f in files:
        if f.is_file():
            ext = f.suffix or "no-ext"
            extensions[ext] = extensions.get(ext, 0) + 1
            total_size += f.stat().st_size

    return {
        "root": str(root.absolute()),
        "is_git": is_git,
        "total_files": len([f for f in files if f.is_file()]),
        "total_size_bytes": total_size,
        "extensions": extensions,
        "key_files": [str(f.relative_to(root)) for f in files if f.name in ("pyproject.toml", "package.json", "README.md", "LICENSE")],
    }

@app.command(
    annotations=ReadOnly,
    when_to_use="List all files in a repository with their sizes and modification times",
    task_group="Query",
    pipe_output={"format": "json"},
)
def inventory(
    root: Annotated[Path, Argument(help="Root directory to scan")] = Path("."),
    include_hidden: Annotated[bool, Option(help="Include hidden files")] = False,
) -> list[dict]:
    """Emit a structured inventory of files in the repository."""
    # This command uses JSONL streaming by returning a list
    results = []
    for path in root.rglob("*"):
        if not include_hidden and any(p.startswith(".") for p in path.parts if p != "."):
            continue
        if path.is_file():
            results.append({
                "path": str(path.relative_to(root)),
                "size": path.stat().st_size,
                "modified": path.stat().st_mtime,
            })
    return results

if __name__ == "__main__":
    app()
