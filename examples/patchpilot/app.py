"""PatchPilot: Apply edits safely with dry-run plans."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from tooli import Argument, Option, Tooli
from tooli.annotations import Destructive
from tooli.dry_run import dry_run_support, record_dry_action
from tooli.errors import InputError, Suggestion

app = Tooli(
    name="patchpilot",
    help="Applies file edits safely with deterministic dry-run plans.",
    version="0.1.0",
)

@app.command(
    annotations=Destructive,
    examples=[
        {"args": ["apply", "fix.diff", "--dry-run"], "description": "Preview a patch application"},
    ],
    capabilities=["fs:read", "fs:write"],
)
@dry_run_support
def apply(
    patch_file: Annotated[Path, Argument(help="Path to the diff/patch file")],
    root: Annotated[Path, Option(help="Root directory to apply patch")] = Path("."),
    fuzz: Annotated[bool, Option(help="Allow fuzzy matching")] = False,
) -> str:
    """Apply a patch to files in the repository."""
    if not patch_file.exists():
        raise InputError(
            message=f"Patch file '{patch_file}' not found.",
            code="E1001",
            suggestion=Suggestion(action="check_path", fix="Verify the patch file path.")
        )

    # Mocking patch logic for demo
    # In a real app, we'd parse the diff and identify targets
    targets = ["src/app.py", "tests/test_main.py"]

    for target in targets:
        # Demo superpower: record dry action
        record_dry_action(
            action="modify_file",
            target=target,
            details={"hunks": 1, "additions": 5, "deletions": 2}
        )

    # If --dry-run is active, @dry_run_support returns the recorded plan automatically.
    # Otherwise, we proceed with the actual destructive operation.

    # Simulate a failure condition
    if "conflict" in patch_file.name:
        raise InputError(
            message="Patch conflict detected in src/app.py",
            code="E1002",
            suggestion=Suggestion(
                action="retry_with_fuzz",
                fix="Conflict at offset 120. Try rerunning with --fuzz.",
                example=f"apply {patch_file} --fuzz"
            )
        )

    return f"Successfully applied patch from {patch_file}"

if __name__ == "__main__":
    app()
