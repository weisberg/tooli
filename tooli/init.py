"""Project scaffolding for ``tooli init``."""

from __future__ import annotations

import re
from pathlib import Path


def _pyproject_template(name: str, *, minimal: bool = False) -> str:
    lines = [
        "[build-system]",
        'requires = ["setuptools>=61.0", "wheel"]',
        'build-backend = "setuptools.build_meta"',
        "",
        "[project]",
        f'name = "{name}"',
        'version = "0.1.0"',
        'description = "A CLI tool built with Tooli"',
        'requires-python = ">=3.10"',
        'dependencies = [',
        '    "tooli>=4.0",',
        "]",
        "",
        "[project.scripts]",
        f'{name} = "{name.replace("-", "_")}:app"',
    ]
    if not minimal:
        lines.extend([
            "",
            "[project.optional-dependencies]",
            "dev = [",
            '    "pytest>=7.0",',
            '    "ruff>=0.4",',
            "]",
        ])
    return "\n".join(lines) + "\n"


def _app_template(name: str, *, minimal: bool = False) -> str:
    lines = [
        f'"""CLI entry point for {name}."""',
        "",
        "from tooli import Tooli",
        "",
        f'app = Tooli(name="{name}", description="{name} — a Tooli CLI tool.", version="0.1.0")',
        "",
        "",
        '@app.command("hello")',
        "def hello(name: str = \"world\") -> str:",
        '    """Say hello."""',
        '    return f"Hello, {{name}}!"',
        "",
        "",
        'if __name__ == "__main__":',
        "    app()",
        "",
    ]
    if not minimal:
        lines.insert(1, "")
        lines.insert(2, "from tooli.annotations import ReadOnly")
    return "\n".join(lines)


def _test_template(name: str) -> str:
    module = name.replace("-", "_")
    return (
        f'"""Basic tests for {name}."""\n\n'
        f"from {module} import app\n\n\n"
        "def test_hello():\n"
        '    """Verify the hello command returns a greeting."""\n'
        "    # Import and call the callback directly\n"
        "    tools = app.get_tools()\n"
        "    assert any(t.name == 'hello' for t in tools)\n"
    )


def _skill_md_template(name: str) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        f'description: "{name} CLI tool"\n'
        "version: 0.1.0\n"
        "---\n"
        f"\n# {name}\n\n"
        "Run `--agent-bootstrap` to regenerate this file.\n"
    )


def _claude_md_template(name: str) -> str:
    return (
        f"# {name}\n\n"
        "## Commands\n\n"
        f"- `{name} hello --name world`\n\n"
        "## Patterns\n\n"
        "- Use `--json` for machine-readable output.\n"
        "- Use `--dry-run` before destructive operations.\n"
    )


def _readme_template(name: str) -> str:
    return (
        f"# {name}\n\n"
        "A CLI tool built with [Tooli](https://github.com/weisberg/tooli).\n\n"
        "## Install\n\n"
        "```bash\n"
        f"pip install -e .\n"
        "```\n\n"
        "## Usage\n\n"
        "```bash\n"
        f"{name} hello --name world\n"
        "```\n"
    )


def _rewrite_typer_imports(source: str) -> str:
    """Rewrite basic Typer imports to Tooli equivalents (best-effort AST-free)."""
    result = source
    result = re.sub(r"import typer\b", "import tooli", result)
    result = re.sub(r"from typer import\b", "from tooli import", result)
    result = re.sub(r"\btyper\.Typer\b", "Tooli", result)
    result = re.sub(r"\btyper\.Option\b", "Option", result)
    result = re.sub(r"\btyper\.Argument\b", "Argument", result)
    return result


def scaffold_project(
    name: str,
    *,
    output_dir: str | None = None,
    minimal: bool = False,
    from_typer: str | None = None,
) -> list[str]:
    """Create a new Tooli project skeleton.

    Returns the list of created file paths.
    """
    base = Path(output_dir) if output_dir else Path(name)
    module = name.replace("-", "_")
    base.mkdir(parents=True, exist_ok=True)

    created: list[str] = []

    def _write(rel_path: str, content: str) -> None:
        path = base / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(str(path))

    _write("pyproject.toml", _pyproject_template(name, minimal=minimal))

    if from_typer is not None:
        source = Path(from_typer).read_text(encoding="utf-8")
        _write(f"{module}.py", _rewrite_typer_imports(source))
    else:
        _write(f"{module}.py", _app_template(name, minimal=minimal))

    if not minimal:
        _write(f"test_{module}.py", _test_template(name))
        _write("SKILL.md", _skill_md_template(name))
        _write("CLAUDE.md", _claude_md_template(name))
        _write("README.md", _readme_template(name))

    return created
