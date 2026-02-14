"""Tests for the taskr example app."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from examples.taskr.app import app

if TYPE_CHECKING:
    from pathlib import Path


def _run_json(runner: CliRunner, args: list[str], **kwargs: object):
    result = runner.invoke(app, args, **kwargs)
    assert result.exit_code == 0, result.output
    for line in reversed(result.output.strip().splitlines()):
        data = json.loads(line)
        if "ok" in data:
            return data["result"]
    raise AssertionError("No envelope found in output")


def test_taskr_add_and_list(tmp_path: Path) -> None:
    store = str(tmp_path / "tasks.json")
    runner = CliRunner()

    result = _run_json(runner, ["add", "Buy groceries", "--store", store])
    assert result["created"] is True
    assert result["task"]["title"] == "Buy groceries"
    assert result["task"]["status"] == "pending"

    tasks = _run_json(runner, ["list", "--store", store])
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Buy groceries"


def test_taskr_add_idempotent(tmp_path: Path) -> None:
    store = str(tmp_path / "tasks.json")
    runner = CliRunner()

    first = _run_json(runner, ["add", "Write tests", "--store", store])
    assert first["created"] is True

    second = _run_json(runner, ["add", "Write tests", "--store", store])
    assert second["created"] is False
    assert second["message"] == "Task already exists"


def test_taskr_done(tmp_path: Path) -> None:
    store = str(tmp_path / "tasks.json")
    runner = CliRunner()

    add_result = _run_json(runner, ["add", "Review PR", "--store", store])
    task_id = add_result["task"]["id"]

    done_result = _run_json(runner, ["done", task_id, "--store", store])
    assert done_result["changed"] is True
    assert done_result["task"]["status"] == "done"


def test_taskr_done_idempotent(tmp_path: Path) -> None:
    store = str(tmp_path / "tasks.json")
    runner = CliRunner()

    add_result = _run_json(runner, ["add", "Ship feature", "--store", store])
    task_id = add_result["task"]["id"]

    _run_json(runner, ["done", task_id, "--store", store])
    second = _run_json(runner, ["done", task_id, "--store", store])
    assert second["changed"] is False
    assert second["message"] == "Task already done"


def test_taskr_edit(tmp_path: Path) -> None:
    store = str(tmp_path / "tasks.json")
    runner = CliRunner()

    add_result = _run_json(runner, ["add", "Draft RFC", "--store", store, "--priority", "low"])
    task_id = add_result["task"]["id"]

    edit_result = _run_json(runner, ["edit", task_id, "--store", store, "--priority", "high"])
    assert edit_result["changed"] is True
    assert edit_result["task"]["priority"] == "high"


def test_taskr_purge(tmp_path: Path) -> None:
    store = str(tmp_path / "tasks.json")
    runner = CliRunner()

    r1 = _run_json(runner, ["add", "Task A", "--store", store])
    r2 = _run_json(runner, ["add", "Task B", "--store", store])
    _run_json(runner, ["done", r1["task"]["id"], "--store", store])

    purge_result = _run_json(runner, ["purge", "--store", store, "--yes"])
    assert purge_result["purged"] == 1
    assert purge_result["remaining"] == 1

    remaining = _run_json(runner, ["list", "--store", store])
    assert len(remaining) == 1
    assert remaining[0]["title"] == "Task B"


def test_taskr_list_with_filters(tmp_path: Path) -> None:
    store = str(tmp_path / "tasks.json")
    runner = CliRunner()

    _run_json(runner, ["add", "Low task", "--store", store, "--priority", "low"])
    r2 = _run_json(runner, ["add", "High task", "--store", store, "--priority", "high"])
    _run_json(runner, ["done", r2["task"]["id"], "--store", store])

    pending = _run_json(runner, ["list", "--store", store, "--status", "pending"])
    assert len(pending) == 1

    high = _run_json(runner, ["list", "--store", store, "--priority", "high"])
    assert len(high) == 1
    assert high[0]["title"] == "High task"
