# Tooli v4.0 — Product Requirements Document

## From CLI Framework to Agent Skill Platform

**Version**: 4.0
**Author**: Brian Weisberg
**Status**: Draft
**Date**: February 2026
**Supersedes**: PRD_v3.md (v3.0)

------

## 1. Executive Summary

Tooli v3.0 delivered the primitives: SKILL.md generation, output schemas, agent manifests, a native backend, and an eval harness. But the end-to-end agent adoption loop is still incomplete. When Claude Code, Codex, or Devin encounters a tooli-built CLI today, there is no standard protocol for the agent to go from "I see a Python file" to "I have a complete, tested skill I can use forever." The agent still has to manually orchestrate discovery, read generated docs, and hope the SKILL.md is good enough.

**Version 4.0 closes the last mile.** The north-star scenario becomes fully automatic:

1. A developer writes a CLI tool using `tooli` instead of Typer.
2. An agent encounters the tool — via source file, installed package, or MCP discovery.
3. The agent runs **one command** (`mytool --agent-bootstrap`) and receives a complete, self-contained skill specification — ready to drop into `/mnt/skills/user/` or equivalent.
4. The specification includes: every command with full input/output schemas, tested examples with expected outputs, error recovery playbooks, composition patterns, and critical rules.
5. The agent uses the tool perfectly on the first attempt and can teach other agents to do the same.

This is the "write a function, get a skill" vision — not just "write a function, get a CLI."

### What's New in v4.0 vs v3.0

| Capability | v3.0 | v4.0 |
|---|---|---|
| SKILL.md generation | Good structure, missing depth | Gold-standard quality matching hand-written Claude skills |
| Agent bootstrap | `--agent-manifest` (JSON only) | `--agent-bootstrap` — single command produces deployable SKILL.md |
| Source-as-documentation | Agent must read SKILL.md separately | Decorated source file is self-documenting enough for agents |
| Example verification | Examples are static strings | Examples are tested and include expected output snapshots |
| Error recovery | Suggestions per error | Full recovery playbooks with multi-step strategies |
| Composition | `workflows` parameter (declarative) | Pipe contracts + automatic composition inference |
| Claude Code integration | Generic agent support | Specific CLAUDE.md generation and `/mnt/skills/` integration |
| Skill validation | `--validate` checks structure | `--validate` runs live tests against actual tool behavior |
| `tooli init` | Not available | Full project scaffolding with skill-ready defaults |
| MCP skill discovery | Tool listing only | Skill metadata exposed as MCP resources |

------

## 2. Problem Analysis

### 2.1 The Agent Skill Adoption Loop (Current State)

Today, when an AI coding agent encounters a tooli-built tool, the workflow looks like this:

```
Agent finds Python file using tooli
    │
    ▼
Agent reads source code to understand imports    ← Requires code comprehension
    │
    ▼
Agent runs `mytool generate-skill`               ← Knows this exists (maybe)
    │
    ▼
Agent reads generated SKILL.md                   ← Quality varies
    │
    ▼
Agent tries a command with --json                ← Usually works
    │
    ▼
Agent encounters edge case                       ← Recovery is ad-hoc
    │
    ▼
Agent wants to chain commands                    ← No composition contracts
    │
    ▼
Agent wants to save skill for reuse              ← Manual process
```

### 2.2 The Target Loop (v4.0)

```
Agent encounters tooli tool (any entry point)
    │
    ▼
Agent runs `mytool --agent-bootstrap`            ← One command
    │
    ▼
Agent receives complete SKILL.md                 ← Deployable as-is
    │
    ▼
Agent drops into /mnt/skills/user/mytool/        ← Zero editing
    │
    ▼
Agent (or future agents) read SKILL.md           ← Perfect first-attempt usage
    │
    ▼
Agent handles every error with playbooks         ← Autonomous recovery
    │
    ▼
Agent chains tools using pipe contracts          ← Documented composition
```

### 2.3 Gap Analysis: Generated SKILL.md vs Hand-Written Claude Skills

Comparing the current `skill_v3.py` output against Claude's built-in skills (docx, pdf, pptx, xlsx) reveals structural and quality gaps:

| Aspect | Claude Built-in Skills | Current Tooli SKILL.md | Gap |
|---|---|---|---|
| **Frontmatter description** | Dense, natural language with specific trigger phrases and anti-triggers | Mechanical concatenation of command names | Need NLP-quality trigger synthesis |
| **Working code examples** | Complete, copy-pasteable code blocks with real output | CLI invocation strings without output | Need output snapshots |
| **Critical rules** | Domain-specific warnings from real usage ("CRITICAL: docx-js defaults to A4") | Generic rules ("Always use --json") | Need tool-specific rule inference |
| **Task-oriented structure** | Organized by *what the user wants to do* | Organized by *command name* | Need task-centric documentation mode |
| **Error handling guidance** | Inline with workflows ("If validation fails, unpack, fix the XML, and repack") | Separate error catalog table | Need inline error guidance in workflows |
| **Prose quality** | Written by humans who used the tools | Generated from metadata | Need richer docstrings and prose generation |
| **Dependencies & setup** | Specific install commands, version notes, gotchas | Generic `pip install` | Need full environment documentation |
| **Code patterns** | Multi-line code examples showing real usage | One-line CLI invocations | Need richer example blocks |

### 2.4 What v3.0 Got Right (Keep)

