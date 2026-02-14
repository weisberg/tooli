"""Image Organizer example app.

Organize and manage image files by metadata (no PIL required).
Showcases: Destructive+Idempotent composite annotations, DryRunRecorder,
batch file operations, ReadOnly scanning.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

import typer  # noqa: TC002

from tooli import Argument, Option, Tooli, dry_run_support, record_dry_action
from tooli.annotations import Destructive, Idempotent, ReadOnly
from tooli.errors import InputError

app = Tooli(name="imgsort", help="Image file organizer (stdlib only)")

DEFAULT_EXTENSIONS = "jpg,jpeg,png,gif,bmp,webp,tiff,svg"


def _image_extensions(ext_str: str) -> set[str]:
    """Parse comma-separated extensions into a normalized set."""
    return {f".{e.strip().lower().lstrip('.')}" for e in ext_str.split(",") if e.strip()}


def _find_images(directory: Path, extensions: set[str], recursive: bool) -> list[Path]:
    """Find image files by extension."""
    if not directory.exists():
        raise InputError(
            message=f"Directory not found: {directory}",
            code="E8001",
            details={"path": str(directory)},
        )
    if not directory.is_dir():
        raise InputError(
            message=f"Not a directory: {directory}",
            code="E8002",
            details={"path": str(directory)},
        )

    pattern = "**/*" if recursive else "*"
    return sorted(
        p for p in directory.glob(pattern)
        if p.is_file() and p.suffix.lower() in extensions
    )


def _file_hash(path: Path, chunk_size: int = 8192) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _file_date(path: Path) -> str:
    """Get file modification date as YYYY-MM-DD."""
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")


@app.command(paginated=True, annotations=ReadOnly)
def scan(
    directory: Annotated[str, Argument(help="Directory to scan for images")],
    *,
    recursive: Annotated[bool, Option(help="Scan subdirectories recursively")] = True,
    extensions: Annotated[str, Option(help="File extensions (comma-separated)")] = DEFAULT_EXTENSIONS,
) -> list[dict[str, Any]]:
    """Find image files by extension."""
    ext_set = _image_extensions(extensions)
    images = _find_images(Path(directory), ext_set, recursive)

    return [
        {
            "path": str(p),
            "name": p.name,
            "extension": p.suffix.lower(),
            "size_bytes": p.stat().st_size,
            "modified": _file_date(p),
        }
        for p in images
    ]


@app.command(annotations=Destructive | Idempotent)
@dry_run_support
def organize(
    ctx: typer.Context,
    directory: Annotated[str, Argument(help="Source directory with images")],
    *,
    target: Annotated[str, Option(help="Target directory for organized files")] = "./organized",
    by: Annotated[str, Option(help="Organize by: date, extension, or size")] = "date",
    extensions: Annotated[str, Option(help="File extensions")] = DEFAULT_EXTENSIONS,
    recursive: Annotated[bool, Option(help="Scan recursively")] = True,
) -> dict[str, Any]:
    """Sort images into subdirectories by date, extension, or size category."""
    if by not in ("date", "extension", "size"):
        raise InputError(
            message=f"Invalid grouping: {by}. Use 'date', 'extension', or 'size'.",
            code="E8003",
            details={"by": by},
        )

    ext_set = _image_extensions(extensions)
    images = _find_images(Path(directory), ext_set, recursive)

    moved = 0
    skipped = 0
    target_dir = Path(target)

    for img in images:
        if by == "date":
            subfolder = _file_date(img)
        elif by == "extension":
            subfolder = img.suffix.lower().lstrip(".")
        else:  # size
            size_mb = img.stat().st_size / (1024 * 1024)
            if size_mb < 1:
                subfolder = "small"
            elif size_mb < 10:
                subfolder = "medium"
            else:
                subfolder = "large"

        dest = target_dir / subfolder / img.name

        if dest.exists():
            skipped += 1
            continue

        record_dry_action("move_file", str(img), details={"to": str(dest)})

        if not getattr(ctx.obj, "dry_run", False):
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(img), str(dest))

        moved += 1

    return {
        "moved": moved,
        "skipped": skipped,
        "total_scanned": len(images),
        "target": str(target_dir),
        "organized_by": by,
    }


@app.command(paginated=True, annotations=ReadOnly)
def duplicates(
    directory: Annotated[str, Argument(help="Directory to scan for duplicates")],
    *,
    recursive: Annotated[bool, Option(help="Scan subdirectories")] = True,
    extensions: Annotated[str, Option(help="File extensions")] = DEFAULT_EXTENSIONS,
) -> list[dict[str, Any]]:
    """Find duplicate images by file content hash."""
    ext_set = _image_extensions(extensions)
    images = _find_images(Path(directory), ext_set, recursive)

    hash_groups: dict[str, list[Path]] = {}
    for img in images:
        h = _file_hash(img)
        hash_groups.setdefault(h, []).append(img)

    results: list[dict[str, Any]] = []
    for h, paths in hash_groups.items():
        if len(paths) > 1:
            results.append({
                "hash": h[:16],
                "count": len(paths),
                "size_bytes": paths[0].stat().st_size,
                "files": [str(p) for p in paths],
            })

    results.sort(key=lambda r: r["count"], reverse=True)
    return results


@app.command(annotations=Destructive | Idempotent)
@dry_run_support
def rename(
    ctx: typer.Context,
    directory: Annotated[str, Argument(help="Directory with images to rename")],
    *,
    pattern: Annotated[str, Option(help="Name pattern using {date}, {n}, {ext}")] = "{date}_{n}{ext}",
    extensions: Annotated[str, Option(help="File extensions")] = DEFAULT_EXTENSIONS,
) -> dict[str, Any]:
    """Batch rename images using a pattern with {date}, {n}, {ext} placeholders."""
    ext_set = _image_extensions(extensions)
    dir_path = Path(directory)
    images = _find_images(dir_path, ext_set, recursive=False)

    renamed = 0
    skipped = 0

    for idx, img in enumerate(images, start=1):
        date_str = _file_date(img)
        new_name = pattern.replace("{date}", date_str).replace("{n}", str(idx)).replace("{ext}", img.suffix.lower())
        new_path = img.parent / new_name

        if new_path == img:
            skipped += 1
            continue

        if new_path.exists():
            skipped += 1
            continue

        record_dry_action("rename_file", str(img), details={"to": str(new_path)})

        if not getattr(ctx.obj, "dry_run", False):
            img.rename(new_path)

        renamed += 1

    return {
        "renamed": renamed,
        "skipped": skipped,
        "total_scanned": len(images),
    }


@app.command(annotations=ReadOnly)
def stats(
    directory: Annotated[str, Argument(help="Directory to analyze")],
    *,
    recursive: Annotated[bool, Option(help="Scan subdirectories")] = True,
    extensions: Annotated[str, Option(help="File extensions")] = DEFAULT_EXTENSIONS,
) -> dict[str, Any]:
    """Collection statistics: counts by type, total size, date range."""
    ext_set = _image_extensions(extensions)
    images = _find_images(Path(directory), ext_set, recursive)

    if not images:
        return {
            "total_files": 0,
            "total_size_mb": 0,
            "by_extension": {},
            "date_range": None,
        }

    total_size = 0
    by_ext: dict[str, int] = {}
    dates: list[str] = []

    for img in images:
        size = img.stat().st_size
        total_size += size
        ext = img.suffix.lower()
        by_ext[ext] = by_ext.get(ext, 0) + 1
        dates.append(_file_date(img))

    return {
        "total_files": len(images),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "by_extension": by_ext,
        "date_range": {
            "earliest": min(dates),
            "latest": max(dates),
        },
    }
