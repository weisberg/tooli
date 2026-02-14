"""ArtifactCatalog: Index local documents and provide structured search."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from tooli import Argument, Tooli
from tooli.annotations import ReadOnly

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

app = Tooli(
    name="artifactcatalog",
    help="Index documents and provide structured search; supports MCP mode.",
    version="0.1.0",
)

@app.command(
    annotations=ReadOnly,
    examples=[
        {"args": ["index", "~/docs"], "description": "Index documents in a folder"},
    ],
)
def index(
    root: Annotated[Path, Argument(help="Directory to index")],
) -> Iterable[dict]:
    """Walk a directory and build a metadata index of files."""
    # Demo superpower: JSONL incremental indexing
    for path in root.rglob("*.md"):
        if path.is_file():
            yield {
                "id": str(path.relative_to(root)),
                "title": path.stem,
                "headings": [line.strip("# ") for line in path.read_text().splitlines() if line.startswith("#")],
                "modified": path.stat().st_mtime,
            }

@app.command(
    annotations=ReadOnly,
)
def search(
    query: Annotated[str, Argument(help="Search query term")],
) -> list[dict]:
    """Query the catalog for matching documents."""
    # Mock search results
    return [
        {
            "id": "docs/api.md",
            "title": "API Reference",
            "snippet": f"...matches for '{query}' found in header...",
            "score": 0.95
        },
        {
            "id": "guides/getting-started.md",
            "title": "Getting Started",
            "snippet": f"Learn how to use {query} here.",
            "score": 0.82
        }
    ]

if __name__ == "__main__":
    app()
