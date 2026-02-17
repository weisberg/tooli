# Tooli v4.1 — Caller-Aware Agent Runtime

## Integrating the TOOLI_CALLER Convention into the Framework

**Version**: 4.1
**Author**: Brian Weisberg
**Status**: Draft
**Date**: February 2026
**Builds on**: PRD_v4.md (v4.0)

------

## 1. Executive Summary

Tooli v4.0 delivered the Agent Skill Platform: gold-standard SKILL.md generation, `--agent-bootstrap`, pipe contracts, and composition inference. But there's a gap between how tooli *documents* itself to agents and how it *behaves* when agents actually call it.

Today, tooli's runtime behavior adapts to agents using a simple heuristic: check `TOOLI_AGENT_MODE`, check `TOOLI_OUTPUT`, fall back to TTY detection. This works for output mode selection, but it's blind to *who* is calling and *why*. Meanwhile, a comprehensive caller detection system (`docs/detect.py`) and agent integration protocol (`docs/AGENT_INTEGRATION.md`) already exist — fully tested, cross-platform, supporting 20+ well-known agents — but they sit outside the framework, unintegrated.

**v4.1 bridges this gap.** It moves the detection module into `tooli/`, wires it into the command pipeline, and makes every tooli-built CLI caller-aware. When Claude Code invokes a tooli tool, the tool knows it's Claude Code and can tailor output format, error verbosity, confirmation behavior, telemetry tags, and SKILL.md generation accordingly. When an unknown automation calls, tooli still adapts gracefully via heuristics. When a human calls, Rich output works exactly as before.

This is not about adding new features for tool authors. It's about making the features they already have — structured output, error recovery, dry-run, annotations — work *better* by knowing who's on the other end.

### What's New in v4.1 vs v4.0

| Capability | v4.0 | v4.1 |
|---|---|---|
| Agent detection | TTY check + `TOOLI_AGENT_MODE` env var | Full caller detection: TOOLI_CALLER convention + 5-signal heuristic triangulation |
| Caller identity | Unknown | Named: "Claude Code", "Cursor", "LangChain", etc. with confidence scores |
| Session correlation | None | `TOOLI_SESSION_ID` threaded through telemetry, eval recordings, and envelope meta |
| Output adaptation | Binary (human/agent) | Caller-specific: JSON defaults, token budgets, error verbosity tuned per agent class |
| SKILL.md caller hints | Generic "use --json" | Caller-specific invocation patterns in generated docs |
| `detect-context` command | Not available | Built-in diagnostic showing exactly how tooli sees the current environment |
| Agent integration docs | External file in `docs/` | Auto-included in generated SKILL.md and CLAUDE.md |
| CI/CD awareness | None | CI pipelines detected separately from agents; output/behavior adapted |
| Container detection | None | Docker/K8s/WSL detected; affects timeout defaults, path assumptions |

------

## 2. Problem Analysis

### 2.1 The Current Detection Gap

The runtime detection in `tooli/command.py` (`_is_agent_mode()`) is a 10-line function:

```python
def _is_agent_mode(ctx, mode):
    if os.getenv("TOOLI_AGENT_MODE") in {"1", "true", "yes", "on"}:
        return True
    if os.getenv("TOOLI_OUTPUT") in {"json", "jsonl"}:
        return True
    if ctx and mode in {JSON, JSONL}:
        return True
    return not stdout.isatty()
```

This returns a boolean. It doesn't know:
- **Who** is calling (Claude Code? Cursor? A cron job? A Docker healthcheck?)
- **What confidence** the detection has (is this definitely an agent, or maybe a piped human command?)
- **What session** this belongs to (is this the same agent task as the last 5 calls?)
- **What environment** the tool runs in (Docker? CI? WSL? Bare metal?)

Meanwhile, `docs/detect.py` (780 lines, 159 tests) answers all of these questions through:
1. **TOOLI_CALLER convention** — 100% confidence, zero overhead when agents self-identify
2. **Environment variable fingerprints** — detects Claude Code, Cursor, Copilot, Aider, Devin, LangChain, etc. by their characteristic env vars
3. **Process tree inspection** — identifies agent parent processes (node, python wrappers)
4. **Container/sandbox detection** — Docker, Kubernetes, WSL, LXC
5. **Call stack inspection** — detects in-process frameworks (LangChain, AutoGen, CrewAI)

### 2.2 What Integration Enables

With caller identity available in the command pipeline, tooli can:

