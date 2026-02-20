# Tooli v5.0 — Product Requirements Document

## The Universal Agent Tool Interface

**Version**: 5.0
**Author**: Brian Weisberg
**Status**: Draft
**Date**: February 2026
**Supersedes**: PRD_v4.1.md (v4.1)

------

## 1. Executive Summary

Tooli v4.1 made every tooli-built CLI caller-aware: it knows who's calling (Claude Code, Cursor, LangChain, a human), threads caller metadata through the envelope, telemetry, and recordings, and adapts its behavior accordingly. The tool-side story is strong — tooli CLIs are the most agent-friendly CLI tools in the ecosystem.

But there's a gap on the **agent-side**. Every major agent framework — Claude Agent SDK, OpenAI Agents SDK, LangChain/LangGraph, Google ADK, GitHub Copilot SDK — eventually shells out to CLI tools via Bash. They all struggle with the same five problems:

1. **No schema** — agents guess at flags
2. **No structured output** — agents regex-parse text
3. **No error contracts** — agents can't self-correct
4. **No discoverability** — agents hallucinate capabilities
5. **No composition metadata** — agents can't chain tools

Tooli solves all five *for CLI invocation*. But most agent frameworks prefer Python-native tool calling — `from myapp import find_files; result = find_files(pattern="*.py")` — not `subprocess.run(["myapp", "find-files", "--json"])`. And each framework has its own tool definition format: OpenAI uses `@function_tool` with Pydantic schemas, LangChain uses `BaseTool` subclasses, ADK uses `FunctionTool` or Agent Config YAML, and Copilot reads `AGENTS.md`.

**v5.0 makes tooli the universal adapter.** One decorated function produces:
- A CLI command (existing)
- A JSON Schema (existing)
- An MCP tool (existing)
- A SKILL.md (existing)
- A **Python API** with the same structured envelope (new)
- An **AGENTS.md** for GitHub Copilot and OpenAI Codex (new)
- **Framework-specific tool definitions** for OpenAI, LangChain, ADK (new)
- **Handoff metadata** for multi-agent orchestration (new)

This is the "Rosetta Stone" vision: write once, run anywhere agents live.

### What's New in v5.0 vs v4.1

| Capability | v4.1 | v5.0 |
|---|---|---|
| Invocation | CLI only (`subprocess.run`) | CLI + Python API (`from myapp import find_files`) |
| Agent doc formats | SKILL.md, CLAUDE.md | + AGENTS.md (Copilot/Codex) |
| Framework integration | Generic JSON Schema | `--export openai`, `--export langchain`, `--export adk` |
| Multi-agent support | Caller identity only | Handoff metadata: "next tool" suggestions, delegation hints |
| Permission model | `ReadOnly`/`Destructive` annotations | Granular capabilities: filesystem scope, network access, side effects |
| Error recovery | Suggestions per error | Error → input field mapping; agents know *which parameter* to fix |
| Output schema | In `--schema` only | In envelope, in AGENTS.md, in framework exports |
| Security enforcement | Metadata only | Runtime policy enforcement (STANDARD/STRICT actually enforced) |

------

## 2. Problem Analysis

### 2.1 The Python API Gap

The single most requested feature. Agent SDKs (Claude Agent SDK, OpenAI, ADK) prefer Python-native tool calling:

```python
# What agents WANT to do:
from myapp import find_files

result = find_files(pattern="*.py", root="./src")
assert result.ok
for f in result.result:
    print(f["path"])
```

```python
# What agents HAVE to do today:
import subprocess, json

proc = subprocess.run(
    ["myapp", "find-files", "*.py", "--root", "./src", "--json"],
    capture_output=True, text=True,
)
data = json.loads(proc.stdout)
if data["ok"]:
    for f in data["result"]:
        print(f["path"])
```

The subprocess path works but has costs:
- **Extra process overhead** — subprocess spawn, shell parsing, environment setup
- **String serialization** — Python objects → CLI args → string parsing → Python objects → JSON → string → JSON parsing → Python objects
- **Lost type information** — the agent gets `dict`, not a typed return value
- **No IDE support** — no autocomplete, no type checking, no docstring hover
- **Error handling mismatch** — agent catches `subprocess.CalledProcessError`, not typed exceptions

Tooli already has the building blocks: commands are decorated Python functions with full type signatures. The function *exists* and is *callable*. What's missing is a clean public API that wraps the call in the same structured envelope and preserves all tooli behaviors (error handling, dry-run, annotations).