- Dual-mode output with auto-TTY detection
- Structured errors with ToolError hierarchy
- JSON Schema from type hints (Pydantic pipeline)
- MCP server mode (stdio/http/sse)
- Behavioral annotations (ReadOnly, Idempotent, Destructive)
- Native backend (no Typer dependency)
- Output schema inference from return types
- Agent manifest (`--agent-manifest`)
- Token-budget tiering for large tools
- YAML frontmatter with triggers

------

## 3. Goals & Non-Goals

### 3.1 Goals

| # | Goal | Success Metric |
|---|---|---|
| G1 | **One-command agent bootstrap**: `mytool --agent-bootstrap` produces a SKILL.md that works in Claude's `/mnt/skills/user/` with zero edits | Drop-in test: generated SKILL.md placed in skills directory enables correct first-attempt invocation ≥95% of the time |
| G2 | **Verified examples**: Every example in SKILL.md includes expected output and has been tested against the actual tool | `mytool generate-skill --validate` runs all examples and reports pass/fail |
| G3 | **Error recovery playbooks**: Error catalog entries include multi-step recovery strategies, not just one-line suggestions | Every error code has ≥1 concrete recovery example with CLI commands |
| G4 | **Pipe contracts**: Tools declare what they accept on stdin and what shape their stdout takes, enabling automatic composition | `pipe_input` and `pipe_output` schemas are documented per command |
| G5 | **`tooli init` scaffolding**: New projects start with skill-ready structure | `tooli init myproject` creates a working project with SKILL.md generation pre-configured |
| G6 | **Source-level agent hints**: Decorated Python source files contain enough metadata that an agent can understand the tool without running `generate-skill` | A `# tooli:agent` comment block in source renders a machine-readable summary |
| G7 | **Claude Code native workflow**: Specific integration patterns for Claude Code's bash tool and skill system | `generate-skill --target claude-code` produces output optimized for Claude Code's context window and skill loading |
| G8 | **MCP skill discovery**: Tool capabilities are discoverable via MCP resources, not just tool listing | `mytool mcp serve` exposes a `skill://manifest` resource that agents can read |

### 3.2 Non-Goals

- **LLM-powered documentation** — Tooli does not call Claude/GPT to generate prose. All documentation comes from developer-provided metadata and deterministic inference.
- **Runtime agent orchestration** — Tooli helps agents *use* tools; it doesn't manage multi-agent coordination.
- **Skill marketplace or registry** — v4.0 focuses on generation quality, not distribution infrastructure.
- **Breaking Python API changes** — `@app.command()` syntax remains backward-compatible.

------

## 4. User Personas

### 4.1 Tool Author (Primary)

A Python developer who builds CLI tools. They want their tool to be immediately usable by AI agents without writing documentation. They currently use Typer or Click and are considering tooli.

**v4.0 promise**: "Write your functions, add type hints and docstrings, run one command, and any AI agent can use your tool perfectly."

### 4.2 AI Coding Agent (Primary Consumer)

Claude Code, Codex CLI, Devin, Cursor Agent, or similar. The agent encounters a tool via source code, installed package, or MCP server. It needs to understand the complete contract in minimal tokens and use the tool correctly on the first attempt.

**v4.0 promise**: "Run `--agent-bootstrap`, read the result, and you know everything. First attempt, every time."

### 4.3 Skill Curator (New Persona)

Someone maintaining a collection of agent skills — e.g., a team's internal skill library or a company's `/mnt/skills/user/` directory. They need consistent, high-quality SKILL.md files that follow a standard format.

**v4.0 promise**: "Every tooli-built tool generates skills in the same high-quality format. Just `generate-skill > SKILL.md`."

------

## 5. Feature Specifications

### 5.1 Agent Bootstrap Protocol (P0)

A single global flag that produces a complete, deployable SKILL.md:

```bash
mytool --agent-bootstrap
```

This is distinct from the existing `--agent-manifest` (which outputs JSON) and `generate-skill` (which is a subcommand). `--agent-bootstrap` is a *global flag* that works on any tooli app and produces output optimized for the specific scenario: "an agent needs to learn this tool right now."

**Output**: A complete SKILL.md document, printed to stdout, ready to be redirected to a file:

```bash
mytool --agent-bootstrap > /mnt/skills/user/mytool/SKILL.md
```

**What makes this different from `generate-skill`**:

1. `--agent-bootstrap` is a *flag*, not a subcommand. It works even if the tool has no `generate-skill` command registered (tooli injects it automatically).
2. The output is optimized for immediate deployment — it includes the full SKILL.md with all sections, verified examples, and inline recovery guidance.
3. It auto-detects the caller's context (Claude Code vs generic agent) via environment variables and adjusts the output format accordingly.

**Environment detection**:

```python
# Auto-detect Claude Code context
if os.environ.get("CLAUDE_CODE") or os.environ.get("ANTHROPIC_API_KEY"):
    # Produce Claude-optimized SKILL.md with frontmatter matching Claude's skill loader
    format = "claude-skill"
else:
    # Produce generic agent SKILL.md
    format = "generic-skill"
```

### 5.2 Gold-Standard SKILL.md Generation (P0)

Complete rewrite of the SKILL.md generation quality to match hand-written Claude skills. The current `skill_v3.py` produces structurally correct but *flat* documentation. v4.0 produces *rich, task-oriented* documentation.

#### 5.2.1 Task-Oriented Command Documentation

Instead of documenting commands alphabetically, v4.0 groups commands by *what the user wants to accomplish*:

