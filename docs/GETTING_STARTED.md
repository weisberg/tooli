# Getting Started

Tooli turns typed Python functions into agent-friendly commands with structured output.

## 1. Install

```bash
pip install tooli
```

## 2. Create an app

```python
from tooli import Tooli, Annotated, Argument, Option

app = Tooli(name="files", version="6.5.0")

@app.command()
def find(
    pattern: Annotated[str, Argument(help="Glob pattern")],
    root: Annotated[str, Option(help="Root directory")] = ".",
) -> list[dict[str, str]]:
    return [{"pattern": pattern, "root": root}]

if __name__ == "__main__":
    raise SystemExit(app.main())
```

## 3. Run it

```bash
python app.py find "*.py" --root . --json
```

You get a structured envelope:

```json
{"ok": true, "result": [...], "meta": {...}}
```

## 4. Expose for agents

- use `--json` for deterministic parsing
- use `--schema` to expose parameter contracts
- use `mcp serve` to expose commands via MCP

## 5. Generate external docs/export artifacts

- docs: `tooli-docs skill app_module:app`
- framework export: `tooli-export openai app_module:app`

This is the full development loop: define command -> run -> schema -> docs/export.
