"""Tests for the Note Indexer example app."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from examples.note_indexer.app import app

if TYPE_CHECKING:
    from pathlib import Path


def _run_json(runner: CliRunner, args: list[str], **kwargs: object):
    result = runner.invoke(app, args, **kwargs)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    return payload["result"]


def _write_note(path: Path, *, title: str, body: str = "", tags: str | None = None) -> None:
    front_matter = [f"title: {title}"]
    if tags:
        front_matter.append(f"tags: [{tags}]")
    front_matter_text = "\n".join(front_matter)
    path.write_text(f"---\n{front_matter_text}\n---\n\n{body}\n", encoding="utf-8")


def test_note_indexer_ingest_and_find(tmp_path: Path) -> None:
    source = tmp_path / "notes"
    source.mkdir()
    _write_note(source / "alpha.md", title="alpha note", tags="python,work", body="# Alpha\nAlpha summary body.")
    _write_note(source / "beta.md", title="beta note", tags="cli", body="Beta summary text.")

    index_path = tmp_path / "notes-index.json"
    runner = CliRunner()

    ingest_result = _run_json(
        runner,
        ["ingest", str(source), "--index-path", str(index_path)],
    )
    assert ingest_result["scan_count"] == 2
    assert ingest_result["total_indexed"] == 2

    second_ingest = _run_json(
        runner,
        ["ingest", str(source), "--index-path", str(index_path)],
    )
    assert second_ingest["unchanged"] == ["alpha.md", "beta.md"]

    query = _run_json(
        runner,
        ["find", "--index-path", str(index_path), "alpha"],
    )
    assert len(query) == 1
    assert query[0]["id"] == "alpha.md"


def test_note_indexer_stdin_uses_first_heading_for_title(tmp_path: Path) -> None:
    index_path = tmp_path / "notes-index.json"
    runner = CliRunner()
    stdin_payload = [
        "---",
        "---",
        "",
        "# Heading title",
        "",
        "A short note body.",
    ]
    result = _run_json(
        runner,
        ["ingest", "-", "--index-path", str(index_path)],
        input="\n".join(stdin_payload),
    )
    assert result["scan_count"] == 1
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["notes"][0]["title"] == "Heading title"


def test_note_indexer_find_tag_matching_modes(tmp_path: Path) -> None:
    source = tmp_path / "notes"
    source.mkdir()
    _write_note(source / "one.md", title="one", tags="python,work", body="Python work note.")
    _write_note(source / "two.md", title="two", tags="python", body="Python note.")
    _write_note(source / "three.md", title="three", tags="work", body="Work note.")

    index_path = tmp_path / "notes-index.json"
    runner = CliRunner()
    _run_json(runner, ["ingest", str(source), "--index-path", str(index_path)])

    all_matches = _run_json(
        runner,
        ["find", "--index-path", str(index_path), "--tags", "python", "--tags", "work"],
    )
    assert [note["id"] for note in all_matches] == ["one.md"]

    any_matches = _run_json(
        runner,
        [
            "find",
            "--index-path",
            str(index_path),
            "--tags-match",
            "any",
            "--tags",
            "python",
            "--tags",
            "work",
        ],
    )
    assert sorted(note["id"] for note in any_matches) == ["one.md", "three.md", "two.md"]


def test_note_indexer_related_prefers_content_overlap(tmp_path: Path) -> None:
    source = tmp_path / "notes"
    source.mkdir()
    _write_note(source / "a.md", title="alpha", tags="python,notes", body="notes indexing and search helpers.")
    _write_note(source / "b.md", title="beta", tags="python,cli", body="command line note indexing tools and search.")
    _write_note(source / "c.md", title="gamma", tags="music", body="random unrelated content.")

    index_path = tmp_path / "notes-index.json"
    runner = CliRunner()
    _run_json(runner, ["ingest", str(source), "--index-path", str(index_path)])

    related = _run_json(runner, ["related", "a.md", "--index-path", str(index_path), "--max-results", "2"])
    assert related[0]["id"] == "b.md"
    assert related[0]["score"] > 0


def test_note_indexer_watch_reports_no_drift_and_drift(tmp_path: Path) -> None:
    source = tmp_path / "notes"
    source.mkdir()
    note_path = source / "note.md"
    _write_note(note_path, title="drift", tags="work", body="first version")
    index_path = tmp_path / "notes-index.json"
    runner = CliRunner()

    _run_json(runner, ["ingest", str(source), "--index-path", str(index_path)])
    first_watch = _run_json(runner, ["watch", str(source), "--index-path", str(index_path)])
    assert first_watch["has_changes"] is False
    assert first_watch["added"] == []
    assert first_watch["updated"] == []
    assert first_watch["removed"] == []

    note_path.write_text("---\ntitle: drift\n---\n\nupdated text.\n", encoding="utf-8")
    time.sleep(1.0)
    second_watch = _run_json(runner, ["watch", str(source), "--index-path", str(index_path)])
    assert second_watch["has_changes"] is True
    assert second_watch["updated"] == ["note.md"]
