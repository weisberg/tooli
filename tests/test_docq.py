"""Tests for the docq example app."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from examples.docq.app import app

if TYPE_CHECKING:
    from pathlib import Path


def _run_json(runner: CliRunner, args: list[str], **kwargs: object):
    result = runner.invoke(app, args, **kwargs)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    return payload["result"]


SAMPLE_MD = """\
# Introduction

This is a sample document with **bold** and *italic* text.
It has multiple paragraphs.

## Getting Started

Follow these steps to get started:

1. Install the package
2. Run the command

### Links

Check out [Example](https://example.com) and [Docs](https://docs.example.com/guide).
Also see https://bare-url.example.com for more info.

## Conclusion

That's all folks.
"""


def test_docq_stats(tmp_path: Path) -> None:
    doc = tmp_path / "sample.md"
    doc.write_text(SAMPLE_MD, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["stats", str(doc)])
    assert result["lines"] > 0
    assert result["words"] > 0
    assert result["characters"] > 0
    assert result["paragraphs"] >= 3


def test_docq_headings(tmp_path: Path) -> None:
    doc = tmp_path / "sample.md"
    doc.write_text(SAMPLE_MD, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["headings", str(doc)])
    assert len(result) == 4  # Introduction, Getting Started, Links, Conclusion
    assert result[0]["level"] == 1
    assert result[0]["text"] == "Introduction"
    assert result[1]["level"] == 2

    # Test max_depth filter
    result_h1 = _run_json(runner, ["headings", str(doc), "--max-depth", "1"])
    assert len(result_h1) == 1
    assert result_h1[0]["text"] == "Introduction"


def test_docq_search(tmp_path: Path) -> None:
    doc = tmp_path / "sample.md"
    doc.write_text(SAMPLE_MD, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["search", str(doc), "example"])
    assert len(result) >= 1
    assert any("example" in r["text"].lower() for r in result)

    # Test with context
    result_ctx = _run_json(runner, ["search", str(doc), "package", "--context-lines", "1"])
    assert len(result_ctx) >= 1
    assert "context_before" in result_ctx[0]
    assert "context_after" in result_ctx[0]


def test_docq_links(tmp_path: Path) -> None:
    doc = tmp_path / "sample.md"
    doc.write_text(SAMPLE_MD, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["links", str(doc)])
    assert len(result) >= 3
    urls = [r["url"] for r in result]
    assert "https://example.com" in urls
    assert "https://docs.example.com/guide" in urls

    inline_links = [r for r in result if r["type"] == "inline"]
    assert len(inline_links) >= 2


def test_docq_extract_by_heading(tmp_path: Path) -> None:
    doc = tmp_path / "sample.md"
    doc.write_text(SAMPLE_MD, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["extract", str(doc), "--heading", "Getting Started"])
    assert "content" in result
    assert "Install the package" in result["content"]
    assert result["heading_level"] == 2


def test_docq_extract_by_lines(tmp_path: Path) -> None:
    doc = tmp_path / "sample.md"
    doc.write_text(SAMPLE_MD, encoding="utf-8")
    runner = CliRunner()

    result = _run_json(runner, ["extract", str(doc), "--start-line", "1", "--end-line", "3"])
    assert result["lines"] == 3
    assert "Introduction" in result["content"]


def test_docq_stdin(tmp_path: Path) -> None:
    runner = CliRunner()

    result = _run_json(runner, ["stats", "-"], input="Hello world\n\nSecond paragraph\n")
    assert result["source"] == "<stdin>"
    assert result["words"] == 4
    assert result["paragraphs"] == 2
