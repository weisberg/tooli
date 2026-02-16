# PRD: Tooli — The Agent-Native CLI Framework

**Version:** 2.0
**Date:** 2026-02-16
**Status:** Implemented (v2.0.x), with v2 roadmap planned.

## 1.x Milestone Progress

- **v2.0.0**: MCP bridge and deferred discovery (`tooli` launcher, `search_tools`, `run_tool`, `defer_loading`), token budgets (`max_tokens`), and optional python payload input mode (`allow_python_eval` + `--python-eval`).
- **v1.2.1**: Added scoped script execution via `orchestrate run` (JSON/Python payload plans and deterministic compact summaries).
- **v1.3.0**: planned for context/runtime safety upgrades and richer deterministic error contracts.
- **v1.4.0**: planned for pluginized execution contexts, resource/prompt surfaces, and formalized orchestration contracts.

---

## 1. Executive Summary

Tooli extends Python's Typer to produce CLI tools that are simultaneously human-friendly and machine-consumable by AI agents. Every decorated function becomes a CLI command, an MCP tool, and a self-documenting schema — from a single function definition.

The core insight: **no existing project auto-generates AI tool schemas from typed CLI command definitions.** FastMCP converts Python functions to MCP tools. Typer converts Python functions to CLI commands. Nothing bridges the two. Tooli fills this gap by extending Typer's decorator-to-CLI pipeline with schema generation, producing tools optimized for the emerging agent-driven workflow.

AI coding agents invoke thousands of CLI commands daily. Claude Code's bash tool, Codex CLI's sandboxed executor, and Cursor's terminal all rely on the same fragile pipeline: the agent generates a shell command string, executes it, and parses unstructured text output. This fails in predictable ways — interactive commands hang, unfamiliar CLIs cause hallucinated flags, unstructured output wastes tokens, and error messages lack actionability.

Tooli eliminates these failures by treating the CLI as a **structured protocol** rather than a text interface.

---

## 2. Problem Statement

### 2.1 The Translation Gap

Most CLIs are written for humans; agents are not humans. They are schema-driven and sensitive to:

- **Ambiguous naming** ("user" vs "user_id")
- **Verbose outputs** that explode context windows
- **Hidden side effects** (destructive actions without clear flags)
- **Interactive prompts** in non-interactive environments
- **Inconsistent output formatting** that breaks parsing

### 2.2 Specific Failure Modes

- **Interactive commands hang** — agents cannot navigate prompts, pagers, or password dialogs. Claude Code's system prompt explicitly prohibits `git rebase -i`, `vim`, and `less`.
- **Unfamiliar CLIs cause guessing** — agents trained on well-documented tools hallucinate flags for internal or niche tools.
- **Unstructured output wastes tokens** — benchmarks show structured output delivers 10-100x lower token usage because it allows selective queries.
- **Error messages lack actionability** — "Error: invalid input" provides no path to self-correction, while structured errors with suggestions enable automatic recovery.
- **Token waste from noise** — "Welcome to Tool X v1.0" headers and decorative ASCII consume tokens with zero semantic value.

### 2.3 Why CLI-First Matters Even in the MCP Era

MCP is becoming the standard protocol for agent tools, but CLIs still matter because:

- Local code execution + filesystem workflows remain the highest-leverage way for agents to do real work
- CLIs are composable with bash tools and pipelines
- CLIs are simple to deploy and audit
- When exposing tools via MCP stdio transport, stdout becomes a protocol channel — any logging to stdout corrupts JSON-RPC, forcing disciplined stdout/stderr separation

---

## 3. Product Vision

Tooli turns a Typer app into a **multi-interface tool**:

1. A **best-practice Unix CLI** for humans and scripts
2. A **machine-precise tool contract** for agents (schemas + stable structured output)
3. Optionally, an **MCP-compatible tool surface** generated from the same Python types and docstrings
4. Optionally, an **HTTP API surface** (OpenAPI-described) generated from the same contracts

**One source of truth** (Python types + docstrings) generates: human CLI UX, machine schemas, stable structured output, SKILL.md docs, and optional MCP server/tool export and HTTP/OpenAPI export.

