# Tooli v3 → v4 Migration Guide

## Overview

Tooli v4 is a **backward-compatible** upgrade. All v3 code runs unchanged. v4 adds agent skill platform capabilities: task-oriented documentation, composition contracts, and bootstrap tooling.

## What's New

### New `@app.command()` Parameters

| Parameter | Type | Purpose |
|---|---|---|
| `when_to_use` | `str` | Prose description of when to use this command |
| `task_group` | `str` | Group commands by task category in SKILL.md |
| `pipe_input` | `dict` | Input pipe contract (format, schema, description) |
| `pipe_output` | `dict` | Output pipe contract |
| `expected_outputs` | `list[dict]` | Expected output for each example |
| `recovery_playbooks` | `dict[str, list[str]]` | Error recovery steps per scenario |

### New Types

```python
from tooli import PipeContract

# Define pipe contracts
output = PipeContract(format="json", description="List of items").to_dict()

@app.command("list-items", pipe_output=output)
def list_items() -> list:
    ...
```

### New Global Flag

`--agent-bootstrap` — generates a deployable SKILL.md and exits. Works on any command.

### New Generator

The `generate-skill` command now uses v4 generator by default with a `--target` option:
- `generic-skill` — universal agent format (default)
- `claude-skill` — optimized for Claude models
- `claude-code` — optimized for Claude Code CLI

### New Modules

| Module | Purpose |
|---|---|
| `tooli.pipes` | `PipeContract` dataclass |
| `tooli.bootstrap` | `--agent-bootstrap` logic |
| `tooli.docs.skill_v4` | v4 SKILL.md generator |
| `tooli.docs.claude_md_v2` | Enhanced CLAUDE.md generator |
| `tooli.docs.source_hints` | Source-level `# tooli:agent` blocks |
| `tooli.init` | `tooli init` project scaffolding |
| `tooli.eval.coverage` | Metadata coverage reporter |
| `tooli.eval.skill_roundtrip` | LLM-powered skill evaluation |
| `tooli.upgrade` | Metadata improvement suggestions |

## Migration Steps

### Step 1: Update Version

```bash
pip install --upgrade tooli>=4.0
```

### Step 2: Add v4 Metadata (Optional)

Add `when_to_use`, `task_group`, and other v4 fields to your commands for richer documentation:

```python
@app.command(
    "search",
    when_to_use="Search for items by keyword or pattern",
    task_group="Query",
    pipe_output=PipeContract(format="json", description="Search results").to_dict(),
    recovery_playbooks={
        "No results": ["Try a broader search term", "Check spelling"],
    },
)
def search(query: str) -> list:
    ...
```

### Step 3: Run Upgrade Analysis

```bash
# See what metadata you're missing
python -c "from your_app import app; from tooli.upgrade import analyze_metadata; print(analyze_metadata(app))"

# Check coverage
python -c "from your_app import app; from tooli.eval.coverage import eval_coverage; print(eval_coverage(app))"
```

### Step 4: Regenerate SKILL.md

```bash
your-app generate-skill --target generic-skill --output SKILL.md
# or
your-app any-command --agent-bootstrap > SKILL.md
```

## What's New in v4.1

v4.1 adds the **Caller-Aware Agent Runtime** — a detection system that identifies who is calling your CLI (human, AI agent, CI/CD, container) and adapts behavior accordingly.

### TOOLI_CALLER Convention

Set `TOOLI_CALLER` in the environment to identify your agent with 100% confidence:

```bash
TOOLI_CALLER=claude-code TOOLI_CALLER_VERSION=1.5.3 mytool list --json
```

This gives you:
- Immediate classification (no heuristic probing)
- Caller metadata in the JSON envelope (`caller_id`, `caller_version`, `session_id`)
- Adaptive confirmation (agents with `--yes` skip prompts)
- Structured YAML help from `--help`

### New Modules

| Module | Purpose |
|---|---|
| `tooli.detect` | 5-category caller detection (convention + heuristics) |

### New Exports

```python
from tooli import CallerCategory, ExecutionContext, detect_execution_context
```

### New Builtin Command

`detect-context` — inspect the current execution context (hidden from `--help`):

```bash
TOOLI_CALLER=my-agent mytool detect-context --json
```

See [AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md) for the full integration guide.

## Breaking Changes

**None.** All v3 and v4.0 APIs continue to work without modification.

## SKILL.md Format Changes

v4 SKILL.md has a different section order and new sections compared to v3:

| v3 Section | v4 Section |
|---|---|
| Quick Reference | Quick Reference |
| Installation | Installation |
| Global Flags | Commands (task-grouped) |
| Output Envelope Format | Composition Patterns (new) |
| Commands | Global Flags |
| Error Catalog | Output Format |
| Workflow Patterns | Error Catalog + Exit Codes |
| Critical Rules | Critical Rules |

New per-command sections:
- **When to use** — from `when_to_use` or auto-synthesized
- **If Something Goes Wrong** — from `recovery_playbooks` + `error_codes`
- **Expected output** — from `expected_outputs` or `output_example`
