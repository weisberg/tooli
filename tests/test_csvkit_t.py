"""Tests for the csvkit-t example app."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from examples.csvkit_t.app import app

if TYPE_CHECKING:
    from pathlib import Path

SAMPLE_CSV = """\
name,age,city
Alice,30,New York
Bob,25,San Francisco
Charlie,35,Chicago
"""


def _run_json(runner: CliRunner, args: list[str], **kwargs: object):
    result = runner.invoke(app, args, **kwargs)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    return payload["result"]


def test_csvkit_inspect(tmp_path: Path) -> None:
    csv_file = tmp_path / "data.csv"
    csv_file.write_text(SAMPLE_CSV, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["inspect", str(csv_file)])
    assert result["row_count"] == 3
    assert result["column_count"] == 3
    col_names = [c["name"] for c in result["columns"]]
    assert "name" in col_names
    assert "age" in col_names

    age_col = next(c for c in result["columns"] if c["name"] == "age")
    assert age_col["type"] == "int"


def test_csvkit_query_with_filter(tmp_path: Path) -> None:
    csv_file = tmp_path / "data.csv"
    csv_file.write_text(SAMPLE_CSV, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["query", str(csv_file), "--where", "city=Chicago"])
    assert len(result) == 1
    assert result[0]["name"] == "Charlie"


def test_csvkit_query_with_columns(tmp_path: Path) -> None:
    csv_file = tmp_path / "data.csv"
    csv_file.write_text(SAMPLE_CSV, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["query", str(csv_file), "--columns", "name,age"])
    assert len(result) == 3
    assert set(result[0].keys()) == {"name", "age"}


def test_csvkit_convert(tmp_path: Path) -> None:
    csv_file = tmp_path / "data.csv"
    csv_file.write_text(SAMPLE_CSV, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["convert", str(csv_file)])
    assert result["format"] == "json"
    assert result["row_count"] == 3
    assert len(result["rows"]) == 3


def test_csvkit_validate(tmp_path: Path) -> None:
    csv_file = tmp_path / "data.csv"
    csv_file.write_text(SAMPLE_CSV, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["validate", str(csv_file), "--require-columns", "name,age,email"])
    assert result["valid"] is False
    assert any("email" in issue for issue in result["issues"])


def test_csvkit_merge(tmp_path: Path) -> None:
    left_csv = tmp_path / "left.csv"
    left_csv.write_text("id,name\n1,Alice\n2,Bob\n3,Charlie\n", encoding="utf-8")
    right_csv = tmp_path / "right.csv"
    right_csv.write_text("id,score\n1,95\n2,87\n4,72\n", encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["merge", str(left_csv), str(right_csv), "--on", "id"])
    assert result["join_type"] == "inner"
    assert result["row_count"] == 2
    merged_ids = {r["id"] for r in result["rows"]}
    assert merged_ids == {"1", "2"}


def test_csvkit_stdin(tmp_path: Path) -> None:
    runner = CliRunner()

    result = _run_json(runner, ["inspect", "-"], input=SAMPLE_CSV)
    assert result["row_count"] == 3
    assert result["column_count"] == 3
