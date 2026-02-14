"""Structured SQLite exploration example for Tooli.

This tool demonstrates read-only database access patterns where agents need:
- schema visibility before querying,
- strict query validation to avoid destructive actions,
- compact result packaging and cursor-style pagination hints.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Annotated, Any

from tooli import Argument, Option, Tooli
from tooli.annotations import Idempotent, ReadOnly
from tooli.errors import InputError, Suggestion

app = Tooli(name="sqlite-probe", description="Explore SQLite databases safely and read-only")


def _validate_db_path(db_path: str) -> None:
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

    if not os.path.exists(db_path):
        raise InputError(
            message=f"Database file does not exist: {db_path}",
            code="E1001",
            suggestion=Suggestion(
                action="provide db path",
                fix="Use a real SQLite file path.",
                example="sqlite-probe schema notes.db",
            ),
            details={"path": db_path},
        )

    if not os.path.isfile(db_path):
        raise InputError(
            message=f"Expected a file for database path: {db_path}",
            code="E1002",
            suggestion=Suggestion(
                action="provide file path",
                fix="Provide a concrete SQLite database file path, not a directory.",
                example="sqlite-probe query local.db --sql \"SELECT 1\"",
            ),
            details={"path": db_path},
        )


def _read_schema(path: str) -> list[dict[str, str | None]]:
    _validate_db_path(path)
    try:
        with sqlite3.connect(path) as conn:
            cursor = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name")
            return [{"table": row[0], "sql": row[1]} for row in cursor.fetchall()]
    except sqlite3.DatabaseError as exc:
        raise InputError(
            message=f"Could not read schema from '{path}': {exc}",
            code="E1003",
            suggestion=Suggestion(
                action="check database",
                fix="Verify the file is a valid SQLite database.",
                example=f"sqlite3 {path} \".schema\"",
            ),
            details={"path": path},
        ) from exc


@app.command(
    annotations=ReadOnly | Idempotent,
    paginated=True,
    list_processing=True,
    cost_hint="low",
    examples=[
        {"args": ["schema", "notes.db"], "description": "Inspect table names and SQL definitions"},
    ],
    error_codes={"E1003": "Unable to read database schema."},
)
def schema(
    db_path: Annotated[str, Argument(help="Path to SQLite database")],
) -> list[dict[str, str | None]]:
    """Read-only table schema inspection.

    Agent guidance:
    - call this before `query` to discover table/column names,
    - pair with `--output json` for machine-readable table lists.
    """
    return _read_schema(db_path)


def _validate_select(sql: str) -> str:
    raw = sql.strip()
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
    ],
    error_codes={
        "E1004": "Non-select query rejected.",
        "E1005": "Limit must be >= 1.",
        "E1006": "Query execution failed.",
    },
)
def query(
    db_path: Annotated[str, Argument(help="Path to SQLite database")],
    sql: Annotated[str, Option(help="SELECT query to execute")],
    limit: Annotated[int, Option(help="Maximum rows to return", min=1)] = 50,
    offset: Annotated[int, Option(help="Pagination offset for next page", min=0)] = 0,
) -> dict[str, Any]:
    """Execute read-only SELECT queries with explicit pagination metadata.

    Agent guidance:
    - use `--limit` and `--offset` instead of OFFSET-free queries for pagination,
    - prefer deterministic ORDER BY clauses when paging,
    - validate query shape in a small LIMIT before reading large tables.
    """
    _validate_db_path(db_path)

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

    validated_sql = _validate_select(sql)

    # Inject paging at the SQL layer while preserving agent intent.
    paged_sql = f"{validated_sql} LIMIT {limit} OFFSET {offset}"

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(paged_sql)
            rows = [dict(row) for row in cursor.fetchall()]
    except sqlite3.DatabaseError as exc:
        raise InputError(
            message=f"SQLite query failed: {exc}",
            code="E1006",
            suggestion=Suggestion(
                action="check schema first",
                fix="Call `sqlite-probe schema <db>` and verify table/column names.",
                example="sqlite-probe schema notes.db",
            ),
            details={"path": db_path, "sql": paged_sql},
        ) from exc

    has_more = len(rows) == limit
    return {
        "data": rows,
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
        "sql": {
            "requested": validated_sql,
            "executed": paged_sql,
        },
    }


if __name__ == "__main__":
    app()
