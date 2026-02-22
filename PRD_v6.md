# Tooli v6.0 — Product Requirements Document

## The Lean Agent-Native CLI Framework

**Version**: 6.0
**Author**: Brian Weisberg
**Status**: Draft
**Date**: February 2026
**Supersedes**: PRD_v5.md (v5.0)

---

## 1. Executive Summary

Tooli started with a clean idea: **write a Python function, get a CLI that agents can use.** A developer decorates a function with `@app.command()`, adds type hints, and tooli handles the rest — argument parsing, structured JSON output for agents, Rich output for humans, structured errors when things go wrong.

Between v2 and v5, that clarity eroded. Tooli accumulated seven distinct subsystems: CLI framework, documentation generation (SKILL.md, CLAUDE.md, AGENTS.md), MCP server, multi-framework export, project scaffolding, eval harness, and pipe composition. It became a platform masquerading as a library.

**v6.0 corrects course.** It applies findings from two independent red team assessments and grounds every decision in the 10 canonical scenarios that define how tooli-based tools are actually built, discovered, composed, and governed.

The guiding principle: **tooli is a CLI framework that makes agent-friendly tools. Everything else is a plugin, a separate tool, or someone else's problem.**

### What Changes in v6.0

| Area | v5.0 | v6.0 |
|---|---|---|
| **Identity** | "The Universal Agent Tool Interface" — platform | "The Lean Agent-Native CLI Framework" — library |
| **Scope** | 7 subsystems in one package | Core framework + optional extras |
| **Doc generation** | SKILL.md, CLAUDE.md, AGENTS.md built-in | Extracted to `tooli-docs` package |
| **Framework export** | `--export openai\|langchain\|adk` built-in | Extracted to `tooli-export` package |
| **MCP** | Built-in server mode | Stays as `tooli[mcp]` optional extra |
| **Scaffolding** | `tooli init`, `--from-typer` | Removed — documentation + cookiecutter |
| **Eval** | Built-in eval harness | Removed — community/separate tool |
| **Pipe contracts** | `PipeContract`, `accepts`/`produces` | Removed entirely |
| **Source hints** | `# tooli:agent` blocks | Removed entirely |
| **Python API** | `app.call()`, `TooliResult` | **Kept** — promoted to core |
| **Capabilities** | Schema declarations + STRICT enforcement | Declarations in core, enforcement in core |
| **Errors** | `suggestion` + `field` mapping | **Kept** — the differentiator |

### The Dependency Test

A feature belongs in tooli core if and only if:

1. It is required by at least 3 of the 5 Tier 1 scenarios (decorator, envelope, schema, errors, dual-mode output).
2. It does NOT require tooli to track changes in an external system it doesn't control.
3. It would break the framework's core value proposition if removed.

Features that fail this test are extracted, not deleted. They become separate packages that consume tooli's schema output.

---

## 2. Problem Analysis

### 2.1 The Bloat Problem (Red Team Finding)

Two independent assessments reached the same conclusion: tooli has lost focus.

**Assessment 1** ("Tooli Has Lost the Plot") identified 7 distinct subsystems and argued that tooli should export JSON Schema and let the ecosystem handle everything else. Key insight: *"if a feature requires tooli to track changes in an external system it doesn't control, it doesn't belong in tooli."*

**Assessment 2** ("Reclaiming Tooli") argued from Unix philosophy: tooli should be a pure, composable tool. Key insight: *"The initial authoring of code accounts for less than 10% of its total cost. The remaining 90% is the ongoing maintenance burden."*

Both assessments are directionally correct but overcorrect in places. The scenarios reveal features that the assessments would cut but that users demonstrably need:

