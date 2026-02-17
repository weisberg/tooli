"""ConfigMigrate: Schema-driven config upgrades with hints."""

from __future__ import annotations

import json
from typing import Annotated, Literal

from tooli import Argument, Option, StdinOr, Tooli
from tooli.annotations import ReadOnly
from tooli.errors import InputError, Suggestion

app = Tooli(
    name="configmigrate",
    help="Validates and upgrades JSON/YAML/TOML configurations.",
    version="0.1.0",
)

@app.command(
    annotations=ReadOnly,
    examples=[
        {"args": ["run", "old_config.json"], "description": "Validate and migrate a config file"},
    ],
    capabilities=["fs:read"],
)
def run(
    source: Annotated[StdinOr[str], Argument(help="Config source")],
    target_version: Annotated[Literal["v1", "v2"], Option(help="Version to migrate to")] = "v2",
) -> dict:
    """Migrate a configuration to a new schema version."""
    try:
        config = json.loads(str(source))
    except json.JSONDecodeError as e:
        # Structured error for malformed input
        raise InputError(
            message=f"Config is not valid JSON: {e}",
            code="E1001",
            suggestion=Suggestion(
                action="fix_format",
                fix="Ensure the input is valid JSON format."
            )
        ) from e

    # Demo superpower: specific suggestions for schema changes
    if "legacy_port" in config:
        raise InputError(
            message="'legacy_port' field is no longer supported.",
            code="E1002",
            suggestion=Suggestion(
                action="update_field",
                fix="Rename 'legacy_port' to 'server.port' in your configuration.",
                example='{"server": {"port": 8080}}'
            )
        )

    return {
        "status": "migrated",
        "from": "v1",
        "to": target_version,
        "config": {**config, "metadata": {"migrated": True}}
    }

if __name__ == "__main__":
    app()
