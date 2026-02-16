#!/usr/bin/env python3
"""1.x stabilization checks for repository hygiene and doc consistency."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
PLAN_MD = ROOT / "PLAN.md"
PRD_MD = ROOT / "PRD.md"
CHANGELOG = ROOT / "CHANGELOG.md"


def _load_project_version() -> str:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _load_latest_changelog_version() -> str:
    changelog = CHANGELOG.read_text(encoding="utf-8")
    match = re.search(r"^## \[(\d+\.\d+\.\d+)\]", changelog, flags=re.MULTILINE)
    if not match:
        raise RuntimeError("CHANGELOG.md is missing a semver heading like '## [x.y.z]'.")
    return match.group(1)


def _git_tracked_files() -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=False,
    )
    paths: list[Path] = []
    for item in proc.stdout.split(b"\x00"):
        if item:
            paths.append(Path(item.decode("utf-8")))
    return paths


def _check_duplicate_suffix_files() -> list[str]:
    offenders: list[str] = []
    # Common accidental duplicate pattern from conflict/IDE copies:
    # "name 2.py", "name 3.md", etc.
    pattern = re.compile(r" \d+\.[^./]+$")
    for path in _git_tracked_files():
        if pattern.search(path.name):
            offenders.append(str(path))
    return offenders


def _check_doc_status_markers() -> list[str]:
    errors: list[str] = []
    plan_text = PLAN_MD.read_text(encoding="utf-8")
    prd_text = PRD_MD.read_text(encoding="utf-8")
    release_line = "v" + ".".join(_load_project_version().split(".")[:2]) + ".x"

    if f"Tooli {release_line} has been released." not in plan_text:
        errors.append(
            "PLAN.md status line is stale or missing expected marker "
            f"\"Tooli {release_line} has been released.\""
        )

    if f"Implemented ({release_line}), with v2 roadmap planned." not in prd_text:
        errors.append(
            "PRD.md status line is stale or missing expected marker "
            f"\"Implemented ({release_line}), with v2 roadmap planned.\""
        )

    return errors


def main() -> int:
    failures: list[str] = []

    package_version = _load_project_version()
    changelog_version = _load_latest_changelog_version()
    if package_version != changelog_version:
        failures.append(
            "Version mismatch: pyproject.toml has "
            f"{package_version}, but latest CHANGELOG.md entry is {changelog_version}."
        )

    duplicate_files = _check_duplicate_suffix_files()
    if duplicate_files:
        rendered = "\n".join(f"  - {path}" for path in duplicate_files)
        failures.append(
            "Tracked duplicate-suffix files detected (e.g. 'file 2.py'):\n"
            f"{rendered}"
        )

    failures.extend(_check_doc_status_markers())

    if failures:
        print("1.x hardening checks failed:\n", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("1.x hardening checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