| Assessment Recommendation | Scenario Evidence | v6.0 Decision |
|---|---|---|
| Cut MCP server entirely | Scenario 10 shows resource-first patterns saving 10x tokens | **Keep as optional extra** (`tooli[mcp]`) |
| Cut SKILL.md generation | Scenario 1-4 show agents working from schema + human CLAUDE.md | **Extract to `tooli-docs`** |
| Cut capabilities | Scenario 6 shows capability enforcement blocking unauthorized ops | **Keep declarations + enforcement in core** |
| Cut `--dry-run` | Scenario 6 shows dry-run preventing destructive ops | **Keep** — `@dry_run_support` stays |
| Cut all annotations | Scenario 8 shows `ReadOnly`/`Destructive` guiding agent behavior | **Keep** — annotations are core metadata |
| Cut Python API | Scenario 9 shows `app.call()` enabling in-process framework wrappers | **Keep** — promoted to core |
| Cut framework export | Scenario 9 shows multi-framework need | **Extract to `tooli-export`** |
| Cut error recovery playbooks | Scenario 1 shows single `suggestion` + `retry` is sufficient | **Simplify** — single suggestion only |

### 2.2 What the Scenarios Actually Require

Analyzing all 10 scenarios for which tooli features they exercise:

**Used by 5/5 Tier 1 scenarios (irreducible core):**
- `@app.command()` decorator with type hints
- `{ok, result, error, meta}` envelope
- JSON Schema via `--schema`
- Structured errors with `suggestion` and `retry`
- Dual-mode output (Rich TTY / JSON agent)

**Used by 4/5 Tier 1 scenarios:**
- Error `field` mapping (Scenarios 1, 2, 4, 5)
- `--dry-run` support (Scenarios 1, 3, 6, 8)

**Used by Tier 2 scenarios only:**
- Capabilities declarations and enforcement (Scenario 6)
- `ReadOnly`/`Destructive`/`Idempotent` annotations (Scenarios 6, 7, 8)
- MCP resources (Scenario 10)
- Framework export (Scenario 9)
- AGENTS.md generation (Scenario 9)
- SKILL.md / CLAUDE.md generation (referenced but human-authored docs preferred)
- `TOOLI_CALLER` convention (Scenario 9)
- Python API `app.call()` (Scenario 9)
- Deprecation metadata in schema (Scenario 5)

### 2.3 The Real Competitive Advantage

Tooli's moat is not breadth of features — it's that **one decorated function produces a CLI that both humans and agents can use**. The envelope, the schema, and the structured errors are what make tools agent-friendly. Everything else amplifies that core but is not the core itself.

Compare:
- **Typer**: Great human UX, zero agent UX
- **Raw JSON APIs**: Zero human UX, decent agent UX
- **MCP servers**: No human UX, good agent UX
- **Tooli**: Both — and that's the entire product

---

## 3. Goals and Non-Goals

### 3.1 Goals

| # | Goal | Success Metric |
|---|---|---|
| G1 | **Lean core**: Core package has zero non-essential subsystems | `tooli/` directory has no doc generators, no export, no scaffolding, no eval |
| G2 | **Python API in core**: `app.call()` and `TooliResult` are first-class | All 18 example apps callable via `app.call()` |
| G3 | **Capabilities in core**: Declare-then-enforce pattern works end-to-end | STRICT mode blocks unauthorized capabilities before function body runs |
| G4 | **Clean extraction**: Doc generators and export work as separate packages | `tooli-docs` and `tooli-export` consume `--schema` output |
| G5 | **Deprecation path**: Removed features have migration guides | Every cut feature has a documented alternative |
| G6 | **Scenario validation**: All 10 scenarios pass with v6 feature set | Tier 1 scenarios use only core; Tier 2 scenarios use core + optional extras |
| G7 | **Smaller surface**: Public API fits on one page | Developer can learn tooli in 15 minutes |

### 3.2 Non-Goals

- **Rewrite**: v6 is a subtraction, not a rewrite. Existing code stays; excess is extracted.
- **Breaking `@app.command()`**: The decorator API is unchanged. All existing apps work on v6.
- **Killing extracted features**: `tooli-docs` and `tooli-export` ship simultaneously. Nothing disappears.
- **Unix purism**: The GM assessment's streaming-only, zero-dependency vision is aspirational but impractical for a Python framework that depends on Pydantic. We take the directional advice without the dogma.

---

## 4. Architecture: What Stays, What Moves, What Dies

### 4.1 The Irreducible Core (stays in `tooli/`)

These features define tooli. They are polished to perfection in v6.

#### 4.1.1 The Decorator-to-CLI Pipeline