```markdown
## Reading & Inspecting Files

### `find-files`

Find files matching a glob pattern in a directory tree.

**When to use**: User says "find files", "search for files", "locate Python files",
"what files are in this directory". Use this before `process` to identify targets.

**Behavior**: `read-only`, `idempotent`

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | string | Yes | — | Glob pattern (e.g., `"*.py"`, `"**/*.json"`) |
| `root` | string (path) | No | `"."` | Root directory to search from |
| `max_depth` | integer | No | `10` | Maximum directory depth (1-100) |

#### Example

```bash
$ file-tools find-files "*.py" --root ./src --json
```

Expected output:
```json
{
  "ok": true,
  "result": [
    {"path": "src/main.py", "size": 1204},
    {"path": "src/utils.py", "size": 892}
  ],
  "meta": {"tool": "file-tools.find-files", "version": "1.0.0", "duration_ms": 34}
}
```

#### If Something Goes Wrong

| Symptom | Cause | Fix |
|---------|-------|-----|
| Empty result array | No files match pattern | Try `"*"` first to see what exists, then narrow pattern |
| Exit code 10 | Root directory doesn't exist | Verify path with `ls` before calling |
| E1003 error | Invalid glob syntax | Check for unescaped special characters in pattern |
```

**Key improvements over v3.0:**

1. **"When to use" prose** — generated from command docstring, behavioral annotations, and trigger inference.
2. **Expected output** — generated from `output_example` or by running the example against the tool during `--validate`.
3. **"If Something Goes Wrong" section** — replaces the error catalog table with inline, contextual recovery guidance per command.
4. **Parameter constraints** — `(1-100)` ranges shown inline, extracted from Pydantic validators or `Option(min=, max=)`.

#### 5.2.2 Enhanced Trigger Synthesis

The current trigger synthesis (`_triggers` property in `skill_v3.py`) extracts tokens from command names and descriptions. This produces generic triggers like "find files", "process". v4.0 produces natural-language triggers:

**Current (v3.0)**:
```yaml
description: "File manipulation utilities. Useful for: find files, process, rename files."
```

**Target (v4.0)**:
```yaml
description: "Use this skill whenever you need to find, search, or process files on disk.
  Triggers include: any mention of 'find files', 'glob pattern', 'file search',
  'count lines', 'rename files', 'batch file operations', or requests involving
  file system traversal. Also use when the user asks to process CSV files, check file
  sizes, or perform bulk renaming. Do NOT use for database operations, network API calls,
  or in-memory data processing."
```

**Implementation**: The description is composed from:
1. The developer's `description` string (base)
2. Command names expanded to natural language phrases
3. Argument descriptions mined for domain keywords
4. `anti_triggers` expanded to "Do NOT use" phrases
5. Docstring first sentences aggregated

The generator uses a template system:

```python
DESCRIPTION_TEMPLATE = (
    "Use this skill whenever {base_description}. "
    "Triggers include: {trigger_phrases}. "
    "{also_use_clause}"
    "Do NOT use for {anti_trigger_phrases}."
)
```

#### 5.2.3 Verified Examples with Output Snapshots

Every example in the SKILL.md must include its expected output. This requires a new parameter on `@app.command()`:

```python
@app.command(
    examples=[
        {
            "args": ["--pattern", "*.py", "--root", "/project"],
            "description": "Find all Python files in a project",
            "expected_output": [
                {"path": "src/main.py", "size": 1204},
                {"path": "src/utils.py", "size": 892},
            ],
        },
    ],
)
```

If `expected_output` is not provided, the `generate-skill --validate` command will:
1. Run the example against the tool with `--json`.
2. Capture the output.
3. Warn if no output snapshot is available.
4. Optionally write the captured output back as a snapshot file.

#### 5.2.4 Inline Error Recovery (Replaces Error Catalog)

The current SKILL.md has a global "Error Catalog" table at the bottom. This is hard for agents to use because the errors are disconnected from the commands that produce them. v4.0 moves error guidance inline:

**Current approach (v3.0)**:
```markdown
## Error Catalog

| Code | Category | Commands | Meaning | Recovery Action |
|------|----------|----------|---------|-----------------|
| E3001 | state | find-files | No files matched | Try broader pattern |
```

**New approach (v4.0)**:
Each command gets an "If Something Goes Wrong" section (see §5.2.1) that includes:
- Common symptoms (not just error codes)
- Root causes in plain language
- Multi-step recovery strategies with example commands
- Cross-references to related commands that might help

The global error catalog is retained but becomes a supplementary index, not the primary error documentation.

### 5.3 Pipe Contracts (P1)

Tools that accept piped input or produce pipeable output should declare this explicitly. This enables agents to compose tools without guessing.

#### 5.3.1 New Decorator Parameters

```python
@app.command(
    pipe_input={
        "format": "jsonl",          # What stdin format this command accepts
        "schema": FileResult,       # Pydantic model or JSON schema for each line
        "description": "One file result per line from find-files",
    },
    pipe_output={
        "format": "jsonl",          # What stdout produces when piped
        "schema": ProcessResult,    # Schema for each output line
        "description": "Processed file results",
    },
)
def process(
    input_data: Annotated[StdinOr[Path], Argument(help="Input file or stdin")],
) -> list[ProcessResult]:
    ...
```

#### 5.3.2 Composition Documentation

Pipe contracts are rendered in SKILL.md as a "Composition Patterns" section:

```markdown
## Composition Patterns

### find-files → process (pipe)

`find-files` produces JSONL output that `process` accepts on stdin:

```bash
file-tools find-files "*.csv" --jsonl | file-tools process -
```

### Safe Destructive Operations (dry-run → execute)

```bash
# Step 1: Preview
file-tools rename-files --pattern "*.tmp" --suffix ".bak" --dry-run --json
# Step 2: Review the plan in .result, then execute
file-tools rename-files --pattern "*.tmp" --suffix ".bak" --json
```
```