### 2.2 The AGENTS.md Gap

GitHub Copilot (150M+ users) and OpenAI Codex both read `AGENTS.md` for project-specific agent instructions. This is the equivalent of SKILL.md but for a different ecosystem. Tooli generates SKILL.md and CLAUDE.md — adding AGENTS.md is low effort and high reach.

### 2.3 The Framework Integration Gap

Each framework has its own tool definition format:

| Framework | Tool Format | Current Tooli Support |
|---|---|---|
| **OpenAI Agents SDK** | `@function_tool` decorator with Pydantic schemas | Schema compatible, but no ready-to-use code |
| **LangChain** | `BaseTool` subclass with `_run()` method | Not supported |
| **LangGraph** | Same as LangChain + state graph integration | Not supported |
| **Google ADK** | `FunctionTool`, Agent Config YAML | Not supported |
| **Claude Agent SDK** | Python functions + `query()` | MCP integration only |
| **Copilot SDK** | JSON-RPC tool definitions | Not supported |

Generating ready-to-paste integration code for the top 3 frameworks would make tooli the bridge between CLI tools and every agent platform.

### 2.4 The Multi-Agent Coordination Gap

Agent teams are emerging: Claude Code Agent Teams, LangGraph multi-agent graphs, ADK agent hierarchies, OpenAI handoffs. When an orchestrator assigns tools to specialized agents, it needs metadata about what each tool is *good for* — not just what it *does*.

Currently, tooli commands have `when_to_use` prose and `task_group` labels. What's missing:
- **Delegation hints** — "This tool is best used by an agent with filesystem access"
- **Handoff suggestions** — "After this command, consider running `deploy` or `verify`"
- **Capability requirements** — "This tool needs network access" / "This tool modifies the filesystem"
- **Coordination metadata** — how tools relate to each other in multi-step workflows

### 2.5 The Security Enforcement Gap

Tooli has `SecurityPolicy` (OFF/STANDARD/STRICT) and `AuthContext` with scope-based access control, but they're metadata only — not enforced at runtime. Agents need real guardrails:

- Claude Code has permission modes (ask/auto-approve)
- ADK has Tool Confirmation (HITL)
- OpenAI has guardrails (input/output validation)
- MCP has capability declarations

Tooli should enforce its security policies, not just declare them.

------

## 3. Goals & Non-Goals

### 3.1 Goals

| # | Goal | Success Metric |
|---|---|---|
| G1 | **Python API mode**: Every tooli command callable as a typed Python function returning `TooliResult` | `from myapp import find_files; r = find_files(pattern="*.py"); assert r.ok` works |
| G2 | **AGENTS.md generation**: One command produces AGENTS.md for Copilot/Codex | `mytool generate-skill --format agents-md > AGENTS.md` produces valid AGENTS.md |
| G3 | **Framework export**: Generate ready-to-use tool definitions for OpenAI, LangChain, ADK | `mytool export --target openai` produces copy-pasteable `@function_tool` code |
| G4 | **Handoff metadata**: Commands declare what should run next and what capabilities they need | Manifest includes `handoffs` and `capabilities` per command |
| G5 | **Granular capabilities**: Commands declare filesystem, network, and side-effect scope | `@app.command(capabilities=["fs:read", "fs:write:./output"])` |
| G6 | **Error field mapping**: Structured errors link to specific input parameters | `error.field: "pattern"` tells the agent which argument to fix |
| G7 | **Security enforcement**: `SecurityPolicy.STRICT` actually blocks unauthorized operations | Strict mode rejects destructive commands without `--yes`, enforces auth scopes |
| G8 | **Output schema in envelope**: JSON response includes output schema reference | `meta.output_schema` links to the command's return type schema |

### 3.2 Non-Goals

- **Runtime agent orchestration** — tooli helps agents *use* tools, not coordinate multi-agent workflows. Handoff metadata is declarative, not executable.
- **Agent marketplace / registry** — tooli generates documentation and schemas. Distribution is via PyPI, MCP, or manual sharing.
- **Framework-specific runtimes** — `--export langchain` generates integration code. It does not embed LangChain as a dependency.
- **LLM-powered generation** — all output is deterministic from metadata. No API calls to generate prose.
- **Breaking API changes** — `@app.command()` syntax remains backward-compatible. Python API is additive.

