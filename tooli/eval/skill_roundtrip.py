"""LLM-powered skill roundtrip evaluation.

Generates SKILL.md -> feeds to an LLM -> asks for invocations -> verifies.
Requires an API key; opt-in only.
"""

from __future__ import annotations

import json
import os
from typing import Any


def _get_api_key() -> str | None:
    return os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")


def eval_skill_roundtrip(
    app: Any,
    *,
    model: str = "claude-sonnet-4-20250514",
    max_commands: int = 5,
) -> dict[str, Any]:
    """Run a skill roundtrip evaluation.

    1. Generate SKILL.md
    2. Send to LLM with prompt asking for example invocations
    3. Parse and verify the invocations

    Returns a report dict with success rate and details.
    """
    api_key = _get_api_key()
    if not api_key:
        return {
            "error": "No API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.",
            "success_rate": 0.0,
            "results": [],
        }

    from tooli.docs.skill_v4 import generate_skill_md

    skill_md = generate_skill_md(app)
    app_name = app.info.name or "tooli-app"

    visible_commands = [t for t in app.get_tools() if not t.hidden][:max_commands]
    command_names = [t.name for t in visible_commands]

    prompt = (
        f"You are testing the CLI tool '{app_name}'. Here is its documentation:\n\n"
        f"{skill_md}\n\n"
        f"For each of these commands: {', '.join(command_names)}\n"
        "Generate a valid CLI invocation with `--json` flag. "
        "Return a JSON array of objects with 'command' (the full CLI string) and 'name' (command name).\n"
        "Only return the JSON array, nothing else."
    )

    # Try Anthropic first, then OpenAI
    invocations = _call_llm(prompt, api_key=api_key, model=model)
    if invocations is None:
        return {
            "error": "Failed to get LLM response.",
            "success_rate": 0.0,
            "results": [],
        }

    # Verify invocations
    results: list[dict[str, Any]] = []
    correct = 0
    for inv in invocations:
        name = inv.get("name", "")
        command = inv.get("command", "")
        is_valid = (
            app_name in command
            and name in command
            and "--json" in command
        )
        results.append({
            "name": name,
            "command": command,
            "valid": is_valid,
        })
        if is_valid:
            correct += 1

    total = len(results) or 1
    return {
        "success_rate": correct / total,
        "total": total,
        "correct": correct,
        "results": results,
    }


def _call_llm(prompt: str, *, api_key: str, model: str) -> list[dict[str, Any]] | None:
    """Call an LLM and parse JSON array response."""
    try:
        import anthropic  # type: ignore[import-not-found]

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        return json.loads(text)
    except Exception:
        pass

    try:
        import openai  # type: ignore[import-not-found]

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        text = response.choices[0].message.content or "[]"
        return json.loads(text)
    except Exception:
        pass

    return None