```python
from tooli import Tooli, Annotated, Argument, Option

app = Tooli(name="mytool", version="6.0.0")

@app.command(
    annotations=ReadOnly | Idempotent,
    capabilities=["fs:read"],
)
def find_files(
    pattern: Annotated[str, Argument(help="Glob pattern")],
    root: Annotated[str, Option(help="Root directory")] = ".",
) -> list[dict]:
    """Find files matching a pattern."""
    ...
```

The developer gets:
- `mytool find-files "*.py"` — Rich table for humans
- `mytool find-files "*.py" --json` — `{ok, result, error, meta}` envelope
- `mytool find-files "*.py" --jsonl` — one result per line, streaming
- `mytool --schema` — JSON Schema for all commands
- Structured errors with codes, categories, suggestions, and field mapping on failure

**Scenario validation**: Scenarios 1-5 use only this.

#### 4.1.2 Structured Error Contract

```python
from tooli.errors import InputError, StateError, AuthError, Suggestion

raise InputError(
    message="Invalid glob pattern: unmatched bracket",
    code="E1003",
    field="pattern",
    suggestion=Suggestion(
        action="fix",
        fix="Close the bracket in the pattern",
        retry=True,
    ),
)
```

Envelope output:
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
      "retry": true
    },
    "is_retryable": true
  }
}
```

The error contract enables:
- **Reflection pattern** (Scenario 1): agent reads `retry: true`, retries with suggested fix
- **Field targeting** (Scenario 4): agent knows which parameter to change
- **Escalation** (Scenario 2): agent knows when NOT to retry (auth/policy errors)
- **Migration** (Scenario 5): deprecated flags produce structured migration errors

**Simplification from v5**: Error recovery playbooks (multi-step) are removed. A single `suggestion` with `action`, `fix`, `example`, and `retry` is the right level of abstraction. The agent decides what to do with it.

#### 4.1.3 Python API

```python
from myapp import app

# Sync
result = app.call("find-files", pattern="*.py", root="./src")
assert result.ok
for f in result.result:
    print(f["path"])

# Async
result = await app.acall("find-files", pattern="*.py")

# Generated accessor
result = app.find_files(pattern="*.py")
```

`TooliResult[T]` is the return type:

```python
@dataclass(frozen=True)
class TooliResult[T]:
    ok: bool
    result: T | None = None
    error: TooliError | None = None
    meta: dict[str, Any] | None = None

    def unwrap(self) -> T:
        """Return result or raise ToolError."""
        if not self.ok:
            raise self.error.to_exception()
        return self.result
```

The Python API uses the same pipeline as CLI invocation (validation, capability checks, telemetry, error handling) but skips Click/argparse parsing and output mode routing. Results stay as Python objects.

**Why this stays in core**: The Python API is how framework wrappers call tooli commands in-process. Without it, every integration goes through subprocess. Scenario 9 depends on this. The API is also how `tooli-export` generates its wrappers — they call `app.call()` internally.

#### 4.1.4 Behavioral Annotations

```python
from tooli import ReadOnly, Destructive, Idempotent, OpenWorld

@app.command(annotations=Destructive)
def delete_files(pattern: str) -> dict:
    ...

@app.command(annotations=ReadOnly | Idempotent)
def list_files(path: str) -> list[dict]:
    ...
```

Annotations appear in JSON Schema and inform agent behavior:
- `ReadOnly`: Agent can call without confirmation
- `Destructive`: Agent should confirm or use `--dry-run`
- `Idempotent`: Safe to retry on transient failures
- `OpenWorld`: Tool may produce results not fully described by schema

**Scenario validation**: Scenarios 6, 7, 8 depend on annotations to guide agent safety decisions.

#### 4.1.5 Capability Declarations and Enforcement

```python
@app.command(capabilities=["fs:read", "net:read"])
def scan_logs(path: str) -> list[dict]:
    """Scan logs for credential leaks."""
    ...
