# Tooli - Agent-Native CLI Framework

## Quick Reference

- **Version**: 5.0.0
- **Language**: Python 3.10+
- **Framework**: Typer (CLI) + Pydantic (schemas) + Rich (output)
- **Package**: `tooli/` directory
- **Tests**: `tests/` directory (529+ tests)
- **Examples**: `examples/` directory (18 complete apps)

## Commands

```bash
# Install
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .

# Type check
mypy tooli
```

## Architecture

Tooli extends Typer to produce CLI tools that are human-friendly and machine-consumable by AI agents. One decorated function produces a CLI command, a JSON Schema, an MCP tool definition, and documentation.

### Core Files
- `tooli/app.py` -- `Tooli` class (extends `typer.Typer`), command registration, built-in commands
- `tooli/command.py` -- `TooliCommand` (extends `TyperCommand`), global flags, output routing, invoke() pipeline
- `tooli/command_meta.py` -- `CommandMeta` dataclass, `get_command_meta()` accessor
- `tooli/errors.py` -- `ToolError` hierarchy: `InputError`, `AuthError`, `StateError`, `ToolRuntimeError`, `InternalError`
- `tooli/output.py` -- `OutputMode` enum, mode resolution
- `tooli/envelope.py` -- JSON envelope wrapper (`ok`, `result`, `meta`)
- `tooli/schema.py` -- JSON Schema generation from function signatures
- `tooli/annotations.py` -- `ReadOnly`, `Idempotent`, `Destructive`, `OpenWorld` (composable with `|`)
- `tooli/input.py` -- `StdinOr[T]`, `SecretInput[T]`, `StdinOrType`
- `tooli/dry_run.py` -- `@dry_run_support` decorator, `record_dry_action()`
- `tooli/auth.py` -- `AuthContext` with scope-based access control
- `tooli/pagination.py` -- Cursor-based pagination primitives

### v4 Agent Skill Platform Modules
- `tooli/pipes.py` -- `PipeContract` dataclass for command composition contracts
- `tooli/bootstrap.py` -- `--agent-bootstrap` flag logic with auto-detection of target environment
- `tooli/docs/skill_v4.py` -- Task-oriented SKILL.md generator (v4 format)
- `tooli/docs/claude_md_v2.py` -- Enhanced CLAUDE.md generator
- `tooli/docs/source_hints.py` -- `# tooli:agent` source-level hint blocks
- `tooli/init.py` -- `tooli init` project scaffolding
- `tooli/eval/coverage.py` -- Metadata coverage reporter
- `tooli/eval/skill_roundtrip.py` -- LLM-powered skill evaluation (opt-in)
- `tooli/upgrade.py` -- Metadata improvement analyzer

### v4.1 Caller-Aware Agent Runtime Modules
- `tooli/detect.py` -- Caller detection: `CallerCategory` enum, `ExecutionContext`, `detect_execution_context()`, heuristic + convention-based detection
- `tooli/envelope.py` -- Now includes `caller_id`, `caller_version`, `session_id` in `EnvelopeMeta`
- `tooli/telemetry.py` -- OTel span caller attributes via `set_caller()`
- `tooli/eval/recorder.py` -- `InvocationRecord` schema v2 with `caller_id`/`session_id` fields

### v5 Universal Agent Tool Interface Modules
- `tooli/python_api.py` -- `TooliResult[T]`, `TooliError` frozen dataclasses for typed Python API results
- `tooli/app.py` -- `call()`, `acall()`, `stream()`, `astream()`, `get_command()` methods
- `tooli/command_meta.py` -- v5 fields: `capabilities`, `handoffs`, `delegation_hint`
- `tooli/docs/agents_md.py` -- AGENTS.md generator (GitHub Copilot / OpenAI Codex compatible)
- `tooli/command.py` -- Capability enforcement (`TOOLI_ALLOWED_CAPABILITIES`), output schema in envelope

### Optional Modules
- `tooli/mcp/` -- MCP server support (requires `tooli[mcp]`), includes auto-registered `skill://` resources
- `tooli/api/` -- HTTP API server + OpenAPI generation (requires `tooli[api]`, experimental)

### Metadata System
Command metadata is stored as a single `CommandMeta` dataclass on `func.__tooli_meta__`. Access it with `get_command_meta(callback)`. Do NOT use individual `setattr`/`getattr` with `__tooli_xxx__` attributes.

### Providers & Transforms
- `tooli/providers/` -- `LocalProvider` (decorated functions), `FileSystemProvider` (directory scanning)
- `tooli/transforms.py` -- `NamespaceTransform`, `VisibilityTransform` modify tool surfaces

### Output Modes
Commands return values; `TooliCommand.invoke()` routes them through: AUTO (Rich for TTY, JSON for pipes), JSON (envelope-wrapped), JSONL, TEXT, PLAIN.

## Conventions

- Error classes: use `ToolRuntimeError` (not `RuntimeError` -- don't shadow the builtin)
- Imports: use `collections.abc.Iterable`/`Callable` (not `typing`)
- Cross-platform: guard `signal.SIGALRM` with `hasattr`, use `_file_lock()` context manager for file locking
- Output to stderr: use `click.echo(..., err=True)` (not `print()`)
- Python 3.10 compat: use `Annotated[(str, *metadata)]` not `Annotated[str, *metadata]` (PEP 646 syntax is 3.11+)
- Tests: run with `pytest -x -q` for quick feedback
