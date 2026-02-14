# PRD: Tooli Agent-First CLI Extension

## 1) Executive summary

Typer is already a great human-friendly CLI framework, built on Python type hints and powered by Click. ([typer.tiangolo.com](https://typer.tiangolo.com/))
This PRD proposes an **agent-first extension** to Typer that makes it dramatically easier to build CLI tools that:

- behave like **good Unix citizens** (pipes, `stdin`/files parity, exit codes, predictable stdout/stderr),
- are **self-describing** (machine-readable schemas, manifests, stable output contracts),
- are **token-efficient and agent-robust** (concise/detailed response formats, pagination, field selection, truncation with guidance),
- can be **exported as MCP tools** (and optionally served as an MCP server) using the same source-of-truth types and docstrings, aligned with MCP’s schema concepts (input/output schemas + tool annotations). ([modelcontextprotocol.io](https://modelcontextprotocol.io/specification/2025-06-18/schema))
- automatically generate **SKILL.md** and **llms.txt-style docs** to optimize agent onboarding and tool discovery. ([llms-txt](https://llmstxt.org/))

The goal: **the ultimate CLI tool-building experience for AI agents and the humans who ship tools to them**.

------

## 2) Problem statement

### The uncomfortable truth

Most CLIs are written for humans; agents are… *not humans*. They are extremely literal, often schema-driven, and sensitive to:

- ambiguous naming (“user” vs “user_id”),
- verbose outputs that explode context windows,
- hidden side effects (destructive actions without clear flags),
- interactive prompts in non-interactive environments,
- inconsistent output formatting that breaks parsing.

Anthropic’s tool-writing guidance highlights recurring failure modes: agents call the wrong tools, misuse parameters, over-call tools redundantly, and get derailed by unclear specs and unhelpful errors; success improves with better namespacing, clearer parameter naming, response verbosity controls, and token-efficient outputs via pagination/truncation. ([Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents))

### Why “CLI-first” matters even in the MCP era

MCP is becoming the standard “port” for agent tools, but CLIs still matter because:

- local code execution + filesystem workflows remain the highest-leverage way for agents to do real work,
- CLIs are composable with bash tools,
- CLIs are dead-simple to deploy and audit.

Also: if you *do* expose tools via MCP using stdio transport, stdout becomes a protocol channel; any logging to stdout can corrupt JSON-RPC. This forces disciplined stdout/stderr separation. ([modelcontextprotocol.io](https://modelcontextprotocol.io/docs/develop/build-server))

------

## 3) Product vision

**Tooli** turns a Typer app into a *dual-interface tool*:

1. A **best-practice Unix CLI** for humans and scripts
2. A **machine-precise “tool contract”** for agents (schemas + stable structured output)
3. Optionally, an **MCP-compatible tool surface** generated from the exact same Python types/docstrings (FastMCP-style ergonomics). ([FastMCP](https://gofastmcp.com/v2/getting-started/welcome))

------

## 4) Research synthesis: what agents need from CLI tools

### 4.1 Unix composability requirements (bash compatibility)

From CLI Guidelines (clig.dev), key expectations include:

- Support `-` to read from stdin / write to stdout when a file is involved. ([CLI Guidelines](https://clig.dev/))
- Put primary output on **stdout**, and errors/logging on **stderr**. ([CLI Guidelines](https://clig.dev/))
- Provide machine-readable output when possible, e.g. `--json`, and a `--plain` mode when “pretty” output breaks pipelines. ([CLI Guidelines](https://clig.dev/))
- Only prompt if stdin is a TTY; otherwise error with instructions/flags. ([CLI Guidelines](https://clig.dev/))
- Disable color/animations when not in a TTY or when `NO_COLOR` / `--no-color` is set. ([CLI Guidelines](https://clig.dev/))
- Return meaningful exit codes (0 success, non-zero for failure modes). ([CLI Guidelines](https://clig.dev/))

Also: safe list processing needs null delimiters (`xargs -0` style) to handle filenames with spaces/newlines. ([Man7.org](https://man7.org/linux/man-pages/man1/xargs.1.html?utm_source=chatgpt.com))

### 4.2 Agent robustness requirements (tool design)

From Anthropic’s tool-writing guidance:

- Too many tools can hurt; tools should consolidate high-impact workflows and reduce agent confusion. ([Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents))
- Namespacing improves tool selection. ([Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents))
- Prefer meaningful identifiers; optionally provide both “concise” and “detailed” formats via a `response_format` enum. ([Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents))
- Make outputs token-efficient: pagination, filtering, truncation (with *helpful* guidance). ([Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents))
- Improve errors: actionable messages beat raw tracebacks. ([Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents))

### 4.3 MCP alignment requirements

MCP tool definitions are explicitly schema-based:

- Tools have `inputSchema` (and optionally `outputSchema`) as JSON Schema objects. ([modelcontextprotocol.io](https://modelcontextprotocol.io/specification/2025-06-18/schema))
- Tools may include behavioral hints (read-only, destructive, idempotent, etc.) via tool annotations. ([modelcontextprotocol.io](https://modelcontextprotocol.io/specification/2025-06-18/schema))
- Some specs support progress notifications out-of-band. ([modelcontextprotocol.io](https://modelcontextprotocol.io/specification/draft/schema))

### 4.4 “Docs for LLMs” requirements

FastMCP and llms.txt converge on a point: **LLM-friendly docs are a product feature**, not an afterthought.

- FastMCP ships LLM-friendly docs (e.g., `llms.txt` + `llms-full.txt`) and even exposes its docs via MCP. ([PyPI](https://pypi.org/project/fastmcp/))
- llms.txt proposes a standardized markdown structure to help LLMs navigate documentation quickly. ([llms-txt](https://llmstxt.org/))

------

## 5) Goals and non-goals

### Goals (what success looks like)

1. **One source of truth** (Python types/docstrings) generates:
   - human CLI UX,
   - machine schemas/manifests,
   - stable structured output,
   - SKILL.md + llms.txt-like docs,
   - optional MCP server/tool export.
2. **Bash-first ergonomics** without sacrificing agent precision:
   - pipelines work reliably,
   - `stdin`/file symmetry is default behavior,
   - output contracts are stable and parseable.
3. **Agent-first reliability**
   - fewer invalid-parameter failures,
   - reduced redundant tool calls,
   - controlled verbosity and context footprint.

### Non-goals (boundaries)

- Not replacing FastMCP; rather, borrowing its best “developer ergonomics + contract clarity” ideas and making Typer a first-class tool authoring surface.
- Not building a full agent framework; instead, building the best possible **tool substrate**.

------

## 6) Target users & personas

1. **Tool Developer (primary)**
   - writes Python functions and wants a CLI + agent contract “for free”
   - cares about packaging, testing, versioning, docs
2. **Agent Runtime / Orchestrator (primary)**
   - executes commands non-interactively
   - needs stable structured output + schemas
   - benefits from low-token, filtered outputs
3. **Ops / Platform Engineer (secondary)**
   - cares about safety, auditing, predictable logs, configuration precedence, and deployability

------

## 7) Proposed product surface

### 7.1 New core abstractions (Tooli layer)

**A) AgentApp / Tooli**

- `tooli.AgentApp(...)` extends `typer.Typer` and introduces:
  - global standard flags (formatting, logging, schema export, etc.)
  - output contract enforcement
  - command metadata (read-only/destructive/idempotent hints)

**B) Tool metadata**
A lightweight model aligned with MCP tool annotations:

- `read_only: bool`
- `destructive: bool`
- `idempotent: bool`
- `open_world: bool` (network calls, non-determinism)
- `output_schema: JSONSchema | inferred`
- `examples: list[str]`
- `cost_hint: "low|medium|high"` (runtime cost/latency)

MCP explicitly treats such annotations as hints and warns clients not to trust untrusted servers; we mirror that framing. ([modelcontextprotocol.io](https://modelcontextprotocol.io/specification/2025-06-18/schema))

**C) AgentIO**
First-class input/output channels:

- `InputSource`: `{path | "-" | bytes | text}`
- `OutputSink`: `{path | "-" }`
- auto-detect piped stdin vs interactive tty
- supports Click’s `-` file convention and safe open behaviors. ([Click](https://click.palletsprojects.com/en/stable/handling-files/))

**D) Providers + Transforms (FastMCP-inspired)**
Borrow the *conceptual* separation FastMCP uses:

- Providers: register tools from:
  - decorated Python functions (default)
  - filesystem (load tool modules)
  - OpenAPI specs (generate wrapper commands) (FastMCP lists OpenAPI generation/transforms as part of its advanced patterns) ([FastMCP](https://gofastmcp.com/v2/getting-started/welcome))
- Transforms:
  - namespacing (e.g. `git_*`, `fs_*`)
  - filtering commands for specific agent roles
  - versioned “views” of the same tool surface

This is directly motivated by agent tool-selection challenges and the usefulness of namespacing. ([Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents))

------

## 8) Standard flags and behaviors (the “Agent-First CLI Contract”)

Tooli should ship a **consistent CLI contract** across all tools.

### 8.1 Output format contract

Default:

- Human-friendly output when stdout is a TTY
- Machine-friendly output when `--json` or `--jsonl` is passed

Flags:

- `--json` : output a single JSON object
- `--jsonl` : output newline-delimited JSON events/results (stream-friendly)
- `--plain` : disable pretty formatting for pipeline tools like `grep/awk` ([CLI Guidelines](https://clig.dev/))
- `--no-color` + respect `NO_COLOR` and TTY detection ([CLI Guidelines](https://clig.dev/))

**Output envelope (recommended default for `--json`):**

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

**Rationale:** Terraform explicitly distinguishes human output vs machine-readable JSON formats for long-term compatibility. ([HashiCorp Developer](https://developer.hashicorp.com/terraform/internals/json-format?utm_source=chatgpt.com))

### 8.2 stdout/stderr rules

- Primary output: stdout ([CLI Guidelines](https://clig.dev/))
- Logs, warnings, progress, diagnostics: stderr ([CLI Guidelines](https://clig.dev/))
- In MCP stdio mode: *never* write logs to stdout (protocol corruption risk). ([modelcontextprotocol.io](https://modelcontextprotocol.io/docs/develop/build-server))

### 8.3 stdin/file parity

- Any “input file” parameter should accept:
  - a path
  - `-` meaning stdin ([CLI Guidelines](https://clig.dev/))
- Symmetrically, output destinations accept `-` meaning stdout.

### 8.4 Safe list delimiters (bash tooling)

- `--print0` to emit `\0`-delimited items (safe for filenames)
- `--null` / `--delim` to parse null-delimited stdin lists
- Align with `xargs -0` best practices for whitespace/newline-safe processing. ([Man7.org](https://man7.org/linux/man-pages/man1/xargs.1.html?utm_source=chatgpt.com))

### 8.5 Interactivity controls

- Never prompt unless stdin is a TTY. ([CLI Guidelines](https://clig.dev/))
- Provide `--yes` / `--no-input` for automation.
- If prompting is needed while stdin is used for data (`-`), read prompts from the terminal device (where available) instead of stdin. This is a known pain point in Click ecosystems. ([GitHub](https://github.com/pallets/click/issues/304))

### 8.6 Exit code taxonomy

Adopt a standard, documented set (example):

- `0` success
- `2` invalid usage / validation error (Click-like)
- `10` not found
- `20` conflict
- `30` permission denied
- `40` external dependency failure
- `50` timeout
- `70` internal error

CLI guidelines explicitly recommend mapping non-zero codes to meaningful failure modes. ([CLI Guidelines](https://clig.dev/))

------

## 9) Functional requirements (prioritized)

### P0: Must-have for “agent-grade”

1. **Schema export per command**
   - `mytool --schema json` outputs full JSON Schema for:
     - args/options
     - env vars
     - config keys
     - output schema (if known/inferred)
   - Must align conceptually with MCP `inputSchema`/`outputSchema`. ([modelcontextprotocol.io](https://modelcontextprotocol.io/specification/2025-06-18/schema))
2. **Machine output modes**
   - `--json`, `--jsonl`, `--plain`
   - Deterministic ordering and stable keys (versioned)
3. **stdin/file symmetry**
   - `-` supported anywhere an input/output file is accepted ([CLI Guidelines](https://clig.dev/))
   - Auto-detect piped stdin and treat it as input when appropriate
4. **Strict stdout/stderr separation**
   - Especially in MCP stdio mode: no stdout logging ([modelcontextprotocol.io](https://modelcontextprotocol.io/docs/develop/build-server))
5. **Agent-friendly errors**
   - On validation errors, emit structured error detail (optionally JSON on stderr) with *actionable guidance*, not raw stack traces. ([Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents))
6. **Response verbosity control**
   - A consistent `--response-format {concise|detailed}` pattern across commands (or per command), mirroring the proven benefit Anthropic notes. ([Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents))
7. **Pagination / filtering / truncation primitives**
   - Standard flags: `--limit`, `--cursor`, `--filter`, `--fields/--select`, `--max-bytes`, `--max-items`
   - Truncation must include instructions on getting more targeted data. ([Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents))
8. **Automatic SKILL.md generation**
   - Generate a concise “how to use this tool” doc optimized for agent consumption:
     - purpose
     - command list
     - schemas
     - examples
     - output formats
     - side-effect hints
     - exit codes

### P1: Strong differentiators

1. **MCP export + optional MCP server mode**
   - `mytool mcp export` produces MCP tool definitions from Typer commands (schemas + descriptions)
   - `mytool mcp serve --transport stdio|http` runs as MCP server
   - Must follow logging rules (stderr) for stdio transport. ([modelcontextprotocol.io](https://modelcontextprotocol.io/docs/develop/build-server))
2. **Docs generation in llms.txt style**
   - `mytool docs llms` emits:
     - `llms.txt` (curated navigation + key guidance)
     - `llms-full.txt` (expanded docs)
   - This mirrors the llms.txt proposal and FastMCP’s approach to LLM-friendly docs. ([llms-txt](https://llmstxt.org/))
3. **Tool surface “transforms”**
   - Namespacing, filtering, and “views” (human vs agent vs restricted mode)
   - Directly supports tool selection reliability. ([Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents))
4. **Null-delimited list processing**
   - `--print0` and `--null` input parsing ([Man7.org](https://man7.org/linux/man-pages/man1/xargs.1.html?utm_source=chatgpt.com))
5. **Config precedence + XDG + .env reading**
   - Apply precedence: flags > env > project config > user config > system config ([CLI Guidelines](https://clig.dev/))
   - Respect security guidance: avoid secrets in env vars; support `--secret-file` or stdin for sensitive data. ([CLI Guidelines](https://clig.dev/))

### P2: “Ultimate mode” features

1. **Agent evaluation harness**
   - Built-in tooling to:
     - record command invocations
     - analyze invalid parameter rates and redundancy
   - This mirrors Anthropic’s emphasis on evaluation-driven tool improvement. ([Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents))
2. **Observability**
   - OpenTelemetry spans, JSONL event streams, structured logs
3. **Policy + sandbox hooks**
   - safe working directory enforcement
   - path allow/deny lists
   - “destructive actions require explicit flags” guardrails
4. **OpenAPI ingestion + wrapper commands**
   - generate CLI subcommands from OpenAPI specs (provider)
   - consistent schema/output contract

------

## 10) Developer experience design (how building tools should feel)

### 10.1 “Zero-boilerplate agent contract” defaults

Tooli should infer:

- input schemas from type hints,
- output schemas from return types (dataclasses / pydantic models / TypedDict),
- descriptions from docstrings,
- examples from `Examples:` blocks in docstrings.

This mirrors FastMCP’s “wrap a function, schema/docs handled” philosophy and MCP’s schema-first nature. ([FastMCP](https://gofastmcp.com/))

### 10.2 Minimal code to opt in

Example (illustrative API shape, not a final design):

```python
import tooli as ta
from typing import Annotated

app = ta.AgentApp(name="repo")

@app.tool(
    read_only=True,
    output_schema="inferred",
    examples=[
        "repo search --query 'typer agent output schema' --limit 5 --json",
        "cat queries.txt | repo search --stdin --jsonl"
    ],
)
def search(
    query: str,
    limit: int = 10,
    response_format: Annotated[str, ta.ResponseFormat()] = "concise",
):
    """Search repositories.
    - Use response_format=concise for short results; detailed includes IDs for follow-up actions.
    """
    ...
```

### 10.3 Built-in contract tests

- Snapshot tests for:
  - `--schema`
  - `--help --plain`
  - `--json` output envelope stability
- “Round-trip” tests for stdin/file equivalence

------

## 11) Output schema and error model

### 11.1 Output schema

MCP explicitly supports optional `outputSchema` for structured output. Tooli should adopt the same philosophy: the tool output is not “whatever text got printed”, it’s a typed contract. ([modelcontextprotocol.io](https://modelcontextprotocol.io/specification/2025-06-18/schema))

### 11.2 Error schema

Structured error object (recommended):

```json
{
  "ok": false,
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "limit must be between 1 and 100",
    "hint": "Use --limit 25 or add --cursor for pagination."
  },
  "meta": { "tool": "repo.search" }
}
```

**Key requirement:** errors must be actionable—Anthropic explicitly calls out that helpful errors steer agents toward correct usage. ([Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents))

------

## 12) Security and safety requirements

1. **Secrets handling**

- Provide `--secret-file` patterns and stdin support for sensitive values; avoid encouraging env-var secrets (clig.dev warns about leakage risks). ([CLI Guidelines](https://clig.dev/))

1. **Destructive operations**

- Require explicit flags (`--force`, `--yes`) and annotate destructiveness (aligning with MCP hints). ([modelcontextprotocol.io](https://modelcontextprotocol.io/specification/2025-06-18/schema))

1. **Prompt injection resistance**

- Separate “data” vs “instructions” in tool outputs:
  - structured output is treated as data
  - any natural language explanation is clearly labeled (and optionally suppressed in `--json` mode)

------

## 13) Compatibility and constraints

- Must remain compatible with standard Typer usage patterns (Typer is built on Click). ([typer.tiangolo.com](https://typer.tiangolo.com/))
- Must preserve POSIX-ish conventions (stdin/stdout/stderr discipline, `-` file convention). ([Click](https://click.palletsprojects.com/en/stable/handling-files/))
- Must behave correctly in non-interactive environments (CI, agent runners).

------

## 14) Rollout plan (phased delivery)

### Phase 1 (P0 foundation)

- AgentApp wrapper
- Standard flags (`--json`, `--plain`, `--no-color`, `--schema`)
- stdin/file symmetry + safe prompts
- output envelope + structured errors
- SKILL.md generator

### Phase 2 (P1 differentiation)

- MCP export + MCP serve mode
- llms.txt-style doc output
- transforms (namespacing/filtering/views)
- null-delimited list support

### Phase 3 (P2 “ultimate”)

- evaluation harness + metrics
- OpenTelemetry + JSONL event stream
- OpenAPI ingestion provider
- policy/sandbox modules

------

## 15) Success metrics (what to measure)

1. **Agent success rate**

- task completion % using only CLI tools
- reduction in retries / redundant calls (Anthropic suggests watching redundant calls and invalid parameter errors). ([Anthropic](https://www.anthropic.com/engineering/writing-tools-for-agents))

1. **Parameter validity**

- % of invocations failing validation
- top invalid fields → doc/spec improvements

1. **Token efficiency proxy**

- median bytes returned per command in “concise” mode vs “detailed”
- usage rate of `--select`, pagination, truncation

1. **Developer throughput**

- time-to-first-tool
- number of lines of “glue code” needed for schema/docs/MCP export

------

## 16) Open questions (worth deciding early)

1. **Output envelope strictness**

- Always wrap `--json` output in `{ok,result,meta}`?
  vs allow raw JSON for Unix-y pipelines?

1. **Schema inference scope**

- Support only JSON-schema-friendly types by default?
  How to represent unions, recursive types, bytes, streams?

1. **Cross-platform prompt handling**

- `/dev/tty` isn’t universal; how to guarantee prompts don’t steal stdin on Windows (notorious issue class in Click land). ([GitHub](https://github.com/pallets/click/issues/304))

1. **MCP server strategy**

- Implement directly using MCP SDK, or provide a shim that interoperates cleanly with FastMCP patterns?

------

## 17) The “why this wins” summary

Tooli is aiming for a rare combo:

- **Unix-native** (pipes, TTY detection, stderr discipline, `-` semantics, null delimiters),
- **Schema-native** (JSON Schema-first, stable contracts),
- **Agent-native** (verbosity controls, token-efficient responses, evaluation-driven improvement),
- **MCP-native** (input/output schemas + tool annotations + stdio-safe logging), ([modelcontextprotocol.io](https://modelcontextprotocol.io/specification/2025-06-18/schema))
- **Docs-native** (SKILL.md + llms.txt-style outputs that teach agents how to use the tool). ([llms-txt](https://llmstxt.org/))

That’s the recipe for tools that agents don’t merely *can* use, but *reliably* use—without turning your CLI into a bespoke snowflake every time.

------
