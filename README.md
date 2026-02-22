# Tooli

[![CI](https://github.com/weisberg/tooli/actions/workflows/ci.yml/badge.svg)](https://github.com/weisberg/tooli/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/tooli)](https://pypi.org/project/tooli/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/tooli)](https://pypi.org/project/tooli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**The agent-native CLI framework for Python.** Write one function, get a CLI, an MCP tool, and a self-documenting schema.

Tooli turns typed Python functions into CLI commands that are simultaneously human-friendly (Rich output, shell completions) and machine-consumable (JSON schemas, structured output, MCP compatibility). No separate "agent version" of your tool required.

The name comes from "tool" + "CLI" = "tooli".

---

## The Problem

AI agents invoke thousands of CLI commands daily, but standard CLIs were designed for humans:

- **Interactive prompts hang agents** that can't navigate pagers or password dialogs
- **Unstructured output wastes tokens** -- agents parse text with regex instead of reading JSON
- **Vague errors prevent self-correction** -- "Error: invalid input" gives agents nothing to work with
- **No discoverability** -- agents hallucinate flags for undocumented tools

Tooli treats the CLI as a **structured protocol** rather than a text interface. One decorated function produces a CLI command, a JSON Schema, an MCP tool definition, structured errors with recovery suggestions, and auto-generated documentation -- all from a single source of truth.

---

## Current State (v6.5.0)

Tooli v6.5.0 is production-ready and published on [PyPI](https://pypi.org/project/tooli/). The framework implements the complete feature set defined in its PRDs, with 529+ tests passing across Python 3.10+.

### What ships today

| Category | Features |
|---|---|
| **Output** | Dual-mode (Rich for TTY, JSON/JSONL for agents), auto-detected. Standard envelope: `{ok, result, meta}` |
| **Errors** | Typed hierarchy (`InputError`, `AuthError`, `StateError`, `ToolRuntimeError`, `InternalError`) with structured suggestions and recovery playbooks |
| **Schemas** | JSON Schema from type hints, compatible with MCP `inputSchema` and OpenAI function-calling. `$ref` dereferencing for broad client compatibility |
| **MCP** | Serve any Tooli app as an MCP tool server over stdio, HTTP, or SSE -- zero extra code. Auto-registered `skill://` resources |
| **Input** | `StdinOr[T]` unifies files, URLs, and piped stdin. `SecretInput[T]` with automatic redaction |
| **Orchestration** | Hidden `orchestrate run` command for deterministic multi-tool plan execution (`JSON` / `python` payloads) |
| **Safety** | Behavioral annotations (`ReadOnly`, `Destructive`, `Idempotent`, `OpenWorld`), `@dry_run_support`, security policies (OFF/STANDARD/STRICT), auth scopes |
| **Docs** | Task-oriented SKILL.md, enhanced CLAUDE.md, llms.txt, Unix man pages -- always in sync with code |
| **Docs Tooling** | Use external `tooli-docs` to generate SKILL.md, CLAUDE.md, and AGENTS.md from app/schema input |
| **Composition** | Schema-first composition via JSON/JSONL contracts and orchestration plans |
| **Scaffolding** | Use `cookiecutter gh:weisberg/tooli-template` for project bootstrap |
| **Pagination** | Cursor-based with `--limit`, `--cursor`, `--fields`, `--filter` |
| **Caller Detection** | `TOOLI_CALLER` convention for agent identification, 5-category heuristic detection, `detect-context` builtin command, caller metadata in envelope/telemetry/recordings |
| **Observability** | Opt-in telemetry, invocation recording for eval workflows, OpenTelemetry spans with caller attributes |
| **Eval** | Metadata coverage reporter, upgrade analyzer, LLM-powered skill roundtrip evaluation |
| **Extensibility** | Provider system (local, filesystem), transform pipeline (namespace, visibility), tool versioning |
| **Python API** | `app.call()`, `app.acall()`, `app.stream()`, `app.astream()` for direct in-process invocation with typed `TooliResult` objects |
| **Capabilities** | Granular permission declarations (`fs:read`, `net:write`) with STRICT mode enforcement via `TOOLI_ALLOWED_CAPABILITIES` |
| **Multi-Agent** | Handoff metadata and delegation hints for agent workflow orchestration. AGENTS.md generator for GitHub Copilot / Codex compatibility |
| **HTTP API** | OpenAPI 3.1 schema generation + Starlette server (experimental) |

---

## Installation

```bash
pip install tooli
```

Optional extras:

```bash
pip install tooli[mcp]   # MCP server support (fastmcp)
pip install tooli[api]   # HTTP API server (starlette, uvicorn) -- experimental
```

---

## Quick Start

```python
from tooli import Tooli, Annotated, Option, Argument
from tooli.annotations import ReadOnly, Idempotent
from pathlib import Path

app = Tooli(
    name="file-tools",
    description="File manipulation utilities",
    version="6.5.0",
)

@app.command(
    annotations=ReadOnly | Idempotent,
    examples=[
        {"args": ["--pattern", "*.py", "--root", "/project"],
         "description": "Find all Python files in a project"},
    ],
)
def find_files(
    pattern: Annotated[str, Argument(help="Glob pattern to match files")],
    root: Annotated[Path, Option(help="Root directory to search from")] = Path("."),
    max_depth: Annotated[int, Option(help="Maximum directory depth")] = 10,
) -> list[dict]:
    """Find files matching a glob pattern in a directory tree."""
    results = []
    for path in root.rglob(pattern):
        results.append({"path": str(path), "size": path.stat().st_size})
    return results

if __name__ == "__main__":
    app()
```

### Human usage

```bash
$ file-tools find-files "*.py" --root ./src
┌──────────────────────┬───────┐
│ Path                 │ Size  │
├──────────────────────┼───────┤
│ src/main.py          │ 1,204 │
│ src/utils.py         │   892 │
└──────────────────────┴───────┘
```

### Agent usage

```bash
$ file-tools find-files "*.py" --root ./src --json
{
  "ok": true,
  "result": [
    {"path": "src/main.py", "size": 1204},
    {"path": "src/utils.py", "size": 892}
  ],
  "meta": {"tool": "file-tools.find-files", "version": "6.5.0", "duration_ms": 34}
}
```

### Schema export

```bash
$ file-tools find-files --schema
{
  "name": "find-files",
  "description": "Find files matching a glob pattern in a directory tree.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "pattern": {"type": "string", "description": "Glob pattern to match files"},
      "root": {"type": "string", "default": ".", "description": "Root directory to search from"},
      "max_depth": {"type": "integer", "default": 10, "description": "Maximum directory depth"}
    },
    "required": ["pattern"]
  },
  "annotations": {"readOnlyHint": true, "idempotentHint": true}
}
```

### MCP server mode

```bash
$ file-tools mcp serve --transport stdio
$ file-tools mcp serve --transport http --host 127.0.0.1 --port 8080
$ file-tools mcp serve --transport sse --host 127.0.0.1 --port 8080
```

Add to your MCP client config and every command becomes a tool.

---

## Structured Errors

When something goes wrong, agents get actionable recovery guidance instead of opaque messages:

```bash
$ file-tools find-files "*.rs" --root ./src --json
{
  "ok": false,
  "error": {
    "code": "E3001",
    "category": "state",
    "message": "No files matched pattern '*.rs' in ./src",
    "suggestion": {
      "action": "retry_with_modified_input",
      "fix": "The directory contains .py files. Try pattern '*.py' instead.",
      "example": "find-files '*.py' --root ./src"
    },
    "is_retryable": true
  }
}
```

---

## Output Modes

Tooli auto-detects the right output format, or you can be explicit:

| Flag | Behavior |
|---|---|
| *(TTY, no flag)* | Rich formatted output for humans |
| `--json` | Single JSON envelope to stdout |
| `--jsonl` | Newline-delimited JSON for streaming |
| `--plain` | Unformatted text for grep/awk pipelines |
| `--quiet` | Suppress non-essential output |

---

## Input Unification

The `StdinOr[T]` type makes files, URLs, and piped data interchangeable:

```python
from tooli import StdinOr

@app.command()
def process(
    input_data: Annotated[StdinOr[Path], Argument(help="Input file, URL, or stdin")],
) -> dict:
    """Process data from any input source."""
    ...
```

```bash
# All equivalent:
$ file-tools process data.csv
$ file-tools process https://example.com/data.csv
$ cat data.csv | file-tools process -
```

---

## Dry-Run Planning

Preview side effects before executing:

```python
from tooli import dry_run_support, record_dry_action

@app.command(annotations=Destructive)
@dry_run_support
def deploy(target: str) -> dict:
    record_dry_action("upload", target, details={"size": "12MB"})
    record_dry_action("restart", f"{target}-service")
    # ... actual deployment logic
```

```bash
$ file-tools deploy production --dry-run --json
{
  "ok": true,
  "result": [
    {"action": "upload", "target": "production", "details": {"size": "12MB"}},
    {"action": "restart", "target": "production-service"}
  ],
  "meta": {"dry_run": true}
}
```

---

## Auto-Generated Documentation

```bash
# Agent-readable skill documentation (external package)
$ tooli-docs skill examples/docq/app.py:app --output SKILL.md
$ tooli-docs claude-md examples/docq/app.py:app --output CLAUDE.md
$ tooli-docs agents-md examples/docq/app.py:app --output AGENTS.md

# Framework wrappers (external package)
$ tooli-export openai examples/docq/app.py:app --mode import > tools_openai.py
$ tooli-export langchain examples/docq/app.py:app --mode import > tools_langchain.py

# LLM-friendly docs (llms.txt standard)
$ file-tools docs llms

# Unix man page
$ file-tools docs man
```

Useful validation and automation flows:

- Use `--schema` for strict command contracts.
- Use `tooli-docs ... --from-schema schema.json` for schema-driven docs.
- Use CI assertions around envelope shape (`ok/result/meta`) and error codes.

Migration guidance: see [`MIGRATION_GUIDE_v4.md`](MIGRATION_GUIDE_v4.md) (v3 to v4) or [`MIGRATION_GUIDE_v3.md`](MIGRATION_GUIDE_v3.md) (v2 to v3).

---

## Global Flags

Every Tooli command automatically gets:

```
--output, -o       auto|json|jsonl|text|plain
--json/--jsonl     Convenience aliases
--quiet, -q        Suppress non-essential output
--verbose, -v      Increase verbosity (-vvv)
--dry-run          Preview without executing
--yes              Skip confirmation prompts (for automation/agents)
--no-color         Disable colors (also respects NO_COLOR)
--print0           Emit NUL-separated output for list types in text/plain modes
--timeout          Max execution time in seconds
--null             Parse NUL-delimited list input from stdin (list-processing)
--schema           Print JSON Schema and exit
--response-format  concise|detailed
--help-agent       Token-optimized help for agents
```

---

## Architecture

Tooli builds on the Python typing + decorator pipeline, adding a parallel schema generation path:

```
          @app.command()
     Python function + type hints
            |              |
            v              v
      CLI Pipeline    Schema Pipeline
     -> CLI params     -> Pydantic model
     -> CLI parser     -> JSON Schema
            |              |
            v              v
      CLI Output       Agent Output
      Rich tables      MCP tool schema
      Completions      SKILL.md / JSON
```

Key design decisions:
- **Library-first API** -- the public surface is Tooli-native (no framework objects leaked into user code)
- **Pydantic schemas** -- same pipeline as FastAPI and FastMCP
- **Functions stay callable** -- no mutation; test with `CliRunner` or call directly as Python

---

## Examples

The [`examples/`](examples/) directory contains 18 complete CLI apps built with Tooli, each demonstrating different features:

| App | Features |
|---|---|
| **[docq](examples/docq/)** | ReadOnly, paginated, stdin input, output formats |
| **[gitsum](examples/gitsum/)** | ReadOnly, subprocess, StdinOr for diffs |
| **[csvkit_t](examples/csvkit_t/)** | StdinOr, JSONL output, paginated, OpenWorld |
| **[syswatch](examples/syswatch/)** | ReadOnly, paginated, structured errors |
| **[taskr](examples/taskr/)** | Idempotent, Destructive, paginated CRUD |
| **[proj](examples/proj/)** | Destructive, DryRunRecorder, Idempotent |
| **[envar](examples/envar/)** | SecretInput, AuthContext scopes |
| **[imgsort](examples/imgsort/)** | Destructive+Idempotent, DryRunRecorder, batch ops |
| **[note_indexer](examples/note_indexer/)** | ReadOnly, paginated, JSON index, error handling |

See the [examples README](examples/README.md) for the full list of 18 apps and usage guide.

---

## Version History

- **v6.5.0** (current) -- latest stable v6 release line with core cleanup, extraction follow-through, and ongoing reliability improvements.
- **v6.0** -- extraction and cleanup release. Docs and export generation moved to external packages (`tooli-docs`, `tooli-export`); deprecated internal shims removed.
- **v5.0** -- Universal Agent Tool Interface. Added Python API, capabilities, handoff metadata, and AGENTS.md generation.
- **v4.1** -- Caller-Aware Agent Runtime. `TOOLI_CALLER` convention, 5-category heuristic detection, `detect-context` builtin, caller metadata in envelope/telemetry/recordings, adaptive confirmation and help formatting.
- **v4.0** -- Agent Skill Platform foundations and schema-first workflows.
- **v2.0** -- Agent-Environment Interface. MCP bridge, orchestration runtime, deferred discovery, token budgets, Python eval mode.
- **v1.0** -- Core framework. Dual-mode output, structured errors, JSON Schema, MCP server, annotations, pagination, observability.

See [CHANGELOG.md](CHANGELOG.md) for full details and [MIGRATION_GUIDE_v4.md](MIGRATION_GUIDE_v4.md) for upgrade steps.

---

## Development

```bash
# Clone and install for development
git clone https://github.com/weisberg/tooli.git
cd tooli
pip install -e ".[dev]"

# Run tests
pytest

# Lint and type check
ruff check .
mypy tooli
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License. See [LICENSE](LICENSE) for details.
