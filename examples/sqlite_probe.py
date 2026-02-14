"""Structured SQLite exploration example for Tooli.

`sqlite-probe` gives agents a safe, read-only path into local databases:
- inspect schema before drafting queries,
- execute only `SELECT` statements,
- constrain result sets so token budgets stay bounded,
- surface recoverable errors with next-step suggestions.

Use it as a repeatable pattern when an agent needs machine-readable database
context without losing control over destructive operations.

Agent workflow:
- `python sqlite_probe.py schema local.db`
- `python sqlite_probe.py query local.db --sql "SELECT * FROM users ORDER BY id" --limit 25`
- `python sqlite_probe.py query local.db --sql "SELECT * FROM users" --explain`
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Annotated, Any

from tooli import Argument, Option, Tooli
from tooli.annotations import Idempotent, ReadOnly
from tooli.errors import InputError, Suggestion

app = Tooli(name="sqlite-probe", description="Explore SQLite databases safely and read-only")


def _validate_db_path(db_path: str) -> Path:
    if not db_path or not db_path.strip():
        raise InputError(
            message="Database path must not be empty.",
            code="E1001",
            suggestion=Suggestion(
                action="provide db path",
                fix="Pass a concrete SQLite database file path.",
                example="sqlite-probe schema local.db",
            ),
        )

    normalized = db_path.strip()
    if not os.path.exists(normalized):
        raise InputError(
            message=f"Database file does not exist: {normalized}",
            code="E1001",
            suggestion=Suggestion(
                action="provide db path",
                fix="Use a real SQLite file path.",
                example="sqlite-probe schema notes.db",
            ),
            details={"path": normalized},
        )

    if not os.path.isfile(normalized):
        raise InputError(
            message=f"Expected a file for database path: {normalized}",
            code="E1002",
            suggestion=Suggestion(
                action="provide file path",
                fix="Provide a concrete SQLite database file path, not a directory.",
                example="sqlite-probe query local.db --sql \"SELECT 1\"",
            ),
            details={"path": normalized},
        )

    return Path(normalized)


def _read_schema(path: str) -> list[dict[str, str | None]]:
    database = _validate_db_path(path)
    try:
        with sqlite3.connect(database) as conn:
            cursor = conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            return [{"table": row[0], "sql": row[1]} for row in cursor.fetchall()]
    except sqlite3.DatabaseError as exc:
        raise InputError(
            message=f"Could not read schema from '{database}': {exc}",
            code="E1003",
            suggestion=Suggestion(
                action="check database",
                fix="Verify the file is a valid SQLite database.",
                example=f"sqlite3 {database} .schema",
            ),
            details={"path": str(database)},
        ) from exc


def _validate_select(sql: str) -> str:
    raw = sql.strip()
    if not raw:
        raise InputError(
            message="SQL must not be empty.",
            code="E1004",
            suggestion=Suggestion(
                action="provide query",
                fix='Use a SELECT query. Example: "SELECT * FROM table LIMIT 10".',
            ),
            details={"sql": sql},
        )

    if raw.endswith(";"):
        raw = raw[:-1].strip()

    if ";" in raw:
        raise InputError(
            message="Only one SQL statement is allowed.",
            code="E1004",
            suggestion=Suggestion(
                action="split statements",
                fix="Run one SELECT statement per invocation.",
                example="sqlite-probe query local.db --sql \"SELECT id FROM notes\"",
            ),
            details={"sql": raw},
        )

    if not raw.upper().startswith("SELECT"):
        raise InputError(
            message="Only SELECT statements are allowed.",
            code="E1004",
            suggestion=Suggestion(
                action="change query",
                fix="Use read-only SELECT queries only.",
                example="sqlite-probe query local.db --sql \"SELECT * FROM users LIMIT 20\"",
            ),
        )
    return raw


def _run_select(path: Path, sql: str, limit: int, offset: int) -> list[dict[str, Any]]:
    paged_sql = f"{sql} LIMIT {limit} OFFSET {offset}"
    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(paged_sql)
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.DatabaseError as exc:
        raise InputError(
            message=f"SQLite query failed: {exc}",
            code="E1006",
            suggestion=Suggestion(
                action="check schema first",
                fix="Call `sqlite-probe schema <db>` and verify table/column names.",
                example="sqlite-probe schema notes.db",
            ),
            details={"path": str(path), "sql": paged_sql},
        ) from exc


def _run_plan(path: Path, sql: str) -> list[dict[str, Any]]:
    try:
        with sqlite3.connect(path) as conn:
            cursor = conn.execute(f"EXPLAIN QUERY PLAN {sql}")
            rows = cursor.fetchall()
            return [
                {
                    "query_plan_step": idx,
                    "details": tuple(row),
                }
                for idx, row in enumerate(rows)
            ]
    except sqlite3.DatabaseError as exc:
        raise InputError(
            message=f"Failed to explain query: {exc}",
            code="E1007",
            suggestion=Suggestion(
                action="retry query",
                fix="Ensure query is a valid SELECT before asking for a plan.",
                example="sqlite-probe query local.db --sql \"SELECT * FROM notes\" --explain",
            ),
            details={"sql": sql},
        ) from exc


@app.command(
    annotations=ReadOnly | Idempotent,
    paginated=True,
    list_processing=True,
    cost_hint="low",
    examples=[
        {
            "args": ["schema", "notes.db"],
            "description": "Inspect table names and SQL definitions before querying",
        },
        {
            "args": ["schema", "notes.db", "--max-name-width", "20"],
            "description": "Limit table-name width in tooling-driven outputs",
        },
    ],
    error_codes={
        "E1001": "Invalid database path.",
        "E1002": "Path is not a file.",
        "E1003": "Unable to read database schema.",
    },
)
def schema(
    db_path: Annotated[str, Argument(help="Path to SQLite database")],
) -> list[dict[str, str | None]]:
    """Read-only table schema inspection.

    Agent guidance:
    - call this before `query` to discover table/column names,
    - pair with `--output json` for machine-readable lists,
    - reduce noise before paging deeply nested schemas.
    """
    return _read_schema(db_path)


@app.command(
    annotations=ReadOnly | Idempotent,
    paginated=True,
    cost_hint="medium",
    examples=[
        {
            "args": [
                "query",
                "notes.db",
                "--sql",
                "SELECT id, title FROM notes ORDER BY id LIMIT 20",
            ],
            "description": "Read-only query with predictable pagination fields.",
        },
        {
            "args": [
                "query",
                "notes.db",
                "--sql",
                "SELECT * FROM notes",
                "--explain",
            ],
            "description": "Validate execution plan before pulling a larger page.",
        },
    ],
    error_codes={
        "E1004": "Non-select query rejected.",
        "E1005": "Limit must be >= 1.",
        "E1006": "Query execution failed.",
        "E1007": "Query plan failed.",
    },
)
def query(
    db_path: Annotated[str, Argument(help="Path to SQLite database")],
    sql: Annotated[str, Option(help="SELECT query to execute")],
    limit: Annotated[int, Option(help="Maximum rows to return", min=1)] = 50,
    offset: Annotated[int, Option(help="Pagination offset for next page", min=0)] = 0,
    explain: Annotated[bool, Option(help="Return EXPLAIN QUERY PLAN instead of rows")]=False,
) -> dict[str, Any]:
    """Execute read-only SELECT queries with explicit pagination metadata.

    Agent guidance:
    - use `--limit` and `--offset` instead of raw OFFSET in SQL,
    - prefer deterministic `ORDER BY` clauses when paging,
    - run `--explain` if results are unexpectedly empty.
    """

    path = _validate_db_path(db_path)
    validated_sql = _validate_select(sql)

    if explain:
        plan = _run_plan(path, validated_sql)
        return {
            "mode": "explain",
            "query": validated_sql,
            "query_plan": plan,
            "count": len(plan),
            "path": str(path),
        }

    if limit < 1:
        raise InputError(
            message=f"limit must be >= 1: {limit}",
            code="E1005",
            suggestion=Suggestion(
                action="set limit",
                fix="Pass a positive integer for --limit.",
                example="sqlite-probe query local.db --sql \"SELECT * FROM users\" --limit 10",
            ),
            details={"limit": limit},
        )

    rows = _run_select(path, validated_sql, limit=limit, offset=offset)
    has_more = len(rows) == limit

    return {
        "data": rows,
        "path": str(path),
        "query": {
            "requested": validated_sql,
            "executed": f"{validated_sql} LIMIT {limit} OFFSET {offset}",
        },
        "pagination": {
            "has_more": has_more,
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if has_more else None,
            "returned": len(rows),
            "hint": (
                f"Use --offset {offset + limit} to fetch the next window."
                if has_more
                else "End of result set for this query."
            ),
        },
    }


if __name__ == "__main__":
    app()
