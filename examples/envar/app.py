"""Environment & Secrets Manager example app.

Manage environment variables and secrets in dotenv files.
Showcases: SecretInput type, AuthContext scopes, mixed ReadOnly/Destructive
annotations, structured output.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any

import typer  # noqa: TC002

from tooli import Argument, Option, SecretInput, Tooli
from tooli.annotations import Destructive, ReadOnly
from tooli.errors import InputError, Suggestion

app = Tooli(
    name="envar",
    help="Environment variable and secrets manager",
    rules=[
        "Always validate variable names before writing",
        "Values are masked by default in list output",
    ],
    env_vars={
        "ENVAR_DEFAULT_FILE": {
            "description": "Default dotenv file path",
            "default": ".env",
        },
    },
)


def _parse_dotenv(path: str) -> dict[str, str]:
    """Parse a dotenv file into a dict of name→value pairs."""
    file_path = Path(path)
    if not file_path.exists():
        return {}

    result: dict[str, str] = {}
    try:
        for line in file_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                result[key] = value
    except OSError as exc:
        raise InputError(
            message=f"Failed to read dotenv file '{path}': {exc}",
            code="E7001",
            details={"path": path},
        ) from exc

    return result


def _write_dotenv(path: str, data: dict[str, str]) -> None:
    """Write a dict of name→value pairs as a dotenv file."""
    lines = [f"{key}={value}" for key, value in sorted(data.items())]
    Path(path).write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")


@app.command(
    annotations=ReadOnly,
    capabilities=["fs:read", "env:read"],
)
def get(
    name: Annotated[str, Argument(help="Variable name")],
    *,
    env_file: Annotated[str, Option(help="Dotenv file path")] = ".env",
) -> dict[str, Any]:
    """Read an environment variable from the dotenv file or current environment."""
    file_vars = _parse_dotenv(env_file)
    if name in file_vars:
        return {"name": name, "value": file_vars[name], "source": "file"}

    env_val = os.environ.get(name)
    if env_val is not None:
        return {"name": name, "value": env_val, "source": "env"}

    raise InputError(
        message=f"Variable not found: {name}",
        code="E7002",
        details={"name": name, "env_file": env_file},
        suggestion=Suggestion(
            action="check_name",
            fix=f"Verify the variable name '{name}' is correct, or use 'list' to see available variables.",
        ),
    )


@app.command(
    name="set",
    annotations=Destructive,
    auth=["env:write"],
    capabilities=["fs:read", "fs:write", "env:write"],
    handoffs=[{"command": "get", "when": "verify the value was set"}, {"command": "validate", "when": "verify environment is still valid"}],
)
def set_(
    ctx: typer.Context,
    name: Annotated[str, Argument(help="Variable name")],
    value: Annotated[SecretInput[str], Argument(help="Variable value (secret)")],
    *,
    env_file: Annotated[str, Option(help="Dotenv file path")] = ".env",
) -> dict[str, Any]:
    """Set an environment variable in the dotenv file."""
    if not name.replace("_", "").isalnum():
        raise InputError(
            message=f"Invalid variable name: {name}",
            code="E7003",
            details={"name": name},
        )

    data = _parse_dotenv(env_file)
    existed = name in data
    data[name] = value

    if not getattr(ctx.obj, "dry_run", False):
        _write_dotenv(env_file, data)

    return {
        "name": name,
        "written": True,
        "file": env_file,
        "overwritten": existed,
    }


@app.command(
    name="list",
    paginated=True,
    annotations=ReadOnly,
    capabilities=["fs:read", "env:read"],
    handoffs=[{"command": "get", "when": "read a specific variable's value"}],
)
def list_(
    *,
    env_file: Annotated[str, Option(help="Dotenv file path")] = ".env",
    prefix: Annotated[str | None, Option(help="Filter by variable name prefix")] = None,
    show_values: Annotated[bool, Option(help="Show actual values (default: masked)")] = False,
) -> list[dict[str, Any]]:
    """List all variables in the dotenv file."""
    data = _parse_dotenv(env_file)

    results: list[dict[str, Any]] = []
    for name, value in sorted(data.items()):
        if prefix and not name.startswith(prefix):
            continue
        results.append({
            "name": name,
            "value": value if show_values else "***",
            "masked": not show_values,
        })

    return results


@app.command(
    annotations=ReadOnly,
    capabilities=["fs:read", "env:read"],
    handoffs=[{"command": "export", "when": "export validated environment to a file"}],
)
def validate(
    *,
    env_file: Annotated[str, Option(help="Dotenv file path")] = ".env",
    require: Annotated[str | None, Option(help="Required variable names (comma-separated)")] = None,
) -> dict[str, Any]:
    """Check that required variables are set and non-empty."""
    data = _parse_dotenv(env_file)

    if not require:
        return {
            "valid": True,
            "variable_count": len(data),
            "missing": [],
            "present": list(sorted(data.keys())),
        }

    required = {r.strip() for r in require.split(",") if r.strip()}
    present = sorted(required & set(data.keys()))
    missing = sorted(required - set(data.keys()))

    empty = [name for name in present if not data[name].strip()]
    if empty:
        missing.extend(empty)
        present = [p for p in present if p not in empty]

    return {
        "valid": len(missing) == 0,
        "variable_count": len(data),
        "missing": sorted(missing),
        "present": present,
    }


@app.command(
    annotations=ReadOnly,
    capabilities=["fs:read", "env:read"],
)
def export(
    *,
    env_file: Annotated[str, Option(help="Dotenv file path")] = ".env",
    format_: Annotated[str, Option("--format", help="Format: dotenv, json, or shell")] = "dotenv",
) -> dict[str, Any]:
    """Export variables in various formats."""
    if format_ not in ("dotenv", "json", "shell"):
        raise InputError(
            message=f"Unsupported format: {format_}. Use 'dotenv', 'json', or 'shell'.",
            code="E7004",
            details={"format": format_},
        )

    data = _parse_dotenv(env_file)

    if format_ == "dotenv":
        output = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    elif format_ == "json":
        output = ""  # The dict itself is the JSON output
    else:  # shell
        output = "\n".join(f"export {k}={v}" for k, v in sorted(data.items()))

    return {
        "format": format_,
        "variable_count": len(data),
        "variables": data if format_ == "json" else None,
        "output": output if format_ != "json" else None,
    }


if __name__ == "__main__":
    app()