------

## 4. Feature Specifications

### 4.1 Python API Mode (P0)

The flagship feature. Every tooli command becomes importable as a typed Python function.

#### 4.1.1 `TooliResult` Return Type

```python
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")

@dataclass(frozen=True)
class TooliResult[T]:
    """Structured result from a tooli command invocation."""
    ok: bool
    result: T | None = None
    error: TooliError | None = None
    meta: dict[str, Any] | None = None

    def unwrap(self) -> T:
        """Return result or raise ToolError."""
        if not self.ok:
            raise self.error.to_exception()
        return self.result

@dataclass(frozen=True)
class TooliError:
    code: str
    category: str
    message: str
    suggestion: dict[str, str] | None = None
    is_retryable: bool = False
    field: str | None = None  # NEW: which input parameter caused the error
```

#### 4.1.2 Command as Python Function

Every `@app.command()` decorated function gets a companion callable on the app instance:

```python
app = Tooli(name="file-tools", version="5.0.0")

@app.command(annotations=ReadOnly | Idempotent)
def find_files(
    pattern: Annotated[str, Argument(help="Glob pattern")],
    root: Annotated[Path, Option(help="Root directory")] = Path("."),
) -> list[dict]:
    """Find files matching a pattern."""
    return [{"path": str(p)} for p in root.rglob(pattern)]
```

After registration, the command is callable two ways:

```python
# CLI (existing):
# $ file-tools find-files "*.py" --root ./src --json

# Python API (new):
result = app.call("find-files", pattern="*.py", root="./src")
# Returns TooliResult[list[dict]]
assert result.ok
assert result.result[0]["path"] == "src/main.py"
assert result.meta["tool"] == "file-tools.find-files"
assert result.meta["duration_ms"] > 0
```

#### 4.1.3 Direct Import Pattern

For convenience, commands are also accessible as module-level functions:

```python
from myapp import app

# Option A: app.call()
result = app.call("find-files", pattern="*.py")

# Option B: app.find_files() (generated accessor)
result = app.find_files(pattern="*.py")
```

The `app.find_files()` accessor is auto-generated from the command name (hyphen → underscore). It has the same signature as the original function but returns `TooliResult` instead of the raw return type.

#### 4.1.4 Execution Pipeline

The Python API uses the same pipeline as CLI invocation:

```
app.call("find-files", pattern="*.py")
    │
    ▼
TooliCommand.invoke_python(kwargs)
    │
    ├── Validate inputs (same as CLI)
    ├── Check security policy
    ├── Detect caller context (in-process → CallerCategory.PYTHON_API)
    ├── Start telemetry span
    │
    ▼
    Execute function
    │
    ├── Success → TooliResult(ok=True, result=..., meta=...)
    └── ToolError → TooliResult(ok=False, error=..., meta=...)
```

Key differences from CLI path:
- No Click/Typer parameter parsing — kwargs are passed directly
- No output mode routing — result stays as Python object
- No process exit — errors returned as `TooliResult`, not `sys.exit()`
- Caller detection sets `CallerCategory.PYTHON_API` (new category)
- Telemetry and recording still fire (for observability)
- Dry-run still works (`app.call("deploy", target="prod", dry_run=True)`)

#### 4.1.5 Async Support

```python
# Sync (default)
result = app.call("find-files", pattern="*.py")

# Async
result = await app.acall("find-files", pattern="*.py")
```

The async variant runs the command function in a thread pool if it's synchronous, or awaits it directly if it's an async function. This matches the OpenAI Agents SDK and Claude Agent SDK patterns.

#### 4.1.6 Agent SDK Integration Examples

**Claude Agent SDK:**
```python
from claude_code_sdk import query, Message
import myapp

async def run():
    # Option A: Use as MCP server (existing)
    # Option B: Call directly via Python API (new)
    result = myapp.app.call("find-files", pattern="*.py")
    if result.ok:
        # Feed result into conversation
        ...
```

**OpenAI Agents SDK:**
```python
from agents import Agent, function_tool
import myapp

@function_tool
def find_files(pattern: str, root: str = ".") -> str:
    """Find files matching a pattern."""
    result = myapp.app.call("find-files", pattern=pattern, root=root)
    return result.model_dump_json()

agent = Agent(tools=[find_files])
```

