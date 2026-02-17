"""CSV Data Wrangling Toolkit example app.

Process and transform CSV data with structured output.
Showcases: StdinOr input pattern, JSONL output mode, paginated results,
OpenWorld annotation for data transformation commands.
"""

from __future__ import annotations

import contextlib
import csv
import io
import sys
from pathlib import Path
from typing import Annotated, Any

from tooli import Argument, Option, Tooli
from tooli.annotations import OpenWorld, ReadOnly
from tooli.errors import InputError

app = Tooli(name="csvkit-t", help="CSV data wrangling toolkit")


def _read_csv(source: str, delimiter: str = ",") -> tuple[list[str], list[dict[str, str]]]:
    """Read CSV from a file path or stdin ('-').

    Returns (headers, rows) where rows are dicts keyed by header names.
    """
    if source == "-":
        try:
            content = sys.stdin.read()
        except Exception as exc:
            raise InputError(
                message=f"Failed to read CSV from stdin: {exc}",
                code="E3001",
            ) from exc
    else:
        path = Path(source)
        if not path.exists():
            raise InputError(
                message=f"CSV file not found: {source}",
                code="E3002",
                details={"path": source},
            )
        if not path.is_file():
            raise InputError(
                message=f"Not a file: {source}",
                code="E3003",
                details={"path": source},
            )
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            raise InputError(
                message=f"Failed to read file '{source}': {exc}",
                code="E3004",
                details={"path": source},
            ) from exc

    if not content.strip():
        raise InputError(message="CSV input is empty", code="E3005")

    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    headers = reader.fieldnames or []
    rows = list(reader)
    return list(headers), rows


def _infer_type(values: list[str]) -> str:
    """Infer column type from a sample of values."""
    non_empty = [v for v in values if v.strip()]
    if not non_empty:
        return "empty"

    all_int = True
    all_float = True
    for v in non_empty:
        try:
            int(v)
        except ValueError:
            all_int = False
        try:
            float(v)
        except ValueError:
            all_float = False

    if all_int:
        return "int"
    if all_float:
        return "float"
    return "str"


@app.command(annotations=ReadOnly, capabilities=["fs:read"])
def inspect(
    source: Annotated[str, Argument(help="CSV file or '-' for stdin")],
    *,
    delimiter: Annotated[str, Option(help="Column delimiter")] = ",",
) -> dict[str, Any]:
    """Show column names, inferred types, row count, and basic stats."""
    headers, rows = _read_csv(source, delimiter)

    columns: list[dict[str, Any]] = []
    for header in headers:
        values = [row.get(header, "") for row in rows]
        non_null = sum(1 for v in values if v.strip())
        unique = len({v for v in values if v.strip()})
        col_type = _infer_type(values)

        col_info: dict[str, Any] = {
            "name": header,
            "type": col_type,
            "non_null": non_null,
            "unique": unique,
        }

        if col_type in ("int", "float"):
            numeric = []
            for v in values:
                with contextlib.suppress(ValueError):
                    numeric.append(float(v))
            if numeric:
                col_info["min"] = min(numeric)
                col_info["max"] = max(numeric)

        columns.append(col_info)

    return {
        "row_count": len(rows),
        "column_count": len(headers),
        "columns": columns,
    }


@app.command(paginated=True, annotations=ReadOnly, capabilities=["fs:read"])
def query(
    source: Annotated[str, Argument(help="CSV file or '-' for stdin")],
    *,
    where: Annotated[str | None, Option(help="Filter expression: column=value")] = None,
    columns: Annotated[str | None, Option(help="Comma-separated column names to select")] = None,
    sort_by: Annotated[str | None, Option(help="Sort by column name")] = None,
    descending: Annotated[bool, Option(help="Sort in descending order")] = False,
    delimiter: Annotated[str, Option(help="Column delimiter")] = ",",
) -> list[dict[str, Any]]:
    """Filter, select, and sort rows from CSV data."""
    headers, rows = _read_csv(source, delimiter)

    if where:
        if "=" not in where:
            raise InputError(
                message="Filter must be in 'column=value' format",
                code="E3006",
                details={"where": where},
            )
        col, _, val = where.partition("=")
        col = col.strip()
        val = val.strip()
        if col not in headers:
            raise InputError(
                message=f"Unknown column in filter: {col}",
                code="E3007",
                details={"column": col, "available": headers},
            )
        rows = [r for r in rows if r.get(col, "").strip() == val]

    if sort_by:
        if sort_by not in headers:
            raise InputError(
                message=f"Unknown sort column: {sort_by}",
                code="E3008",
                details={"column": sort_by, "available": headers},
            )
        rows.sort(key=lambda r: r.get(sort_by, ""), reverse=descending)

    if columns:
        selected = [c.strip() for c in columns.split(",")]
        for col_name in selected:
            if col_name not in headers:
                raise InputError(
                    message=f"Unknown column: {col_name}",
                    code="E3009",
                    details={"column": col_name, "available": headers},
                )
        rows = [{k: r[k] for k in selected if k in r} for r in rows]

    return rows