---

## 4. Goals and Non-Goals

### Goals

1. **Single definition, multiple interfaces** — one decorated function produces CLI commands, JSON schemas, MCP tool definitions, and documentation
2. **Bash-first ergonomics** — pipelines work reliably, stdin/file symmetry is default, output contracts are stable and parseable
3. **Agent-first reliability** — fewer invalid-parameter failures, reduced redundant tool calls, controlled verbosity and context footprint
4. **Self-healing errors** — structured error objects with actionable suggestions that enable agent self-correction
5. **Context efficiency** — minimize token count required to understand and use the tool
6. **Contract testability** — output, schema, and stdin/file behaviors are verifiable via built-in snapshot/round-trip tests

### Non-Goals

- Not replacing FastMCP — borrowing its best ergonomics and making Typer a first-class tool authoring surface
- Not building a full agent framework — building the best possible **tool substrate**
- Not a CLI-only solution — MCP compatibility is a first-class feature, not an afterthought

---

## 5. Target Users

1. **Tool Developer (primary)** — writes Python functions, wants a CLI + agent contract "for free"
2. **Agent Runtime / Orchestrator (primary)** — executes commands non-interactively, needs stable structured output + schemas
3. **Platform / DevOps Engineer (secondary)** — cares about safety, auditing, predictable logs, and deployability

---

## 6. Architecture

### 6.1 Dual-Path Pipeline

Tooli's dual-path pipeline routes the same type annotations through two parallel paths. The CLI path produces human-friendly commands; the schema path produces JSON Schema definitions compatible with MCP's `inputSchema` and OpenAI's function-calling format. The underlying CLI framework (currently Typer/Click) is an implementation detail — the public API is Tooli-native.

```
┌─────────────────────────────────────────────────────────┐
│                    @app.command()                        │
│              Python function + type hints                │
└───────────┬──────────────────────┬──────────────────────┘
            │                      │
            ▼                      ▼
   ┌────────────────┐    ┌──────────────────┐
   │  CLI Pipeline   │    │  Schema Pipeline  │
   │  → CLI params   │    │  func_metadata()  │
   │  → CLI parser   │    │  → Pydantic model │
   │  → Completions  │    │  → JSON Schema    │
   └───────┬────────┘    └────────┬──────────┘
           │                      │
           ▼                      ▼
   ┌────────────────┐    ┌──────────────────┐
   │   CLI Output    │    │   Agent Output    │
   │  Human-readable │    │  MCP tool schema  │
   │  Rich formatting│    │  SKILL.md gen     │
   │  Shell complete  │    │  JSON/JSONL out   │
   └────────────────┘    └──────────────────┘
```

### 6.2 Three-Layer Design

```
┌─────────────────────────────────────────────────────────┐
│                    Interface Layer                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │   CLI    │  │   MCP    │  │  HTTP API (FastAPI)  │  │
│  │ (Typer)  │  │  Server  │  │                      │  │
│  └──────────┘  └──────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ▲
┌─────────────────────────────────────────────────────────┐
│                  Transform Pipeline Layer                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │Namespace │  │ Version  │  │Visibility│  │ Custom │ │
│  │Transform │  │ Filter   │  │ Filter   │  │Transform│ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
└─────────────────────────────────────────────────────────┘
                          ▲
┌─────────────────────────────────────────────────────────┐
│                    Provider Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │  Local   │  │   File   │  │ Database │  │  API   │ │
│  │ Provider │  │  System  │  │ Provider │  │Provider│ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
└─────────────────────────────────────────────────────────┘
```

- **Provider Layer:** Sources tools from decorated functions, filesystem modules, databases, or external APIs
- **Transform Pipeline Layer:** Middleware that modifies tools as they flow — namespacing, versioning, filtering, role-based views
- **Interface Layer:** CLI, MCP server, or HTTP API — all from the same tool definitions

### 6.3 Key Architectural Decisions

