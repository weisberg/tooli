"""Tests for the imgsort example app."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from examples.imgsort.app import app

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


def _create_images(path: "Path") -> None:
    """Create fake image files for testing."""
    (path / "photo1.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"A" * 100)
    (path / "photo2.png").write_bytes(b"\x89PNG" + b"B" * 200)
    (path / "photo3.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"C" * 150)
    (path / "document.txt").write_text("not an image", encoding="utf-8")


def test_imgsort_scan(tmp_path: Path) -> None:
    _create_images(tmp_path)
    runner = CliRunner()

    result = _run_json(runner, ["scan", str(tmp_path)])
    assert len(result) == 3  # 2 jpg + 1 png, not the .txt
    extensions = {r["extension"] for r in result}
    assert ".jpg" in extensions
    assert ".png" in extensions


def test_imgsort_organize_dry_run(tmp_path: Path) -> None:
    _create_images(tmp_path)
    target = tmp_path / "organized"
    runner = CliRunner()

    result = runner.invoke(app, [
        "organize", str(tmp_path),
        "--target", str(target),
        "--by", "extension",
        "--dry-run",
        "--yes",
    ])
    assert result.exit_code == 0

    payload = None
    for line in reversed(result.output.strip().splitlines()):
        data = json.loads(line)
        if "ok" in data:
            payload = data
            break
    assert payload is not None

    actions = payload["result"]
    assert isinstance(actions, list)
    assert len(actions) == 3
    assert all(a["action"] == "move_file" for a in actions)

    # Files should NOT be moved in dry-run
    assert (tmp_path / "photo1.jpg").exists()


def test_imgsort_organize_by_extension(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _create_images(source)
    target = tmp_path / "organized"
    runner = CliRunner()

    result = _run_json(runner, [
        "organize", str(source),
        "--target", str(target),
        "--by", "extension",
        "--yes",
    ])
    assert result["moved"] == 3
    assert (target / "jpg").exists()
    assert (target / "png").exists()


def test_imgsort_duplicates(tmp_path: Path) -> None:
    # Create two identical files
    content = b"\xff\xd8\xff\xe0" + b"DUPLICATE" * 50
    (tmp_path / "orig.jpg").write_bytes(content)
    (tmp_path / "copy.jpg").write_bytes(content)
    (tmp_path / "unique.png").write_bytes(b"\x89PNG" + b"UNIQUE" * 30)
    runner = CliRunner()

    result = _run_json(runner, ["duplicates", str(tmp_path)])
    assert len(result) == 1
    assert result[0]["count"] == 2


def test_imgsort_rename_dry_run(tmp_path: Path) -> None:
    _create_images(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, [
        "rename", str(tmp_path),
        "--pattern", "img_{n}{ext}",
        "--dry-run",
        "--yes",
    ])
    assert result.exit_code == 0

    payload = None
    for line in reversed(result.output.strip().splitlines()):
        data = json.loads(line)
        if "ok" in data:
            payload = data
            break
    assert payload is not None

    actions = payload["result"]
    assert isinstance(actions, list)
    assert all(a["action"] == "rename_file" for a in actions)


def test_imgsort_stats(tmp_path: Path) -> None:
    _create_images(tmp_path)
    runner = CliRunner()

    result = _run_json(runner, ["stats", str(tmp_path)])
    assert result["total_files"] == 3
    assert ".jpg" in result["by_extension"]
    assert ".png" in result["by_extension"]
    assert result["date_range"] is not None
