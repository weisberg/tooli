# Tooli v3.0 — Product Requirements Document

## Agent-Native CLI Framework: From Tool to Skill in One Step

**Version**: 3.0
 **Author**: Brian Weisberg
 **Status**: Implemented. Superseded by [PRD_v4.md](PRD_v4.md). Current release: v6.5.0.
 **Date**: February 2026
 **Supersedes**: PRD.md (v2.0)

------

## 1. Executive Summary

Tooli v2.0 proved the concept: a single decorated Python function can produce a CLI, a JSON Schema, an MCP tool, and structured errors. But the agent adoption loop is still broken. An AI agent (Claude Code, Codex, Devin, etc.) that encounters a tooli-built CLI today still has to *read the source code*, *guess the output format*, and *manually author integration instructions*. Version 3.0 closes this gap by making every tooli CLI **self-describing to the point where an agent can read a single file and build a complete skill integration** — no source code reading required.

The north-star scenario:

1. A developer writes a CLI tool using `tooli` instead of Typer.
2. They run `mytool generate-skill` (or it auto-generates on install).
3. An AI agent like Claude Code reads the generated `SKILL.md` and **immediately knows**: every command, every parameter with types/defaults/constraints, every output schema, every error code with recovery actions, every workflow pattern, and every critical rule.
4. The agent can invoke the tool correctly on the first try, handle errors programmatically, chain commands together, and teach other agents how to use the tool.

This is the "write once, agent-readable everywhere" vision.

------

## 2. Problem Analysis

### 2.1 What v2.0 Gets Right

| Capability                                | Status       | Notes                                         |
| ----------------------------------------- | ------------ | --------------------------------------------- |
| Dual-mode output (Rich/JSON)              | ✅ Solid      | Auto-TTY detection works well                 |
| Structured errors with suggestions        | ✅ Solid      | `ToolError` hierarchy is well-designed        |
| JSON Schema from type hints               | ✅ Solid      | Pydantic-based, MCP-compatible                |
| MCP server mode                           | ✅ Solid      | stdio/http/sse via FastMCP                    |
| Global flags (`--json`, `--schema`, etc.) | ✅ Solid      | Comprehensive set                             |
| Behavioral annotations                    | ✅ Solid      | ReadOnly, Idempotent, Destructive, OpenWorld  |
| Orchestration (plan execution)            | ✅ Basic      | JSON/Python plan payloads                     |
| SKILL.md generation                       | ⚠️ Incomplete | See §2.2                                      |
| Output schemas                            | ❌ Missing    | Input schemas exist, output schemas don't     |
| Agent bootstrap protocol                  | ❌ Missing    | No single-command "teach an agent everything" |

### 2.2 Why the Current SKILL.md Generation Falls Short

The current `generate_skill_md()` in `tooli/docs/skill.py` produces output that is **structurally incomplete for agent consumption**. Specific gaps:

**Missing from current SKILL.md output:**

1. **No YAML frontmatter** — Claude's skill system expects `---\nname:\ndescription:\n---` frontmatter for skill discovery and routing. The current generator produces bare markdown.
2. **No parameter detail tables** — Commands list examples but don't show parameter types, defaults, constraints, or whether they're required. An agent seeing `find-files` doesn't know that `pattern` is a required `str` argument and `max_depth` is an optional `int` defaulting to `10`.
3. **No output schema documentation** — The generator documents inputs but says nothing about what the tool *returns*. An agent doesn't know the shape of `{"path": str, "size": int}[]`.
4. **No global flags documentation** — The `--json`, `--jsonl`, `--plain`, `--quiet`, `--dry-run`, `--schema`, `--timeout`, etc. flags are never mentioned. An agent must discover them by trial.
5. **No envelope format documentation** — The `{"ok": bool, "result": ..., "meta": {...}}` envelope is not described. An agent parsing output doesn't know to check `ok` or look for `meta.truncated`.
6. **No error catalog** — Individual commands can declare `error_codes` but the SKILL.md doesn't render them into a lookup table with recovery actions.
7. **No workflow/chaining examples** — No documentation of how commands compose. An agent can't learn "run `search` then pipe results to `process`."
8. **No installation/setup section** — No `pip install` command, no dependency list, no environment variable documentation.
9. **No critical rules / pitfalls section** — Every good SKILL.md (like the docx skill) has a "Critical Rules" section. The current generator has nothing equivalent.
10. **No token-budget awareness** — The generator dumps everything. For tools with 50+ commands, the SKILL.md could exceed an agent's context window. No summarization, tiering, or pagination.

### 2.3 The Agent Adoption Funnel (Current State)

```
Developer writes tooli CLI
        │
        ▼
    Agent encounters tool          ← No discoverability
        │
        ▼
    Agent reads --help             ← Designed for humans, wastes tokens
        │
        ▼
    Agent tries --schema           ← Gets input schema only
        │
        ▼
    Agent guesses output format    ← Trial and error
        │
        ▼
    Agent hits error               ← Gets structured error (good!)
        │
        ▼
    Agent retries with suggestion  ← Works (good!)
        │
        ▼
    Agent succeeds                 ← But took 3-5 attempts
```