**LangChain:**
```python
from langchain_core.tools import tool
import myapp

@tool
def find_files(pattern: str, root: str = ".") -> dict:
    """Find files matching a pattern."""
    result = myapp.app.call("find-files", pattern=pattern, root=root)
    return result.unwrap()
```

### 4.2 AGENTS.md Generation (P0)

AGENTS.md is the documentation format read by GitHub Copilot and OpenAI Codex for project-level agent instructions. It serves the same purpose as CLAUDE.md for Claude Code and SKILL.md for skill-based systems.

#### 4.2.1 Format

```markdown
# AGENTS.md

## Project Overview

file-tools is a CLI tool for file manipulation built with [tooli](https://github.com/weisberg/tooli).

## Available Commands

### find-files

Find files matching a glob pattern in a directory tree.

**Usage:**
```bash
file-tools find-files <pattern> [--root <path>] [--max-depth <int>] --json
```

**Parameters:**
- `pattern` (required): Glob pattern to match (e.g., `"*.py"`)
- `--root` (default: `.`): Root directory to search from
- `--max-depth` (default: `10`): Maximum directory depth

**Output:** JSON envelope with `ok`, `result`, `meta` fields.

**Behavior:** read-only, idempotent

### rename-files

...

## Output Format

All commands support `--json` for structured output:
```json
{"ok": true, "result": [...], "meta": {"tool": "file-tools.find-files", ...}}
```

On error:
```json
{"ok": false, "error": {"code": "E3001", "message": "...", "suggestion": {...}}}
```

## Important Rules

- Always use `--json` flag when invoking programmatically
- Check the `ok` field before accessing `result`
- Use `--dry-run` before destructive commands
- Use `--yes` to skip confirmation prompts in automation
```

#### 4.2.2 Generation

```bash
# Generate AGENTS.md
mytool generate-skill --format agents-md > AGENTS.md

# Or via dedicated command
mytool generate-agents-md > AGENTS.md

# Include in --agent-bootstrap auto-detection
# If GITHUB_COPILOT or CODEX env vars detected, produce AGENTS.md format
```

#### 4.2.3 AGENTS.md vs SKILL.md vs CLAUDE.md

| Aspect | SKILL.md | CLAUDE.md | AGENTS.md |
|---|---|---|---|
| **Primary consumer** | Claude skill system | Claude Code (codebase) | Copilot / Codex |
| **Format** | YAML frontmatter + rich Markdown | Concise project guide | Flat Markdown |
| **Focus** | Task-oriented tool docs | Development workflow | Command reference |
| **Size target** | ~3-5K tokens | ~500-1K tokens | ~2-4K tokens |
| **Generated by** | `generate-skill` | `generate-skill --format claude-md` | `generate-skill --format agents-md` |

### 4.3 Framework Export System (P0)

A new `export` builtin command that generates framework-specific tool integration code.

#### 4.3.1 OpenAI Agents SDK Export

```bash
mytool export --target openai
```

Produces:
```python
"""Auto-generated OpenAI Agents SDK tool definitions for file-tools.
Generated by tooli v5.0 — https://github.com/weisberg/tooli
"""
import subprocess
import json
from agents import function_tool

@function_tool
def find_files(pattern: str, root: str = ".") -> str:
    """Find files matching a glob pattern in a directory tree.

    Args:
        pattern: Glob pattern to match (e.g., "*.py", "**/*.json")
        root: Root directory to search from (default: ".")
    """
    result = subprocess.run(
        ["file-tools", "find-files", pattern, "--root", root, "--json"],
        capture_output=True, text=True,
        env={**__import__("os").environ, "TOOLI_CALLER": "openai-agents-sdk"},
    )
    return result.stdout

# ... repeat for each command
```

#### 4.3.2 LangChain Export

```bash
mytool export --target langchain
```

Produces:
```python
"""Auto-generated LangChain tool definitions for file-tools.
Generated by tooli v5.0 — https://github.com/weisberg/tooli
"""
import subprocess
import json
import os
from langchain_core.tools import tool

@tool
def find_files(pattern: str, root: str = ".") -> dict:
    """Find files matching a glob pattern in a directory tree.

    Args:
        pattern: Glob pattern to match (e.g., "*.py", "**/*.json")
        root: Root directory to search from (default: ".")
    """
    result = subprocess.run(
        ["file-tools", "find-files", pattern, "--root", root, "--json"],
        capture_output=True, text=True,
        env={**os.environ, "TOOLI_CALLER": "langchain"},
    )
    data = json.loads(result.stdout)
    if not data["ok"]:
        raise ValueError(data["error"]["message"])
    return data["result"]

# ... repeat for each command
```