@app.command(annotations=OpenWorld, capabilities=["fs:read"])
def convert(
    source: Annotated[str, Argument(help="CSV file or '-' for stdin")],
    *,
    to_format: Annotated[str, Option(help="Output format: json or jsonl")] = "json",
    delimiter: Annotated[str, Option(help="Column delimiter")] = ",",
) -> dict[str, Any]:
    """Convert CSV to JSON format."""
    if to_format not in ("json", "jsonl"):
        raise InputError(
            message=f"Unsupported format: {to_format}. Use 'json' or 'jsonl'.",
            code="E3010",
            details={"format": to_format},
        )

    headers, rows = _read_csv(source, delimiter)
    return {
        "format": to_format,
        "row_count": len(rows),
        "columns": headers,
        "rows": rows,
    }


@app.command(annotations=ReadOnly, capabilities=["fs:read"])
def validate(
    source: Annotated[str, Argument(help="CSV file or '-' for stdin")],
    *,
    delimiter: Annotated[str, Option(help="Column delimiter")] = ",",
    require_columns: Annotated[str | None, Option(help="Required column names (comma-separated)")] = None,
    max_rows: Annotated[int | None, Option(help="Maximum allowed row count")] = None,
) -> dict[str, Any]:
    """Validate CSV structure and report issues."""
    headers, rows = _read_csv(source, delimiter)
    issues: list[str] = []

    if require_columns:
        required = {c.strip() for c in require_columns.split(",")}
        missing = required - set(headers)
        if missing:
            issues.append(f"Missing required columns: {', '.join(sorted(missing))}")

    if max_rows is not None and len(rows) > max_rows:
        issues.append(f"Row count {len(rows)} exceeds maximum {max_rows}")

    for idx, row in enumerate(rows):
        empty_cols = [h for h in headers if not row.get(h, "").strip()]
        if empty_cols:
            issues.append(f"Row {idx + 1}: empty values in columns: {', '.join(empty_cols)}")

    return {
        "valid": len(issues) == 0,
        "row_count": len(rows),
        "column_count": len(headers),
        "columns": headers,
        "issues": issues,
    }


@app.command(annotations=OpenWorld, capabilities=["fs:read"])
def merge(
    left: Annotated[str, Argument(help="Left CSV file path")],
    right: Annotated[str, Argument(help="Right CSV file path")],
    *,
    on: Annotated[str, Option(help="Join column name")],
    how: Annotated[str, Option(help="Join type: inner, left, or right")] = "inner",
    delimiter: Annotated[str, Option(help="Column delimiter")] = ",",
) -> dict[str, Any]:
    """Join two CSV files on a shared column."""
    if how not in ("inner", "left", "right"):
        raise InputError(
            message=f"Unsupported join type: {how}. Use 'inner', 'left', or 'right'.",
            code="E3011",
            details={"how": how},
        )

    left_headers, left_rows = _read_csv(left, delimiter)
    right_headers, right_rows = _read_csv(right, delimiter)

    if on not in left_headers:
        raise InputError(
            message=f"Join column '{on}' not found in left CSV",
            code="E3012",
            details={"column": on, "available": left_headers},
        )
    if on not in right_headers:
        raise InputError(
            message=f"Join column '{on}' not found in right CSV",
            code="E3013",
            details={"column": on, "available": right_headers},
        )

    right_index: dict[str, list[dict[str, str]]] = {}
    for row in right_rows:
        key = row.get(on, "")
        right_index.setdefault(key, []).append(row)

    all_headers = list(left_headers)
    for h in right_headers:
        if h not in all_headers:
            all_headers.append(h)

    result_rows: list[dict[str, str]] = []

    if how in ("inner", "left"):
        for l_row in left_rows:
            key = l_row.get(on, "")
            matches = right_index.get(key, [])
            if matches:
                for r_row in matches:
                    merged = {**l_row, **r_row}
                    result_rows.append(merged)
            elif how == "left":
                merged = dict(l_row)
                for h in right_headers:
                    if h not in merged:
                        merged[h] = ""
                result_rows.append(merged)
    elif how == "right":
        left_index: dict[str, list[dict[str, str]]] = {}
        for row in left_rows:
            key = row.get(on, "")
            left_index.setdefault(key, []).append(row)

        for r_row in right_rows:
            key = r_row.get(on, "")
            matches = left_index.get(key, [])
            if matches:
                for l_row in matches:
                    merged = {**l_row, **r_row}
                    result_rows.append(merged)
            else:
                merged = dict(r_row)
                for h in left_headers:
                    if h not in merged:
                        merged[h] = ""
                result_rows.append(merged)

    return {
        "row_count": len(result_rows),
        "columns": all_headers,
        "join_type": how,
        "join_column": on,
        "rows": result_rows,
    }


if __name__ == "__main__":
    app()
