"""DataWrangler: Local data transforms without pandas scripts."""

from __future__ import annotations

from typing import Annotated

from tooli import Argument, StdinOr, Tooli
from tooli.annotations import ReadOnly

app = Tooli(
    name="datawrangler",
    help="CSV/JSON transforms with structured machine contracts.",
    version="0.1.0",
)

@app.command(
    annotations=ReadOnly,
    paginated=True,
    examples=[
        {"args": ["profile", "data.csv"], "description": "Profile a local CSV file"},
    ],
    capabilities=["fs:read"],
)
def profile(
    source: Annotated[StdinOr[str], Argument(help="Data source (file, URL, or '-')")],
) -> dict:
    """Get metadata and sample stats for a dataset."""
    content = str(source)
    # Simple row count for demo
    rows = content.splitlines()

    return {
        "format": "csv", # Mock detection
        "row_count": len(rows),
        "columns": ["id", "name", "email", "created_at"],
        "samples": [r.split(",") for r in rows[:5] if "," in r]
    }

@app.command(
    annotations=ReadOnly,
    capabilities=["fs:read"],
)
def infer_schema(
    source: Annotated[StdinOr[str], Argument(help="Data source")],
) -> dict:
    """Generate a JSON Schema based on input data columns."""
    return {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"},
            "email": {"type": "string", "format": "email"}
        }
    }

if __name__ == "__main__":
    app()
