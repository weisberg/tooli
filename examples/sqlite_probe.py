"""SQLite inspection example for Tooli."""

from __future__ import annotations

import os
import sqlite3
from typing import Annotated, Any

from tooli import Argument, Option, Tooli
from tooli.annotations import ReadOnly
from tooli.errors import InputError, Suggestion

app = Tooli(name="sqlite-probe", description="Explore local SQLite data with guarded queries")


def _validate_db_path(db_path: str) -> str:
    if not os.path.exists(db_path):
        raise InputError(
            message=f"Database file does not exist: {db_path}",
            code="E1001",
            suggestion=Suggestion(
                action="provide db path",
                fix="Pass a path to an existing SQLite database file.",
                example="sqlite-probe schema data/local.db",
            ),
            details={"path": db_path},
        )

    if not os.path.isfile(db_path):
        raise InputError(
            message=f"Expected a file for database path: {db_path}",
            code="E1002",
            suggestion=Suggestion(
                action="use file path",
                fix="Provide a concrete SQLite database file, not a directory.",
                example="sqlite-probe query local.db --sql \"SELECT 1\"",
            ),
            details={"path": db_path},
        )

    return db_path


@app.command(annotations=ReadOnly)
def schema(
    db_path: Annotated[str, Argument(help="Path to SQLite database")],
) -> list[dict[str, str | None]]:
    """Return SQLite table names and schema SQL."""

    path = _validate_db_path(db_path)
    try:
        with sqlite3.connect(path) as conn:
            cursor = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
            return [{"table": name, "sql": sql} for name, sql in cursor.fetchall()]
    except sqlite3.DatabaseError as exc:
        raise InputError(
            message=f"Could not read schema from '{db_path}': {exc}",
            code="E1003",
            suggestion=Suggestion(
                action="check database",
                fix="Verify the file is a valid SQLite database.",
                example=f"sqlite3 {db_path} \".schema\"",
            ),
        ) from exc


@app.command(annotations=ReadOnly)
def query(
    db_path: Annotated[str, Argument(help="Path to SQLite database")],
    sql: Annotated[str, Option(help="SELECT query to execute")],
    limit: Annotated[int, Option(help="Maximum rows to return to limit context size")] = 50,
) -> dict[str, Any]:
    """Execute a read-only SELECT query with cursor-safe pagination hints."""

    if not sql.strip().upper().startswith("SELECT"):
        raise InputError(
            message="Only SELECT queries are allowed.",
            code="E1004",
            suggestion=Suggestion(
                action="change query",
                fix="Use a read-only SELECT query only.",
                example="sqlite-probe query my.db --sql \"SELECT * FROM users LIMIT 20\"",
            ),
        )

    if limit < 1:
        raise InputError(
            message=f"limit must be >= 1: {limit}",
            code="E1005",
            suggestion=Suggestion(
                action="increase limit",
                fix="Pass a positive integer.",
                example="sqlite-probe query my.db --sql \"SELECT * FROM users\" --limit 10",
            ),
            details={"limit": limit},
        )

    path = _validate_db_path(db_path)
    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            rows: list[dict[str, Any]] = []
            has_more = False
            for index, row in enumerate(cursor, 1):
                if index > limit:
                    has_more = True
                    break
                rows.append(dict(row))
    except sqlite3.DatabaseError as exc:
        raise InputError(
            message=f"SQLite query failed: {exc}",
            code="E1006",
            suggestion=Suggestion(
                action="consult schema",
                fix="Run sqlite-probe schema first, then retry with exact table and column names.",
                example="sqlite-probe schema local.db",
            ),
            details={"path": path, "sql": sql},
        ) from exc

    return {
        "data": rows,
        "pagination": {
            "has_more": has_more,
            "returned": len(rows),
            "hint": f"Add OFFSET to see rows after {limit}." if has_more else None,
        },
    }


if __name__ == "__main__":
    app()
