# Migration Guide: v4.1 to v5.0

Tooli v5.0 ("The Universal Agent Tool Interface") adds a Python API for direct in-process invocation, granular capability declarations, multi-agent handoff metadata, and AGENTS.md documentation generation. **All changes are additive** -- your existing v4.x code will run unchanged.

## What's New

### Python API (`app.call`, `app.stream`)

You can now invoke commands directly from Python without CLI parsing:

```python
from myapp import app

# Single invocation
result = app.call("find-files", pattern="*.py")
if result.ok:
    print(result.result)  # typed dict/list
else:
    print(result.error.message)  # structured error

# Streaming (yields individual items from list-returning commands)
for item in app.stream("find-files", pattern="*.py"):
    print(item.result)

# Async variants
result = await app.acall("find-files", pattern="*.py")
async for item in app.astream("find-files", pattern="*.py"):
    print(item.result)
```

`TooliResult` and `TooliError` are available from `tooli`:

```python
from tooli import TooliResult, TooliError
```

### Capabilities

Declare what permissions a command needs:

```python
@app.command(
    annotations=ReadOnly,
    capabilities=["fs:read"],
)
def find_files(pattern: str) -> list[dict]:
    ...
```

Common capability tokens: `fs:read`, `fs:write`, `fs:delete`, `net:read`, `net:write`, `env:read`, `env:write`, `process:exec`, `process:read`.

Capabilities are rendered in SKILL.md, AGENTS.md, CLAUDE.md, manifest, and JSON Schema.

### Security Enforcement

In STRICT security policy mode, set `TOOLI_ALLOWED_CAPABILITIES` to control which capabilities are permitted:

```bash
export TOOLI_ALLOWED_CAPABILITIES="fs:read,net:read"
mytool find-files "*.py" --json   # OK (fs:read allowed)
mytool write-file output.txt --json  # BLOCKED (fs:write not in allowlist)
```

Wildcard matching is supported: `fs:*` allows `fs:read`, `fs:write`, `fs:delete`.

### Handoffs

Declare multi-agent workflow transitions:

```python
@app.command(
    capabilities=["fs:read"],
    handoffs=[
        {"command": "organize", "when": "sort scanned images into folders"},
        {"command": "duplicates", "when": "check for duplicate images"},
    ],
    delegation_hint="Use this as a first step before organizing files",
)
def scan(directory: str) -> list[dict]:
    ...
```

### Error Field Mapping

Link errors to specific input parameters:

```python
from tooli.errors import InputError

raise InputError(
    message="Invalid file path",
    code="E1001",
    field="path",  # NEW: maps error to the 'path' parameter
)
```

The `field` value appears in the JSON error envelope and is preserved through `TooliError` → `to_exception()` roundtrips.

### Output Schema in Envelope

When `--response-format detailed` or `TOOLI_INCLUDE_SCHEMA=true`, the envelope `meta` includes an `output_schema` field derived from the command's return type annotation:

```json
{
  "ok": true,
  "result": [...],
  "meta": {
    "tool": "myapp.find-files",
    "output_schema": {"type": "array"}
  }
}
```

### AGENTS.md

Generate GitHub Copilot / OpenAI Codex compatible documentation:

```bash
mytool generate-agents-md --output AGENTS.md
```

### Agent SDK Integration

Four framework integration examples are provided under `examples/integrations/`:

| File | Framework |
|---|---|
| `claude_sdk_example.py` | Claude Agent SDK |
| `openai_agents_example.py` | OpenAI Agents SDK |
| `langchain_example.py` | LangChain / LangGraph |
| `google_adk_example.py` | Google ADK |

Each example shows both the Python API approach (`app.call()`) and the subprocess approach with `TOOLI_CALLER`.

## Migration Steps

### Step 1: Add capabilities to your commands (recommended)

```python
# Before (v4.x)
@app.command(annotations=ReadOnly)
def stats(path: str) -> dict:
    ...

# After (v5.0)
@app.command(annotations=ReadOnly, capabilities=["fs:read"])
def stats(path: str) -> dict:
    ...
```

### Step 2: Add handoffs where commands naturally chain (optional)

```python
@app.command(
    capabilities=["fs:read"],
    handoffs=[{"command": "extract", "when": "need a specific section"}],
)
def headings(path: str) -> list[dict]:
    ...
```

### Step 3: Add field to error raises (optional)

```python
# Before
raise InputError("File not found", code="E1001")

# After
raise InputError("File not found", code="E1001", field="path")
```

### Step 4: Use Python API for in-process integrations (optional)

Replace subprocess calls with `app.call()` for faster, typed invocation.

### Step 5: Regenerate documentation

```bash
mytool generate-skill --output SKILL.md
mytool generate-agents-md --output AGENTS.md
mytool generate-claude-md --output CLAUDE.md
```

## Breaking Changes

**None.** All v5 features are additive. Existing v4.x code runs unchanged on v5.0.

## Version Compatibility

| Feature | v4.0 | v4.1 | v5.0 |
|---|---|---|---|
| `@app.command()` | Yes | Yes | Yes |
| `capabilities` | -- | -- | Yes |
| `handoffs` | -- | -- | Yes |
| `app.call()` | -- | -- | Yes |
| `app.stream()` | -- | -- | Yes |
| `TOOLI_CALLER` | -- | Yes | Yes |
| AGENTS.md | -- | -- | Yes |
| Error `field` | -- | -- | Yes |