```

Capabilities appear in `--schema` output. In STRICT mode (`TOOLI_SECURITY=strict`), capabilities are enforced at runtime:

```bash
export TOOLI_ALLOWED_CAPABILITIES="fs:read,net:read,db:read"
```

A tool requesting `fs:write` when only `fs:read` is allowed gets blocked before the function body runs:

```json
{
  "ok": false,
  "error": {
    "code": "E2002",
    "category": "auth",
    "message": "Capability 'fs:write' is not in the allowed set",
    "suggestion": {
      "action": "contact_admin",
      "fix": "Request 'fs:write' capability approval from your security team"
    }
  }
}
```

**Capability taxonomy** (unchanged from v5):

| Capability | Description |
|---|---|
| `fs:read` | Reads files from the filesystem |
| `fs:write` | Writes/modifies files |
| `fs:delete` | Deletes files |
| `net:read` | Makes outbound HTTP requests |
| `net:write` | Sends data to external services |
| `proc:spawn` | Spawns subprocesses |
| `env:read` | Reads environment variables |
| `state:mutate` | Modifies persistent state |
| `none` | Pure computation, no side effects |

**Why this stays in core**: The declare-then-enforce pattern requires runtime integration with `TooliCommand.invoke()`. It can't be a plugin because it must intercept execution before the function body runs. Scenario 6 is the validation case.

#### 4.1.6 Dry-Run Support

```python
from tooli.dry_run import dry_run_support, record_dry_action

@app.command(annotations=Destructive, capabilities=["fs:delete"])
@dry_run_support
def prune(path: str, older_than: str = "30d") -> dict:
    """Delete files older than the specified age."""
    ...
```

`--dry-run` previews destructive operations. The decorator handles the flag and routing; the developer implements what "preview" means for their command.

#### 4.1.7 Deprecation Metadata

```python
@app.command(
    deprecated="Use --output-format instead of --format",
    deprecated_version="2.0.0",
)
def run(
    source: str,
    format: Annotated[str, Option(help="[DEPRECATED]")] = "csv",
    output_format: Annotated[str | None, Option(help="Output format")] = None,
) -> dict:
    ...
```

Deprecation metadata appears in schema. Agents auto-migrate. Removed flags produce structured migration errors. Scenario 5 validates this.

#### 4.1.8 Caller Detection

The `TOOLI_CALLER` convention and `tooli/detect.py` module stay in core. Caller metadata flows through the envelope:

```json
{
  "meta": {
    "tool": "mytool.find-files",
    "caller_id": "claude-code",
    "session_id": "sess_abc123"
  }
}
```

Caller categories: `HUMAN`, `AI_AGENT`, `CI_CD`, `CONTAINER`, `PYTHON_API`, `UNKNOWN_AUTOMATION`.

#### 4.1.9 Core Module Inventory

After extraction, `tooli/` contains:

| Module | Purpose |
|---|---|
| `tooli/app.py` | `Tooli` class, command registration, builtins |
| `tooli/command.py` | `TooliCommand`, invoke pipeline, global flags |
| `tooli/command_meta.py` | `CommandMeta` dataclass |
| `tooli/errors.py` | `ToolError` hierarchy with `field` and `suggestion` |
| `tooli/output.py` | `OutputMode` enum, mode resolution |
| `tooli/envelope.py` | JSON envelope wrapper |
| `tooli/schema.py` | JSON Schema generation |
| `tooli/annotations.py` | `ReadOnly`, `Destructive`, `Idempotent`, `OpenWorld` |
| `tooli/input.py` | `StdinOr[T]`, `SecretInput[T]` |
| `tooli/dry_run.py` | `@dry_run_support`, `record_dry_action()` |
| `tooli/auth.py` | `AuthContext`, scope-based access control |
| `tooli/capabilities.py` | Capability taxonomy and enforcement |
| `tooli/python_api.py` | `TooliResult`, `app.call()`, `app.acall()` |
| `tooli/detect.py` | Caller detection, `TOOLI_CALLER` convention |
| `tooli/pagination.py` | Cursor-based pagination |
| `tooli/telemetry.py` | OTel span support |
| `tooli/manifest.py` | `--agent-manifest` JSON output |

**Removed from core** (see Section 4.2-4.3):
- `tooli/docs/skill_v4.py`
- `tooli/docs/claude_md_v2.py`
- `tooli/docs/agents_md.py`
- `tooli/docs/source_hints.py`
- `tooli/export.py`
- `tooli/init.py`
- `tooli/upgrade.py`
- `tooli/pipes.py`
- `tooli/eval/`
- `tooli/bootstrap.py`

### 4.2 Extracted to Separate Packages

These features are valuable but don't belong in the core framework. They are extracted into packages that consume tooli's `--schema` output and Python API.

#### 4.2.1 `tooli-docs` — Documentation Generation

Contains: SKILL.md generator, CLAUDE.md generator, AGENTS.md generator, source hints, token-budget tiering, `upgrade-metadata`.

```bash
pip install tooli-docs