1. **Library-first API.** The public surface is Tooli-native — users import `Tooli`, not framework internals. Internally, Tooli subclasses Typer's `Typer`, `TyperCommand`, and `TyperGroup` via the `cls` parameter, ensuring ecosystem compatibility while keeping the implementation detail hidden.

2. **Pydantic as the schema backbone.** `inspect.signature()` -> dynamic Pydantic `BaseModel` -> `model_json_schema()` is the industry-standard path from type hints to JSON Schema (used by FastAPI, FastMCP, Instructor). Tooli adopts it directly, with `$ref` dereferencing for broad client compatibility.

3. **Canonical output mode with aliases.** Every command supports `--output auto|json|jsonl|text|plain`; `--json`, `--jsonl`, `--text`, and `--plain` are convenience aliases that map to `--output`.

4. **Strict machine-output contract.** In `--output json`, Tooli always emits a single envelope on stdout for both success and failure (`ok: true|false`) and uses stderr only for optional diagnostics.

5. **Functions remain directly callable.** Decorated functions stay unmodified — callable as Python, via CLI, through MCP, or with `CliRunner` for testing.

---

## 7. Core API Design

### 7.1 The `Tooli` Class

```python
from tooli import Tooli, Annotated, Option, Argument
from tooli.annotations import ReadOnly, Idempotent, Destructive
from pathlib import Path
from enum import Enum

app = Tooli(
    name="file-tools",
    description="File manipulation utilities for development workflows",
    version="2.0.0",
    default_output="auto",         # auto|json|text|jsonl
    mcp_transport="stdio",         # stdio|http|sse
    skill_auto_generate=True,      # Generate SKILL.md on install
    permissions={"fs": "read"},    # Permission scopes for agents
)
```

### 7.2 Command Decorator with Agent Metadata

```python
@app.command(
    annotations=ReadOnly | Idempotent,  # Behavioral hints for agents
    cost_hint="low",                    # "low"|"medium"|"high"
    human_in_the_loop=False,            # Force human confirmation in agent mode
    auth=["scopes:read"],               # Required authorization scopes
    examples=[
        {"args": ["--pattern", "*.py", "--root", "/project"],
         "description": "Find all Python files in a project"},
    ],
    error_codes={"E3001": "No files matched the pattern"},
    timeout=60.0,
)
def find_files(
    pattern: Annotated[str, Argument(help="Glob pattern to match files")],
    root: Annotated[Path, Option(
        help="Root directory to search from",
        exists=True, file_okay=False, resolve_path=True,
    )] = Path("."),
    max_depth: Annotated[int, Option(
        help="Maximum directory depth to traverse",
        min=1, max=100,
    )] = 10,
    include_hidden: Annotated[bool, Option(
        help="Include hidden files and directories"
    )] = False,
) -> list[dict]:
    """Find files matching a glob pattern in a directory tree.

    Recursively searches from the root directory using the specified
    glob pattern. Respects .gitignore rules by default.
    """
    ...
```

### 7.3 Tool Metadata Model

Aligned with MCP tool annotations:

| Field | Type | Description |
|---|---|---|
| `read_only` | `bool` | Tool only reads data, no side effects |
| `destructive` | `bool` | Tool may delete or overwrite data |
| `idempotent` | `bool` | Safe to call multiple times with same result |
| `open_world` | `bool` | Makes network calls or has non-determinism |
| `output_schema` | `JSONSchema` | Schema for return value (inferred from type hints) |
| `examples` | `list` | Usage examples for documentation and agent learning |
| `cost_hint` | `str` | Runtime cost/latency hint: "low", "medium", "high" |

### 7.4 Return Value Routing

Standard CLI frameworks print to stdout and return `None`. Tooli commands return typed values. The framework intercepts the return value and routes it:

- **Human mode** (TTY, no `--output` flag): Render with Rich tables, formatted text, colors
- **JSON mode** (`--output json` or piped): Serialize return value as JSON to stdout
- **JSONL mode** (`--output jsonl`): One JSON object per line for streaming
- **MCP mode** (invoked via MCP): Return as `structuredContent` in MCP response

---

## 8. Standard Flags and Behaviors (Agent-First CLI Contract)