#### 4.3.3 Google ADK Export

```bash
mytool export --target adk
```

Produces an Agent Config YAML that references the tool via MCP:

```yaml
# Auto-generated Google ADK agent config for file-tools
# Generated by tooli v5.0

name: file-tools-agent
model: gemini-2.0-flash
instruction: |
  You are an agent that uses the file-tools CLI for file operations.
  Always pass --json for structured output.

tools:
  - mcp_tool:
      server_command: file-tools mcp serve --transport stdio
```

#### 4.3.4 Python API Export

```bash
mytool export --target python
```

Produces a typed Python wrapper using the v5 Python API:

```python
"""Auto-generated Python API wrapper for file-tools.
Generated by tooli v5.0 — https://github.com/weisberg/tooli

Usage:
    from file_tools_api import find_files
    result = find_files(pattern="*.py")
"""
from myapp import app

def find_files(pattern: str, root: str = ".") -> dict:
    """Find files matching a glob pattern in a directory tree."""
    return app.call("find-files", pattern=pattern, root=root).unwrap()

# ... repeat for each command
```

### 4.4 Handoff Metadata (P1)

Commands can declare what should logically follow them, enabling orchestrators to build multi-step workflows.

#### 4.4.1 New `@app.command()` Parameters

```python
@app.command(
    handoffs=[
        {"command": "process", "when": "After finding files to analyze"},
        {"command": "rename-files", "when": "To rename matched files"},
    ],
    capabilities=["fs:read"],
    delegation_hint="Use an agent with filesystem access",
)
def find_files(pattern: str) -> list[dict]:
    ...
```

#### 4.4.2 Manifest Integration

```json
{
  "commands": {
    "find-files": {
      "handoffs": [
        {"command": "process", "when": "After finding files to analyze"},
        {"command": "rename-files", "when": "To rename matched files"}
      ],
      "capabilities": ["fs:read"],
      "delegation_hint": "Use an agent with filesystem access"
    }
  }
}
```

#### 4.4.3 SKILL.md Integration

The "Composition Patterns" section already exists. Handoff metadata enriches it with explicit "next step" suggestions:

```markdown
#### After `find-files`

Consider running:
- `process` — to analyze the found files
- `rename-files` — to rename the matched files
```

### 4.5 Granular Capability Declarations (P1)

Move beyond binary `ReadOnly`/`Destructive` to a capability-based system that maps to agent permission models.

#### 4.5.1 Capability Taxonomy

| Capability | Description | Maps to |
|---|---|---|
| `fs:read` | Reads files from the filesystem | MCP `readOnlyHint`, Claude Code read permission |
| `fs:read:<path>` | Reads files from a specific path | Scoped filesystem access |
| `fs:write` | Writes/modifies files | MCP `destructiveHint`, Copilot write permission |
| `fs:write:<path>` | Writes to a specific path | Scoped filesystem write |
| `fs:delete` | Deletes files | Highest filesystem risk |
| `net:read` | Makes outbound HTTP requests | Network access permission |
| `net:write` | Sends data to external services | Network + data exfiltration risk |
| `proc:spawn` | Spawns subprocesses | Process execution permission |
| `env:read` | Reads environment variables | Environment access |
| `env:write` | Modifies environment | Environment mutation |
| `state:mutate` | Modifies persistent state (DB, config) | Side-effect declaration |
| `none` | Pure computation, no side effects | Fully safe |

#### 4.5.2 Usage

```python
@app.command(
    annotations=ReadOnly | Idempotent,
    capabilities=["fs:read", "net:read"],
)
def fetch_and_scan(
    url: str,
    local_dir: Path,
) -> list[dict]:
    """Fetch a remote manifest and scan local files."""
    ...
```

#### 4.5.3 Schema Integration

Capabilities appear in JSON Schema, MCP tool definitions, agent manifest, SKILL.md, and AGENTS.md:

```json
{
  "name": "fetch-and-scan",
  "annotations": {"readOnlyHint": true, "idempotentHint": true},
  "capabilities": ["fs:read", "net:read"]
}
```

### 4.6 Error Field Mapping (P1)

Structured errors gain a `field` attribute linking the error to the specific input parameter that caused it.