| Scenario | Current Behavior | With Caller Detection |
|---|---|---|
| Claude Code calls a destructive command | Prompts for confirmation (may hang) | Auto-applies `--yes` when `TOOLI_CALLER=claude-code` (Claude Code handles its own approval) |
| Cursor runs `--help` | Full Rich-formatted help | Returns `--help-agent` style compact output |
| CI pipeline runs a command | JSON output (TTY heuristic) | JSON output (CI detected at confidence 0.95) + CI-appropriate exit codes |
| LangChain tool wrapper calls | JSON output (TTY heuristic) | JSON output + `caller_id` in envelope meta for observability |
| Unknown agent calls | JSON output (TTY heuristic) | JSON output + warning in envelope: "Set TOOLI_CALLER for better integration" |
| Human in terminal | Rich output | Rich output (unchanged — human detection confidence high) |

### 2.3 The TOOLI_CALLER Convention

The convention defined in `docs/AGENT_INTEGRATION.md` is the primary integration mechanism. It's simple: agents set an environment variable before invoking tooli CLIs.

```bash
TOOLI_CALLER=claude-code mytool list --json
```

This gives tooli 100% confidence with zero overhead — no process tree inspection, no filesystem probing. The convention is already documented with integration examples for:
- Shell (one-shot and session-wide)
- Python subprocess
- Node.js child_process
- Docker (build-time and runtime)
- LangChain/LangGraph tool wrappers
- GitHub Actions

**The integration guide is ready.** What's missing is the framework consuming it.

------

## 3. Goals & Non-Goals

### 3.1 Goals

| # | Goal | Success Metric |
|---|---|---|
| G1 | **Move detection into `tooli/`**: `docs/detect.py` becomes `tooli/detect.py`, a first-class module | `from tooli.detect import detect_execution_context` works |
| G2 | **Wire detection into command pipeline**: `_is_agent_mode()` replaced by `ExecutionContext`-aware logic | `ctx.meta["tooli_execution_context"]` is an `ExecutionContext` during every command invocation |
| G3 | **Caller identity in envelope meta**: JSON output includes `caller_id` and `session_id` when available | `"meta": {"caller_id": "claude-code", "session_id": "sess-abc123", ...}` |
| G4 | **Caller-adaptive behavior**: Output mode, confirmation prompts, error verbosity, and help format adapt to detected caller | Claude Code gets auto-`--yes` on non-destructive confirms; CI gets plain exit codes; humans get Rich |
| G5 | **`detect-context` built-in command**: Any tooli app can diagnose how it sees the current environment | `mytool detect-context --json` returns full `ExecutionContext` |
| G6 | **SKILL.md integration hints**: Generated SKILL.md includes caller-specific invocation patterns | SKILL.md "Installation" section includes `TOOLI_CALLER` setup instructions |
| G7 | **Session-aware telemetry**: `TOOLI_SESSION_ID` threads through eval recordings and OTel spans | Session ID appears in invocation records and span attributes |
| G8 | **Agent integration guide in generated docs**: `AGENT_INTEGRATION.md` content auto-included in SKILL.md when relevant | SKILL.md includes "Agent Integration" section with env var setup |

### 3.2 Non-Goals

- **Changing the TOOLI_CALLER convention itself** — the protocol is stable and well-documented. v4.1 integrates it, not redesigns it.
- **Agent-specific output formatting** — v4.1 adapts *behavior* (output mode, confirmations, verbosity), not the *content* of results. A dict return is still a dict.
- **Remote agent registration** — no call-home, no agent registry. Detection is local-only.
- **Breaking changes** — `_is_agent_mode()` callers continue to work; `ExecutionContext` is additive.

------

## 4. Feature Specifications

### 4.1 Detection Module Integration (P0)

Move `docs/detect.py` into the `tooli/` package as `tooli/detect.py`.

**Changes required**:
- Move `docs/detect.py` → `tooli/detect.py`
- Move `docs/test_detect.py` → `tests/test_detect.py`
- Update imports to use `from __future__ import annotations` and `collections.abc` (match tooli conventions)
- Replace `typing.List`/`Optional` with `list`/`X | None` (Python 3.10+ style)
- Guard `psutil` import behind `try/except` (already done)
- Guard `signal.SIGALRM` with `hasattr` (match tooli cross-platform convention)
- Export public API from `tooli/__init__.py`: `detect_execution_context`, `ExecutionContext`, `CallerCategory`
- Add `tooli/detect.py` to CLAUDE.md architecture section

### 4.2 Command Pipeline Integration (P0)

Wire `detect_execution_context()` into `TooliCommand.invoke()` so every command has access to caller context.

#### 4.2.1 Context Population

In `tooli/command.py`, during the global callback (or early in `invoke()`):

