# Tooli Examples

This directory contains complete CLI applications built with Tooli, demonstrating the full range of agent-native CLI features.

## The Agent-First CLI Contract

Every app in this directory adheres to these principles:

1. **Discoverable** -- Use `--schema` to see exactly what the tool can do
2. **Predictable** -- Use `--json` or `--jsonl` for stable, machine-readable output
3. **Safe** -- Destructive operations require `--yes` and support `--dry-run`
4. **Actionable** -- Errors include `suggestions` that help agents self-correct
5. **Universal** -- `StdinOr[T]` makes files, URLs, and pipes interchangeable

---

## Quick Start

```bash
# Install tooli with dev dependencies
pip install -e ".[dev]"

# Run any example app
python -m examples.docq.app --help
python -m examples.gitsum.app summary . --json
python -m examples.taskr.app add "My task" --json
```

Every app also supports direct execution:

```bash
python examples/docq/app.py --help
```

---

## Example Apps

### Core Showcase (ReadOnly / OpenWorld)

| App | Description | Key Features |
|---|---|---|
| **[note_indexer](note_indexer/)** | Markdown file indexer with query and export | ReadOnly, paginated, JSON index, structured errors |
| **[docq](docq/)** | Document query tool for text/markdown analysis | ReadOnly, paginated, stdin input, multiple output formats |
| **[gitsum](gitsum/)** | Git repository analyst | ReadOnly, subprocess integration, StdinOr for diffs |
| **[csvkit_t](csvkit_t/)** | CSV data wrangling toolkit | StdinOr, JSONL output, paginated, OpenWorld |
| **[syswatch](syswatch/)** | System health inspector | ReadOnly, paginated, structured errors, stdlib OS |

### State Management (Destructive / Idempotent / DryRun)

| App | Description | Key Features |
|---|---|---|
| **[taskr](taskr/)** | Local task manager with JSON storage | Idempotent, Destructive, paginated CRUD, state management |
| **[proj](proj/)** | Project scaffolder with templates | Destructive, DryRunRecorder, Idempotent validation |
| **[envar](envar/)** | Environment & secrets manager | SecretInput, AuthContext scopes, mixed annotations |
| **[imgsort](imgsort/)** | Image organizer by metadata | Destructive+Idempotent, DryRunRecorder, batch operations |

### Additional Examples

| App | Description | Key Features |
|---|---|---|
| **[repolens](repolens/)** | Codebase structure scanner | Structured inventory, JSONL streaming |
| **[patchpilot](patchpilot/)** | Safe file patch application | Dry-run planning, structured errors |
| **[logslicer](logslicer/)** | Log file parser and query tool | StdinOr, JSONL event streaming |
| **[datawrangler](datawrangler/)** | CSV/JSON data transforms | Input unification, response format variants |
| **[secretscout](secretscout/)** | Local secret scanner | Structured findings, remediation suggestions |
| **[envdoctor](envdoctor/)** | Environment diagnostics | Machine-readable checks, JSONL stream |
| **[mediameta](mediameta/)** | Media metadata inspector | StdinOr for binary data, normalization |
| **[configmigrate](configmigrate/)** | Config file validator/upgrader | Schema-driven discovery, migration hints |
| **[artifactcatalog](artifactcatalog/)** | Document indexer and search | JSONL indexing, structured search |

---

## Demo Flow

Try this sequence with any app to see the agent-first contract in action:

### 1. Introspect capabilities

```bash
python -m examples.docq.app stats --schema
```

### 2. Run in machine mode

```bash
python -m examples.docq.app stats README.md --json
```

### 3. Trigger a structured error

```bash
python -m examples.docq.app stats nonexistent.md --json
```

### 4. Side-effect command with dry-run

```bash
python -m examples.proj.app init my-project --template python --dry-run --json
```

### 5. Flip into MCP mode

```bash
python -m examples.docq.app mcp serve --transport stdio
```

### 6. Orchestrate multiple steps (advanced)

```bash
python - <<'PY'
import json
import subprocess

payload = [
  {"command": "stats", "arguments": {"path": "README.md"}},
  {"command": "stats", "arguments": {"path": "CLAUDE.md"}}
]

subprocess.run([
    "python",
    "-m",
    "examples.docq.app",
    "orchestrate",
    "run",
    "--json",
], input=json.dumps(payload), text=True, check=True)
PY
```

`orchestrate run` is an internal helper for plan execution and returns compact step-level summaries.