#### 4.6.1 Usage

```python
from tooli.errors import InputError

raise InputError(
    message="Invalid glob pattern: unmatched bracket",
    code="E1003",
    field="pattern",  # NEW: links error to the 'pattern' parameter
    suggestion=Suggestion(
        action="fix",
        fix="Close the bracket in the pattern",
        example='find-files "*.py" --root ./src',
    ),
)
```

#### 4.6.2 Envelope Output

```json
{
  "ok": false,
  "error": {
    "code": "E1003",
    "category": "input",
    "message": "Invalid glob pattern: unmatched bracket",
    "field": "pattern",
    "suggestion": {
      "action": "fix",
      "fix": "Close the bracket in the pattern",
      "example": "find-files '*.py' --root ./src"
    },
    "is_retryable": true
  }
}
```

Agents can use `error.field` to programmatically identify which parameter to modify in their retry logic, rather than parsing the error message.

### 4.7 Security Policy Enforcement (P1)

Promote `SecurityPolicy` from metadata to runtime enforcement.

#### 4.7.1 Policy Behaviors

| Behavior | OFF | STANDARD | STRICT |
|---|---|---|---|
| Destructive commands without `--yes` | Allowed | Prompt (TTY) or structured error (agent) | Blocked |
| Auth scope mismatch | Allowed | Warning in meta | Blocked with error |
| Output sanitization | Off | ANSI stripping | Full sanitization (secrets, paths) |
| Capability violations | Allowed | Warning | Blocked |
| Unsigned commands | Allowed | Allowed | Blocked (requires `auth_scopes`) |

#### 4.7.2 Enforcement Points

In `TooliCommand.invoke()`, after input validation:

```python
if policy == SecurityPolicy.STRICT:
    # Check auth scopes
    if cmd_meta.auth and not _check_scopes(cmd_meta.auth):
        raise AuthError("Missing required scope", code="E2001")

    # Check capabilities
    if cmd_meta.capabilities:
        _verify_capabilities(cmd_meta.capabilities)

    # Block destructive without --yes
    if Destructive in cmd_meta.annotations and not yes_flag:
        raise InputError(
            "Destructive command requires --yes in strict mode",
            code="E1010",
            suggestion=Suggestion(action="fix", fix="Add --yes flag"),
        )
```

### 4.8 Output Schema in Envelope (P2)

Include a reference to the output schema in the response envelope so agents know the shape of `result` without calling `--schema` separately.

#### 4.8.1 Envelope Extension

```json
{
  "ok": true,
  "result": [...],
  "meta": {
    "tool": "file-tools.find-files",
    "version": "5.0.0",
    "duration_ms": 34,
    "output_schema": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": {"type": "string"},
          "size": {"type": "integer"}
        }
      }
    }
  }
}
```

The `output_schema` field is included when:
- The command has a return type annotation (inferred via Pydantic)
- The `--response-format detailed` flag is used
- The first invocation from a new `TOOLI_SESSION_ID` (helps agents learn the schema)

It is omitted in `concise` mode (default) to save tokens.

------

## 5. Architecture Changes

### 5.1 New Modules

| Module | Purpose |
|---|---|
| `tooli/python_api.py` | `TooliResult`, `app.call()`, `app.acall()`, command accessor generation |
| `tooli/export.py` | `export` builtin command and framework-specific code generators |
| `tooli/docs/agents_md.py` | AGENTS.md generator |
| `tooli/capabilities.py` | Capability taxonomy, parsing, and validation |

### 5.2 Modified Modules

| Module | Changes |
|---|---|
| `tooli/app.py` | Register `export` builtin, generate `app.<command>()` accessors, `app.call()` / `app.acall()` methods |
| `tooli/app_native.py` | Same for native backend |
| `tooli/command.py` | `invoke_python()` path, security enforcement, error field support |
| `tooli/command_meta.py` | Add `handoffs`, `capabilities`, `delegation_hint` fields |
| `tooli/errors.py` | Add `field: str | None` to `ToolError` and all subclasses |
| `tooli/envelope.py` | Add optional `output_schema` to `EnvelopeMeta` |
| `tooli/manifest.py` | Add `handoffs`, `capabilities`, `delegation_hint` to command entries |
| `tooli/security/policy.py` | Runtime enforcement logic |
| `tooli/docs/skill_v4.py` | Render handoffs in Composition Patterns, capabilities in command docs |
| `tooli/docs/claude_md_v2.py` | Add Python API usage hints |
| `tooli/detect.py` | Add `CallerCategory.PYTHON_API` |
| `tooli/__init__.py` | Export `TooliResult`, `TooliError` |

