"""Document Query Tool example app.

Analyze and query text/markdown documents with structured output.
Showcases: ReadOnly annotation, paginated list commands, stdin input, output formats.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Annotated, Any

from tooli import Argument, Option, Tooli
from tooli.annotations import ReadOnly
from tooli.errors import InputError

app = Tooli(name="docq", help="Query and analyze text documents")


def _read_source(source: str) -> tuple[str, str]:
    """Read content from a file path or stdin ('-').

    Returns (content, label) where label is the source description.
    """
    if source == "-":
        try:
            content = sys.stdin.read()
        except Exception as exc:
            raise InputError(
                message=f"Failed to read from stdin: {exc}",
                code="E5001",
            ) from exc
        return content, "<stdin>"

    path = Path(source)
    if not path.exists():
        raise InputError(
            message=f"File not found: {source}",
            code="E5002",
            details={"path": source},
        )
    if not path.is_file():
        raise InputError(
            message=f"Not a file: {source}",
            code="E5003",
            details={"path": source},
        )
    try:
        return path.read_text(encoding="utf-8"), path.name
    except Exception as exc:
        raise InputError(
            message=f"Failed to read file '{source}': {exc}",
            code="E5004",
            details={"path": source},
        ) from exc


@app.command(annotations=ReadOnly)
def stats(
    source: Annotated[str, Argument(help="File path or '-' for stdin")],
) -> dict[str, Any]:
    """Count words, lines, characters, and paragraphs."""
    content, label = _read_source(source)
    lines = content.splitlines()
    words = content.split()

    paragraph_count = 0
    in_paragraph = False
    for line in lines:
        stripped = line.strip()
        if stripped and not in_paragraph:
            in_paragraph = True
            paragraph_count += 1
        elif not stripped:
            in_paragraph = False

    return {
        "source": label,
        "lines": len(lines),
        "words": len(words),
        "characters": len(content),
        "paragraphs": paragraph_count,
    }


@app.command(paginated=True, annotations=ReadOnly)
def headings(
    source: Annotated[str, Argument(help="Markdown file or '-' for stdin")],
    *,
    max_depth: Annotated[int, Option(help="Maximum heading depth (1-6)")] = 6,
) -> list[dict[str, Any]]:
    """Extract markdown heading outline."""
    content, _label = _read_source(source)
    results: list[dict[str, Any]] = []

    for line_num, line in enumerate(content.splitlines(), start=1):
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            level = len(match.group(1))
            if level <= max_depth:
                results.append({
                    "level": level,
                    "text": match.group(2).strip(),
                    "line": line_num,
                })

    return results


@app.command(paginated=True, annotations=ReadOnly)
def search(
    source: Annotated[str, Argument(help="File or '-' for stdin")],
    pattern: Annotated[str, Argument(help="Search pattern (substring or regex)")],
    *,
    case_sensitive: Annotated[bool, Option(help="Case-sensitive matching")] = False,
    context_lines: Annotated[int, Option(help="Lines of context around each match")] = 0,
) -> list[dict[str, Any]]:
    """Search for pattern matches with optional context."""
    content, _label = _read_source(source)
    lines = content.splitlines()

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        raise InputError(
            message=f"Invalid regex pattern: {exc}",
            code="E5005",
            details={"pattern": pattern},
        ) from exc

    results: list[dict[str, Any]] = []
    for idx, line in enumerate(lines):
        if compiled.search(line):
            before = lines[max(0, idx - context_lines):idx] if context_lines > 0 else []
            after = lines[idx + 1:idx + 1 + context_lines] if context_lines > 0 else []
            results.append({
                "line": idx + 1,
                "text": line,
                "context_before": before,
                "context_after": after,
            })

    return results


@app.command(paginated=True, annotations=ReadOnly)
def links(
    source: Annotated[str, Argument(help="Markdown file or '-' for stdin")],
) -> list[dict[str, Any]]:
    """Extract all URLs from markdown content."""
    content, _label = _read_source(source)
    results: list[dict[str, Any]] = []

    inline_pattern = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
    bare_url_pattern = re.compile(r"(?<!\()(https?://[^\s\)>]+)")

    for line_num, line in enumerate(content.splitlines(), start=1):
        for match in inline_pattern.finditer(line):
            results.append({
                "url": match.group(2),
                "text": match.group(1),
                "line": line_num,
                "type": "inline",
            })

        inline_urls = {m.group(2) for m in inline_pattern.finditer(line)}
        for match in bare_url_pattern.finditer(line):
            url = match.group(1)
            if url not in inline_urls:
                results.append({
                    "url": url,
                    "text": "",
                    "line": line_num,
                    "type": "bare",
                })

    return results


@app.command(annotations=ReadOnly)
def extract(
    source: Annotated[str, Argument(help="File or '-' for stdin")],
    *,
    heading: Annotated[str | None, Option(help="Extract section under this heading")] = None,
    start_line: Annotated[int | None, Option(help="Start line number (1-based)")] = None,
    end_line: Annotated[int | None, Option(help="End line number (1-based, inclusive)")] = None,
) -> dict[str, Any]:
    """Extract sections or line ranges from a document."""
    content, label = _read_source(source)
    lines = content.splitlines()

    if heading is not None:
        extracted, heading_level = _extract_by_heading(lines, heading)
        if extracted is None:
            raise InputError(
                message=f"Heading not found: {heading}",
                code="E5006",
                details={"heading": heading},
            )
        return {
            "source": label,
            "heading": heading,
            "heading_level": heading_level,
            "content": "\n".join(extracted),
            "lines": len(extracted),
        }

    if start_line is not None or end_line is not None:
        s = (start_line or 1) - 1
        e = end_line or len(lines)
        if s < 0 or s >= len(lines):
            raise InputError(
                message=f"Start line {s + 1} is out of range (1-{len(lines)})",
                code="E5007",
            )
        extracted = lines[s:e]
        return {
            "source": label,
            "start_line": s + 1,
            "end_line": min(e, len(lines)),
            "content": "\n".join(extracted),
            "lines": len(extracted),
        }

    return {
        "source": label,
        "content": content,
        "lines": len(lines),
    }


def _extract_by_heading(lines: list[str], heading: str) -> tuple[list[str] | None, int | None]:
    """Extract lines under a matching heading until the next heading of same or higher level."""
    target = heading.lower().strip()
    start_idx = None
    heading_level = None

    for idx, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match and match.group(2).strip().lower() == target:
            start_idx = idx
            heading_level = len(match.group(1))
            break

    if start_idx is None:
        return None, None

    end_idx = len(lines)
    for idx in range(start_idx + 1, len(lines)):
        match = re.match(r"^(#{1,6})\s+", lines[idx])
        if match and len(match.group(1)) <= heading_level:
            end_idx = idx
            break

    return lines[start_idx:end_idx], heading_level


if __name__ == "__main__":
    app()