# Generate docs from any tooli app's schema
tooli-docs skill mytool > SKILL.md
tooli-docs claude-md mytool > CLAUDE.md
tooli-docs agents-md mytool > AGENTS.md

# Or from a schema file
mytool --schema > schema.json
tooli-docs skill --from-schema schema.json > SKILL.md
```

**Why extract**: SKILL.md is a Claude-specific format. AGENTS.md is GitHub Copilot's convention. CLAUDE.md is Claude Code's convention. Each format changes when its platform changes. Tooli shouldn't track those changes. The generators read `--schema` output, which is tooli's stable contract. If Claude changes SKILL.md format, `tooli-docs` updates. Tooli core doesn't need a release.

**Migration path**: In v6.0, the built-in `generate-skill`, `generate-claude-md`, and `generate-agents-md` commands emit a deprecation warning pointing users to `tooli-docs`. They are removed in v7.0.

#### 4.2.2 `tooli-export` — Framework Export

Contains: OpenAI Agents SDK wrapper generator, LangChain wrapper generator, Google ADK config generator, Python API wrapper generator.

```bash
pip install tooli-export

# Generate framework wrappers
tooli-export openai mytool > openai_tools.py
tooli-export langchain mytool > langchain_tools.py
tooli-export adk mytool > adk_agent.yaml
tooli-export python mytool > typed_api.py
```

**Why extract**: Each export target must track API changes from its framework vendor. When OpenAI changes `@function_tool` signatures, `tooli-export` updates. When LangChain changes `@tool`, `tooli-export` updates. Tooli core is insulated. This directly follows the dependency test.

Generated wrappers use `app.call()` (Python API) for in-process invocation or `subprocess.run()` for isolation, depending on user preference.

**Migration path**: In v6.0, the built-in `export` command emits a deprecation warning. Removed in v7.0.

#### 4.2.3 MCP Server (`tooli[mcp]`)

Stays as an optional extra (already is). No change from v5 except clarifying the boundary:

```bash
pip install tooli[mcp]

# Serve tooli app as MCP server
mytool mcp serve --transport stdio
```

MCP resources, `skill://` URIs, and tool annotations flow through MCP when installed. The core framework is unaware of MCP internals.

**Why keep as optional extra** (not extract to separate package): The MCP integration hooks into `Tooli.serve_mcp()` which needs access to command registration internals. It's more natural as an optional dependency than a fully separate package. Scenario 10 validates the resource-first pattern.

### 4.3 Removed Entirely

These features are cut. No extraction. They are replaced by documentation, shell conventions, or the realization that they solve problems that don't exist.

| Feature | Why It's Cut | Alternative |
|---|---|---|
| **Pipe contracts** (`PipeContract`, `accepts`/`produces`) | Zero proven demand. Unix pipes and JSONL already work. | Document JSONL streaming patterns |
| **Source hints** (`# tooli:agent` blocks) | Custom comment format no tool/IDE understands. Agents read schemas, not source comments. | JSON Schema is the discovery mechanism |
| **`tooli init` scaffolding** | Used once per project, then never again. | Cookiecutter template + "Getting Started" docs |
| **`--from-typer` migration** | Simple enough to document in one page. | Migration guide: replace imports, add return types |
| **Eval harness** (`eval agent-test`, `validate --ptc`) | Testing tools, not CLI framework features. | Community tool or CI recipe in docs |
| **Token-budget tiering** | Optimizing for a constraint (context windows) that's expanding rapidly and that the consumer should manage. | Removed |
| **Error recovery playbooks** (multi-step) | Over-engineered. Single `suggestion` is the right abstraction. | Single `suggestion` with `retry` boolean |
| **`--agent-bootstrap` flag** | Just the SKILL.md generator triggered by a flag. | Use `tooli-docs` directly |
| **Coverage reporter** (`eval/coverage.py`) | Metadata coverage is useful during development, not at runtime. | Lint rule or CI check |
| **Skill roundtrip eval** (`eval/skill_roundtrip.py`) | LLM-powered eval requires API keys and is non-deterministic. | Separate testing tool |

