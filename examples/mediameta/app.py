"""MediaMeta: Media inspection and normalization for pipelines."""

from __future__ import annotations

from typing import Annotated

from tooli import Argument, Option, StdinOr, Tooli
from tooli.annotations import Destructive, ReadOnly
from tooli.dry_run import dry_run_support, record_dry_action

app = Tooli(
    name="mediameta",
    help="Reads media metadata and performs safe normalization.",
    version="0.1.0",
)

@app.command(
    annotations=ReadOnly,
    examples=[
        {"args": ["inspect", "photo.jpg"], "description": "Inspect an image"},
    ],
)
def inspect(
    source: Annotated[StdinOr[bytes], Argument(help="Media file or bytes")],
) -> dict:
    """Read technical metadata from an image, audio, or video file."""
    # Demo superpower: StdinOr[bytes] handles binary data
    data_size = len(source)

    return {
        "size_bytes": data_size,
        "format": "jpeg", # Mock
        "dimensions": {"width": 1920, "height": 1080},
        "has_exif": True,
    }

@app.command(
    annotations=Destructive,
    cost_hint="high",
)
@dry_run_support
def normalize(
    source: Annotated[StdinOr[bytes], Argument(help="Media file or bytes")],
    preset: Annotated[str, Option(help="Normalization preset")] = "web",
) -> str:
    """Resize and strip metadata for optimized delivery."""
    # Demo superpower: record_dry_action for binary processing pipeline
    record_dry_action(
        action="strip_exif",
        target="in-memory-stream",
        details={"bytes_removed": 1024}
    )

    record_dry_action(
        action="resize",
        target="output.jpg",
        details={"scale": 0.5, "format": "webp"}
    )

    return "Successfully normalized media."

if __name__ == "__main__":
    app()
