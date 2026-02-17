"""OpenAI Agents SDK integration with tooli.

Shows how to expose tooli commands as OpenAI agent tools using both:
1. Python API (app.call) — fast, in-process, typed results
2. CLI subprocess — when the tool runs as a separate binary

Requirements: pip install openai
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

# ---------------------------------------------------------------------------
# Approach 1: Python API (recommended)
# ---------------------------------------------------------------------------

def python_api_example() -> None:
    """Use app.call() to invoke tooli commands directly."""
    from examples.docq.app import app

    # Single call
    result = app.call("stats", path="README.md")
    if result.ok:
        print(f"Stats: {result.result}")
    else:
        err = result.error
        print(f"Error [{err.code}]: {err.message}")

    # Streaming
    for item in app.stream("headings", path="README.md"):
        if item.ok:
            print(f"Heading: {item.result}")


def build_openai_tools_from_app() -> list[dict[str, Any]]:
    """Build OpenAI function tool definitions from a tooli app.

    Returns the ``tools`` array expected by the OpenAI Chat Completions
    API or the Agents SDK ``function_tool()`` helper.
    """
    from examples.docq.app import app
    from tooli.schema import generate_tool_schema

    tools = []
    for tool_def in app.get_tools():
        if tool_def.hidden:
            continue
        schema = generate_tool_schema(tool_def.callback, name=tool_def.name)
        tools.append({
            "type": "function",
            "function": {
                "name": schema.name,
                "description": schema.description,
                "parameters": schema.parameters,
            },
        })
    return tools


def handle_openai_tool_call(name: str, arguments: str) -> str:
    """Handle an OpenAI function call by delegating to app.call().

    ``arguments`` is the raw JSON string from the model's tool call.
    Returns a JSON string for the tool result message.
    """
    from examples.docq.app import app

    kwargs = json.loads(arguments)
    result = app.call(name, **kwargs)

    if result.ok:
        return json.dumps(result.result, default=str)
    return json.dumps({"error": result.error.message})


# ---------------------------------------------------------------------------
# Approach 2: CLI subprocess
# ---------------------------------------------------------------------------

def cli_subprocess_example() -> None:
    """Invoke a tooli CLI tool via subprocess."""
    env = {
        **os.environ,
        "TOOLI_CALLER": "openai-agents-sdk",
        "TOOLI_SESSION_ID": "agent-run-001",
    }

    proc = subprocess.run(
        ["python", "-m", "examples.docq.app", "stats", "README.md", "--json"],
        capture_output=True,
        text=True,
        env=env,
    )

    if proc.returncode == 0:
        envelope = json.loads(proc.stdout)
        print(f"OK={envelope['ok']}, result={envelope.get('result')}")
    else:
        print(f"Failed: {proc.stderr}")


if __name__ == "__main__":
    print("=== Python API Example ===")
    python_api_example()

    print("\n=== OpenAI Tool Definitions ===")
    tools = build_openai_tools_from_app()
    for t in tools:
        print(f"  - {t['function']['name']}: {t['function']['description'][:60]}...")

    print("\n=== CLI Subprocess Example ===")
    cli_subprocess_example()
