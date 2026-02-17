"""Note Indexer example app.

The Note Indexer ingests Markdown files into a deterministic JSON index and
provides query, related-note, export, and drift-watch workflows.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Annotated, Any

import typer  # noqa: TC002

from tooli import Argument, Option, Tooli
from tooli.annotations import ReadOnly
from tooli.errors import InputError

app = Tooli(name="note-indexer", help="Index and query markdown notes")

DEFAULT_INDEX_PATH = "tooli-notes-index.json"
DEFAULT_PATTERNS = ("*.md", "*.markdown")
INDEX_VERSION = "1.0.0"


def _to_json_time(epoch: float | None = None) -> str:
    if epoch is None:
        return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
    return datetime.fromtimestamp(epoch, tz=timezone.utc).replace(microsecond=0).isoformat()


def _normalize_path(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def _normalize_word(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _to_tokens(value: str) -> list[str]:
    return sorted(set(token for token in _normalize_word(value).split() if token))


def _parse_front_matter(lines: list[str]) -> tuple[dict[str, Any], int]:
    if not lines or lines[0].strip() != "---":
        return {}, 0

    metadata: dict[str, Any] = {}
    index = 1
    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()
        index += 1

        if stripped == "---":
            break
        if not stripped:
            continue
        if ":" not in raw:
            continue

        key, _, value = raw.partition(":")
        key = key.strip().lower()
        value = value.strip()

        if value:
            metadata[key] = value.strip('"\'')
            continue

        items: list[str] = []
        while index < len(lines):
            next_line = lines[index]
            next_stripped = next_line.strip()
            if next_stripped.startswith("- "):
                items.append(next_stripped[2:].strip().strip('"\''))
                index += 1
                continue
            if next_line.startswith("  -"):
                items.append(next_line[3:].strip().strip('"\''))
                index += 1
                continue
            break

        if items:
            metadata[key] = items

    return metadata, index


def _coerce_tag_value(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
        if text:
            return [entry.strip().strip('"\'') for entry in text.split(",") if entry.strip()]
        return []
    if "," in text:
        return [entry.strip().strip('"\'') for entry in text.split(",") if entry.strip()]
    return [text]


def _extract_tags(front_matter: dict[str, Any], body_lines: list[str]) -> list[str]:
    tag_values: list[str] = []
    for key in ("tags", "tag", "keywords"):
        tag_values.extend(_coerce_tag_value(front_matter.get(key)))

    if tag_values:
        normalized = {_normalize_word(tag) for tag in tag_values if _normalize_word(tag)}
        return sorted(normalized)

    fallback = next((line[1:].strip() for line in body_lines if line.strip().startswith("#")), "")
    if not fallback:
        return []
    return [_normalize_word(fallback)]


def _extract_title_and_summary(
    *,
    source_path: Path | None,
    front_matter: dict[str, Any],
    body_lines: list[str],
) -> tuple[str, str, int]:
    title = front_matter.get("title")
    has_explicit_title = isinstance(title, str) and title.strip()
    if has_explicit_title:
        resolved_title = title.strip()
    else:
        resolved_title = source_path.stem if source_path is not None else "stdin-note"

    heading_count = 0
    summary_lines: list[str] = []
    should_pick_title_from_heading = source_path is None and not has_explicit_title
    for line in body_lines:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            heading_count += 1
            if should_pick_title_from_heading:
                heading_title = stripped.lstrip("#").strip()
                if heading_title:
                    resolved_title = heading_title
                    should_pick_title_from_heading = False
            continue
        if not line.strip():
            continue
        summary_lines.append(line.strip())
        if len(summary_lines) >= 8:
            break

    summary = _normalize_word(" ".join(summary_lines))
    if len(summary) > 220:
        summary = summary[:217] + "..."

    return resolved_title, summary, heading_count


def _checksum(data: bytes) -> str:
    hasher = hashlib.sha256()
    hasher.update(data)
    return hasher.hexdigest()


@dataclass
class IndexNote:
    id: str
    path: str
    title: str
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    updated_at: str = ""
    updated_epoch: int = 0
    size: int = 0
    words: int = 0
    headings: int = 0
    checksum: str = ""
    terms: list[str] = field(default_factory=list)
    source: str = ""

    def as_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "title": self.title,
            "tags": self.tags,
            "summary": self.summary,
            "updated_at": self.updated_at,
            "updated_epoch": self.updated_epoch,
            "size": self.size,
            "words": self.words,
            "headings": self.headings,
            "checksum": self.checksum,
            "terms": self.terms,
            "source": self.source,
        }


def _note_id_and_path(path: Path, source_root: Path | None) -> tuple[str, str]:
    if source_root is None:
        return path.name, path.name

    try:
        return (
            str(path.resolve().relative_to(source_root.resolve())).replace("\\", "/"),
            str(path.resolve().relative_to(source_root.resolve())).replace("\\", "/"),
        )
    except ValueError:
        return path.name, path.name


def _parse_note(path: Path | None, raw: str, source_root: Path | None) -> IndexNote:
    lines = raw.splitlines()
    front_matter, body_start = _parse_front_matter(lines)
    body_lines = lines[body_start:]

    title, summary, heading_count = _extract_title_and_summary(
        source_path=path,
        front_matter=front_matter,
        body_lines=body_lines,
    )
    tags = _extract_tags(front_matter, body_lines)

    encoded = raw.encode("utf-8")
    term_text = f"{title} {summary}"
    terms = _to_tokens(term_text)

    if path is None:
        note_id = f"stdin/{_checksum(encoded)[:12]}"
        rel_path = "stdin"
        stat_epoch = int(time.time())
    else:
        note_id, rel_path = _note_id_and_path(path, source_root)
        stat_epoch = int(path.stat().st_mtime)

    return IndexNote(
        id=note_id,
        path=rel_path,
        title=title,
        tags=tags,
        summary=summary,
        updated_at=_to_json_time(stat_epoch),
        updated_epoch=stat_epoch,
        size=len(encoded),
        words=len(re.findall(r"[a-zA-Z0-9_']+", raw)),
        headings=heading_count,
        checksum=_checksum(encoded),
        terms=terms,
        source=str(source_root) if source_root is not None else "stdin",
    )


def _coerce_patterns(value: list[str] | None) -> list[str]:
    return value if value else list(DEFAULT_PATTERNS)


def _collect_markdown_files(
    source: Path,
    *,
    include: list[str] | None,
    exclude: list[str] | None,
    recursive: bool,
) -> list[Path]:
    if source.is_file():
        return [source]
    if not source.is_dir():
        raise InputError(message=f"Source path does not exist: {source}", code="E1001", details={"path": str(source)})

    scanner = source.rglob if recursive else source.glob
    include_patterns = _coerce_patterns(include)
    exclude_patterns = exclude or []
    candidates: set[Path] = set()
    for pattern in include_patterns:
        candidates.update(scanner(pattern))

    selected: list[Path] = []
    for candidate in sorted(candidates):
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(source).as_posix()
        if any(fnmatch(relative, pattern) for pattern in exclude_patterns):
            continue
        selected.append(candidate)

    return selected


def _read_index(index_path: Path) -> dict[str, Any]:
    if not index_path.exists():
        return {
            "version": INDEX_VERSION,
            "generated_at": _to_json_time(),
            "notes": [],
            "sources": {},
        }

    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise InputError(
            message=f"Unable to parse index JSON: {index_path}",
            code="E1002",
            details={"path": str(index_path)},
        ) from exc

    if not isinstance(data, dict):
        raise InputError(
            message=f"Invalid index payload in {index_path}",
            code="E1003",
            details={"path": str(index_path)},
        )

    notes = data.get("notes")
    if not isinstance(notes, list):
        raise InputError(
            message=f"Invalid notes payload in {index_path}",
            code="E1004",
            details={"path": str(index_path)},
        )

    return data


def _write_index(index_path: Path, payload: dict[str, Any], *, dry_run: bool) -> None:
    if dry_run:
        return
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )


def _index_lookup(index_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for item in index_data.get("notes", []):
        if not isinstance(item, dict):
            continue
        note_id = item.get("id")
        if isinstance(note_id, str):
            mapping[note_id] = item
    return mapping


def _merge_index(
    *,
    existing: dict[str, Any],
    updates: dict[str, IndexNote],
    remove_missing: bool,
    source_id: str,
    incremental: bool,
    observed_ids: set[str],
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    merged: dict[str, Any] = {}
    existing_map = _index_lookup(existing)
    added: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []

    for note_id, note in updates.items():
        previous = existing_map.get(note_id)
        merged[note_id] = note.as_payload()
        if previous is None:
            added.append(note_id)
        elif incremental and previous.get("checksum") == note.checksum:
            unchanged.append(note_id)
        else:
            updated.append(note_id)

    removed: list[str] = []
    if remove_missing:
        for note_id, note_payload in list(existing_map.items()):
            if note_payload.get("source") != source_id:
                merged[note_id] = note_payload
                continue
            if note_id in observed_ids:
                merged[note_id] = note_payload
                continue
            removed.append(note_id)

    for note_id, note_payload in existing_map.items():
        if note_payload.get("source") == source_id and note_id in removed:
            continue
        merged[note_id] = note_payload

    return {
        "version": INDEX_VERSION,
        "generated_at": _to_json_time(),
        "notes": sorted(merged.values(), key=lambda item: item.get("id", "")),
        "sources": existing.get("sources", {}),
    }, {
        "added": sorted(added),
        "updated": sorted(updated),
        "unchanged": sorted(unchanged),
        "removed": sorted(removed),
    }


def _coerce_sort_key(value: str) -> str:
    if value not in {"title", "size", "words", "updated_at", "headings", "updated_epoch"}:
        raise InputError(
            message=f"Invalid sort key: {value!r}",
            code="E1005",
            details={"sort": value},
        )
    return value


def _parse_sort_datetime(value: str | None) -> float | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise InputError(message=f"Invalid ISO timestamp: {value}", code="E1006", details={"value": value}) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _build_records_from_source(
    source_path: Path,
    *,
    include: list[str] | None,
    exclude: list[str] | None,
    recursive: bool,
) -> tuple[dict[str, IndexNote], set[str]]:
    if source_path.is_file():
        raw = source_path.read_text(encoding="utf-8")
        parsed = _parse_note(source_path, raw, source_root=source_path.parent)
        note_id = parsed.id
        return {note_id: parsed}, {note_id}

    files = _collect_markdown_files(
        source_path,
        include=include,
        exclude=exclude,
        recursive=recursive,
    )

    updates: dict[str, IndexNote] = {}
    for note_path in files:
        if not note_path.is_file():
            continue
        raw = note_path.read_text(encoding="utf-8")
        note = _parse_note(note_path, raw, source_root=source_path)
        updates[note.id] = note

    return updates, set(updates)


def _compute_diff(
    *,
    source_path: str,
    index_path: Path,
    include: list[str] | None,
    exclude: list[str] | None,
    recursive: bool,
    incremental: bool = True,
) -> dict[str, list[str]]:
    normalized_source = _normalize_path(source_path)
    updates, observed_ids = _build_records_from_source(
        normalized_source,
        include=include,
        exclude=exclude,
        recursive=recursive,
    )
    index_payload = _read_index(index_path)
    _, summary = _merge_index(
        existing=index_payload,
        updates=updates,
        remove_missing=True,
        source_id=str(normalized_source),
        incremental=incremental,
        observed_ids=observed_ids,
    )
    return summary


@app.command(paginated=False, capabilities=["fs:read", "fs:write"])
def ingest(
    ctx: typer.Context,
    source: Annotated[str, Argument(help="Directory, file, or '-' to read markdown from stdin")],
    *,
    index_path: Annotated[str, Option(help="Where to write the index JSON file")] = DEFAULT_INDEX_PATH,
    include: Annotated[list[str] | None, Option(help="Glob pattern(s) to include")] = None,
    exclude: Annotated[list[str], Option(help="Glob pattern(s) to exclude")] = None,
    recursive: Annotated[bool, Option(help="Scan source directories recursively")] = True,
    incremental: Annotated[bool, Option(help="Skip unchanged notes using content checksum")] = True,
    remove_missing: Annotated[bool, Option(help="Remove index entries that disappeared from source")] = True,
) -> dict[str, Any]:
    """Ingest markdown notes and persist a deterministic index file."""

    resolved_index = _normalize_path(index_path)
    existing = _read_index(resolved_index)
    include_patterns = _coerce_patterns(include)
    exclude_patterns = exclude or []
    source_is_stdin = source == "-"

    if source_is_stdin:
        raw = sys.stdin.read()
        parsed = _parse_note(None, raw, source_root=None)
        updates = {parsed.id: parsed}
        observed_ids = {parsed.id}
        source_id = "stdin"
    else:
        source_path = _normalize_path(source)
        source_id = str(source_path)
        updates, observed_ids = _build_records_from_source(
            source_path,
            include=include_patterns,
            exclude=exclude_patterns,
            recursive=recursive,
        )

    merged, summary = _merge_index(
        existing=existing,
        updates=updates,
        remove_missing=not source_is_stdin and remove_missing,
        source_id=source_id,
        incremental=incremental,
        observed_ids=observed_ids,
    )

    source_metrics = merged["sources"].get(source_id, {}) if isinstance(merged.get("sources"), dict) else {}
    source_metrics["last_scanned"] = _to_json_time()
    source_metrics["count"] = len(updates)
    merged["sources"][source_id] = source_metrics

    _write_index(
        resolved_index,
        merged,
        dry_run=bool(getattr(ctx.obj, "dry_run", False)),
    )

    notes = 0 if source_is_stdin and not updates else len(updates)

    if not incremental:
        summary["unchanged"] = []

    return {
        "index_path": str(resolved_index),
        "source": source,
        "scan_count": notes,
        "dry_run": bool(getattr(ctx.obj, "dry_run", False)),
        "added": summary["added"],
        "updated": summary["updated"],
        "unchanged": summary["unchanged"],
        "removed": summary["removed"],
        "total_indexed": len(merged.get("notes", [])),
    }


@app.command(paginated=True, annotations=ReadOnly, capabilities=["fs:read"])
def find(
    query: Annotated[str | None, Argument(help="Search query")] = None,
    *,
    index_path: Annotated[str, Option(help="Index JSON file to search")] = DEFAULT_INDEX_PATH,
    tags: Annotated[list[str], Option(help="Filter by tags (AND)")] = None,
    tags_match: Annotated[str, Option(help="Tag matching mode: all|any")] = "all",
    min_words: Annotated[int | None, Option(help="Minimum word count")] = None,
    after: Annotated[str | None, Option(help="Match notes updated at/after ISO timestamp")] = None,
    before: Annotated[str | None, Option(help="Match notes updated at/before ISO timestamp")] = None,
    include_headings: Annotated[bool, Option(help="Include heading count in payload")] = True,
    sort: Annotated[str, Option(help="Sort key: title|size|words|updated_at|headings|updated_epoch")] = "updated_at",
    reverse: Annotated[bool, Option(help="Reverse sort order")] = True,
) -> list[dict[str, Any]]:
    """Query the index with structured filters and stable ordering."""

    notes = _read_index(_normalize_path(index_path)).get("notes", [])
    tokens = set(_to_tokens(query or ""))
    desired_tags = {_normalize_word(tag) for tag in tags or [] if tag}
    after_ts = _parse_sort_datetime(after)
    before_ts = _parse_sort_datetime(before)

    if tags_match not in {"all", "any"}:
        raise InputError(message="--tags-match must be one of all|any", code="E1009", details={"value": tags_match})

    filtered: list[dict[str, Any]] = []
    for item in notes:
        if not isinstance(item, dict):
            continue

        note_tags = {_normalize_word(tag) for tag in item.get("tags", []) if isinstance(tag, str)}
        if desired_tags:
            if tags_match == "all" and not desired_tags.issubset(note_tags):
                continue
            if tags_match == "any" and not desired_tags.intersection(note_tags):
                continue

        if min_words is not None and int(item.get("words", 0)) < min_words:
            continue

        if after_ts is not None and float(item.get("updated_epoch", 0)) < after_ts:
            continue

        if before_ts is not None and float(item.get("updated_epoch", 0)) > before_ts:
            continue

        searchable = f"{item.get('title', '')} {item.get('summary', '')} {item.get('path', '')}"
        if tokens and not tokens.intersection(_to_tokens(searchable)):
            continue

        result_item = dict(item)
        if not include_headings:
            result_item.pop("headings", None)
        filtered.append(result_item)

    filtered.sort(key=lambda item: item.get(_coerce_sort_key(sort), ""), reverse=reverse)
    return filtered


@app.command(paginated=True, annotations=ReadOnly, capabilities=["fs:read"])
def related(
    note_id: Annotated[str, Argument(help="Reference note id")],
    *,
    index_path: Annotated[str, Option(help="Index JSON file to query")] = DEFAULT_INDEX_PATH,
    max_results: Annotated[int, Option(help="Maximum results to return", min=1)] = 10,
    min_score: Annotated[float, Option(help="Minimum score threshold", min=0.0, max=1.0)] = 0.0,
    weight_tags: Annotated[float, Option(help="Weight for tag overlap", min=0.0, max=1.0)] = 0.7,
    weight_terms: Annotated[float, Option(help="Weight for term overlap", min=0.0, max=1.0)] = 0.3,
) -> list[dict[str, Any]]:
    """Find related notes with deterministic overlap scoring."""

    if (weight_tags + weight_terms) <= 0.0:
        raise InputError(
            message="--weight-tags and --weight-terms cannot both be zero",
            code="E1010",
            details={"weight_tags": weight_tags, "weight_terms": weight_terms},
        )

    notes = _read_index(_normalize_path(index_path)).get("notes", [])
    notes_by_id = {note.get("id"): note for note in notes if isinstance(note, dict) and note.get("id")}
    if note_id not in notes_by_id:
        sample = ",".join(sorted(notes_by_id)[:3])
        raise InputError(message="Note not found", code="E1011", details={"note_id": note_id, "sample": sample})

    target = notes_by_id[note_id]
    target_tags = set(str(tag).lower() for tag in target.get("tags", []))
    target_terms = set(str(term).lower() for term in target.get("terms", []))

    candidates: list[dict[str, Any]] = []
    for candidate_id, candidate in notes_by_id.items():
        if candidate_id == note_id:
            continue

        tag_score = _jaccard(
            {str(tag).lower() for tag in candidate.get("tags", []) if isinstance(tag, str)},
            target_tags,
        )
        term_score = _jaccard(
            {str(term).lower() for term in candidate.get("terms", []) if isinstance(term, str)},
            target_terms,
        )
        score = (weight_tags * tag_score) + (weight_terms * term_score)
        if score < min_score:
            continue

        candidates.append({"score": round(score, 4), **candidate})

    candidates.sort(key=lambda item: (item.get("score", 0.0), item.get("title", "")), reverse=True)
    return candidates[:max_results]


@app.command(annotations=ReadOnly, capabilities=["fs:read"])
def export(
    *,
    index_path: Annotated[str, Option(help="Index JSON file to export")] = DEFAULT_INDEX_PATH,
    note_id: Annotated[list[str], Option(help="Filter by one or more note ids")] = None,
    tags: Annotated[list[str], Option(help="Filter by one or more tags (any)")] = None,
    compact: Annotated[bool, Option(help="Return compact output")] = False,
    sort: Annotated[str, Option(help="Sort key: title|size|words|updated_at|headings|updated_epoch")] = "updated_at",
) -> dict[str, Any]:
    """Export index payloads for automation and downstream systems."""

    notes = _read_index(_normalize_path(index_path)).get("notes", [])
    id_filter = set(note_id or [])
    tag_filter = {_normalize_word(tag) for tag in tags or [] if tag}

    selected: list[dict[str, Any]] = []
    for note in notes:
        if not isinstance(note, dict):
            continue

        if id_filter and note.get("id") not in id_filter:
            continue

        note_tags = {_normalize_word(tag) for tag in note.get("tags", []) if isinstance(tag, str)}
        if tag_filter and not note_tags.intersection(tag_filter):
            continue

        if compact:
            selected.append({
                "id": note.get("id"),
                "path": note.get("path"),
                "title": note.get("title"),
                "updated_at": note.get("updated_at"),
                "tags": note.get("tags"),
            })
        else:
            selected.append(note)

    selected.sort(key=lambda item: item.get(_coerce_sort_key(sort), ""))

    return {
        "index_path": str(_normalize_path(index_path)),
        "count": len(selected),
        "notes": selected,
    }


@app.command(paginated=True, annotations=ReadOnly, capabilities=["fs:read"])
def watch(
    source: Annotated[str, Argument(help="Directory or file to compare against index")],
    *,
    index_path: Annotated[str, Option(help="Index JSON file to compare against")] = DEFAULT_INDEX_PATH,
    include: Annotated[list[str] | None, Option(help="Glob pattern(s) to include")] = None,
    exclude: Annotated[list[str], Option(help="Glob pattern(s) to exclude")] = None,
    recursive: Annotated[bool, Option(help="Scan source directories recursively")] = True,
    loop: Annotated[bool, Option(help="Continue polling for changes")] = False,
    interval: Annotated[float, Option(help="Seconds between checks", min=0.1)] = 1.0,
    max_checks: Annotated[int, Option(help="Maximum checks when --loop is set", min=1)] = 1,
) -> dict[str, Any]:
    """Watch for drift between source and index without writing changes."""

    normalized_index = _normalize_path(index_path)
    include_patterns = _coerce_patterns(include)
    exclude_patterns = exclude or []

    checks = 0
    while True:
        checks += 1
        summary = _compute_diff(
            source_path=source,
            index_path=normalized_index,
            include=include_patterns,
            exclude=exclude_patterns,
            recursive=recursive,
            incremental=True,
        )

        has_changes = bool(summary["added"] or summary["updated"] or summary["removed"])
        payload = {
            "source": source,
            "index_path": str(normalized_index),
            "checks": checks,
            "has_changes": has_changes,
            "added": summary["added"],
            "updated": summary["updated"],
            "removed": summary["removed"],
            "unchanged": summary["unchanged"],
        }

        if not loop or has_changes or checks >= max_checks:
            return payload

        time.sleep(interval)


if __name__ == "__main__":
    app()