### 2.4 The Target Adoption Funnel (v3.0)

```
Developer writes tooli CLI
        │
        ▼
    `mytool generate-skill`        ← One command
        │
        ▼
    Agent reads SKILL.md           ← Knows EVERYTHING
        │
        ▼
    Agent invokes correctly        ← First try
        │
        ▼
    Agent handles errors           ← Knows every error code
        │
        ▼
    Agent chains commands          ← Knows workflow patterns
```

------

## 3. Goals & Non-Goals

### 3.0 Design Philosophy

Tooli v3.0 has a guiding principle: **agents shouldn't need to read your source code**. Everything an agent needs to know must be extractable from the tool itself at runtime. This means:

- Schemas describe inputs AND outputs.
- Error catalogs are exhaustive and machine-parseable.
- Workflow patterns are documented alongside the commands they connect.
- The SKILL.md is a single, self-contained file that any agent can read and immediately begin using the tool with zero additional context.

### 3.1 Goals

| #    | Goal                                                         | Success Metric                                               |
| ---- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| G1   | SKILL.md generation produces agent-ready documentation that matches the quality of hand-written skills (like Claude's docx/pdf/xlsx skills) | An agent reading only the SKILL.md can invoke any command correctly on first attempt ≥90% of the time |
| G2   | Output schemas are first-class citizens alongside input schemas | Every `@app.command()` has a documented return type that appears in schema export and SKILL.md |
| G3   | A single `--agent-manifest` flag dumps everything an agent needs in one structured JSON payload | Manifest includes: all schemas, error catalog, workflow patterns, envelope format, global flags, install instructions |
| G4   | SKILL.md frontmatter is compatible with Claude's skill system format | Generated SKILL.md can be dropped into `/mnt/skills/user/` and work immediately |
| G5   | Token-budget-aware documentation generation                  | SKILL.md for tools with >20 commands auto-tiers into summary + detail sections |
| G6   | Remove Typer as a hard runtime dependency                    | Tooli's public API is self-contained; Typer becomes an optional integration backend |
| G7   | First-party agent testing harness                            | `mytool eval agent-test` validates that an agent can parse outputs and handle errors from all commands |

### 3.2 Non-Goals

- **GUI or web dashboard** — Tooli is CLI/agent-first. No admin panels.
- **Agent orchestration framework** — Tooli helps agents *use* tools; it doesn't orchestrate multi-agent workflows (that's the agent's job).
- **Backward-incompatible Python API changes** — `@app.command()` decorator syntax stays the same. New features are additive.
- **Built-in LLM calls** — Tooli doesn't call Claude/GPT/etc. It generates static documentation that agents consume.

------

## 4. User Personas

### 4.1 Tool Author (Primary)

A Python developer building CLI tools for internal or open-source use. They currently use Typer or Click. They want their tool to be usable by both humans and AI agents without maintaining two interfaces. They don't want to write documentation manually.

**Key pain**: "I wrote a great CLI, but Claude Code keeps hallucinating flags that don't exist."

### 4.2 AI Agent (Primary Consumer)

Claude Code, Codex, Devin, Cursor Agent, or any LLM-based agent that invokes CLI tools. The agent needs to: discover what tools are available, understand input/output contracts, handle errors, and chain commands.

**Key pain**: "I can see this tool exists but I don't know what it returns or what errors it can throw."

### 4.3 Platform Builder (Secondary)

Someone building an agent platform or skill repository who wants to automatically index and catalog CLI tools. They need machine-readable metadata.

**Key pain**: "Every tool documents itself differently. I need a standard format."

------

## 5. Feature Specifications

### 5.1 SKILL.md Generation (Complete Rewrite)

**Priority**: P0 — This is the core deliverable of v3.0.

The `generate_skill_md()` function must produce documentation that matches the quality and structure of Claude's built-in skills. The generated SKILL.md must include:

#### 5.1.1 YAML Frontmatter

```yaml
---
name: file-tools
description: "Use this skill whenever you need to find, process, or manipulate
  files on disk. Triggers include: file search, glob patterns, file statistics,
  bulk rename, content extraction. Use this skill when the user asks to find files,
  process directories, or perform batch file operations."
version: 1.0.0
---
```

**Generation logic**: The `name` and `description` come from `Tooli(name=..., description=...)`. The description field should be auto-expanded to include trigger phrases derived from command names, argument descriptions, and the tool's docstrings. The generator should produce a description that reads like the hand-written ones in Claude's built-in skills — mentioning specific trigger words and when NOT to use the skill.

**New decorator parameter**: Add an optional `triggers` parameter to `Tooli()`:

```python
app = Tooli(
    name="file-tools",
    description="File manipulation utilities",
    triggers=["find files", "glob pattern", "file search", "directory listing"],
    anti_triggers=["database queries", "API calls", "network requests"],
)
```

If `triggers` is not provided, the generator infers trigger phrases from command names and docstrings.

#### 5.1.2 Quick Reference Table

Every generated SKILL.md starts with a task→command mapping:

```markdown
## Quick Reference

| Task | Command |
|------|---------|
| Find files matching a pattern | `file-tools find-files "*.py" --root ./src` |
| Count lines in matched files | `file-tools count-lines --pattern "*.py"` |
| Get JSON output (any command) | Append `--json` to any command |
| Preview without executing | Append `--dry-run` to any command |
| Get schema for a command | `file-tools <command> --schema` |
```

**Generation logic**: One row per non-hidden command, using the first example if available, otherwise synthesizing from the command name and first required argument. The last rows always document the global flags.

#### 5.1.3 Command Detail Blocks

Each command gets a full specification block:

~~~markdown
### `find-files`

Find files matching a glob pattern in a directory tree.

**Behavior**: `read-only`, `idempotent`
**Cost Hint**: `low`

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | `string` | Yes | — | Glob pattern to match files |
| `root` | `string` (path) | No | `"."` | Root directory to search from |
| `max_depth` | `integer` | No | `10` | Maximum directory depth |

#### Output Schema

Returns `list[object]` with shape:
```json
[{"path": "string", "size": "integer"}]
~~~

#### Examples

```bash
# Find all Python files in a project
file-tools find-files "*.py" --root /project --json
```

#### Error Codes

| Code  | Condition                | Recovery                                        |
| ----- | ------------------------ | ----------------------------------------------- |
| E3001 | No files matched pattern | Try a broader pattern; check `root` path exists |
| E1003 | Invalid glob syntax      | Fix the pattern string                          |

```
**Generation logic**: Parameters come from `inspect.signature()` + Pydantic schema generation (already in v2). Output schema comes from the new return-type annotation system (§5.2). Error codes come from the `error_codes` parameter on `@app.command()`. Examples come from the `examples` parameter.

#### 5.1.4 Global Flags Section

```markdown
## Global Flags (Available on Every Command)

| Flag | Effect |
|------|--------|
| `--json` | Output as JSON envelope: `{"ok": bool, "result": ..., "meta": {...}}` |
| `--jsonl` | Output as newline-delimited JSON (streaming) |
| `--plain` | Unformatted text for grep/awk pipelines |
| `--quiet` | Suppress non-essential output |
| `--dry-run` | Preview actions without executing (if command supports it) |
| `--schema` | Print JSON Schema for this command and exit |
| `--timeout N` | Max execution time in seconds |
| `--yes` | Skip confirmation prompts (for automation) |
| `--response-format concise\|detailed` | Control output verbosity |
```

#### 5.1.5 Envelope Format Section

~~~markdown
## Output Envelope Format

All commands with `--json` return this structure:

```json
{
  "ok": true,
  "result": <command-specific data>,
  "meta": {
    "tool": "file-tools.find-files",
    "version": "1.0.0",
    "duration_ms": 34,
    "dry_run": false,
    "truncated": false,
    "next_cursor": null,
    "warnings": []
  }
}
~~~

On failure:

```json
{
  "ok": false,
  "error": {
    "code": "E3001",
    "category": "state",
    "message": "No files matched pattern '*.rs' in ./src",
    "suggestion": {
      "action": "retry_with_modified_input",
      "fix": "The directory contains .py files. Try pattern '*.py'.",
      "example": "find-files '*.py' --root ./src"
    },
    "is_retryable": true
  },
  "meta": { ... }
}
```

**Agent instructions**: Always check `ok` first. If `false`, read `error.suggestion.action` to decide next step. If `is_retryable` is `true`, retry with the suggested `example`.

```
#### 5.1.6 Error Catalog

A consolidated table of ALL error codes across all commands:

```markdown
## Error Catalog

| Code | Category | Commands | Meaning | Recovery Action |
|------|----------|----------|---------|-----------------|
| E1001 | input | (global) | Unknown flag or argument | Check `--schema` output |
| E1003 | input | find-files | Invalid glob pattern | Fix pattern syntax |
| E2001 | auth | upload | Missing API key | Set `FILE_TOOLS_API_KEY` env var |
| E3001 | state | find-files | No files matched | Try broader pattern |
| E4001 | runtime | upload | Remote server timeout | Retry with `--timeout 60` |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Invalid usage / validation error |
| 10 | Not found / state error |
| 30 | Permission denied |
| 50 | Timeout / temporary external delay |
| 70 | Internal or runtime error |
| 101 | Human handoff required |
```

#### 5.1.7 Workflow Patterns Section

~~~markdown
## Workflow Patterns

### Search Then Process
```bash
# Find files, then process them
results=$(file-tools find-files "*.csv" --root ./data --json)
# Parse the JSON result array and feed to next command
echo "$results" | jq -r '.result[].path' | xargs -I{} file-tools process {}
~~~

### Dry Run First

~~~bash
# Preview what would happen
file-tools rename-files --pattern "*.tmp" --suffix ".bak" --dry-run --json
# If the plan looks good, execute
file-tools rename-files --pattern "*.tmp" --suffix ".bak" --json
**Generation logic**: Workflows are derived from the new `workflows` parameter on `Tooli()` (see §5.3) or auto-generated from command annotations. Commands marked `ReadOnly` naturally pair as "discovery" steps before `Destructive` commands.

#### 5.1.8 Installation & Setup Section

```markdown
## Installation

```bash
pip install file-tools
~~~

### Environment Variables

| Variable             | Required             | Description                                           |
| -------------------- | -------------------- | ----------------------------------------------------- |
| `FILE_TOOLS_API_KEY` | For `upload` command | API key for remote uploads                            |
| `TOOLI_OUTPUT`       | No                   | Default output mode: `json`, `jsonl`, `text`, `plain` |

### Dependencies

- Python ≥ 3.10
- No external binary dependencies

```
#### 5.1.9 Critical Rules Section

```markdown
## Critical Rules

- **Always use `--json` when invoking from an agent** — Human-formatted Rich output is not parseable.
- **Always check `ok` before accessing `result`** — Failed commands set `ok: false` and `result: null`.
- **Paths are relative to CWD unless `--root` is specified** — Don't assume absolute paths.
- **`--dry-run` is advisory** — Some commands may not support it. Check `meta.dry_run` in the response.
- **Pagination**: If `meta.truncated` is `true`, use `meta.next_cursor` with `--cursor` on the next call.
```

**Generation logic**: Critical rules are composed from behavioral annotations, command flags, and the new `rules` parameter on `Tooli()`.

#### 5.1.10 Token-Budget Tiering

For tools with many commands, the SKILL.md should be structured in tiers:

- **Tier 1 (always included)**: Frontmatter, Quick Reference, Global Flags, Envelope Format, Exit Codes, Critical Rules, Installation.
- **Tier 2 (included if ≤ 20 commands)**: Full command detail blocks with parameter tables, output schemas, examples, error codes.
- **Tier 3 (summary only if > 20 commands)**: Command detail blocks are replaced with a one-line synopsis and a pointer: "Run `mytool <command> --schema` for full details."

Add a `--detail-level` flag to `generate-skill`:

```bash
mytool generate-skill --detail-level full    # Everything
mytool generate-skill --detail-level summary # Tier 1 + Tier 3
mytool generate-skill --detail-level auto    # Chooses based on command count
```

------

### 5.2 Output Schema Annotations

**Priority**: P0

Currently, tooli generates input schemas from function signatures but says nothing about return types. In v3.0, return types become first-class.

#### 5.2.1 Return Type Annotation

```python
from tooli import Tooli, Annotated, Argument
from pydantic import BaseModel

class FileResult(BaseModel):
    path: str
    size: int

@app.command()
def find_files(
    pattern: Annotated[str, Argument(help="Glob pattern")],
) -> list[FileResult]:
    """Find files matching a glob pattern."""
    ...
```

The return type `list[FileResult]` is introspected to generate:

```json
{
  "outputSchema": {
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
```

This appears in:

- `--schema` output (new `outputSchema` field alongside `inputSchema`)
- SKILL.md command detail blocks
- MCP tool registration
- Agent manifest

#### 5.2.2 Output Schema from Raw Types

For simple return types (`dict`, `list[dict]`, `str`, `int`, `bool`), tooli infers the schema. For `dict` returns without Pydantic models, the developer can use the new `output_example` parameter:

```python
@app.command(
    output_example={"path": "src/main.py", "size": 1204, "modified": "2025-01-01T00:00:00Z"},
)
def find_files(...) -> dict:
    ...
```

The `output_example` is used to:

1. Infer the output schema (types from values).
2. Render in SKILL.md as the example output.
3. Validate actual output shape in dev/test mode.

------

### 5.3 Workflow Declarations

**Priority**: P1

New parameter on `Tooli()` and `@app.command()` to declare how commands compose:

```python
app = Tooli(
    name="file-tools",
    workflows=[
        {
            "name": "search-then-process",
            "description": "Find files and then process them",
            "steps": [
                {"command": "find-files", "pipe_result_to": "process"},
            ],
        },
        {
            "name": "safe-rename",
            "description": "Preview renames before executing",
            "steps": [
                {"command": "rename-files", "flags": ["--dry-run"]},
                {"command": "rename-files", "note": "Execute after reviewing dry-run output"},
            ],
        },
    ],
)
```

Workflows are rendered into the SKILL.md's Workflow Patterns section and included in the agent manifest.

------

### 5.4 Agent Manifest (`--agent-manifest`)

**Priority**: P0

A new global flag that dumps everything an agent needs in one structured JSON payload:

```bash
mytool --agent-manifest
```

Outputs:

```json
{
  "manifest_version": "3.0",
  "tool": {
    "name": "file-tools",
    "version": "1.0.0",
    "description": "File manipulation utilities",
    "install": "pip install file-tools",
    "python_requires": ">=3.10",
    "triggers": ["find files", "glob pattern", "file search"],
    "anti_triggers": ["database queries", "API calls"]
  },
  "commands": [
    {
      "name": "find-files",
      "description": "Find files matching a glob pattern in a directory tree.",
      "annotations": {"readOnlyHint": true, "idempotentHint": true},
      "inputSchema": { ... },
      "outputSchema": { ... },
      "examples": [ ... ],
      "error_codes": { ... },
      "cost_hint": "low",
      "supports_dry_run": true
    }
  ],
  "global_flags": {
    "--json": "Output as JSON envelope",
    "--jsonl": "Newline-delimited JSON",
    "--plain": "Unformatted text",
    "--quiet": "Suppress non-essential output",
    "--dry-run": "Preview without executing",
    "--schema": "Print JSON Schema and exit",
    "--timeout": "Max execution time in seconds",
    "--yes": "Skip confirmation prompts"
  },
  "envelope_schema": {
    "success": {"ok": true, "result": "...", "meta": { ... }},
    "failure": {"ok": false, "error": { ... }, "meta": { ... }}
  },
  "error_catalog": [ ... ],
  "exit_codes": { ... },
  "workflows": [ ... ],
  "env_vars": { ... },
  "rules": [ ... ],
  "mcp": {
    "supported": true,
    "transports": ["stdio", "http", "sse"],
    "serve_command": "file-tools mcp serve --transport stdio"
  }
}
```

This is the machine-readable counterpart to SKILL.md. The SKILL.md is the *human/agent-readable prose version*; the manifest is the *structured data version*. Both are generated from the same source of truth.

------

### 5.5 Decouple from Typer

**Priority**: P1

In v2.0, `Tooli` extends `typer.Typer` and `TooliCommand` extends `TyperCommand`. This creates problems:

1. **Dependency weight** — Typer pulls in Click, Shellingham, and Annotated-Doc.
2. **API leakage** — Users must import `Argument` and `Option` from Typer's namespace.
3. **Upgrade risk** — Typer breaking changes directly break Tooli.
4. **Testing overhead** — `CliRunner` comes from Click, not Tooli.

**v3.0 approach**: Make the CLI backend pluggable.

```python
# Default: tooli's own lightweight CLI engine (new)
app = Tooli(name="file-tools", backend="native")

# Opt-in: Typer backend for existing users who need Typer compatibility
app = Tooli(name="file-tools", backend="typer")
```

The native backend:

- Parses arguments directly from `inspect.signature()` + type hints (same as schema generation).
- Uses `argparse` under the hood for the actual parsing (stdlib, no extra deps).
- Injects global flags automatically.
- Routes output through the existing `OutputMode` system.
- Supports shell completions via a simple completion script generator.

The Typer backend:

- Preserves 100% backward compatibility with v2.0 code.
- Remains available as `pip install tooli[typer]`.

**Migration path**: Existing `from tooli import Argument, Option` continues to work regardless of backend. Tooli provides its own `Argument` and `Option` classes that are API-compatible with Typer's but backend-agnostic.

------

### 5.6 `generate-skill` Subcommand Enhancements

**Priority**: P0

New flags on the existing `generate-skill` command:

```bash
# Generate with Claude-compatible frontmatter (default in v3.0)
mytool generate-skill --format claude-skill

# Generate as agent manifest (JSON)
mytool generate-skill --format manifest

# Auto-detect token budget
mytool generate-skill --detail-level auto

# Output to a specific file
mytool generate-skill --output ./skills/file-tools/SKILL.md

# Include inferred workflow patterns
mytool generate-skill --infer-workflows

# Validate the generated SKILL.md against the schema
mytool generate-skill --validate
```

#### 5.6.1 `--infer-workflows`

When this flag is set, the generator analyzes command annotations to auto-generate workflow patterns:

- **ReadOnly → Destructive** pairs become "preview then execute" workflows.
- Commands with overlapping parameter names (e.g., both take `--pattern`) become "search then process" workflows.
- Commands with `paginated=True` get a "paginate through results" workflow example.
- Commands with `StdinOr[T]` parameters get "pipe from previous command" examples.

#### 5.6.2 `--validate`

Validates the generated SKILL.md:

- Checks all referenced commands exist.
- Verifies parameter tables match actual schemas.
- Ensures all error codes are documented.
- Confirms examples are syntactically valid.
- Checks that the frontmatter is valid YAML.

------

### 5.7 CLAUDE.md Generation

**Priority**: P2

New built-in command:

```bash
mytool generate-claude-md
```

Generates a `CLAUDE.md` file optimized for Claude Code containing:

```markdown
# CLAUDE.md — file-tools

## Project overview
This is a CLI tool built with tooli (the agent-native CLI framework).
Always use `--json` flag when invoking commands.

## Key commands
- `file-tools find-files "*.py" --root ./src --json`
- `file-tools process data.csv --json`

## Testing
Run `file-tools eval agent-test` to validate tool behavior.

## Important patterns
- Check `ok` field in JSON output before processing results.
- Use `--dry-run` before destructive operations.
- Use `--schema` to inspect any command's parameter schema.

## Full skill documentation
See SKILL.md for complete command reference.
```

------

### 5.8 Agent Test Harness

**Priority**: P2

New evaluation command:

```bash
mytool eval agent-test [--commands find-files,process] [--output report.json]
```

This generates a synthetic test suite that validates:

1. **Schema accuracy**: Invoke each command with `--schema` and verify the output matches the manifest.
2. **Output conformance**: Invoke each command with test inputs and verify the output matches the declared output schema.
3. **Error handling**: Invoke each command with invalid inputs and verify structured errors are returned with correct codes.
4. **Envelope format**: Verify `ok`, `result`, `meta` fields are present and correctly typed.
5. **Global flags**: Verify `--json`, `--quiet`, `--dry-run` work on each command.

Output:

```json
{
  "tool": "file-tools",
  "version": "1.0.0",
  "tests_run": 24,
  "tests_passed": 23,
  "tests_failed": 1,
  "failures": [
    {
      "command": "process",
      "test": "output_schema_conformance",
      "expected": {"type": "object", "properties": {"lines": {"type": "integer"}}},
      "actual": {"lines": "42"},
      "error": "Field 'lines' expected integer, got string"
    }
  ]
}
```

------

### 5.9 `rules` and `env_vars` on Tooli()

**Priority**: P1

New configuration parameters:

```python
app = Tooli(
    name="file-tools",
    rules=[
        "Always use --json when invoking from an agent.",
        "Paths are relative to CWD unless --root is specified.",
        "The 'upload' command requires FILE_TOOLS_API_KEY.",
    ],
    env_vars={
        "FILE_TOOLS_API_KEY": {"required_for": ["upload"], "description": "API key for remote uploads"},
        "FILE_TOOLS_ROOT": {"required_for": None, "description": "Default root directory"},
    },
)
```

These are rendered into SKILL.md (Critical Rules and Environment Variables sections) and included in the agent manifest.

------

### 5.10 Enhanced `--help-agent` Flag

**Priority**: P1

The existing `--help-agent` flag (v2.0) provides token-optimized help. In v3.0, enhance it to output structured YAML instead of prose:

```bash
mytool find-files --help-agent
command: find-files
description: Find files matching a glob pattern in a directory tree.
behavior: [read-only, idempotent]
params:
  - name: pattern
    type: string
    required: true
    help: Glob pattern to match files
  - name: root
    type: string
    required: false
    default: "."
    help: Root directory to search from
  - name: max_depth
    type: integer
    required: false
    default: 10
    help: Maximum directory depth
output: list[{path: string, size: integer}]
errors: [E3001, E1003]
example: find-files "*.py" --root ./src --json
```

This is much more token-efficient than the standard `--help` output and directly parseable by agents.

------

## 6. Architecture Changes

### 6.1 New Module: `tooli/docs/skill_v3.py`

Complete rewrite of SKILL.md generation. The current `tooli/docs/skill.py` (118 lines) is replaced with a structured generator that produces each section from §5.1.

Key classes:

```python
class SkillGenerator:
    """Generates SKILL.md from a Tooli app instance."""

    def __init__(self, app: Tooli, detail_level: str = "auto"):
        ...

    def generate(self) -> str:
        """Generate complete SKILL.md content."""
        sections = [
            self._frontmatter(),
            self._quick_reference(),
            self._installation(),
            self._global_flags(),
            self._envelope_format(),
            self._commands(),          # Respects detail_level
            self._error_catalog(),
            self._workflows(),
            self._env_vars(),
            self._critical_rules(),
            self._exit_codes(),
        ]
        return "\n\n".join(s for s in sections if s)
```

### 6.2 New Module: `tooli/manifest.py`

Generates the structured agent manifest (§5.4).

### 6.3 New Module: `tooli/schema_output.py`

Output schema inference from return type annotations and `output_example` parameters.

### 6.4 Modified Module: `tooli/app.py`

New constructor parameters: `triggers`, `anti_triggers`, `workflows`, `rules`, `env_vars`, `backend`.

### 6.5 Modified Module: `tooli/command_meta.py`

New fields: `output_example`, `output_schema`.

### 6.6 New Module: `tooli/backends/native.py`

The lightweight CLI backend that replaces Typer for the default case.

### 6.7 New Module: `tooli/eval/agent_test.py`

The agent test harness (§5.8).

------

## 7. Implementation Phases

### Phase 1: SKILL.md + Output Schemas (P0) — Weeks 1-3

1. Implement `tooli/docs/skill_v3.py` with all sections from §5.1.
2. Implement output schema inference from return type annotations.
3. Add `output_example` parameter to `@app.command()`.
4. Add YAML frontmatter generation.
5. Add `--detail-level`, `--validate`, `--format` flags to `generate-skill`.
6. Add `--agent-manifest` global flag and `tooli/manifest.py`.
7. Write tests for generated SKILL.md structure.

**Exit criteria**: `generate-skill` produces a SKILL.md that can be dropped into Claude's `/mnt/skills/user/` directory and work correctly.

### Phase 2: Declarative Metadata (P1) — Weeks 4-5

1. Add `triggers`, `anti_triggers`, `workflows`, `rules`, `env_vars` parameters to `Tooli()`.
2. Implement `--infer-workflows` logic.
3. Enhance `--help-agent` to output structured YAML.
4. Integrate all new metadata into SKILL.md and manifest generation.

**Exit criteria**: A developer can declare workflows and rules in code, and they appear correctly in both SKILL.md and agent manifest.

### Phase 3: Native Backend (P1) — Weeks 6-8

1. Implement `tooli/backends/native.py` using argparse.
2. Create Tooli-native `Argument` and `Option` classes.
3. Implement `backend="native"` selection in `Tooli()`.
4. Ensure all existing tests pass with both backends.
5. Make `typer` an optional dependency (`pip install tooli[typer]`).

**Exit criteria**: `pip install tooli` has zero dependencies beyond `pydantic` and `rich`. All existing test suites pass with both backends.

### Phase 4: Testing & Polish (P2) — Weeks 9-10

1. Implement `generate-claude-md` command.
2. Implement `eval agent-test` harness.
3. Write comprehensive integration tests.
4. Benchmark token counts of generated SKILL.md files.
5. Documentation and migration guide.

**Exit criteria**: Full test coverage, migration guide published, v3.0 release on PyPI.

------

## 8. Migration Guide (v2 → v3)

### Breaking Changes

None. All v2.0 code runs unchanged on v3.0.

### Recommended Changes

1. **Add return type annotations** to all `@app.command()` functions. This enables output schema generation.

```python
# Before (v2)
@app.command()
def find_files(pattern: str) -> list[dict]:
    ...

# After (v3) - use Pydantic models for better schemas
class FileResult(BaseModel):
    path: str
    size: int

@app.command()
def find_files(pattern: str) -> list[FileResult]:
    ...
```

1. **Add `triggers` to your Tooli() constructor** for better SKILL.md frontmatter.
2. **Add `rules` and `env_vars`** for complete agent documentation.
3. **Run `generate-skill --validate`** to check your SKILL.md.
4. **Consider `backend="native"`** to reduce dependencies (optional).

------

## 9. Success Metrics

| Metric                                           | Target        | Measurement                                                  |
| ------------------------------------------------ | ------------- | ------------------------------------------------------------ |
| Agent first-attempt success rate                 | ≥90%          | Have Claude Code read only the SKILL.md and invoke 10 diverse commands |
| SKILL.md token count (10 commands)               | ≤3,000 tokens | Measure with `tiktoken`                                      |
| SKILL.md token count (50 commands, summary mode) | ≤5,000 tokens | Measure with `tiktoken`                                      |
| Agent manifest parse time                        | <50ms         | Benchmark on standard hardware                               |
| Existing v2 test suite pass rate                 | 100%          | CI/CD                                                        |
| PyPI install without Typer                       | Works         | `pip install tooli` succeeds; `import tooli` works           |

------

## 10. Open Questions

1. **Should SKILL.md generation be automatic on `pip install`?** A post-install hook could write SKILL.md to the package's data directory. But post-install hooks are controversial and being removed from setuptools.
2. **Should the agent manifest be served via MCP?** When running as an MCP server, the manifest could be a special resource. This would let agents discover capabilities without a separate `--agent-manifest` call.
3. **How should versioned commands appear in SKILL.md?** Currently, versioned commands create aliases (e.g., `find-files-v1`, `find-files-v2`). Should SKILL.md document all versions or only the latest?
4. **Should `generate-skill` support custom templates?** Some teams may want to add organization-specific sections (e.g., compliance notes, internal links). A Jinja2 template system could support this without much complexity.
5. **Should tooli ship a `tooli init` scaffolding command?** Similar to `npm init`, this would create a new tooli project with the right structure, including a pre-configured `generate-skill` step.

------

## 11. Competitive Landscape

| Feature             | Tooli v3   | Typer     | Click    | Fire | argparse |
| ------------------- | ---------- | --------- | -------- | ---- | -------- |
| Agent-readable docs | ✅ SKILL.md | ❌         | ❌        | ❌    | ❌        |
| JSON Schema export  | ✅          | ❌         | ❌        | ❌    | ❌        |
| Output schemas      | ✅          | ❌         | ❌        | ❌    | ❌        |
| MCP server          | ✅          | ❌         | ❌        | ❌    | ❌        |
| Structured errors   | ✅          | ❌         | ❌        | ❌    | ❌        |
| Dual-mode output    | ✅          | ❌         | ❌        | ❌    | ❌        |
| Agent manifest      | ✅          | ❌         | ❌        | ❌    | ❌        |
| Zero extra deps     | ✅ (native) | ❌ (click) | ❌ (many) | ✅    | ✅        |

Tooli v3 is the only CLI framework that treats AI agents as a first-class consumer.

------

## 12. Appendix: Example Generated SKILL.md

Below is an example of what `file-tools generate-skill` would produce in v3.0:

```markdown
---
name: file-tools
description: "Use this skill whenever you need to find, search, or process files
  on disk. Triggers include: finding files by pattern, counting lines, getting file
  statistics, bulk renaming. Use when the user mentions 'find files', 'glob', 'file
  search', 'count lines', 'rename files'. Do NOT use for database operations, API
  calls, or network requests."
version: 1.0.0
---

# file-tools

File manipulation utilities for searching, analyzing, and transforming files.

## Quick Reference

| Task | Command |
|------|---------|
| Find files by pattern | `file-tools find-files "*.py" --root ./src --json` |
| Count lines in files | `file-tools count-lines --pattern "*.py" --json` |
| Rename files in bulk | `file-tools rename-files --pattern "*.tmp" --suffix ".bak" --json` |
| Any command as JSON | Append `--json` to any command |
| Preview any change | Append `--dry-run` to any command |
| Inspect a command | `file-tools <command> --schema` |

## Installation

\`\`\`bash
pip install file-tools
\`\`\`

## Commands

### `find-files`

Find files matching a glob pattern in a directory tree.

**Behavior**: `read-only`, `idempotent`

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | string | Yes | — | Glob pattern to match files |
| `root` | string (path) | No | `"."` | Root directory to search from |
| `max_depth` | integer | No | `10` | Maximum directory depth |

#### Output

Returns `list[object]`:
\`\`\`json
[{"path": "src/main.py", "size": 1204}]
\`\`\`

#### Examples

\`\`\`bash
file-tools find-files "*.py" --root /project --json
\`\`\`
> Find all Python files in a project

#### Error Codes

| Code | Condition | Recovery |
|------|-----------|----------|
| E3001 | No files matched | Try broader pattern or verify root path |
| E1003 | Invalid glob syntax | Check pattern string |

### `count-lines`

Count lines in files matching a pattern.

**Behavior**: `read-only`, `idempotent`

...

## Global Flags

| Flag | Effect |
|------|--------|
| `--json` | JSON envelope output |
| `--jsonl` | Newline-delimited JSON |
| `--plain` | Unformatted text |
| `--quiet` | Suppress non-essential output |
| `--dry-run` | Preview without executing |
| `--schema` | Print JSON Schema and exit |
| `--timeout N` | Max execution time in seconds |
| `--yes` | Skip confirmation prompts |

## Output Format

All `--json` output uses this envelope:

\`\`\`json
{
  "ok": true,
  "result": <command data>,
  "meta": {"tool": "file-tools.find-files", "version": "1.0.0", "duration_ms": 34}
}
\`\`\`

On failure, check `error.suggestion` for recovery guidance:

\`\`\`json
{
  "ok": false,
  "error": {"code": "E3001", "message": "...", "suggestion": {"action": "retry_with_modified_input", "fix": "...", "example": "..."}, "is_retryable": true}
}
\`\`\`

## Error Catalog

| Code | Category | Meaning |
|------|----------|---------|
| E1001 | input | Unknown flag or argument |
| E1003 | input | Invalid glob syntax |
| E3001 | state | No files matched pattern |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Invalid usage |
| 10 | State error |
| 30 | Permission denied |
| 70 | Internal error |

## Workflow Patterns

### Search Then Process
\`\`\`bash
file-tools find-files "*.csv" --json | jq -r '.result[].path' | xargs -I{} file-tools process {} --json
\`\`\`

### Safe Destructive Operations
\`\`\`bash
file-tools rename-files --pattern "*.tmp" --suffix ".bak" --dry-run --json
# Review output, then:
file-tools rename-files --pattern "*.tmp" --suffix ".bak" --json
\`\`\`

## Critical Rules

- Always use `--json` when invoking from an agent.
- Always check `ok` field before accessing `result`.
- Paths are relative to CWD unless `--root` is specified.
- Use `--dry-run` before any destructive command.

Generated by Tooli v3.0.
```

------

*End of PRD v3.0*
