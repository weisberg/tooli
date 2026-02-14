"""Local Task Manager example app.

Manage tasks with a local JSON store.
Showcases: Idempotent and Destructive annotations, paginated CRUD,
state management with local file storage.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

import typer  # noqa: TC002

from tooli import Argument, Option, Tooli
from tooli.annotations import Destructive, Idempotent, ReadOnly
from tooli.errors import InputError

app = Tooli(name="taskr", help="Local task manager with JSON storage")

DEFAULT_STORE = "taskr-data.json"

VALID_PRIORITIES = ("low", "medium", "high")
VALID_STATUSES = ("pending", "done")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def _task_id(title: str) -> str:
    """Deterministic short ID from title for idempotency."""
    return hashlib.sha256(title.encode()).hexdigest()[:8]


def _read_store(store: str) -> list[dict[str, Any]]:
    path = Path(store)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return data
    except (json.JSONDecodeError, OSError):
        return []


def _write_store(store: str, tasks: list[dict[str, Any]]) -> None:
    Path(store).write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")


def _find_task(tasks: list[dict[str, Any]], task_id: str) -> dict[str, Any] | None:
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return None


@app.command(annotations=Idempotent)
def add(
    ctx: typer.Context,
    title: Annotated[str, Argument(help="Task title")],
    *,
    store: Annotated[str, Option(help="JSON store file path")] = DEFAULT_STORE,
    priority: Annotated[str, Option(help="Priority: low, medium, or high")] = "medium",
    tags: Annotated[str | None, Option(help="Comma-separated tags")] = None,
) -> dict[str, Any]:
    """Create a new task. Idempotent: same title produces same ID."""
    if priority not in VALID_PRIORITIES:
        raise InputError(
            message=f"Invalid priority: {priority}. Use: {', '.join(VALID_PRIORITIES)}",
            code="E9001",
            details={"priority": priority},
        )

    tid = _task_id(title)
    tasks = _read_store(store)
    existing = _find_task(tasks, tid)

    if existing is not None:
        return {
            "id": tid,
            "created": False,
            "message": "Task already exists",
            "task": existing,
        }

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    task: dict[str, Any] = {
        "id": tid,
        "title": title,
        "status": "pending",
        "priority": priority,
        "tags": tag_list,
        "created_at": _now_iso(),
        "completed_at": None,
    }

    if not getattr(ctx.obj, "dry_run", False):
        tasks.append(task)
        _write_store(store, tasks)

    return {
        "id": tid,
        "created": True,
        "task": task,
    }


@app.command(name="list", paginated=True, annotations=ReadOnly)
def list_(
    *,
    store: Annotated[str, Option(help="JSON store file path")] = DEFAULT_STORE,
    status_filter: Annotated[str | None, Option("--status", help="Filter: pending or done")] = None,
    priority: Annotated[str | None, Option(help="Filter by priority")] = None,
    sort_by: Annotated[str, Option(help="Sort by: created, priority, or title")] = "created",
) -> list[dict[str, Any]]:
    """List tasks with optional filtering and sorting."""
    if status_filter and status_filter not in VALID_STATUSES:
        raise InputError(
            message=f"Invalid status filter: {status_filter}. Use: {', '.join(VALID_STATUSES)}",
            code="E9002",
        )

    tasks = _read_store(store)

    if status_filter:
        tasks = [t for t in tasks if t.get("status") == status_filter]

    if priority:
        tasks = [t for t in tasks if t.get("priority") == priority]

    priority_order = {"high": 0, "medium": 1, "low": 2}
    if sort_by == "priority":
        tasks.sort(key=lambda t: priority_order.get(t.get("priority", "medium"), 1))
    elif sort_by == "title":
        tasks.sort(key=lambda t: t.get("title", "").lower())
    else:
        tasks.sort(key=lambda t: t.get("created_at", ""))

    return tasks


@app.command(annotations=Idempotent)
def done(
    ctx: typer.Context,
    task_id: Annotated[str, Argument(help="Task ID to mark as complete")],
    *,
    store: Annotated[str, Option(help="JSON store file path")] = DEFAULT_STORE,
) -> dict[str, Any]:
    """Mark a task as done. Idempotent: marking an already-done task is a no-op."""
    tasks = _read_store(store)
    task = _find_task(tasks, task_id)

    if task is None:
        raise InputError(
            message=f"Task not found: {task_id}",
            code="E9003",
            details={"task_id": task_id},
        )

    if task["status"] == "done":
        return {
            "id": task_id,
            "changed": False,
            "message": "Task already done",
            "task": task,
        }

    task["status"] = "done"
    task["completed_at"] = _now_iso()

    if not getattr(ctx.obj, "dry_run", False):
        _write_store(store, tasks)

    return {
        "id": task_id,
        "changed": True,
        "task": task,
    }


@app.command(annotations=Idempotent)
def edit(
    ctx: typer.Context,
    task_id: Annotated[str, Argument(help="Task ID to edit")],
    *,
    store: Annotated[str, Option(help="JSON store file path")] = DEFAULT_STORE,
    title: Annotated[str | None, Option(help="New title")] = None,
    priority: Annotated[str | None, Option(help="New priority")] = None,
) -> dict[str, Any]:
    """Modify a task's title or priority."""
    tasks = _read_store(store)
    task = _find_task(tasks, task_id)

    if task is None:
        raise InputError(
            message=f"Task not found: {task_id}",
            code="E9004",
            details={"task_id": task_id},
        )

    if priority and priority not in VALID_PRIORITIES:
        raise InputError(
            message=f"Invalid priority: {priority}",
            code="E9005",
            details={"priority": priority},
        )

    changes: dict[str, Any] = {}
    if title is not None and title != task["title"]:
        changes["title"] = {"from": task["title"], "to": title}
        task["title"] = title
    if priority is not None and priority != task["priority"]:
        changes["priority"] = {"from": task["priority"], "to": priority}
        task["priority"] = priority

    if changes and not getattr(ctx.obj, "dry_run", False):
        _write_store(store, tasks)

    return {
        "id": task_id,
        "changed": len(changes) > 0,
        "changes": changes,
        "task": task,
    }


@app.command(annotations=Destructive)
def purge(
    ctx: typer.Context,
    *,
    store: Annotated[str, Option(help="JSON store file path")] = DEFAULT_STORE,
) -> dict[str, Any]:
    """Remove all completed tasks. Destructive: cannot be undone."""
    tasks = _read_store(store)
    completed = [t for t in tasks if t.get("status") == "done"]
    remaining = [t for t in tasks if t.get("status") != "done"]

    if not getattr(ctx.obj, "dry_run", False):
        _write_store(store, remaining)

    return {
        "purged": len(completed),
        "remaining": len(remaining),
        "purged_ids": [t["id"] for t in completed],
    }