```python
from tooli.detect import detect_execution_context

# Run detection once per process, cache result
ctx.meta["tooli_execution_context"] = detect_execution_context()
```

The detection result is cached at the module level (already implemented in `detect.py`), so this adds negligible overhead even if called multiple times.

#### 4.2.2 Replace `_is_agent_mode()`

Replace the current `_is_agent_mode()` with a richer function that consults `ExecutionContext`:

```python
def _resolve_caller_context(
    ctx: click.Context | None = None,
    mode: OutputMode | None = None,
) -> tuple[bool, ExecutionContext | None]:
    """Return (is_agent, execution_context) for the current invocation."""
    # Explicit output mode always wins
    if mode in {OutputMode.JSON, OutputMode.JSONL}:
        ec = ctx.meta.get("tooli_execution_context") if ctx else None
        return True, ec

    # TOOLI_OUTPUT env var
    if os.getenv("TOOLI_OUTPUT", "").lower() in {"json", "jsonl"}:
        ec = ctx.meta.get("tooli_execution_context") if ctx else None
        return True, ec

    # Full detection
    ec = detect_execution_context()
    if ec.is_agent or ec.is_ci:
        return True, ec

    return False, ec
```

**Backward compatibility**: `_is_agent_mode()` is retained as a thin wrapper returning just the boolean. Internal callers are migrated to use `_resolve_caller_context()`.

#### 4.2.3 Caller-Adaptive Behaviors

With `ExecutionContext` available, the following behaviors adapt:

| Behavior | Human | AI Agent | CI/CD | Container |
|---|---|---|---|---|
| Default output mode | AUTO (Rich) | JSON | JSON | AUTO |
| `--yes` auto-applied | No | Yes (for non-destructive confirms) | Yes | No |
| Error verbosity | Rich formatted | Structured JSON with suggestions | Structured JSON, minimal | Rich formatted |
| `--help` format | Full Rich help | `--help-agent` compact format | Full text | Full Rich help |
| Timeout default | None | `TOOLI_TIMEOUT` or 120s | None | None |
| Envelope meta | Standard | + `caller_id`, `session_id` | + `ci_name` | Standard |

**Important**: Destructive commands with `requires_approval=True` are NEVER auto-confirmed, even for known agents. The `--yes` adaptation only applies to non-critical confirmations (e.g., "This will scan 10,000 files. Continue?").

### 4.3 Envelope Meta Extension (P0)

When caller identity is available, include it in the JSON envelope `meta` field:

```json
{
  "ok": true,
  "result": [...],
  "meta": {
    "tool": "mytool.list",
    "version": "4.1.0",
    "duration_ms": 42,
    "caller_id": "claude-code",
    "caller_version": "1.5.3",
    "session_id": "sess-abc123",
    "execution_context": "ai_agent"
  }
}
```

Fields are only included when non-null. The `execution_context` field is the `CallerCategory` string value.

### 4.4 `detect-context` Built-In Command (P0)

Register a built-in `detect-context` command on every Tooli app:

```bash
$ TOOLI_CALLER=claude-code mytool detect-context --json
{
  "ok": true,
  "result": {
    "category": "ai_agent",
    "agent_name": "Claude Code",
    "confidence": 1.0,
    "is_interactive": false,
    "is_agent": true,
    "is_ci": false,
    "identified_via_convention": true,
    "caller_id": "claude-code",
    "caller_version": null,
    "session_id": null,
    "platform": "Darwin",
    "signals": ["TOOLI_CALLER=claude-code"]
  }
}
```

This is a diagnostic command for:
- Agents to verify their detection setup works before using the tool
- Developers to debug detection in their environment
- CI pipelines to confirm tooli recognizes their automation context

The command is registered as a hidden built-in (like `generate-skill`, `mcp serve`).

### 4.5 SKILL.md Agent Integration Section (P1)

When `SkillV4Generator` produces SKILL.md, include an "Agent Integration" section derived from the AGENT_INTEGRATION.md concepts:

```markdown
## Agent Integration

Set `TOOLI_CALLER` before invoking this tool for optimal behavior:

```bash
TOOLI_CALLER=claude-code mytool list --json
```

| Variable | Required | Description |
|----------|----------|-------------|
| `TOOLI_CALLER` | Recommended | Your agent identifier (e.g., `claude-code`, `cursor`, `langchain`) |
| `TOOLI_CALLER_VERSION` | No | Your agent's version |
| `TOOLI_SESSION_ID` | No | Session ID for correlating multiple calls |

When `TOOLI_CALLER` is set:
- JSON output is used by default
- Structured errors include recovery suggestions
- Interactive prompts are suppressed
- Session ID appears in telemetry for tracing

Verify detection: `mytool detect-context --json`
```