### 4.4 Handoff Metadata — Demoted to Documentation

v5 proposed `handoffs` and `delegation_hint` as `@app.command()` parameters:

```python
@app.command(
    handoffs=[{"command": "deploy", "when": "After successful build"}],
    delegation_hint="Use an agent with filesystem access",
)
```

**v6 decision**: Demote to optional metadata only. Handoffs are declarative hints, not executable logic. They add complexity to the decorator API for metadata that belongs in human-authored CLAUDE.md files. Jordan's deployment workflow (Scenario 2) demonstrates that workflow sequencing is a human judgment call, not schema metadata.

Handoffs remain available as optional `CommandMeta` fields for tools that want them, but they are not promoted or documented as a primary feature. The CLAUDE.md is where workflow knowledge lives.

---

## 5. Implementation Phases

### Phase 1: Core Hardening (P0)

**Goal**: Polish the irreducible core. Everything that stays gets better.

1. **Python API stabilization** — Ensure `app.call()`, `app.acall()`, `TooliResult` work for all 18 example apps. Add generated `app.<command>()` accessors.
2. **Error field mapping** — Ensure all built-in error classes support `field` parameter. Update all `InputError` raises across the codebase.
3. **Capability enforcement** — Wire STRICT mode enforcement into `TooliCommand.invoke()`. Capabilities checked against `TOOLI_ALLOWED_CAPABILITIES` before function body runs.
4. **Caller detection integration** — Wire `tooli/detect.py` into envelope, telemetry, and recording. `TOOLI_CALLER` convention documented.
5. **Deprecation infrastructure** — Ensure deprecated flags produce structured migration errors (Scenario 5 pattern).
6. **Native backend as default** — Drop Typer backend entirely. One backend, no choice, less code.

**Exit criteria**: All 259+ existing tests pass. All 18 example apps work via CLI and Python API. STRICT mode blocks unauthorized capabilities.

### Phase 2: Extraction (P0)

**Goal**: Move non-core features to separate packages without breaking existing users.

1. **Create `tooli-docs` package** — Extract `skill_v4.py`, `claude_md_v2.py`, `agents_md.py`, `source_hints.py` into a new package. Package reads `--schema` output.
2. **Create `tooli-export` package** — Extract `export.py` into a new package. Package uses `app.call()` or `subprocess` to generate framework wrappers.
3. **Add deprecation warnings** — Built-in `generate-skill`, `generate-claude-md`, `generate-agents-md`, and `export` commands warn: "This command is moving to `tooli-docs` / `tooli-export`. Install it with `pip install tooli-docs`."
4. **Remove dead code** — Delete `tooli/pipes.py`, `tooli/docs/source_hints.py` (from core), `tooli/init.py`, `tooli/upgrade.py`, `tooli/eval/`.
5. **Update `pyproject.toml`** — Remove extracted code from core package. Add `tooli-docs` and `tooli-export` as separate packages in a monorepo or separate repos.

**Exit criteria**: `pip install tooli` installs only the core. `pip install tooli-docs` provides doc generators. `pip install tooli-export` provides framework export. All three work independently.

### Phase 3: Documentation (P1)

**Goal**: Replace removed features with documentation.