### 8.1 Global Flags (Injected Automatically)

Every command receives these flags without the developer declaring them:

```
--output, -o       Output format: auto|json|jsonl|text|plain [default: auto]
--json             Alias for --output json
--jsonl            Alias for --output jsonl
--text             Alias for --output text
--plain            Alias for --output plain
--quiet, -q        Suppress non-essential output
--verbose, -v      Increase verbosity (stackable: -vvv)
--dry-run          Show planned actions without executing
--no-color         Disable colored output (also respects NO_COLOR env)
--timeout          Maximum execution time in seconds
--idempotency-key  Unique key for safe retries
--help-agent       Emit token-optimized, minified schema help
--schema           Output JSON Schema for this command and exit
--response-format  Concise or detailed output [default: concise]
```

If multiple output flags are provided, the last one wins.

### 8.2 stdout/stderr Rules

- Primary output: stdout
- Logs, warnings, progress, diagnostics: stderr
- In MCP stdio mode: **never** write logs to stdout (protocol corruption risk)
- In `--output json`, failure payloads are emitted to stdout using the standard envelope; stderr is reserved for optional diagnostics and MUST NOT contain a second JSON payload
- **Interactive Prompts:** If `stdin` is a data pipe, prompts MUST be read from `/dev/tty` (Unix) or `CON` (Windows) to avoid stealing from the data stream.

### 8.3 stdin/File Parity

- Any "input file" parameter accepts a path or `-` meaning stdin
- Symmetrically, output destinations accept `-` meaning stdout
- **Safe List Processing:** Support `--print0` for `\0`-delimited output and `--null` for `\0`-delimited input (equivalent to `xargs -0`).
- Auto-detect piped stdin and treat it as input when appropriate
- Never prompt unless stdin is a TTY; provide `--yes` / `--no-input` for automation

### 8.4 Exit Code Taxonomy

| Exit Code | Meaning | Agent Action |
|---|---|---|
| **0** | Success | Process result |
| **2** | Invalid usage / validation error | Fix arguments and retry |
| **10** | Not found | Check resource path |
| **20** | Conflict | Resolve conflict |
| **30** | Permission denied | Request escalation |
| **40** | External dependency failure | Check dependency |
| **50** | Timeout | Retry with backoff |
| **65** | Data format error | Fix input data |
| **70** | Internal error | Report bug |
| **75** | Temporary failure (retryable) | Retry immediately |
| **101** | Human handoff required | Pause agent; request human help |

### 8.5 Configuration Precedence

Tooli follows a strict precedence order to ensure predictable behavior:
1.  **Command-line flags** (highest)
2.  **Environment variables** (`TOOLI_*`)
3.  **`.env` file** (project root)
4.  **Project-local config** (`.tooli.yaml` or `pyproject.toml`)
5.  **User-global config** (`~/.config/tooli/config.yaml`)
6.  **System config** (`/etc/tooli/config.yaml`)
7.  **Default values** (lowest)

### 8.6 Output Envelope (for `--json` mode)

```json
{
  "ok": true,
  "result": { ... },
  "meta": {
    "tool": "namespace.command",
    "version": "1.4.0",
    "duration_ms": 123,
    "warnings": []
  }
}
```

Failure shape in `--output json`:

```json
{
  "ok": false,
  "error": {
    "code": "E3001",
    "category": "state",
    "message": "No files matched pattern '*.rs'",
    "is_retryable": true
  },
  "meta": {
    "tool": "namespace.command",
    "version": "1.4.0"
  }
}
```

### 8.7 Pagination and Filtering

Standard flags for controlling output volume:

- `--limit`, `--cursor` — pagination
- `--filter`, `--fields/--select` — field selection
- `--max-bytes`, `--max-items` — truncation with guidance on getting more targeted data

---

## 9. Schema Generation Pipeline

The schema pipeline converts a command function into multiple output formats from a single source of truth:

### 9.1 Type Mapping

