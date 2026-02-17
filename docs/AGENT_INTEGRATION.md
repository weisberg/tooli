# Tooli Agent Integration Guide

## The TOOLI_CALLER Convention

When your agent invokes a CLI tool built with [tooli](https://github.com/weisberg/tooli), set the `TOOLI_CALLER` environment variable to identify yourself. This is the **recommended, highest-confidence** way for tooli to recognize your agent and tailor its behavior accordingly — structured JSON output, machine-readable errors with recovery suggestions, and suppressed interactive prompts.

Without `TOOLI_CALLER`, tooli falls back to heuristic detection (process tree inspection, TTY checks, other env vars). Heuristics work, but they're probabilistic. Setting `TOOLI_CALLER` gives you **100% confidence, zero overhead** — tooli skips all probing and immediately enters agent mode.

Think of it as good etiquette: you're telling the tool who you are so it can serve you better.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TOOLI_CALLER` | **Yes** | Your agent's identifier (see well-known values below) |
| `TOOLI_CALLER_VERSION` | No | Semver of your agent (e.g. `1.4.2`) |
| `TOOLI_SESSION_ID` | No | Opaque ID for the current session or run |

### TOOLI_CALLER Values

Use one of the well-known identifiers when applicable. If your agent isn't listed, use a descriptive lowercase hyphen-separated slug.

| Value | Agent |
|---|---|
| `claude-code` | Claude Code |
| `cursor` | Cursor |
| `copilot-workspace` | GitHub Copilot Workspace |
| `copilot-cli` | GitHub Copilot CLI |
| `aider` | Aider |
| `devin` | Devin |
| `windsurf` | Windsurf (Codeium) |
| `amazon-q` | Amazon Q Developer |
| `codex-cli` | OpenAI Codex CLI |
| `continue` | Continue.dev |
| `langchain` | LangChain |
| `langgraph` | LangGraph |
| `autogen` | AutoGen |
| `crewai` | CrewAI |
| `llamaindex` | LlamaIndex |
| `haystack` | Haystack |
| `semantic-kernel` | Semantic Kernel |
| `pydantic-ai` | PydanticAI |
| `dspy` | DSPy |
| `smolagents` | SmolAgents |
| `agency-swarm` | Agency Swarm |
| `openai-agents-sdk` | OpenAI Agents SDK |
| `custom` | Generic / unspecified agent |
| `my-org-build-bot` | *(example custom value)* |

## How to Set It

### Shell (one-shot)

```bash
TOOLI_CALLER=claude-code TOOLI_CALLER_VERSION=1.5.3 mytool list --json
```

### Shell (session-wide)

```bash
export TOOLI_CALLER=aider
export TOOLI_CALLER_VERSION=0.82.1
export TOOLI_SESSION_ID=session-$(uuidgen)

# All subsequent tooli CLI calls in this shell are now identified
mytool sync
mytool status
```

### Python (subprocess)

```python
import subprocess, os, uuid

env = {
    **os.environ,
    "TOOLI_CALLER": "crewai",
    "TOOLI_CALLER_VERSION": "0.75.0",
    "TOOLI_SESSION_ID": f"run-{uuid.uuid4().hex[:12]}",
}

result = subprocess.run(
    ["mytool", "list", "--json"],
    capture_output=True, text=True, env=env,
)
```

### Node.js (child_process)

```javascript
const { execSync } = require('child_process');

const output = execSync('mytool list --json', {
  env: {
    ...process.env,
    TOOLI_CALLER: 'claude-code',
    TOOLI_CALLER_VERSION: '1.5.3',
    TOOLI_SESSION_ID: `sess-${Date.now()}`,
  },
  encoding: 'utf8',
});
```

### Docker

```dockerfile
ENV TOOLI_CALLER=autogen
ENV TOOLI_CALLER_VERSION=0.4.0
```

Or at runtime:

```bash
docker run -e TOOLI_CALLER=autogen -e TOOLI_CALLER_VERSION=0.4.0 myimage mytool list
```

### LangChain / LangGraph Tool Wrapper

```python
from langchain_core.tools import tool
import subprocess, os

@tool
def run_mytool(command: str) -> str:
    """Run a tooli CLI command."""
    env = {**os.environ, "TOOLI_CALLER": "langchain"}
    result = subprocess.run(
        command.split(),
        capture_output=True, text=True, env=env,
    )
    return result.stdout
```

### GitHub Actions

```yaml
- name: Run tooli CLI
  env:
    TOOLI_CALLER: github-actions-bot
    TOOLI_SESSION_ID: ${{ github.run_id }}
  run: mytool deploy --yes --json
```

## What Happens When TOOLI_CALLER Is Set

When tooli detects `TOOLI_CALLER` in the environment:

1. **Immediate classification** — confidence 1.0, no heuristic probing, no process tree inspection, no filesystem checks. This is faster and deterministic.
2. **JSON output by default** — tooli switches to structured `{"ok": true, "result": ...}` envelope output unless the tool author has configured otherwise.
3. **Structured errors** — failures return machine-parseable `{"ok": false, "error": {"code": "E1003", "message": "...", "suggestion": {...}}}` instead of Rich-formatted text.
4. **No interactive prompts** — confirmations that would block a pipe are auto-skipped or return structured errors with `--yes` suggestions.
5. **Tracing** — when `TOOLI_SESSION_ID` is provided, it appears in telemetry and log output, making it easy to correlate multiple CLI calls within one agent task.

## Python API (In-Process)

When your agent is written in Python, you can skip the CLI entirely and call tooli commands directly via `app.call()`, `app.stream()`, and their async variants.

### Basic Usage

```python
from examples.docq.app import app

# Single invocation — returns TooliResult
result = app.call("stats", path="README.md")
if result.ok:
    data = result.result  # typed dict
else:
    print(result.error.message)
    print(result.error.suggestion)
```

### Streaming

```python
# Iterate individual items from a list-returning command
for item in app.stream("headings", path="README.md"):
    if item.ok:
        print(item.result)
```

### Async

```python
import asyncio

async def main():
    result = await app.acall("stats", path="README.md")
    print(result.unwrap())

    async for item in app.astream("headings", path="README.md"):
        print(item.result)

asyncio.run(main())
```

### Building Tool Definitions

```python
from tooli.schema import generate_tool_schema

tools = []
for tool_def in app.get_tools():
    if tool_def.hidden:
        continue
    schema = generate_tool_schema(tool_def.callback, name=tool_def.name)
    tools.append({
        "name": schema.name,
        "description": schema.description,
        "input_schema": schema.parameters,
    })
```

### Framework Examples

Full integration examples are available under `examples/integrations/`:

| File | Framework | Approach |
|---|---|---|
| `claude_sdk_example.py` | Claude Agent SDK | app.call() + subprocess |
| `openai_agents_example.py` | OpenAI Agents SDK | app.call() + subprocess |
| `langchain_example.py` | LangChain / LangGraph | StructuredTool + subprocess |
| `google_adk_example.py` | Google ADK | FunctionDeclaration + subprocess |

## Legacy: TOOLI_AGENT_MODE

The boolean `TOOLI_AGENT_MODE=true` flag is still supported for backward compatibility. It triggers agent-mode output but provides no caller identification, version tracking, or session correlation. Prefer `TOOLI_CALLER` for new integrations.

## Verifying Detection

Any tooli-built CLI includes the `detect-context` builtin command:

```bash
# With TOOLI_CALLER set — confirms convention-based detection
TOOLI_CALLER=my-agent TOOLI_CALLER_VERSION=2.0.0 mytool detect-context --json
```

```bash
# Without TOOLI_CALLER — shows heuristic detection result
mytool detect-context --json
```

```bash
# Human-readable report format
mytool detect-context
```

Expected JSON output when `TOOLI_CALLER` is set:

```json
{
  "category": "ai_agent",
  "agent_name": "CrewAI",
  "confidence": 1.0,
  "is_interactive": false,
  "is_agent": true,
  "is_ci": false,
  "identified_via_convention": true,
  "caller_id": "crewai",
  "caller_version": null,
  "session_id": null,
  "platform": "Linux",
  "signals": [
    "TOOLI_CALLER=crewai"
  ]
}
```

The `detect-context` command is hidden from `--help` but always available. It is useful for debugging integration issues — run it first to confirm your agent is being recognized correctly before issuing other commands.

## Instructions for Agents

If you are an AI agent reading this document as part of a SKILL.md, CLAUDE.md, or similar integration file, here is what you should do:

1. **Before invoking any tooli CLI tool**, set `TOOLI_CALLER` in the subprocess environment. Use your well-known identifier from the table above, or a descriptive custom slug.
2. **Optionally set `TOOLI_SESSION_ID`** to a unique value for the current task or conversation so that multiple CLI calls can be correlated in logs.
3. **Always pass `--json`** (or `--output json`) when you need to parse the result programmatically. While `TOOLI_CALLER` triggers JSON-by-default in most tooli tools, being explicit never hurts.
4. **Always pass `--yes`** for commands that might prompt for confirmation.
5. **Parse the envelope**: tooli wraps results in `{"ok": bool, "result": ..., "meta": {...}}`. Check `ok` first, then read `result`. On failure, read `error.suggestion.fix` for the recommended recovery action.