#### 5.3.3 Automatic Composition Inference

When `--infer-workflows` is used (or automatically during `--agent-bootstrap`), the generator analyzes:

1. **Output→Input type matching**: If command A returns `list[FileResult]` and command B accepts `StdinOr[list[FileResult]]`, they can be piped.
2. **ReadOnly→Destructive pairs**: Commands sharing parameters (e.g., both take `--pattern`) where one is read-only and one is destructive form a "preview then execute" pattern.
3. **Pagination chains**: Commands with `paginated=True` get a "paginate through results" workflow.
4. **Dry-run patterns**: Any command with `supports_dry_run=True` gets a "dry-run first" workflow.

### 5.4 `tooli init` — Project Scaffolding (P1)

A new top-level command that creates a skill-ready project:

```bash
tooli init myproject
```

Creates:

```
myproject/
├── pyproject.toml          # Pre-configured with tooli dependency
├── myproject/
│   ├── __init__.py
│   └── app.py              # Skeleton Tooli app with example command
├── tests/
│   └── test_app.py         # Contract tests using tooli's test helpers
├── SKILL.md                # Pre-generated (updates on build)
├── CLAUDE.md               # Claude Code instructions
└── README.md               # Human-readable docs
```

The generated `app.py` includes:

```python
from tooli import Tooli, Annotated, Argument, Option
from tooli.annotations import ReadOnly, Idempotent

app = Tooli(
    name="myproject",
    description="<your tool description>",
    version="0.1.0",
    triggers=["<trigger phrases>"],
    anti_triggers=["<when NOT to use>"],
    rules=[
        "Always use --json when invoking from an agent.",
    ],
)


@app.command(
    annotations=ReadOnly | Idempotent,
    examples=[
        {
            "args": ["world"],
            "description": "Greet the world",
            "expected_output": {"greeting": "Hello, world!"},
        },
    ],
)
def greet(
    name: Annotated[str, Argument(help="Name to greet")],
) -> dict:
    """Greet someone by name."""
    return {"greeting": f"Hello, {name}!"}


if __name__ == "__main__":
    app()
```

**Flags**:

```bash
tooli init myproject                    # Interactive setup
tooli init myproject --minimal          # Minimal template
tooli init myproject --from-typer app.py # Convert existing Typer app
```

#### 5.4.1 Typer Migration Assistant

`tooli init --from-typer existing_app.py` reads an existing Typer app and generates a tooli equivalent:

1. Parses the existing `typer.Typer()` and `@app.command()` decorators.
2. Rewrites imports to use `tooli`.
3. Adds `annotations`, `examples`, and `error_codes` stubs for the developer to fill in.
4. Generates initial SKILL.md from the converted code.
5. Produces a migration report listing what was auto-converted and what needs manual attention.

### 5.5 Source-Level Agent Hints (P1)

When an agent encounters a Python file that uses tooli, it should be able to understand the tool's capabilities without running it. v4.0 adds a convention for inline agent documentation:

#### 5.5.1 `# tooli:agent` Block

A special comment block at the top of the source file, auto-generated by `tooli generate-source-hints`:

```python
# tooli:agent
# name: file-tools
# version: 1.0.0
# commands: find-files(pattern:str, root:path=".", max_depth:int=10) -> list[{path:str, size:int}]
#           process(input_data:stdin_or_path) -> list[{path:str, lines:int}]
# flags: --json --jsonl --plain --quiet --dry-run --schema
# invoke: file-tools <command> [args] --json
# errors: E1003(invalid glob) E3001(no match) E4001(timeout)
# skill: file-tools --agent-bootstrap > SKILL.md
# tooli:end

from tooli import Tooli, Annotated, Argument, Option
...
```

This is a compact, machine-readable summary that any agent can parse with simple text extraction. It tells the agent:
- What commands exist with their signatures
- How to invoke the tool
- Where to get the full skill documentation

#### 5.5.2 Auto-Generation

```bash
mytool generate-source-hints                    # Print to stdout
mytool generate-source-hints --write app.py     # Insert/update in-place
```

The `--write` flag uses AST-safe insertion to place or update the comment block immediately after the module docstring and before the first import.

### 5.6 Claude Code Integration (P1)

Specific features for Claude Code's workflow and context model.

#### 5.6.1 `generate-skill --target claude-code`

Produces SKILL.md optimized for Claude Code's specific patterns:
- Frontmatter matches Claude's `<available_skills>` XML format expectations.
- Examples use `bash_tool` invocation patterns.
- Critical rules reference Claude Code's working directory conventions (`/home/user`).
- Token budget respects Claude Code's typical context allocation for skills (~3K tokens).

#### 5.6.2 Enhanced `generate-claude-md`

The existing CLAUDE.md generator (v3.0) produces a basic project overview. v4.0 produces a CLAUDE.md that specifically helps Claude Code work on the tool's codebase:

```markdown
# CLAUDE.md — file-tools

## Build & Test
pip install -e ".[dev]"
pytest tests/ -v
ruff check .

## Architecture
- `app.py` — Main Tooli app with command definitions
- `tooli/` — Framework code (do not modify)
- `tests/test_app.py` — Contract tests for all commands

## Agent Invocation
Always use `--json` flag. Parse the `ok` field first.
Full skill docs: `file-tools --agent-bootstrap`

## Key Patterns
- Return typed values from commands (not print)
- Use Pydantic BaseModel for complex return types
- Add `output_example` for dict returns
- Run `file-tools generate-skill --validate` after changes

## Development Workflow
1. Edit command in `app.py`
2. Run `pytest tests/test_app.py -k <command_name>`
3. Run `file-tools generate-skill --validate`
4. Run `file-tools --agent-bootstrap > SKILL.md`
```

