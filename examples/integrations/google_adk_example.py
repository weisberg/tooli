"""Google Agent Development Kit (ADK) integration with tooli.

Shows how to expose tooli commands as Google ADK tools using both:
1. Python API (app.call) — fast, in-process, typed results
2. CLI subprocess — when the tool runs as a separate binary

Requirements: pip install google-adk
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

# ---------------------------------------------------------------------------
# Approach 1: Python API
# ---------------------------------------------------------------------------

def python_api_example() -> None:
    """Use app.call() for direct in-process invocation."""
    from examples.docq.app import app

    # Single call
    result = app.call("stats", path="README.md")
    if result.ok:
        print(f"Stats: {result.result}")
    else:
        print(f"Error: {result.error.message}")

    # Streaming
    for item in app.stream("headings", path="README.md"):
        if item.ok:
            print(f"Heading: {item.result}")


def build_adk_tool_declarations() -> list[dict[str, Any]]:
    """Build Google ADK FunctionDeclaration-compatible dicts from tooli.

    Each tooli command maps to a FunctionDeclaration with its
    parameters derived from the JSON Schema.
    """
    from examples.docq.app import app
    from tooli.schema import generate_tool_schema

    declarations = []
    for tool_def in app.get_tools():
        if tool_def.hidden:
            continue
        schema = generate_tool_schema(tool_def.callback, name=tool_def.name)
        declarations.append({
            "name": schema.name,
            "description": schema.description,
            "parameters": schema.parameters,
        })
    return declarations


def handle_adk_function_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Handle a function call from Google ADK by delegating to app.call().

    Returns the response dict expected by ADK's FunctionResponse.
    """
    from examples.docq.app import app

    result = app.call(name, **args)

    if result.ok:
        return {"result": result.result}
    return {"error": result.error.message}


# ---------------------------------------------------------------------------
# Approach 2: CLI subprocess
# ---------------------------------------------------------------------------

def cli_subprocess_example() -> None:
    """Invoke a tooli CLI tool via subprocess for ADK agents."""
    env = {
        **os.environ,
        "TOOLI_CALLER": "google-adk",
        "TOOLI_SESSION_ID": "adk-session-001",
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

    print("\n=== ADK Tool Declarations ===")
    decls = build_adk_tool_declarations()
    for d in decls:
        print(f"  - {d['name']}: {d['description'][:60]}...")

    print("\n=== CLI Subprocess Example ===")
    cli_subprocess_example()