1. **Migration guide** (v5 → v6) — Document every removed feature and its alternative.
2. **"Getting Started" rewrite** — The entire framework explained in one page.
3. **Cookbook: "Using tooli with Claude Code"** — Replace built-in Claude integration with a recipe.
4. **Cookbook: "Using tooli with MCP"** — Resource-first patterns, `mcp serve` configuration.
5. **Cookbook: "Migrating from Typer"** — Replace `--from-typer` with a one-page guide.
6. **Cookbook: "Multi-framework integration"** — How to use `tooli-export` or write your own 5-line wrapper.
7. **Cookiecutter template** — Replace `tooli init` with a community-standard template.

**Exit criteria**: A developer can go from zero to a working tooli app in 15 minutes using only documentation.

### Phase 4: Cleanup (P2)

**Goal**: Remove deprecation shims and finalize the lean core.

1. Remove deprecated built-in commands (`generate-skill`, `generate-claude-md`, `generate-agents-md`, `export`).
2. Remove `--agent-bootstrap` global flag.
3. Remove any remaining references to extracted code.
4. Final audit: `tooli/` directory should contain only the modules listed in Section 4.1.9.

**Exit criteria**: `wc -l tooli/*.py` is significantly smaller than v5. Public API fits on one page.

---

## 6. Scenario Validation Matrix

Every v6 feature maps to at least one scenario. Every scenario is satisfiable with v6's feature set.

| Scenario | Tier | Core Features Used | Optional Extras Used |
|---|---|---|---|
| 1. Diagnostic Skill Lifecycle | 1 | decorator, envelope, schema, errors+suggestion+retry | — |
| 2. Platform Team's Deployment Toolchain | 1 | decorator, envelope, schema, errors, dual-mode output | — |
| 3. Independent Tools That Compose | 1 | envelope, schema, errors, `--dry-run` | — |
| 4. Agent as Tool Author | 1 | decorator, schema, envelope | — |
| 5. CI/CD as First-Class Consumer | 1 | envelope, errors+suggestion, deprecation metadata, schema | — |
| 6. Capability Enforcement & Security | 2 | capabilities, annotations, dry-run, caller detection | — |
| 7. Cross-Team Tool Discovery | 2 | schema, annotations, capabilities | — |
| 8. Customer Support Workflows | 2 | annotations, capabilities, mandatory params | — |
| 9. Global Skill Mesh | 2 | Python API, caller detection | `tooli-export`, `tooli-docs` |
| 10. Resource-First Subagent Ops | 2 | envelope, schema | `tooli[mcp]` |

**Key observations**:
- All Tier 1 scenarios use only core features. No optional extras required.
- Tier 2 scenarios 6-8 use only core features (capabilities, annotations, dry-run are in core).
- Only Scenarios 9 and 10 require optional extras — and both work in degraded mode without them.

---

## 7. What the Lean Tooli Looks Like

After v6, tooli's entire pitch fits in one paragraph:

> **Tooli turns Python functions into CLI tools that agents love.** Decorate a function with `@app.command()`, add type hints, and get: a human-friendly CLI with Rich output, a machine-friendly JSON API with structured envelope, JSON Schema export for agent discovery, structured errors with suggestions for agent self-correction, capability declarations for security enforcement, and a Python API for in-process invocation. That's it. That's the whole framework.

The developer experience:

```python
from tooli import Tooli, Annotated, Argument, Option, ReadOnly

app = Tooli(name="mytool", version="1.0.0")

@app.command(annotations=ReadOnly, capabilities=["fs:read"])
def find_files(
    pattern: Annotated[str, Argument(help="Glob pattern")],
    root: Annotated[str, Option(help="Root directory")] = ".",
) -> list[dict]:
    """Find files matching a pattern."""
    return [{"path": str(p)} for p in Path(root).rglob(pattern)]
```

```bash
# Human
$ mytool find-files "*.py"
┌──────────────────────┐
│ path                 │
├──────────────────────┤
│ src/main.py          │
│ src/utils.py         │
│ tests/test_main.py   │
└──────────────────────┘

# Agent
$ mytool find-files "*.py" --json
{"ok": true, "result": [{"path": "src/main.py"}, ...], "meta": {...}}

# Schema
$ mytool --schema
{"commands": {"find-files": {"parameters": {...}, "capabilities": ["fs:read"], ...}}}

# Python API
>>> from myapp import app
>>> result = app.call("find-files", pattern="*.py")
>>> result.ok
True
```