### 5.3 New `CommandMeta` Fields

```python
@dataclass
class CommandMeta:
    # ... existing fields ...

    # v5.0 additions
    handoffs: list[dict[str, str]] | None = None         # [{"command": "...", "when": "..."}]
    capabilities: list[str] | None = None                 # ["fs:read", "net:read"]
    delegation_hint: str | None = None                    # "Use an agent with filesystem access"
```

### 5.4 New `CallerCategory` Value

```python
class CallerCategory(str, Enum):
    HUMAN = "human"
    AI_AGENT = "ai_agent"
    CI_CD = "ci_cd"
    CONTAINER = "container"
    UNKNOWN_AUTOMATION = "unknown_automation"
    PYTHON_API = "python_api"  # NEW: in-process Python call via app.call()
```

------

## 6. Implementation Phases

### Phase 1: Python API + AGENTS.md (P0) — Core unlock

**Goal**: `app.call()` works and AGENTS.md generates.

1. Implement `TooliResult` and `TooliError` in `tooli/python_api.py`.
2. Implement `app.call(command_name, **kwargs)` → `TooliResult`.
3. Implement `app.acall()` async variant.
4. Generate `app.<command_name>()` accessor methods on command registration.
5. Add `CallerCategory.PYTHON_API` to detection.
6. Wire Python API path through telemetry and recording.
7. Implement `tooli/docs/agents_md.py` — AGENTS.md generator.
8. Register `generate-agents-md` builtin command.
9. Add `--format agents-md` to `generate-skill`.
10. Tests: Python API invocation, error handling, dry-run, async, AGENTS.md generation.

**Exit criteria**: All 18 example apps callable via `app.call()` with correct `TooliResult`. AGENTS.md generation works for all apps.

### Phase 2: Framework Export (P0)

**Goal**: `mytool export --target {openai,langchain,adk,python}` produces working code.

1. Implement `tooli/export.py` with template-based code generation.
2. Register `export` builtin command with `--target` option.
3. Implement OpenAI Agents SDK export (subprocess-based wrapper).
4. Implement LangChain export (subprocess-based wrapper).
5. Implement Google ADK export (Agent Config YAML + MCP reference).
6. Implement Python API export (typed wrapper using `app.call()`).
7. Tests: generated code syntax validation, round-trip invocation tests.

**Exit criteria**: Generated code for all 3 frameworks compiles, runs, and produces correct results for the `docq` example app.

### Phase 3: Handoffs, Capabilities, Error Fields (P1)

**Goal**: Commands declare capabilities and relationships.

1. Implement capability taxonomy in `tooli/capabilities.py`.
2. Add `capabilities` parameter to `@app.command()`.
3. Add `handoffs` and `delegation_hint` parameters.
4. Add `field` to `ToolError` and all subclasses.
5. Render capabilities in SKILL.md, AGENTS.md, manifest, and schema.
6. Render handoffs in Composition Patterns section.
7. Include `error.field` in JSON envelope output.
8. Tests: capability validation, handoff rendering, error field mapping.

**Exit criteria**: Manifest includes capabilities and handoffs for annotated commands. Error field mapping works end-to-end.

### Phase 4: Security Enforcement + Output Schema (P1-P2)

**Goal**: Security policies are enforced, not just declared.

1. Implement runtime enforcement in `TooliCommand.invoke()`.
2. Auth scope checking for `SecurityPolicy.STRICT`.
3. Capability verification.
4. Destructive command gating in strict mode.
5. Output schema inclusion in envelope (`meta.output_schema`).
6. Schema inclusion logic (detailed mode, first session call, explicit flag).
7. Tests: enforcement behavior for each policy level.
8. Update documentation, migration guide, CHANGELOG.

**Exit criteria**: `SecurityPolicy.STRICT` blocks unauthorized operations. Output schema appears in detailed envelope.

------

## 7. Migration Guide (v4.1 → v5.0)

### Breaking Changes

**None.** All v4.1 code runs unchanged on v5.0.

### New Capabilities

1. **Use the Python API** (optional but recommended for agent SDK integration):

