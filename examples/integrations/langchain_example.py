"""LangChain / LangGraph integration with tooli.

Shows how to expose tooli commands as LangChain tools using both:
1. Python API (app.call) — fast, in-process, typed results
2. CLI subprocess — when the tool runs as a separate binary

Requirements: pip install langchain-core
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

# ---------------------------------------------------------------------------
# Approach 1: Python API with LangChain StructuredTool
# ---------------------------------------------------------------------------

def build_langchain_tools() -> list[Any]:
    """Create LangChain StructuredTool instances from a tooli app.

    Each tooli command becomes a LangChain tool that calls app.call()
    under the hood. The schema is derived from the tooli function signature.
    """
    from examples.docq.app import app
    from tooli.schema import generate_tool_schema

    tools = []
    for tool_def in app.get_tools():
        if tool_def.hidden:
            continue
        schema = generate_tool_schema(tool_def.callback, name=tool_def.name)

        # Capture tool_def.name in closure
        cmd_name = tool_def.name

        def _make_runner(name: str) -> Any:
            def run_tool(**kwargs: Any) -> str:
                result = app.call(name, **kwargs)
                if result.ok:
                    return json.dumps(result.result, default=str)
                return json.dumps({"error": result.error.message})
            return run_tool

        # LangChain StructuredTool-compatible dict
        tools.append({
            "name": schema.name,
            "description": schema.description,
            "parameters": schema.parameters,
            "func": _make_runner(cmd_name),
        })
    return tools


def python_api_example() -> None:
    """Direct app.call() usage for LangChain agents."""
    from examples.docq.app import app

    # Single invocation
    result = app.call("stats", path="README.md")
    if result.ok:
        print(f"Stats: {result.result}")

    # Streaming for list commands
    for item in app.stream("headings", path="README.md"):
        if item.ok:
            print(f"Heading: {item.result}")


# ---------------------------------------------------------------------------
# Approach 2: CLI subprocess as a LangChain tool
# ---------------------------------------------------------------------------

def cli_tool_factory(command: str, description: str) -> dict[str, Any]:
    """Create a LangChain-compatible tool definition that wraps a CLI call.

    This approach is useful when the tooli tool is installed as a
    standalone binary rather than imported as a Python package.
    """
    def run_cli(**kwargs: Any) -> str:
        args = ["python", "-m", "examples.docq.app", command, "--json"]
        for k, v in kwargs.items():
            args.extend([f"--{k.replace('_', '-')}", str(v)])

        env = {**os.environ, "TOOLI_CALLER": "langchain"}
        proc = subprocess.run(args, capture_output=True, text=True, env=env)

        if proc.returncode == 0:
            return proc.stdout
        return json.dumps({"error": proc.stderr.strip()})

    return {
        "name": command,
        "description": description,
        "func": run_cli,
    }


if __name__ == "__main__":
    print("=== Python API Example ===")
    python_api_example()

    print("\n=== LangChain Tool Definitions ===")
    tools = build_langchain_tools()
    for t in tools:
        print(f"  - {t['name']}: {t['description'][:60]}...")
