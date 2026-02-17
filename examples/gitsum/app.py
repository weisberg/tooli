"""Git Repository Analyst example app.

Analyze git repositories with structured output for agents.
Showcases: ReadOnly annotation, paginated list commands, subprocess integration,
stdin input for diff analysis.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from tooli import Argument, Option, Tooli
from tooli.annotations import ReadOnly
from tooli.errors import InputError, ToolRuntimeError

app = Tooli(
    name="gitsum",
    help="Git repository analysis and statistics",
    triggers=[
        "analyzing git history",
        "reviewing commit patterns",
        "checking repository health",
    ],
    anti_triggers=[
        "modifying git state",
        "when git is not installed",
    ],
)


def _run_git(args: list[str], repo: str = ".") -> str:
    """Execute a git command and return stdout."""
    git_bin = shutil.which("git")
    if git_bin is None:
        raise ToolRuntimeError(
            message="git is not installed or not found in PATH",
            code="E2001",
        )

    repo_path = Path(repo).resolve()
    if not repo_path.exists():
        raise InputError(
            message=f"Repository path does not exist: {repo}",
            code="E2002",
            details={"path": repo},
        )

    try:
        result = subprocess.run(
            [git_bin, *args],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolRuntimeError(
            message=f"Git command timed out: git {' '.join(args)}",
            code="E2003",
        ) from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "not a git repository" in stderr.lower():
            raise InputError(
                message=f"Not a git repository: {repo}",
                code="E2004",
                details={"path": repo},
            )
        raise ToolRuntimeError(
            message=f"Git command failed: {stderr}",
            code="E2005",
            details={"command": f"git {' '.join(args)}", "stderr": stderr},
        )

    return result.stdout


@app.command(
    annotations=ReadOnly,
    when_to_use="Get a quick overview of a git repository including branch, commit count, and remotes",
    task_group="Query",
    pipe_output={"format": "json"},
    capabilities=["fs:read", "process:exec"],
    handoffs=[{"command": "log-stats", "when": "need detailed commit-level statistics"}, {"command": "branch-health", "when": "need to check for stale branches"}],
)
def summary(
    *,
    repo: Annotated[str, Option(help="Path to git repository")] = ".",
) -> dict[str, Any]:
    """Overview of repository: branch, commit count, file count, remote info."""
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo).strip()
    commit_count = int(_run_git(["rev-list", "--count", "HEAD"], repo).strip())

    tracked_files = _run_git(["ls-files"], repo).strip().splitlines()
    file_count = len([f for f in tracked_files if f.strip()])

    remotes_raw = _run_git(["remote", "-v"], repo).strip()
    remotes: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in remotes_raw.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] not in seen:
            seen.add(parts[0])
            remotes.append({"name": parts[0], "url": parts[1]})

    last_log = _run_git(["log", "-1", "--format=%H%n%an%n%ae%n%aI%n%s"], repo).strip()
    log_parts = last_log.splitlines()
    last_commit = {}
    if len(log_parts) >= 5:
        last_commit = {
            "hash": log_parts[0],
            "author": log_parts[1],
            "email": log_parts[2],
            "date": log_parts[3],
            "message": log_parts[4],
        }

    return {
        "branch": branch,
        "commit_count": commit_count,
        "file_count": file_count,
        "remotes": remotes,
        "last_commit": last_commit,
    }


@app.command(
    paginated=True,
    annotations=ReadOnly,
    timeout=60.0,
    when_to_use="Analyze commit history with per-commit insertion/deletion stats, optionally filtered by date or author",
    task_group="Analysis",
    pipe_output={"format": "json"},
    capabilities=["fs:read", "process:exec"],
    handoffs=[{"command": "diff-review", "when": "need to review changes in a specific commit range"}],
)
def log_stats(
    *,
    repo: Annotated[str, Option(help="Path to git repository")] = ".",
    since: Annotated[str | None, Option(help="Start date (ISO or relative like '2 weeks ago')")] = None,
    until: Annotated[str | None, Option(help="End date")] = None,
    author: Annotated[str | None, Option(help="Filter by author name or email")] = None,
) -> list[dict[str, Any]]:
    """Commit analytics: message, author, date, insertions, deletions."""
    args = ["log", "--format=%H|%an|%ae|%aI|%s", "--numstat"]
    if since:
        args.append(f"--since={since}")
    if until:
        args.append(f"--until={until}")
    if author:
        args.append(f"--author={author}")

    raw = _run_git(args, repo)
    commits: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for line in raw.splitlines():
        if "|" in line and line.count("|") >= 4:
            if current is not None:
                commits.append(current)
            parts = line.split("|", 4)
            current = {
                "hash": parts[0],
                "author": parts[1],
                "email": parts[2],
                "date": parts[3],
                "message": parts[4],
                "insertions": 0,
                "deletions": 0,
                "files_changed": 0,
            }
        elif current is not None and line.strip():
            stat_parts = line.split("\t")
            if len(stat_parts) >= 3:
                ins = stat_parts[0]
                dels = stat_parts[1]
                current["insertions"] += int(ins) if ins != "-" else 0
                current["deletions"] += int(dels) if dels != "-" else 0
                current["files_changed"] += 1

    if current is not None:
        commits.append(current)

    return commits


@app.command(
    annotations=ReadOnly,
    timeout=30.0,
    when_to_use="Review a diff to understand what changed: files affected, lines added/removed",
    task_group="Analysis",
    pipe_input={"format": "text"},
    pipe_output={"format": "json"},
    capabilities=["fs:read", "process:exec"],
)
def diff_review(
    source: Annotated[str, Argument(help="Diff file path, '-' for stdin, or git ref range (e.g. HEAD~3..HEAD)")],
    *,
    repo: Annotated[str, Option(help="Path to git repository")] = ".",
) -> dict[str, Any]:
    """Analyze a diff: files changed, insertions, deletions, file list."""
    if source == "-":
        try:
            diff_text = sys.stdin.read()
        except Exception as exc:
            raise InputError(
                message=f"Failed to read diff from stdin: {exc}",
                code="E2006",
            ) from exc
    elif ".." in source:
        diff_text = _run_git(["diff", source], repo)
    else:
        path = Path(source)
        if path.exists() and path.is_file():
            diff_text = path.read_text(encoding="utf-8")
        else:
            diff_text = _run_git(["diff", source], repo)

    return _parse_diff(diff_text)


def _parse_diff(diff_text: str) -> dict[str, Any]:
    """Parse unified diff text into structured stats."""
    files: list[dict[str, Any]] = []
    current_file: dict[str, Any] | None = None
    total_ins = 0
    total_dels = 0

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            if current_file is not None:
                files.append(current_file)
            parts = line.split()
            name = parts[-1].lstrip("b/") if len(parts) >= 4 else "unknown"
            current_file = {"file": name, "insertions": 0, "deletions": 0}
        elif current_file is not None:
            if line.startswith("+") and not line.startswith("+++"):
                current_file["insertions"] += 1
                total_ins += 1
            elif line.startswith("-") and not line.startswith("---"):
                current_file["deletions"] += 1
                total_dels += 1

    if current_file is not None:
        files.append(current_file)

    return {
        "files_changed": len(files),
        "insertions": total_ins,
        "deletions": total_dels,
        "files": files,
    }


@app.command(
    paginated=True,
    annotations=ReadOnly,
    when_to_use="List all contributors and their commit counts to understand team activity",
    task_group="Report",
    pipe_output={"format": "json"},
    capabilities=["fs:read", "process:exec"],
    handoffs=[{"command": "log-stats", "when": "need to drill into a specific contributor's commits"}],
)
def contributors(
    *,
    repo: Annotated[str, Option(help="Path to git repository")] = ".",
    sort: Annotated[str, Option(help="Sort by: commits or name")] = "commits",
) -> list[dict[str, Any]]:
    """Author statistics: commit count per contributor."""
    raw = _run_git(["shortlog", "-sne", "HEAD"], repo).strip()
    results: list[dict[str, Any]] = []

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        count_str, _, rest = line.partition("\t")
        count = int(count_str.strip())
        name_email = rest.strip()
        email = ""
        name = name_email
        if "<" in name_email and ">" in name_email:
            name = name_email[:name_email.index("<")].strip()
            email = name_email[name_email.index("<") + 1:name_email.index(">")]

        results.append({"name": name, "email": email, "commits": count})

    if sort == "name":
        results.sort(key=lambda r: r["name"].lower())

    return results


@app.command(
    paginated=True,
    annotations=ReadOnly,
    when_to_use="Identify stale branches that may need cleanup based on last commit age",
    task_group="Analysis",
    pipe_output={"format": "json"},
    capabilities=["fs:read", "process:exec"],
    delegation_hint="Use this before cleanup operations to identify stale branches",
)
def branch_health(
    *,
    repo: Annotated[str, Option(help="Path to git repository")] = ".",
    stale_days: Annotated[int, Option(help="Days without commits to consider stale")] = 30,
) -> list[dict[str, Any]]:
    """Detect stale branches by last commit date."""
    raw = _run_git(
        ["for-each-ref", "--format=%(refname:short)|%(committerdate:iso8601)", "refs/heads/"],
        repo,
    ).strip()

    now = datetime.now(tz=timezone.utc)
    results: list[dict[str, Any]] = []

    for line in raw.splitlines():
        if "|" not in line:
            continue
        branch, _, date_str = line.partition("|")
        branch = branch.strip()
        date_str = date_str.strip()

        try:
            commit_date = datetime.fromisoformat(date_str.replace(" ", "T", 1).replace(" ", ""))
            if commit_date.tzinfo is None:
                commit_date = commit_date.replace(tzinfo=timezone.utc)
            age_days = (now - commit_date).days
        except (ValueError, TypeError):
            age_days = -1

        results.append({
            "branch": branch,
            "last_commit": date_str,
            "age_days": age_days,
            "stale": age_days >= stale_days if age_days >= 0 else False,
        })

    results.sort(key=lambda r: r["age_days"], reverse=True)
    return results


if __name__ == "__main__":
    app()
