# Tooli

The agent-native CLI framework for Python. Write one function, get a CLI, an MCP tool, and a self-documenting schema.

Tooli extends [Typer](https://typer.tiangolo.com/) so that every decorated command is simultaneously human-friendly (Rich output, shell completions) and machine-consumable (JSON schemas, structured output, MCP compatibility). No separate "agent version" of your tool required.

## Why Tooli?

AI agents invoke thousands of CLI commands daily, but standard CLIs were designed for humans:

- **Interactive prompts hang agents** that can't navigate pagers or password dialogs
- **Unstructured output wastes tokens** — agents parse text with regex instead of reading JSON
- **Vague errors prevent self-correction** — "Error: invalid input" gives agents nothing to work with
- **No discoverability** — agents hallucinate flags for undocumented tools

Tooli fixes all of this. One decorated function produces a CLI, a JSON Schema, an MCP tool definition, structured errors with recovery suggestions, and auto-generated documentation — from a single source of truth.

## Features

- **Dual-mode output** — Rich tables for humans, JSON/JSONL for agents, auto-detected via TTY
- **Structured errors** — actionable error objects with suggestion fields that guide agent self-correction
- **Schema generation** — JSON Schema from type hints, compatible with MCP `inputSchema` and OpenAI function-calling
- **MCP server mode** — serve your CLI as an MCP tool server over stdio or HTTP with zero extra code
- **SKILL.md generation** — auto-generated agent-readable documentation, always in sync with code
- **stdin/file parity** — `StdinOr[T]` type makes files, URLs, and piped data interchangeable
- **Standard global flags** — `--json`, `--jsonl`, `--plain`, `--quiet`, `--dry-run`, `--schema` injected automatically
- **Agent-safe by default** — no interactive prompts in non-TTY mode, no stdout pollution, strict exit codes

## Installation

```bash
pip install tooli
```

## Quick Start

```python
from tooli import AgentTyper, Annotated, Option, Argument
from tooli.annotations import ReadOnly, Idempotent
from pathlib import Path

agent = AgentTyper(
    name="file-tools",
    description="File manipulation utilities",
    version="1.0.0",
)

@agent.command(
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
    agent()
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
  "meta": {"tool": "file-tools.find-files", "version": "1.0.0", "duration_ms": 34}
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
```

Add to your MCP client config and every command becomes a tool.

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

## Output Modes

Tooli auto-detects the right output format, or you can be explicit:

| Flag | Behavior |
|---|---|
| *(TTY, no flag)* | Rich formatted output for humans |
| `--json` | Single JSON envelope to stdout |
| `--jsonl` | Newline-delimited JSON for streaming |
| `--plain` | Unformatted text for grep/awk pipelines |
| `--quiet` | Suppress non-essential output |

## Auto-Generated Documentation

```bash
# Agent-readable skill documentation
$ file-tools generate-skill > SKILL.md

# LLM-friendly docs (llms.txt standard)
$ file-tools docs llms

# Unix man page
$ file-tools docs man
```

## Input Unification

The `StdinOr[T]` type makes files, URLs, and piped data interchangeable:

```python
from tooli import StdinOr

@agent.command()
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

## Global Flags

Every Tooli command automatically gets:

```
--output, -o       auto|json|jsonl|text|plain
--json/--jsonl     Convenience aliases
--quiet, -q        Suppress non-essential output
--verbose, -v      Increase verbosity (-vvv)
--dry-run          Preview without executing
--no-color         Disable colors (also respects NO_COLOR)
--timeout          Max execution time in seconds
--schema           Print JSON Schema and exit
--response-format  concise|detailed
--help-agent       Token-optimized help for agents
```

## Architecture

Tooli builds on Typer's decorator pipeline, adding a parallel schema generation path:

```
         @agent.command()
     Python function + type hints
            │              │
            ▼              ▼
     Typer Pipeline   Schema Pipeline
     → Click params   → Pydantic model
     → CLI parser     → JSON Schema
            │              │
            ▼              ▼
      CLI Output       Agent Output
      Rich tables      MCP tool schema
      Completions      SKILL.md / JSON
```

Key design decisions:
- **Subclass, don't fork** — extends Typer via `cls` parameter for full ecosystem compatibility
- **Pydantic schemas** — same pipeline as FastAPI and FastMCP
- **Functions stay callable** — no mutation; test with `CliRunner` or call directly as Python

## Development

```bash
# Clone and install for development
git clone https://github.com/weisberg/tooli.git
cd tooli
pip install -e ".[dev]"
```

## Roadmap

See [PRD.md](PRD.md) for the full product requirements document, including detailed architecture, implementation phases, and success metrics.

## License

MIT License. See [LICENSE](LICENSE) for details.
