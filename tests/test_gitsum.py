"""Tests for the gitsum example app."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from examples.gitsum.app import app

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available",
)


def _run_json(runner: CliRunner, args: list[str], **kwargs: object):
    result = runner.invoke(app, args, **kwargs)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    return payload["result"]


def _init_repo(path: "Path") -> None:
    """Create a minimal git repo with one commit."""
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(path), capture_output=True, check=True)

    readme = path / "README.md"
    readme.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(path), capture_output=True, check=True)


def test_gitsum_summary(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    runner = CliRunner()

    result = _run_json(runner, ["summary", "--repo", str(tmp_path)])
    assert result["branch"] in ("main", "master")
    assert result["commit_count"] == 1
    assert result["file_count"] == 1
    assert "last_commit" in result
    assert result["last_commit"]["message"] == "Initial commit"


def test_gitsum_log_stats(tmp_path: Path) -> None:
    _init_repo(tmp_path)

    # Add a second commit
    (tmp_path / "file2.txt").write_text("content\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Add file2"], cwd=str(tmp_path), capture_output=True, check=True)

    runner = CliRunner()
    result = _run_json(runner, ["log-stats", "--repo", str(tmp_path)])
    assert len(result) == 2
    assert result[0]["message"] == "Add file2"
    assert result[0]["insertions"] >= 1


def test_gitsum_diff_review_stdin() -> None:
    runner = CliRunner()
    diff_text = """\
diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1,3 +1,4 @@
 line1
+added line
 line2
-removed line
"""
    result = _run_json(runner, ["diff-review", "-"], input=diff_text)
    assert result["files_changed"] == 1
    assert result["insertions"] == 1
    assert result["deletions"] == 1
    assert result["files"][0]["file"] == "file.txt"


def test_gitsum_contributors(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    runner = CliRunner()

    result = _run_json(runner, ["contributors", "--repo", str(tmp_path)])
    assert len(result) == 1
    assert result[0]["name"] == "Test User"
    assert result[0]["email"] == "test@example.com"
    assert result[0]["commits"] == 1


def test_gitsum_branch_health(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    runner = CliRunner()

    result = _run_json(runner, ["branch-health", "--repo", str(tmp_path), "--stale-days", "1"])
    assert len(result) >= 1
    assert result[0]["stale"] is False  # Just created, not stale


def test_gitsum_not_a_repo(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["summary", "--repo", str(tmp_path)])
    assert result.exit_code != 0