Five things. All done extremely well.

---

## 8. Migration Guide (v5 → v6)

### 8.1 No Breaking Changes to `@app.command()`

All existing decorated functions work unchanged. The decorator API is backward-compatible.

### 8.2 Feature Migration

| v5 Feature | v6 Alternative | Migration Effort |
|---|---|---|
| `mytool generate-skill` | `pip install tooli-docs && tooli-docs skill mytool` | 1 line |
| `mytool generate-claude-md` | `pip install tooli-docs && tooli-docs claude-md mytool` | 1 line |
| `mytool generate-agents-md` | `pip install tooli-docs && tooli-docs agents-md mytool` | 1 line |
| `mytool export --target openai` | `pip install tooli-export && tooli-export openai mytool` | 1 line |
| `tooli init` | `cookiecutter gh:weisberg/tooli-template` | 1 line |
| `tooli init --from-typer` | Follow migration guide in docs | 5 minutes |
| `PipeContract` | Remove — use JSONL for streaming composition | Delete unused code |
| `# tooli:agent` blocks | Remove — agents read `--schema`, not source | Delete comments |
| `eval agent-test` | Use pytest with `app.call()` | Write standard tests |

### 8.3 Deprecation Timeline

- **v6.0**: Extracted commands still work but emit deprecation warnings.
- **v6.1**: Last release with deprecated built-in commands.
- **v7.0**: Deprecated commands removed. Core only.

---

## 9. Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Core package size (LoC) | 30%+ reduction from v5 | `wc -l tooli/*.py` |
| Public API surface | Fits on one page | Count of exported symbols |
| Python API correctness | 100% | All 18 example apps callable via `app.call()` |
| Existing test pass rate | 100% | All tests pass unchanged |
| New test count | ≥50 | Python API, capabilities enforcement, caller detection |
| Scenario coverage | 10/10 | All scenarios satisfiable with v6 features |
| Time to first tool | <15 min | Measure with new developer |
| `tooli-docs` adoption | 80%+ of existing doc generation users | Install metrics |
| `tooli-export` adoption | 80%+ of existing export users | Install metrics |

---

## 10. Open Questions

1. **Monorepo or multi-repo for extracted packages?** A monorepo (`packages/tooli-docs/`, `packages/tooli-export/`) simplifies development and testing. Separate repos give extracted packages full independence. Recommendation: start with monorepo, split later if needed.

2. **Should `tooli-docs` be able to generate docs for non-tooli CLIs?** If `tooli-docs` reads JSON Schema, it could generate SKILL.md for any tool that exports schema. This expands its audience beyond tooli users. Recommendation: yes, design for this from the start.

3. **Should `StdinOr[T]` stay in core or move to a contrib module?** It's a genuinely useful type helper used by multiple example apps. The first assessment suggested extracting it. Recommendation: keep in core — it's small, useful, and doesn't track external systems.

4. **How aggressive should the deprecation timeline be?** The current plan gives one minor version (v6.0-v6.1) with deprecation warnings before removal in v7.0. Enterprise users may want longer. Recommendation: 6 months minimum before removal.

5. **Should `--agent-manifest` stay?** It's the JSON Schema output repackaged with additional metadata (capabilities, annotations, caller convention). It's useful for agent platforms that want more than raw schema. Recommendation: keep, but simplify — it should be a thin wrapper around `--schema` output with annotations added.

---

## 11. Conclusion

Tooli's original insight — that CLI tools need to be agent-friendly — is more true in 2026 than when the project started. But the response to that insight was to absorb every adjacent problem into the framework. The result was a project that was difficult to explain, difficult to evaluate, and difficult to maintain.

v6.0 corrects this by applying a simple filter: **does this feature make a Python function into a better CLI tool for agents?** If yes, it stays. If it's about generating docs for a specific platform, exporting to a specific framework, or scaffolding projects — it's a separate tool that consumes tooli's output.

The core becomes smaller, sharper, and more defensible. The ecosystem grows around it. And the pitch returns to what it always should have been:

**Write a Python function. Get a CLI that agents love.**

---

*End of PRD v6.0*
