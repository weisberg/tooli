"""SecretScout: Fast local secret scanning with suggestions."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from tooli import Argument, Option, Tooli
from tooli.annotations import ReadOnly

app = Tooli(
    name="secretscout",
    help="Scans for patterns (AWS keys, private keys) with remediation hints.",
    version="0.1.0",
)

@app.command(
    annotations=ReadOnly,
    examples=[
        {"args": ["scan", "."], "description": "Scan current directory for secrets"},
    ],
    capabilities=["fs:read"],
)
def scan(
    root: Annotated[Path, Argument(help="Directory to scan")] = Path("."),
    ignore: Annotated[list[str], Option(help="Patterns to ignore")] = None,
) -> list[dict]:
    """Perform a security audit for hardcoded secrets."""
    # Mock timeout demo
    # In Tooli, --timeout flag triggers a RuntimeError(code="E4001")
    # which we can catch or let the framework handle.

    findings = []
    # Mocking findings
    findings.append({
        "file": "src/config.py",
        "line": 12,
        "kind": "AWS_ACCESS_KEY",
        "confidence": "high",
        "snippet": "AKIA..."
    })

    if ignore and ".venv" not in ignore:
        # Demo superpower: Suggestion for performance
        pass # Logic would go here in real app

    return findings

if __name__ == "__main__":
    app()