| Python Type | CLI Representation | JSON Schema | MCP Schema |
|---|---|---|---|
| `str` | `TEXT` | `{"type": "string"}` | `{"type": "string"}` |
| `int` | `INTEGER` | `{"type": "integer"}` | `{"type": "integer"}` |
| `float` | `FLOAT` | `{"type": "number"}` | `{"type": "number"}` |
| `bool` | `--flag/--no-flag` | `{"type": "boolean"}` | `{"type": "boolean"}` |
| `Path` | `PATH` (validated) | `{"type": "string", "format": "path"}` | `{"type": "string"}` |
| `Enum` | `[choice1\|choice2]` | `{"enum": [...]}` | `{"enum": [...]}` |
| `list[str]` | Multiple values | `{"type": "array", "items": {"type": "string"}}` | Same |
| `Optional[T]` | Optional parameter | `{"anyOf": [T, {"type": "null"}]}` | Same |
| `Literal["a","b"]` | `[a\|b]` | `{"enum": ["a","b"]}` | `{"enum": ["a","b"]}` |
| Pydantic `BaseModel` | JSON string argument | Full nested object schema | Same |

### 9.2 Schema Export

```bash
mytool find-files --schema json    # Full JSON Schema for this command
mytool --schema json               # Schemas for all commands
```

`--schema` output includes command args/options, supported environment variables, resolved config keys, and output schema (when inferred or declared).

The `$ref` dereferencing step is essential — VS Code Copilot and Claude Desktop fail to process JSON Schemas containing `$ref` entries. The pipeline inlines all references, producing self-contained schemas.

---

## 10. Structured Error Handling

### 10.1 Error Hierarchy

```python
class ToolError(Exception):
    """Base error that agents can reason about."""
    code: str                      # Stable identifier: "E1001"
    category: ErrorCategory        # input|auth|state|runtime|internal
    message: str                   # Human-readable explanation
    suggestion: Suggestion | None  # Actionable fix
    is_retryable: bool             # Can the agent retry?
    details: dict | None           # Additional context

class InputError(ToolError):
    """E1xxx: Input validation failures."""
    category = ErrorCategory.INPUT

class StateError(ToolError):
    """E3xxx: Precondition or state failures."""
    category = ErrorCategory.STATE
```

### 10.2 Suggestion Model

```python
class Suggestion:
    action: str        # "retry_with_modified_input" | "use_different_tool" | "abort"
    fix: str           # What to do differently
    example: str | None  # Concrete corrected example
    applicability: str   # "machine_applicable" | "maybe_incorrect" | "has_placeholders"
```

### 10.3 Structured Error Output

In `--output json`, errors are emitted on stdout using the same envelope contract as success responses (`ok: false`), with optional human diagnostics to stderr.

In text modes (`auto|text|plain`), errors are emitted to stderr with the mapped exit code.

```json
{
  "ok": false,
  "error": {
    "code": "E3001",
    "category": "state",
    "message": "No files matched pattern '*.rs' in /project/src",
    "suggestion": {
      "action": "retry_with_modified_input",
      "fix": "The directory contains .py files. Try pattern '*.py' instead.",
      "example": "find-files '*.py' --root /project/src",
      "applicability": "maybe_incorrect"
    },
    "is_retryable": true,
    "details": {
      "pattern": "*.rs",
      "root": "/project/src",
      "available_extensions": [".py", ".txt", ".md"]
    }
  }
}
```

The suggestion field gives agents concrete recovery steps instead of forcing guesswork.

---

## 11. MCP Server Auto-Generation

### 11.1 Usage

```python
app = Tooli(name="file-tools")

# ... define commands as normal ...

if __name__ == "__main__":
    app()  # Normal CLI mode

# MCP server mode:
# $ file-tools mcp serve --transport stdio
# $ file-tools mcp serve --transport http --port 8080
```

### 11.2 Mapping Strategy

| Tooli Concept | MCP Concept |
|---|---|
| CLI command (with side effects) | MCP Tool |
| Read-only command (`@app.resource()`) | MCP Resource |
| Prompt template | MCP Prompt |
| Type hints + docstrings | `inputSchema` / `outputSchema` |
| Behavioral annotations | Tool annotations (`readOnlyHint`, `destructiveHint`) |