#### 5.6.3 Skill Directory Structure

For tools that want to be directly deployable as Claude skills:

```bash
mytool generate-skill-package --output ./skills/mytool/
```

Produces:

```
skills/mytool/
├── SKILL.md                # Complete skill documentation
├── install.sh              # One-shot installer (pip install + verify)
└── verify.sh               # Quick smoke test
```

### 5.7 Enhanced Agent Eval Harness (P2)

The existing `eval agent-test` (v3.0) validates schema accuracy and output conformance. v4.0 extends it to test the *skill itself*:

#### 5.7.1 Skill Round-Trip Test

```bash
mytool eval skill-roundtrip [--model claude-sonnet-4-5] [--output report.json]
```

This test:
1. Generates the SKILL.md.
2. Feeds the SKILL.md as context to a model (configurable, defaults to Claude).
3. Asks the model to invoke each command based only on the SKILL.md.
4. Verifies the model produces correct invocations.
5. Reports first-attempt success rate.

**Note**: This requires an API key and is opt-in. The test uses a minimal prompt:
```
You are an AI agent. You have access to a CLI tool. Here is its documentation:

<skill>
{SKILL.md content}
</skill>

Based ONLY on this documentation, write the exact bash command to: {task description}
```

#### 5.7.2 Coverage Report

```bash
mytool eval coverage
```

Reports:
- Commands with/without examples
- Commands with/without output schemas
- Commands with/without error codes
- Commands with/without behavioral annotations
- Parameters with/without help text
- Estimated SKILL.md token count
- Warnings for common issues (e.g., `dict` return without `output_example`)

### 5.8 MCP Skill Resource (P2)

When a tooli app runs as an MCP server, it exposes its skill documentation as an MCP resource:

```python
# Auto-registered when MCP server starts
@mcp_server.resource("skill://manifest")
async def get_manifest():
    return generate_agent_manifest(app)

@mcp_server.resource("skill://documentation")
async def get_skill_md():
    return generate_skill_md(app)
```

This allows MCP clients to discover tool capabilities without running CLI commands:

```json
{
    "method": "resources/read",
    "params": {"uri": "skill://documentation"}
}
```

### 5.9 `tooli upgrade-metadata` — Metadata Enhancement Assistant (P2)

A command that analyzes an existing tooli app and suggests metadata improvements:

```bash
mytool upgrade-metadata
```

Output:
```
Analyzing file-tools...

Missing metadata:
  ✗ find-files: no output_example (return type is dict)
  ✗ process: no error_codes
  ✗ rename-files: no examples
  ✗ App: no anti_triggers

Suggestions:
  → find-files: Add output_example={"path": "...", "size": 0}
  → process: Add error_codes={"E4001": "Input file not found"}
  → rename-files: Add examples=[{"args": [...], "description": "..."}]
  → App: Add anti_triggers=["database operations", "API calls"]

Quick fix:
  mytool upgrade-metadata --apply      # Auto-insert stubs into source
```

The `--apply` flag uses AST manipulation to insert metadata stubs directly into the source code, which the developer then fills in with real values.

------

## 6. Architecture Changes

### 6.1 New Modules

| Module | Purpose |
|---|---|
| `tooli/bootstrap.py` | `--agent-bootstrap` flag implementation and context detection |
| `tooli/init.py` | `tooli init` scaffolding engine |
| `tooli/pipes.py` | Pipe contract declarations and inference |
| `tooli/docs/skill_v4.py` | Rewritten SKILL.md generator with task-oriented structure |
| `tooli/docs/source_hints.py` | `# tooli:agent` block generator and parser |
| `tooli/docs/claude_md_v2.py` | Enhanced CLAUDE.md generator |
| `tooli/upgrade.py` | `upgrade-metadata` analysis and auto-fix |
| `tooli/eval/skill_roundtrip.py` | Skill round-trip testing with LLM |
| `tooli/eval/coverage.py` | Metadata coverage reporter |

### 6.2 Modified Modules

| Module | Changes |
|---|---|
| `tooli/app_native.py` | Add `--agent-bootstrap` global flag, pipe contract support |
| `tooli/app.py` | Same changes for Typer backend |
| `tooli/command_meta.py` | Add `pipe_input`, `pipe_output`, `expected_output`, `when_to_use` fields |
| `tooli/schema.py` | Add pipe schema generation |
| `tooli/mcp/server.py` | Register `skill://` resources automatically |
| `tooli/manifest.py` | Add pipe contracts and composition patterns to manifest |
| `tooli/docs/skill_v3.py` | Deprecated; replaced by `skill_v4.py` |

### 6.3 New `CommandMeta` Fields

```python
@dataclass
class CommandMeta:
    # ... existing fields ...

    # v4.0 additions
    pipe_input: PipeContract | None = None
    pipe_output: PipeContract | None = None
    when_to_use: str | None = None           # Natural-language trigger description
    expected_outputs: list[dict] = field(default_factory=list)  # Snapshot outputs for examples
    recovery_playbooks: dict[str, list[str]] = field(default_factory=dict)  # Error code → recovery steps
    task_group: str | None = None            # Grouping key for task-oriented docs
```

### 6.4 `PipeContract` Type

```python
@dataclass
class PipeContract:
    format: Literal["json", "jsonl", "text", "csv"]
    schema: dict[str, Any] | None = None     # JSON Schema for the pipe data
    description: str = ""
    example: str | None = None               # Example of what the piped data looks like
```