This section is included when the SKILL.md target is `generic-skill` or `claude-skill`. For `claude-code` target, it's simplified to just show `TOOLI_CALLER=claude-code`.

### 4.6 CLAUDE.md Integration Hints (P1)

The `claude_md_v2.py` generator includes TOOLI_CALLER setup in its "Agent Invocation" section:

```markdown
## Agent Invocation

Set `TOOLI_CALLER=claude-code` before invoking:
```bash
TOOLI_CALLER=claude-code mytool <command> --json
```

This ensures optimal output formatting and structured error responses.
```

### 4.7 Session-Aware Telemetry (P1)

Thread `TOOLI_SESSION_ID` through existing telemetry infrastructure:

#### 4.7.1 Invocation Recording

In `tooli/eval/recorder.py`, add `session_id` and `caller_id` to `InvocationRecord`:

```python
@dataclass
class InvocationRecord:
    # ... existing fields ...
    caller_id: str | None = None
    session_id: str | None = None
```

#### 4.7.2 OpenTelemetry Spans

In `tooli/telemetry.py`, add span attributes when available:

```python
span.set_attribute("tooli.caller_id", ec.caller_id or "unknown")
span.set_attribute("tooli.session_id", ec.session_id or "")
span.set_attribute("tooli.caller_category", ec.category.value)
```

#### 4.7.3 MCP Metadata

When running as an MCP server, include caller context in tool response metadata.

### 4.8 Heuristic Fallback Improvements (P2)

The detection module's heuristic system handles agents that don't set `TOOLI_CALLER`. Integrating it into the framework gives all tooli apps free heuristic detection:

- **Claude Code**: Detected via `CLAUDE_CODE`, `ANTHROPIC_API_KEY`, or parent process `claude` (confidence 0.9-1.0)
- **Cursor**: Detected via `CURSOR_*` env vars or Cursor process in parent tree (confidence 0.85-0.95)
- **GitHub Copilot**: Detected via `GITHUB_COPILOT_*` or `CODESPACES` env vars (confidence 0.85-0.95)
- **CI/CD**: Detected via `CI`, `GITHUB_ACTIONS`, `GITLAB_CI`, etc. (confidence 0.85-0.95)
- **Docker**: Detected via `/.dockerenv`, cgroup markers (confidence 0.90)

When heuristics fire with moderate confidence (0.5-0.8), the tool includes a suggestion in verbose mode:

```
[tooli] Detected possible agent context (confidence: 0.7). Set TOOLI_CALLER for reliable detection.
```

### 4.9 Manifest & Schema Extension (P2)

Add caller convention metadata to the agent manifest:

```json
{
  "name": "mytool",
  "version": "4.1.0",
  "caller_convention": {
    "env_var": "TOOLI_CALLER",
    "well_known_values": ["claude-code", "cursor", "langchain", "..."],
    "session_var": "TOOLI_SESSION_ID",
    "detect_command": "mytool detect-context --json"
  }
}
```

------

## 5. Architecture Changes

### 5.1 New Module

| Module | Purpose |
|---|---|
| `tooli/detect.py` | Caller detection engine (moved from `docs/detect.py`) |

### 5.2 Modified Modules

| Module | Changes |
|---|---|
| `tooli/command.py` | Wire `detect_execution_context()` into invoke pipeline; replace `_is_agent_mode()` internals; add caller-adaptive behaviors |
| `tooli/envelope.py` | Add optional `caller_id`, `session_id`, `execution_context` to `EnvelopeMeta` |
| `tooli/app.py` | Register `detect-context` built-in command |
| `tooli/docs/skill_v4.py` | Add "Agent Integration" section to SKILL.md output |
| `tooli/docs/claude_md_v2.py` | Add TOOLI_CALLER setup to "Agent Invocation" section |
| `tooli/eval/recorder.py` | Add `caller_id`, `session_id` to `InvocationRecord` |
| `tooli/telemetry.py` | Add caller span attributes |
| `tooli/manifest.py` | Add `caller_convention` to manifest |
| `tooli/__init__.py` | Export `detect_execution_context`, `ExecutionContext`, `CallerCategory` |

### 5.3 Moved Files

| From | To |
|---|---|
| `docs/detect.py` | `tooli/detect.py` |
| `docs/test_detect.py` | `tests/test_detect.py` |

### 5.4 Performance Considerations