### 11.3 Schema Export

```bash
file-tools mcp export          # Output MCP tool definitions as JSON
file-tools mcp serve --transport stdio   # Run as MCP server
```

### 11.4 HTTP/OpenAPI Export

```bash
file-tools api export-openapi    # Emit OpenAPI schema from tool contracts
file-tools api serve --port 8000 # Serve HTTP API with the same schemas/contracts
```

HTTP responses must preserve the same envelope/error semantics defined for `--output json`.

---

## 12. Automatic Documentation Generation

### 12.1 SKILL.md Generation

```bash
file-tools generate-skill      # Generate SKILL.md from introspection
```

The generator performs runtime introspection:

1. Walks registered commands to identify all available actions
2. Extracts docstrings (Google, NumPy, Sphinx formats) for descriptions
3. Analyzes type hints for parameter schemas
4. Includes behavioral annotations (idempotent, destructive, read-only)
5. **Governance Metadata:** Includes `cost_hint`, `human_in_the_loop`, and `permissions` requirements.
6. Compiles examples, exit codes, and governance metadata

The generated SKILL.md is always 100% in sync with the code, eliminating "hallucinated parameter" errors.

### 12.2 LLM-Friendly Docs (llms.txt)

```bash
file-tools docs llms           # Emit llms.txt + llms-full.txt
```

