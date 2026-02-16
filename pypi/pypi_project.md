# Tooli

The agent-native CLI framework for Python.

Tooli turns typed Python functions into command-line tools that work for both humans and AI agents: rich output in a terminal, strict structured output in automation, and self-describing schemas for tool calling and orchestration.

The name comes from "tool" + "CLI" = "tooli".

## Why Tooli?

AI agents invoke lots of local commands, but typical CLIs are optimized for humans:

- Huge, unstructured stdout that burns context windows
- Opaque errors that don't suggest a fix
- Fragile pipelines that mix logs with machine output
- Undocumented flags that agents hallucinate

Tooli is built to be *machine-consumable by default* while still feeling great for humans.

## Install

```bash
pip install tooli
```

Optional extras:

```bash
pip install "tooli[mcp]"   # MCP server support
pip install "tooli[api]"   # HTTP API + OpenAPI export (experimental)
```

## Quick Start

Create `file_tools.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from tooli import Argument, Option, Tooli
from tooli.annotations import Idempotent, ReadOnly

app = Tooli(name="file-tools", description="File utilities", version="1.1.0")


@app.command(annotations=ReadOnly | Idempotent, paginated=True, list_processing=True)
def find_files(
    pattern: Annotated[str, Argument(help="Glob to match")],
    root: Annotated[Path, Option(help="Root directory")] = Path("."),
) -> list[dict[str, str]]:
    return [{"path": str(p)} for p in root.rglob(pattern)]


if __name__ == "__main__":
    app()
```

Run it:

```bash
python file_tools.py find-files "*.py" --root .
python file_tools.py find-files "*.py" --root . --output json
python file_tools.py find-files --schema
```

## Structured Output (JSON / JSONL)

Tooli supports dual-mode output:

- Human mode: pretty output when attached to a TTY
- Agent mode: strict envelopes when using `--output json` or `--output jsonl`

JSON envelope shape:

```json
{
  "ok": true,
  "result": {"...": "..."},
  "meta": {
    "tool": "file-tools.find-files",
    "version": "1.1.0",
    "duration_ms": 12,
    "annotations": {"readOnlyHint": true, "idempotentHint": true}
  }
}
```

## Structured Errors With Recovery Hints

When a command fails, Tooli emits a structured error with an actionable suggestion:

```json
{
  "ok": false,
  "error": {
    "code": "E1004",
    "category": "input",
    "message": "Exact search string was not found in source.",
    "suggestion": {
      "action": "adjust search text",
      "fix": "Double-check exact spacing/newlines. Did you mean: \"...\"?"
    },
    "is_retryable": true
  }
}
```

## Schemas, Docs, and Orchestration

Tooli can generate tool schemas and agent-facing docs directly from type hints and metadata:

```bash
python file_tools.py find-files --schema
python file_tools.py generate-skill > SKILL.md
python file_tools.py docs llms
python file_tools.py docs man
```

Run as an MCP server (one tool per command):

```bash
python file_tools.py mcp serve --transport stdio
python file_tools.py mcp serve --transport http --host 127.0.0.1 --port 8080
python file_tools.py mcp serve --transport sse --host 127.0.0.1 --port 8080
```

## Universal Input (files / URLs / stdin)

Use `StdinOr[T]` to accept a file path, a URL, or piped stdin with one parameter.

```python
from pathlib import Path
from typing import Annotated

from tooli import Argument, StdinOr, Tooli

app = Tooli(name="log-tools")


@app.command()
def head(
    source: Annotated[StdinOr[str], Argument(help="Path, URL, or '-' for stdin")],
) -> dict[str, int]:
    return {"bytes": len(source)}  # `source` resolves to the content
```

## Built-In Guardrails

Tooli provides primitives for safer automation:

- `ReadOnly`, `Idempotent`, `Destructive`, `OpenWorld` annotations on commands
- `--dry-run` planning support via `@dry_run_support` + `record_dry_action(...)`
- `SecretInput[T]` with automatic redaction in outputs and errors
- Cursor pagination (`--limit`, `--cursor`, `--fields`, `--filter`) for list-shaped results

## Example Apps (agent pain points)

The GitHub repo includes sample apps under `examples/` that target common agent failure modes:

- `code-lens`: token-efficient symbol outlines from Python ASTs (avoid dumping whole files)
- `safe-patch`: self-healing file edits with dry-run plans and recovery hints
- `log-sift`: pipeline-friendly log extraction with strict JSON/JSONL output
- `sqlite-probe`: read-only SQLite exploration with pagination and guardrails

## Links

- Source: https://github.com/weisberg/tooli
- Changelog: https://github.com/weisberg/tooli/blob/main/CHANGELOG.md