------

## 7. SKILL.md v4 Complete Structure

The following is the definitive section structure for generated SKILL.md files. Every section is present unless explicitly empty.

```
---
name: <tool-name>
description: "<natural-language description with triggers and anti-triggers>"
version: <semver>
---

# <tool-name>

<1-2 sentence overview of what this tool does>

## Quick Reference

| Task | Command |
|------|---------|
<one row per command, task-described>
<global flag rows>

## Installation

```bash
pip install <tool-name>
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
<tool-specific env vars>

### Verify Installation

```bash
<tool-name> --version
<tool-name> greet world --json    # Should return {"ok": true, ...}
```

## Commands

### <Task Group 1: e.g., "Reading & Inspecting">

#### `<command-name>`

<docstring>

**When to use**: <natural-language triggers>
**Behavior**: `<annotations>`

##### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
<full parameter table with constraints>

##### Example

```bash
$ <full invocation>
```

Expected output:
```json
<verified JSON output>
```

##### If Something Goes Wrong

| Symptom | Cause | Fix |
|---------|-------|-----|
<inline error guidance>

<repeat for each command in group>
<repeat for each task group>

## Composition Patterns

### <Pattern Name>

<prose description of when to use this pattern>

```bash
<multi-step bash example>
```

## Global Flags

| Flag | Effect |
|------|--------|
<all global flags>

## Output Format

<envelope format with success and failure examples>

## Exit Codes

| Code | Meaning | Agent Action |
|------|---------|--------------|
<full exit code table>

## Critical Rules

- <rule 1>
- <rule 2>
...

---
Generated by tooli v4.0 | Verify: `<tool-name> generate-skill --validate`
```

------

## 8. Implementation Phases

### Phase 1: Gold-Standard SKILL.md + Bootstrap (P0) — Weeks 1-4

**Goal**: `--agent-bootstrap` produces a SKILL.md that passes the drop-in test.

1. Implement `tooli/docs/skill_v4.py` with task-oriented structure.
2. Implement enhanced trigger synthesis (§5.2.2).
3. Implement verified examples with output snapshots (§5.2.3).
4. Implement inline error recovery sections (§5.2.4).
5. Implement `--agent-bootstrap` global flag (§5.1).
6. Implement `when_to_use` auto-generation from docstrings and annotations.
7. Write round-trip tests: generate SKILL.md → parse → verify all metadata is present.
8. Benchmark against Claude's built-in skills for structural parity.

**Exit criteria**: Generated SKILL.md for the `docq` and `gitsum` example apps are structurally equivalent to Claude's built-in docx/pdf skills. A human reviewer cannot distinguish generated from hand-written at a structural level.

### Phase 2: Composition & Metadata (P1) — Weeks 5-7

**Goal**: Tools declare how they compose and agents can chain them.

1. Implement `PipeContract` type and `pipe_input`/`pipe_output` decorator parameters.
2. Implement automatic composition inference (§5.3.3).
3. Implement `tooli init` scaffolding (§5.4).
4. Implement Typer migration assistant (§5.4.1).
5. Implement source-level agent hints `# tooli:agent` (§5.5).
6. Add pipe contracts to agent manifest and SKILL.md.
7. Update all 18 example apps with v4.0 metadata.

**Exit criteria**: `tooli init myproject && cd myproject && myproject --agent-bootstrap` produces a valid, deployable SKILL.md on a fresh project.

### Phase 3: Claude Code + Validation (P1) — Weeks 8-10

**Goal**: Specific Claude Code integration and quality validation.

1. Implement `generate-skill --target claude-code` (§5.6.1).
2. Implement enhanced `generate-claude-md` (§5.6.2).
3. Implement `generate-skill-package` for skill directory output (§5.6.3).
4. Implement `eval coverage` report (§5.7.2).
5. Implement `upgrade-metadata` analysis (§5.9).
6. Implement `upgrade-metadata --apply` for auto-stub insertion.
7. Integration tests with Claude Code's actual skill loading.

**Exit criteria**: Generated skill package can be placed in Claude's `/mnt/skills/user/` and Claude correctly selects and uses the skill based on user prompts.

### Phase 4: Advanced Features (P2) — Weeks 11-13

**Goal**: MCP discovery, LLM-powered eval, polish.

1. Implement MCP skill resources (§5.8).
2. Implement `eval skill-roundtrip` with LLM testing (§5.7.1).
3. Performance benchmarks for SKILL.md generation.
4. Documentation, migration guide v3→v4.
5. Update all PRDs and roadmap docs.
6. v4.0 release on PyPI.

**Exit criteria**: Full test coverage, all 18 examples produce gold-standard SKILL.md, migration guide published.

------

## 9. Migration Guide (v3 → v4)

### Breaking Changes

**None.** All v3.0 code runs unchanged on v4.0.

### Recommended Changes

1. **Add `when_to_use` to commands** — Provides natural-language triggers for SKILL.md "When to use" sections.

```python
# Before (v3)
@app.command()
def find_files(pattern: str) -> list[dict]:
    """Find files matching a glob pattern."""
    ...

# After (v4) — richer metadata
@app.command(
    when_to_use="User wants to find, search, or locate files by pattern",
    task_group="Reading & Inspecting",
)
def find_files(pattern: str) -> list[dict]:
    """Find files matching a glob pattern in a directory tree."""
    ...
```

2. **Add `expected_output` to examples** — Enables verified examples in SKILL.md.