Detection runs once per process and caches. The fast path (TOOLI_CALLER set) is a single `os.environ.get()` — sub-microsecond. The full heuristic path inspects environment, process tree, and filesystem — typically 5-15ms on first call, 0ms on subsequent calls. This is negligible compared to typical command execution time.

Process tree inspection uses `psutil` when available (faster, richer data) with a stdlib fallback (`/proc` on Linux, `ps` on macOS/BSD). Container detection reads a few files from `/proc` or checks for `/.dockerenv`. Call stack inspection walks the Python frame stack.

------

## 6. Implementation Phases

### Phase 1: Core Integration (P0)

1. Move `docs/detect.py` → `tooli/detect.py` with style updates (3.10+ typing, tooli conventions)
2. Move `docs/test_detect.py` → `tests/test_detect.py` with import updates
3. Wire `detect_execution_context()` into `TooliCommand.invoke()` via `ctx.meta`
4. Replace `_is_agent_mode()` internals with `ExecutionContext`-aware logic (keep function signature for compat)
5. Add `caller_id`, `session_id`, `execution_context` to envelope meta
6. Register `detect-context` built-in command
7. Export types from `tooli/__init__.py`
8. Tests: verify detection integration, envelope meta, detect-context output

### Phase 2: Documentation Integration (P1)

1. Add "Agent Integration" section to `SkillV4Generator`
2. Add TOOLI_CALLER hints to `claude_md_v2.py`
3. Thread `session_id` and `caller_id` into `InvocationRecord`
4. Add caller span attributes to OTel telemetry
5. Tests: verify SKILL.md includes integration section, telemetry records caller info

### Phase 3: Adaptive Behavior & Polish (P2)

1. Implement caller-adaptive confirmation behavior (auto-`--yes` for agents on non-critical prompts)
2. Implement caller-adaptive help format (compact help for detected agents)
3. Add `caller_convention` to agent manifest
4. Add heuristic confidence suggestions in verbose mode
5. MCP metadata inclusion
6. Update CLAUDE.md, README, CHANGELOG
7. Tests: verify adaptive behaviors, manifest extension

------

## 7. Migration Guide (v4.0 → v4.1)

### Breaking Changes

**None.** All v4.0 code runs unchanged on v4.1.

### Recommended Changes

1. **Tell your users to set `TOOLI_CALLER`** — add it to your tool's documentation. The generated SKILL.md will include this automatically.

2. **Use `ExecutionContext` for caller-aware logic** (optional):

```python
from tooli.detect import detect_execution_context

@app.command()
def my_command() -> dict:
    ec = detect_execution_context()
    if ec.is_agent:
        # Return compact result for agents
        return {"status": "ok", "count": 42}
    else:
        # Return verbose result for humans
        return {"status": "ok", "count": 42, "details": "..."}
```

3. **Use `TOOLI_SESSION_ID` for tracing** — if you log invocations, the session ID is now available in eval recordings and OTel spans.

------

## 8. Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Detection accuracy with TOOLI_CALLER | 100% | Convention-based detection is deterministic |
| Detection accuracy without TOOLI_CALLER (heuristic) | ≥85% for well-known agents | Test against env var fingerprints from Claude Code, Cursor, Copilot, Aider |
| Detection overhead (fast path) | <1ms | Benchmark `detect_execution_context()` with TOOLI_CALLER set |
| Detection overhead (heuristic path) | <20ms | Benchmark full heuristic detection |
| Existing test suite pass rate | 100% | All 259 existing tests + moved detect tests |
| Envelope meta correctness | 100% | All JSON envelopes include caller info when available |
| SKILL.md includes integration section | 100% | All generated SKILL.md files include agent integration guidance |

------

## 9. Open Questions

1. **Should caller-adaptive `--yes` be opt-in per command?** Auto-confirming for agents is convenient but some tool authors may want explicit control. A `@app.command(agent_auto_confirm=True)` parameter could gate this.

2. **Should `detect-context` be hidden or visible?** Hidden keeps it out of normal `--help` but agents need to discover it. Including it in SKILL.md's Quick Reference solves discoverability.

3. **Should the envelope always include caller info, or only when `TOOLI_CALLER` is set?** Including heuristic-detected caller info could be noisy (confidence < 1.0). Option: only include when confidence ≥ 0.8.

4. **Should agents that don't set `TOOLI_CALLER` see a warning?** A one-time stderr hint ("Set TOOLI_CALLER for better integration") could educate agents but might pollute output. Could gate behind `--verbose`.

5. **Should detection results be available to command functions via `typer.Context`?** Tool authors could use `ctx.obj.execution_context` for caller-specific logic, but this couples business logic to detection.

------

*End of PRD v4.1*
