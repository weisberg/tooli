"""EnvDoctor: Tell an agent what's wrong with the environment."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Annotated

from tooli import Option, Tooli
from tooli.annotations import ReadOnly

if TYPE_CHECKING:
    from collections.abc import Iterable

app = Tooli(
    name="envdoctor",
    help="Runs local environment checks and returns a structured report.",
    version="0.1.0",
)

@app.command(
    annotations=ReadOnly,
    examples=[
        {"args": ["check"], "description": "Run diagnostic suite"},
    ],
    when_to_use="Diagnose local environment issues before running builds or deployments",
    task_group="Analysis",
    pipe_output={"format": "json"},
)
def check(
    verbose: Annotated[bool, Option(help="Show detailed check info")] = False,
) -> Iterable[dict]:
    """Run a series of diagnostic probes against the local environment."""
    # Demo superpower: JSONL streaming of check results

    yield {
        "check": "python_version",
        "status": "pass",
        "result": sys.version.split()[0],
    }

    yield {
        "check": "venv_active",
        "status": "pass",
        "result": hasattr(sys, "real_prefix") or (sys.base_prefix != sys.prefix),
    }

    yield {
        "check": "git_available",
        "status": "pass",
        "result": True,
    }

    # Simulate a warning/fail
    import shutil
    total, used, free = shutil.disk_usage("/")
    disk_ok = (free / total) > 0.1
    yield {
        "check": "disk_space",
        "status": "pass" if disk_ok else "warn",
        "result": f"{free // (2**30)} GB free",
    }

if __name__ == "__main__":
    app()