3. **Add `pipe_input`/`pipe_output`** — Enables composition documentation.

4. **Add `recovery_playbooks` to error codes** — Enables rich error guidance.

```python
@app.command(
    error_codes={
        "E3001": "No files matched pattern",
    },
    recovery_playbooks={
        "E3001": [
            "Run `find-files '*' --root <same-root> --json` to see all available files",
            "Check that the root directory exists with `ls <root>`",
            "Try a broader pattern like `'*.py'` instead of a specific filename",
        ],
    },
)
```

5. **Run `mytool upgrade-metadata`** to identify gaps.
6. **Run `mytool generate-skill --validate`** to verify quality.
7. **Run `mytool --agent-bootstrap > SKILL.md`** to produce the final skill.

------

## 10. Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Agent first-attempt success rate | ≥95% | Claude Code reads generated SKILL.md and invokes 20 diverse commands |
| SKILL.md structural parity with Claude built-in skills | 100% section coverage | Automated comparison against docx/pdf/xlsx skill structure |
| SKILL.md token count (10 commands, full mode) | ≤4,000 tokens | `estimate_skill_tokens()` |
| SKILL.md token count (50 commands, auto/summary mode) | ≤5,000 tokens | `estimate_skill_tokens()` |
| Example verification pass rate | 100% | `generate-skill --validate` passes on all 18 example apps |
| `tooli init` to working skill | <5 minutes | Time from `tooli init` to valid `--agent-bootstrap` output |
| Existing v3 test suite pass rate | 100% | CI/CD with both native and typer backends |
| Metadata coverage across example apps | ≥90% | `eval coverage` reports ≥90% on triggers, examples, output schemas, error codes |

------

## 11. Open Questions

1. **Should `--agent-bootstrap` auto-run examples to capture output snapshots?** This would make the first generation slower but produce better examples. It could be gated behind `--agent-bootstrap --verified`.

2. **Should `tooli init --from-typer` support Click apps too?** Click is the underlying framework, but the decorator patterns are different. Supporting both broadens adoption but increases complexity.

3. **How should pipe contracts handle streaming vs. batch?** A command that processes items one-at-a-time (streaming JSONL) has different composition semantics than one that reads all input first (batch JSON). Should we distinguish these?

4. **Should MCP skill resources be opt-in or automatic?** Auto-registering `skill://` resources could confuse MCP clients that don't understand the convention. Opt-in is safer but requires explicit configuration.

5. **Should `upgrade-metadata --apply` modify docstrings?** Adding `when_to_use` stubs to source is straightforward for decorator parameters, but enriching docstrings with agent-friendly prose is harder and riskier. Could be a separate `--enrich-docstrings` flag.

6. **Should SKILL.md generation support Jinja2 templates for customization?** Some teams want custom sections (compliance notes, internal links). Template support adds flexibility but complexity.

7. **How should `task_group` ordering work?** Should groups appear in declaration order, alphabetical, or by a priority annotation? The docx skill uses logical workflow order (read → create → edit) which requires semantic understanding.

------

## 12. Competitive Positioning

| Feature | Tooli v4 | Tooli v3 | Typer | Click | Fire | argparse |
|---|---|---|---|---|---|---|
| Agent-ready SKILL.md | ✅ Gold-standard | ⚠️ Structural | ❌ | ❌ | ❌ | ❌ |
| One-command skill bootstrap | ✅ `--agent-bootstrap` | ❌ | ❌ | ❌ | ❌ | ❌ |
| Verified examples | ✅ With expected output | ❌ | ❌ | ❌ | ❌ | ❌ |
| Pipe composition contracts | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Error recovery playbooks | ✅ Multi-step | ⚠️ One-line | ❌ | ❌ | ❌ | ❌ |
| Claude Code integration | ✅ Native | ❌ | ❌ | ❌ | ❌ | ❌ |
| MCP server with skill discovery | ✅ | ⚠️ Tool listing only | ❌ | ❌ | ❌ | ❌ |
| Project scaffolding | ✅ `tooli init` | ❌ | ❌ | ❌ | ❌ | ❌ |
| Source-level agent hints | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Typer migration | ✅ | ❌ | N/A | ❌ | ❌ | ❌ |
| JSON Schema export | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Dual-mode output | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Zero extra deps (native backend) | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |

Tooli v4.0 is the first CLI framework designed for the skill-based agent era — not just "agent-friendly" but "skill-native."

------

## 13. Appendix A: Example Generated SKILL.md (v4.0)

Below is a representative excerpt of what `file-tools --agent-bootstrap` produces:

```markdown
---
name: file-tools
description: "Use this skill whenever you need to find, search, process, or manipulate
  files on disk. Triggers include: any mention of 'find files', 'glob pattern',
  'file search', 'count lines', 'rename files', 'file statistics', or requests
  involving file system traversal and batch operations. Also use when the user asks
  to process CSVs from a directory, check file sizes, or perform bulk renaming.
  Do NOT use for database operations, network API calls, in-memory data processing,
  or reading file contents (use standard file I/O for that)."
version: 1.0.0
---

# file-tools

File manipulation utilities for searching, analyzing, and transforming files on disk.

## Quick Reference

| Task | Command |
|------|---------|
| Find files by pattern | `file-tools find-files "*.py" --root ./src --json` |
| Count lines in matched files | `file-tools count-lines --pattern "*.py" --json` |
| Rename files in bulk | `file-tools rename-files --pattern "*.tmp" --suffix ".bak" --json` |
| Get JSON output (any command) | Append `--json` to any command |
| Preview changes safely | Append `--dry-run --json` to any command |
| Inspect command schema | `file-tools <command> --schema` |

## Installation

```bash
pip install file-tools
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TOOLI_OUTPUT` | No | Default output mode: `json`, `jsonl`, `text`, `plain` |

### Verify Installation

```bash
file-tools --version                          # Should print 1.0.0
file-tools find-files "*.py" --root . --json  # Should return {"ok": true, ...}
```

## Commands

### Reading & Inspecting

#### `find-files`

Find files matching a glob pattern in a directory tree. Recursively searches
from the root directory. Respects .gitignore rules by default.

**When to use**: User says "find files", "search for files", "locate Python files",
"what files are in this directory", or "list all CSVs".

**Behavior**: `read-only`, `idempotent`

##### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pattern` | string | Yes | — | Glob pattern to match (e.g., `"*.py"`, `"**/*.json"`) |
| `root` | string (path) | No | `"."` | Root directory to search from |
| `max_depth` | integer | No | `10` | Maximum directory depth (1–100) |

