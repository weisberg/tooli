"""Project Scaffolder example app.

Scaffold new project directory structures with dry-run preview.
Showcases: Destructive annotation, DryRunRecorder, Idempotent validation,
confirmation-safe workflows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer  # noqa: TC002

from tooli import Argument, Option, Tooli, dry_run_support, record_dry_action
from tooli.annotations import Destructive, Idempotent, ReadOnly
from tooli.errors import InputError

app = Tooli(name="proj", help="Project scaffolding tool")

TEMPLATES: dict[str, dict[str, str]] = {
    "python": {
        "pyproject.toml": '[project]\nname = "{name}"\nversion = "0.1.0"\n',
        "src/{name}/__init__.py": '"""Top-level package for {name}."""\n',
        "src/{name}/main.py": '"""Main entry point."""\n\n\ndef main() -> None:\n    print("Hello from {name}!")\n',
        "tests/__init__.py": "",
        "tests/test_main.py": '"""Tests for main module."""\n\n\ndef test_placeholder() -> None:\n    assert True\n',
        "README.md": "# {name}\n\nA Python project.\n",
        ".gitignore": "__pycache__/\n*.pyc\n.venv/\ndist/\n*.egg-info/\n",
    },
    "cli": {
        "pyproject.toml": '[project]\nname = "{name}"\nversion = "0.1.0"\n\n[project.scripts]\n{name} = "{name}.cli:main"\n',
        "src/{name}/__init__.py": '"""Top-level package for {name}."""\n',
        "src/{name}/cli.py": '"""CLI entry point."""\n\nimport click\n\n\n@click.command()\ndef main() -> None:\n    """Run {name}."""\n    click.echo("Hello from {name}!")\n',
        "tests/__init__.py": "",
        "tests/test_cli.py": '"""Tests for CLI."""\n\n\ndef test_placeholder() -> None:\n    assert True\n',
        "README.md": "# {name}\n\nA CLI tool.\n",
        ".gitignore": "__pycache__/\n*.pyc\n.venv/\ndist/\n*.egg-info/\n",
    },
    "library": {
        "pyproject.toml": '[project]\nname = "{name}"\nversion = "0.1.0"\n',
        "src/{name}/__init__.py": '"""Public API for {name}."""\n\n__version__ = "0.1.0"\n',
        "src/{name}/core.py": '"""Core module."""\n',
        "tests/__init__.py": "",
        "tests/test_core.py": '"""Tests for core module."""\n\n\ndef test_placeholder() -> None:\n    assert True\n',
        "README.md": "# {name}\n\nA Python library.\n",
        ".gitignore": "__pycache__/\n*.pyc\n.venv/\ndist/\n*.egg-info/\n",
        "LICENSE": "MIT License\n",
    },
}


@app.command(annotations=Destructive)
@dry_run_support
def init(
    ctx: typer.Context,
    name: Annotated[str, Argument(help="Project name")],
    *,
    template: Annotated[str, Option(help="Template: python, cli, or library")] = "python",
    directory: Annotated[str, Option(help="Parent directory for the project")] = ".",
) -> dict[str, Any]:
    """Scaffold a new project directory structure."""
    if template not in TEMPLATES:
        raise InputError(
            message=f"Unknown template: {template}. Available: {', '.join(TEMPLATES)}",
            code="E6001",
            details={"template": template},
        )

    project_dir = Path(directory) / name
    if project_dir.exists():
        raise InputError(
            message=f"Directory already exists: {project_dir}",
            code="E6002",
            details={"path": str(project_dir)},
        )

    file_map = TEMPLATES[template]
    created_files: list[str] = []

    for rel_path_tpl, content_tpl in file_map.items():
        rel_path = rel_path_tpl.replace("{name}", name)
        full_path = project_dir / rel_path
        content = content_tpl.replace("{name}", name)

        record_dry_action("create_file", str(full_path), details={"size": len(content)})

        if not getattr(ctx.obj, "dry_run", False):
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

        created_files.append(rel_path)

    return {
        "project": name,
        "template": template,
        "directory": str(project_dir),
        "files_created": created_files,
        "file_count": len(created_files),
    }


@app.command(annotations=Destructive)
@dry_run_support
def add_tool(
    ctx: typer.Context,
    name: Annotated[str, Argument(help="Command/tool name to add")],
    *,
    directory: Annotated[str, Option(help="Project directory")] = ".",
) -> dict[str, Any]:
    """Add a new command file to an existing project."""
    project_dir = Path(directory)
    if not project_dir.exists():
        raise InputError(
            message=f"Project directory not found: {directory}",
            code="E6003",
            details={"path": directory},
        )

    src_dirs = list(project_dir.glob("src/*/"))
    if not src_dirs:
        raise InputError(
            message="No src/ package found. Is this a valid project?",
            code="E6004",
            details={"path": directory},
        )

    package_dir = src_dirs[0]
    tool_file = package_dir / f"{name}.py"
    test_file = project_dir / "tests" / f"test_{name}.py"

    tool_content = f'"""{name} command."""\n\n\ndef run() -> None:\n    """Execute {name}."""\n    print("Running {name}")\n'
    test_content = f'"""Tests for {name}."""\n\n\ndef test_{name}_placeholder() -> None:\n    assert True\n'

    record_dry_action("create_file", str(tool_file), details={"size": len(tool_content)})
    record_dry_action("create_file", str(test_file), details={"size": len(test_content)})

    if not getattr(ctx.obj, "dry_run", False):
        tool_file.write_text(tool_content, encoding="utf-8")
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(test_content, encoding="utf-8")

    return {
        "tool_name": name,
        "files_created": [str(tool_file), str(test_file)],
    }


@app.command(annotations=Idempotent | ReadOnly)
def validate(
    *,
    directory: Annotated[str, Option(help="Project directory")] = ".",
) -> dict[str, Any]:
    """Check project structure for required files."""
    project_dir = Path(directory)
    if not project_dir.exists():
        raise InputError(
            message=f"Directory not found: {directory}",
            code="E6005",
            details={"path": directory},
        )

    required = ["pyproject.toml", "README.md"]
    optional = [".gitignore", "LICENSE"]

    found: list[str] = []
    missing: list[str] = []
    extras: list[str] = []

    for name in required:
        if (project_dir / name).exists():
            found.append(name)
        else:
            missing.append(name)

    for name in optional:
        if (project_dir / name).exists():
            extras.append(name)

    has_src = any(project_dir.glob("src/*/"))
    has_tests = (project_dir / "tests").is_dir()

    return {
        "valid": len(missing) == 0 and has_src,
        "directory": str(project_dir),
        "found": found,
        "missing": missing,
        "optional_found": extras,
        "has_src_package": has_src,
        "has_tests": has_tests,
    }


@app.command(annotations=ReadOnly)
def info(
    *,
    directory: Annotated[str, Option(help="Project directory")] = ".",
) -> dict[str, Any]:
    """Show project metadata from pyproject.toml."""
    project_dir = Path(directory)
    pyproject = project_dir / "pyproject.toml"

    if not pyproject.exists():
        raise InputError(
            message=f"pyproject.toml not found in {directory}",
            code="E6006",
            details={"path": directory},
        )

    content = pyproject.read_text(encoding="utf-8")
    info: dict[str, Any] = {"directory": str(project_dir)}

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("name"):
            info["name"] = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("version"):
            info["version"] = line.split("=", 1)[1].strip().strip('"')

    file_count = sum(1 for _ in project_dir.rglob("*") if _.is_file())
    info["file_count"] = file_count

    return info


if __name__ == "__main__":
    app()
