# Tooli - Agent-Native CLI Framework

## Quick Reference

- **Language**: Python 3.10+
- **Framework**: Typer (CLI) + Pydantic (schemas) + Rich (output)
- **Package**: `tooli/` directory
- **Tests**: `tests/` directory

## Commands

```bash
# Install
pip install -e ".[dev]"

# Run tests
.venv/bin/pytest tests

# Lint
ruff check .

# Type check
mypy tooli
```

## Architecture

Tooli extends Typer to produce CLI tools that are human-friendly and machine-consumable by AI agents.

### Core Files
- `tooli/app.py` — `Tooli` class (extends `typer.Typer`), command registration, built-in commands
- `tooli/command.py` — `TooliCommand` (extends `TyperCommand`), global flags, output routing, invoke() pipeline
- `tooli/command_meta.py` — `CommandMeta` dataclass, `get_command_meta()` accessor
- `tooli/errors.py` — `ToolError` hierarchy: `InputError`, `AuthError`, `StateError`, `ToolRuntimeError`, `InternalError`
- `tooli/output.py` — `OutputMode` enum, mode resolution
- `tooli/envelope.py` — JSON envelope wrapper (`ok`, `result`, `meta`)
- `tooli/schema.py` — JSON Schema generation from function signatures

### Metadata System
Command metadata is stored as a single `CommandMeta` dataclass on `func.__tooli_meta__`. Access it with `get_command_meta(callback)`. Do NOT use individual `setattr`/`getattr` with `__tooli_xxx__` attributes.

### Providers & Transforms
- `tooli/providers/` — `LocalProvider` (decorated functions), `FileSystemProvider` (directory scanning)
- `tooli/transforms.py` — `NamespaceTransform`, `VisibilityTransform` modify tool surfaces

### Output Modes
Commands return values; `TooliCommand.invoke()` routes them through: AUTO (Rich for TTY, JSON for pipes), JSON (envelope-wrapped), JSONL, TEXT, PLAIN.

## Conventions

- Error classes: use `ToolRuntimeError` (not `RuntimeError` — don't shadow the builtin)
- Imports: use `collections.abc.Iterable`/`Callable` (not `typing`)
- Cross-platform: guard `signal.SIGALRM` with `hasattr`, use `_file_lock()` context manager for file locking
- Output to stderr: use `click.echo(..., err=True)` (not `print()`)
- Tests: 90+ tests, run with `.venv/bin/pytest -x -q` for quick feedback