##### Example

```bash
$ file-tools find-files "*.py" --root ./src --json
```

Expected output:
```json
{
  "ok": true,
  "result": [
    {"path": "src/main.py", "size": 1204},
    {"path": "src/utils.py", "size": 892}
  ],
  "meta": {"tool": "file-tools.find-files", "version": "1.0.0", "duration_ms": 34}
}
```

##### If Something Goes Wrong

| Symptom | Cause | Fix |
|---------|-------|-----|
| Empty result array | No files match the pattern | Run `find-files "*" --root <root> --json` to see what exists, then narrow your pattern |
| Exit code 10 | Root directory doesn't exist | Verify the path: `ls <root>` |
| `E1003` error | Invalid glob syntax | Remove unescaped special characters; use `"*.py"` not `*.py` |

### Modifying Files

#### `rename-files`

Rename files matching a pattern by adding or changing a suffix.

**When to use**: User says "rename files", "change extension", "bulk rename",
or "add suffix to files".

**Behavior**: `destructive`

...

## Composition Patterns

### Find Then Process

`find-files` output can be piped to `process`:

```bash
file-tools find-files "*.csv" --jsonl | file-tools process --json
```

### Safe Destructive Operations

Always preview before modifying:

```bash
# Step 1: Preview the rename plan
file-tools rename-files --pattern "*.tmp" --suffix ".bak" --dry-run --json

# Step 2: If the plan looks right, execute
file-tools rename-files --pattern "*.tmp" --suffix ".bak" --json
```

## Global Flags

| Flag | Effect |
|------|--------|
| `--json` | Output as JSON envelope: `{"ok": bool, "result": ..., "meta": {...}}` |
| `--jsonl` | Newline-delimited JSON for streaming |
| `--plain` | Unformatted text for grep/awk pipelines |
| `--quiet` | Suppress non-essential output |
| `--dry-run` | Preview actions without executing |
| `--schema` | Print JSON Schema for this command and exit |
| `--timeout N` | Maximum execution time in seconds |
| `--yes` | Skip confirmation prompts (for automation) |

## Output Format

All `--json` output uses this envelope:

```json
{
  "ok": true,
  "result": "<command-specific data>",
  "meta": {
    "tool": "file-tools.find-files",
    "version": "1.0.0",
    "duration_ms": 34,
    "truncated": false
  }
}
```

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
      "fix": "Try a broader pattern. The directory contains .py files.",
      "example": "find-files '*.py' --root ./src"
    },
    "is_retryable": true
  }
}
```

**Agent instructions**: Always check `ok` first. If `false`, read `error.suggestion.action`
to decide next step. If `is_retryable` is `true`, retry using the `example` command.

## Exit Codes

| Code | Meaning | Agent Action |
|------|---------|--------------|
| 0 | Success | Process `result` field |
| 2 | Invalid usage / bad arguments | Fix arguments per `error.suggestion` and retry |
| 10 | Not found / state error | Check resource paths |
| 30 | Permission denied | Request escalation or check file permissions |
| 50 | Timeout | Retry with `--timeout` or back off |
| 70 | Internal error | Report bug; do not retry |

## Critical Rules

- **Always use `--json` when invoking from an agent.** Human-formatted Rich output is not parseable.
- **Always check `ok` before accessing `result`.** Failed commands set `ok: false` and `result` may be null.
- **Paths are relative to CWD** unless `--root` is specified.
- **Use `--dry-run` before any destructive command.** Review the plan before executing.
- If `meta.truncated` is `true`, results were cut off. Use `--limit` and `--cursor` to paginate.

---
Generated by tooli v4.0 | Regenerate: `file-tools --agent-bootstrap`
Validate: `file-tools generate-skill --validate`
```

------

## 14. Appendix B: `tooli:agent` Source Hint Format

The compact source-level hint format for agent discovery:

```python
# tooli:agent
# name: <tool-name>
# version: <semver>
# commands: <name>(<param>:<type>[=<default>], ...) -> <return_type>
#           <name>(<param>:<type>[=<default>], ...) -> <return_type>
# flags: --json --jsonl --plain --quiet --dry-run --schema
# invoke: <tool-name> <command> [args] --json
# errors: <code>(<brief>) <code>(<brief>) ...
# skill: <tool-name> --agent-bootstrap > SKILL.md
# tooli:end
```

Parsing rules:
- Block starts with `# tooli:agent` and ends with `# tooli:end`.
- Each line starts with `# ` followed by a key-value pair.
- `commands:` can span multiple lines (continuation lines start with `#           `).
- All fields are optional except `name`.

------

*End of PRD v4.0*