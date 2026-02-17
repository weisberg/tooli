"""Claude Agent SDK integration with tooli.

Shows how to expose tooli commands as Claude Agent SDK tools using both:
1. Python API (app.call) — fast, in-process, typed results
2. CLI subprocess — when the tool runs as a separate binary

Requirements: pip install anthropic
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

# ---------------------------------------------------------------------------
# Approach 1: Python API (recommended for same-process usage)
# ---------------------------------------------------------------------------

def python_api_example() -> None:
    """Use app.call() to invoke tooli commands directly."""
    from examples.docq.app import app

    # Single invocation
    result = app.call("stats", path="README.md")
    if result.ok:
        print(f"Stats: {result.result}")
    else:
        print(f"Error: {result.error.message}")
        if result.error.suggestion:
            print(f"Fix: {result.error.suggestion}")

    # Streaming — iterate individual items from a list-returning command
    for item in app.stream("headings", path="README.md"):
        if item.ok:
            print(f"Heading: {item.result}")


def build_claude_tools_from_app() -> list[dict[str, Any]]:
    """Build Claude tool definitions from a tooli app's schema.

    Each tooli command becomes a Claude tool with its JSON Schema
    automatically derived from the function signature.
    """
    from examples.docq.app import app
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
    return tools


def handle_claude_tool_call(name: str, input_data: dict[str, Any]) -> str:
    """Handle a tool call from Claude by delegating to app.call()."""
    from examples.docq.app import app

    result = app.call(name, **input_data)
    return json.dumps({"ok": result.ok, "result": result.result}, default=str)


# ---------------------------------------------------------------------------
# Approach 2: CLI subprocess
# ---------------------------------------------------------------------------

def cli_subprocess_example() -> None:
    """Invoke a tooli CLI tool via subprocess with TOOLI_CALLER set."""
    env = {
        **os.environ,
        "TOOLI_CALLER": "claude-code",
        "TOOLI_CALLER_VERSION": "1.0.0",
        "TOOLI_SESSION_ID": "demo-session-001",
    }

    proc = subprocess.run(
        ["python", "-m", "examples.docq.app", "stats", "README.md", "--json"],
        capture_output=True,
        text=True,
        env=env,
    )

    if proc.returncode == 0:
        envelope = json.loads(proc.stdout)
        if envelope["ok"]:
            print(f"Result: {envelope['result']}")
        else:
            print(f"Tool error: {envelope['error']['message']}")
    else:
        print(f"Process failed: {proc.stderr}")


if __name__ == "__main__":
    print("=== Python API Example ===")
    python_api_example()

    print("\n=== Claude Tool Definitions ===")
    tools = build_claude_tools_from_app()
    for t in tools:
        print(f"  - {t['name']}: {t['description'][:60]}...")

    print("\n=== CLI Subprocess Example ===")
    cli_subprocess_example()