```python
# Before (v4.1): subprocess
result = subprocess.run(["mytool", "find-files", "*.py", "--json"], ...)

# After (v5.0): Python API
from myapp import app
result = app.call("find-files", pattern="*.py")
```

2. **Generate AGENTS.md** for Copilot/Codex compatibility:

```bash
mytool generate-skill --format agents-md > AGENTS.md
```

3. **Export framework integrations**:

```bash
mytool export --target openai > tools.py
mytool export --target langchain > langchain_tools.py
```

4. **Add handoff metadata** for multi-agent workflows:

```python
@app.command(
    handoffs=[{"command": "deploy", "when": "After successful build"}],
    capabilities=["fs:read", "proc:spawn"],
)
def build(target: str) -> dict:
    ...
```

5. **Use error field mapping** for precise recovery:

```python
raise InputError(
    message="Invalid date format",
    code="E1005",
    field="start_date",
    suggestion=Suggestion(fix="Use ISO 8601 format: YYYY-MM-DD"),
)
```

------

## 8. Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Python API invocation correctness | 100% | All 18 example apps callable via `app.call()` with correct results |
| Python API overhead vs CLI | <5ms | Benchmark `app.call()` vs `subprocess.run()` |
| AGENTS.md generation | 100% | All apps produce valid AGENTS.md |
| Export targets working | 3/3 | OpenAI, LangChain, ADK exports produce runnable code |
| Existing test suite pass rate | 100% | All 359 existing tests pass unchanged |
| New test count | ≥100 | Python API, AGENTS.md, export, capabilities, handoffs, error fields, security |
| Error field mapping coverage | ≥80% | Built-in `InputError` raises include `field` parameter |
| Framework adoption signal | Measurable | At least one external project uses `--export` in their CI |

------

## 9. Competitive Positioning

```
                   Human UX ←————————————→ Agent UX

 Typer/Click  ████████░░░░░░░░░░░░  (great human UX, zero agent UX)

 Raw JSON API ░░░░░░░░░░░████████  (zero human UX, decent agent UX)

 MCP Servers  ░░░░░░░░████████░░░  (no human UX, good agent UX)

 Tooli v4.1   ████████████████████  (both — CLI only)

 Tooli v5.0   ████████████████████  (both — CLI + Python API + every framework)
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                    The universal adapter
```

**v5.0 value proposition**: Write ONE Python function. Get a beautiful CLI for humans, a JSON API for agents, a Python API for agent SDKs, an MCP server for protocol-level integration, framework-specific tool definitions for OpenAI/LangChain/ADK, SKILL.md for Claude, AGENTS.md for Copilot/Codex, structured errors for self-correction, and handoff metadata for multi-agent orchestration.

No other framework does this. Tooli v5.0 is the Rosetta Stone of agent tool interfaces.

------

## 10. Open Questions

1. **Should `app.call()` respect `--dry-run` semantics?** The Python API equivalent would be `app.call("deploy", target="prod", dry_run=True)`. This is natural but requires the `dry_run` flag to be handled in the Python path, not just as a Click option.

2. **Should `--export` generate subprocess or Python API wrappers?** Subprocess wrappers work without installing the tool as a Python package. Python API wrappers are faster and more Pythonic but require the package to be installed. Answer: generate both, with a `--mode subprocess|import` flag.

3. **Should capabilities be validated at registration time?** If a command declares `capabilities=["fs:read"]` but the function body clearly writes to the filesystem, should tooli warn? Static analysis is imperfect but could catch obvious violations.

4. **Should AGENTS.md support custom sections?** Copilot's AGENTS.md spec is simple — project overview + available tools + rules. Custom sections (compliance notes, internal links) could be useful for enterprise teams but add complexity.

5. **How should the Python API handle streaming commands?** JSONL-producing commands return iterators in CLI mode. The Python API could return `Iterator[TooliResult]` for streaming commands, but this breaks the simple `app.call()` → `TooliResult` pattern. Option: `app.stream("command", **kwargs)` as a separate method.

6. **Should `export` include test scaffolding?** The generated LangChain tool wrapper could include a `test_find_files()` function that validates the wrapper works. This adds value but increases the generated code size.

7. **Should handoff metadata be bidirectional?** If `find-files` declares a handoff to `process`, should `process` automatically know that `find-files` is a common predecessor? Auto-inference of reverse handoffs could be useful but might produce noise.

------

*End of PRD v5.0*