Following the [llms.txt](https://llmstxt.org/) specification — a standardized markdown structure (curated `llms.txt` for navigation + `llms-full.txt` for details) that helps LLMs navigate documentation quickly. Tooli automatically generates these from the same introspection engine used for `SKILL.md`.

### 12.3 Unix Man Pages

```bash
file-tools docs man             # Emit man page content from command metadata
```

Man pages are generated from the same command metadata and must stay contract-consistent with `--help`, `--schema`, and generated SKILL docs.

---

## 13. Input Unification (SmartInput)

### 13.1 The Problem

Agents struggle with the distinction between local files and streamed data. They hallucinate complex scripts to read files when a pipe would suffice.

### 13.2 SmartInput Resolution

| Input State | Condition | Resolved Action |
|---|---|---|
| Explicit argument | Matches a local file path | Open file in read mode |
| Explicit argument | Matches a URL pattern | Stream content via HTTP |
| Explicit argument | Is `-` (dash) | Read from stdin |
| No argument | stdin is piped (not a TTY) | Read from stdin |
| No argument | stdin is a TTY | Error: "Missing Input" |

### 13.3 API

```python
from tooli import StdinOr

@app.command()
def process(
    input_data: Annotated[StdinOr[Path], Argument(help="Input file, URL, or stdin")],
) -> dict:
    """Process data from any input source."""
    ...
```

---

## 14. Security and Safety

1. **Prompt injection resistance** — output sanitization middleware scans for control characters, ANSI escape codes, and known injection patterns before they reach the agent's context window. Structured output is treated as data; natural language is clearly labeled and suppressible in `--json` mode. This prevents "Display-based Prompt Injection" where malicious content in a file could trick an agent into executing commands.

2. **Secrets handling** — provide `--secret-file` patterns and stdin support for sensitive values; avoid encouraging env-var secrets (leakage risk).

3. **Destructive operations** — require explicit flags (`--force`, `--yes`) and annotate destructiveness via tool metadata, aligning with MCP behavioral hints.

4. **Confirmation hooks** — for high-risk commands, force confirmation. In agent mode with "human-in-the-loop" policy active, override `--yes` to require human intervention.
5. **Threat model + policy modes** — define baseline protection levels (`off|standard|strict`) for sanitization and destructive-action guardrails.
6. **Security audit events** — emit structured audit logs for destructive actions, confirmation overrides, and policy denials.

---

## 15. Dependency and Non-Functional Requirements

Minimal footprint for fast startup (agents may call tools thousands of times):

- **typer** — core CLI framework (command routing, argument parsing)
- **pydantic** — schema generation and validation
- **rich** — human-facing UI (lazy-imported only when TTY detected)
- **fastmcp** (optional) — dynamically imported for `mcp serve` command

### 15.1 Performance and Reliability Targets

- Cold startup (no command execution) p95: <= 120ms on a baseline developer laptop
- Command dispatch overhead (framework-only) p95: <= 20ms
- Schema generation for a 50-command app: <= 1.0s
- RSS memory at idle (CLI process): <= 80MB
- Structured output key ordering is deterministic across runs for the same inputs

### 15.2 Operational Constraints

- Telemetry is opt-in only and disabled by default
- Tooli must function in non-interactive environments (CI/agent runners) without hanging
- All machine contracts (schema, output envelope, exit code mapping) are versioned and backward-compatible within a major version

---

## 16. Implementation Roadmap

### Phase 1: Core Foundation (MVP)

1. `Tooli` core class
2. Canonical output mode + aliases (`--output`, `--json`, `--jsonl`, `--text`, `--plain`)
3. Dual-channel output routing (TTY detection, JSON/JSONL/human modes)
4. Output envelope for structured responses (success + failure)
5. stdin/file symmetry with `StdinOr` type
6. Structured error handling with `ToolError` hierarchy
7. Exit code taxonomy
8. Basic SKILL.md generation
9. Built-in contract tests: schema snapshot, `--help --plain`, JSON envelope snapshot, stdin/file round-trip

### Phase 2: Agent Differentiation

1. MCP export + MCP serve mode (stdio and HTTP transports)
2. Schema generation pipeline with `$ref` dereferencing
3. Response verbosity control (`--response-format concise|detailed`)
4. Pagination / filtering / truncation primitives
5. llms.txt-style documentation output
6. Transform pipeline (namespacing, filtering, views, `FileSystemProvider` with hot-reloading)
7. Tool behavioral annotations (read-only, destructive, idempotent, `cost_hint`)
8. OpenAPI export and HTTP serve mode with contract parity

### Phase 3: Advanced Features

1. Provider system (local, filesystem, API providers)
2. Tool versioning
3. Dry-run mode support
4. **Agent evaluation harness** — Built-in tooling to record command invocations, analyze invalid parameter rates, and play back sessions for debugging.
5. OpenTelemetry observability
6. Policy and sandbox hooks (path allow/deny, safe working directory enforcement)
7. Authorization framework (scope-based access)
8. Telemetry pipeline (explicitly opt-in, documented retention controls)

### Phase Gates (Definition of Done)

1. **Contract gate:** snapshot tests for schema, JSON envelope, and help output pass in CI
2. **Compatibility gate:** stdin/file parity tests pass across Linux/macOS/Windows runners
3. **Reliability gate:** startup/dispatch SLOs in section 15 are met on reference hardware
4. **Security gate:** policy mode tests and destructive-action confirmation tests pass

---

## 17. Success Metrics

### Developer Experience

- **Time to create an agent-ready tool** — target >75% reduction vs manual implementation
- **Boilerplate reduction** — target 50% fewer lines of glue code for schema/docs/MCP export
- **Adoption** — number of projects and published tools using Tooli

### Agent Performance

- **Tool discovery rate** — % of tools successfully discovered via generated documentation
- **Execution success rate** — % of successful tool executions by agents
- **Error recovery rate** — % of failures from which agents self-correct using structured errors
- **Parameter validity** — % of invocations passing validation; top invalid fields drive improvements

### Token Efficiency

- Median bytes returned per command in concise vs detailed mode
- Usage rate of `--select`, pagination, and truncation features

### Platform Reliability

- p95 cold startup and dispatch latency vs section 15 targets
- Contract test pass rate in CI

---

## 18. Open Questions

1. **Schema inference scope** — how to represent unions, recursive types, bytes, and streams in JSON Schema?
2. **Cross-platform prompt handling** — `/dev/tty` isn't universal; how to guarantee prompts don't steal stdin on Windows?
3. **MCP server strategy** — implement directly using MCP SDK, or interoperate with FastMCP patterns?
4. **HTTP deployment profile** — WSGI/ASGI adapter boundary, auth middleware model, and default rate-limiting behavior.

---

## 19. v2.0 Roadmap Extension: Agent-Environment Interface (AEI)

### 19.1 Why v2.0

v1 established the core contract: typed Python functions can serve CLI, schema, MCP, and HTTP surfaces with stable machine output.
v2.0 extends that baseline into an **Agent-Environment Interface** where the framework actively manages context safety, discovery scale, approval boundaries, and multi-tool orchestration semantics.

### 19.2 Product Direction

v2.0 prioritizes:

1. **MCP-native interoperability** — zero-config server bridge for existing Tooli apps, plus first-class tools/resources/prompts
2. **Context protection by default** — token-aware output controls and paging artifacts for large result sets
3. **Governance in-framework** — explicit human approval and danger-level policies for high-risk operations
4. **Self-correcting execution loops** — structured semantic errors optimized for LLM retry behavior
5. **Scale-safe discovery** — deferred tool loading and search-first discovery for large command inventories
6. **Plan-before-mutate semantics** — standardized dry-run/state snapshot contracts across CLI, MCP, and HTTP
7. **Agent code-pipe execution** — opt-in Python eval mode for piped code with restricted runtime policies

### 19.3 Proposed v2.0 Capability Set

1. **Zero-config MCP bridge:** `tooli serve <app.py> --transport ...` loads and serves a Tooli app without custom MCP glue.
2. **Resource and prompt APIs:** `@app.resource()` and `@app.prompt()` extend beyond executable commands.
3. **Token-aware command controls:** `@app.command(max_tokens=...)` with structured truncation summaries and follow-up paging.
4. **Native HITL controls:** `requires_approval` and `danger_level` metadata integrated with policy mode and audit logs.
5. **Semantic error payloads:** parser/validation/runtime failures normalize to correction-oriented machine contracts.
6. **Deferred discovery:** namespace-aware `search-tools` + schema-on-demand for low initial context usage.
7. **Programmatic orchestration:** local sandbox workflows that compose multiple tool calls and emit compact final artifacts.
8. **Dry-run snapshot contract:** stable side-effect plan schema and optional pre/post state digests.
9. **Python eval pipe mode:** opt-in execution of Python code piped via stdin for agent workflows, with restricted builtins/import policy, execution limits, and structured/audited outputs.

### 19.4 Release Staging Toward v2.0

1. **v1.1 Stabilization:** hygiene, release consistency, CI quality gates for contract/perf/security baselines.
2. **v1.2 MCP Expansion:** zero-config serve path + tools/resources/prompts parity tests.
3. **v1.3 Context and Safety:** token protector runtime + HITL approval and auditing.
4. **v1.4 Discovery and Orchestration:** deferred discovery/search-first loading + scripted multi-tool runtime + eval-pipe preview behind explicit opt-in.
5. **v2.0 RC/GA:** finalize breaking contract changes (including eval mode contracts), ship migration layer, and enforce upgrade validation suite.

### 19.5 v2.0 Definition of Done

1. **Contract parity:** CLI/MCP/HTTP behavior matches for tool, resource, prompt, dry-run, and error contracts.
2. **Context efficiency:** large-output scenarios stay within configured token budgets with deterministic truncation metadata.
3. **Governance:** approval and policy tests pass across interactive and non-interactive execution environments.
4. **Migration readiness:** v1 reference apps upgrade via documented migration path with compatibility test coverage.
5. **Eval safety:** Python eval mode is disabled by default and passes restricted-runtime and sandbox-escape security tests.

---

## 20. References

- [Typer](https://typer.tiangolo.com/) — CLI framework foundation
- [FastMCP](https://gofastmcp.com/) — MCP server ergonomics and schema patterns
- [Model Context Protocol Spec](https://modelcontextprotocol.io/specification/2025-06-18/schema) — Tool schemas and annotations
- [CLI Guidelines](https://clig.dev/) — Unix CLI best practices
- [Anthropic: Writing Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents) — Agent tool design guidance
- [llms.txt](https://llmstxt.org/) — LLM-friendly documentation standard
- [PALADIN (ICLR 2026)](https://arxiv.org/) — Agent error recovery research
