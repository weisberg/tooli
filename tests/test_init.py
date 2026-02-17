"""Tests for ``tooli init`` project scaffolding."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from tooli.init import _rewrite_typer_imports, scaffold_project


class TestScaffoldProject:
    def test_default_scaffold(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = scaffold_project("my-tool", output_dir=os.path.join(tmp, "my-tool"))
            assert len(created) == 6
            names = [os.path.basename(p) for p in created]
            assert "pyproject.toml" in names
            assert "my_tool.py" in names
            assert "test_my_tool.py" in names
            assert "SKILL.md" in names
            assert "CLAUDE.md" in names
            assert "README.md" in names

    def test_minimal_scaffold(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = scaffold_project("my-tool", output_dir=os.path.join(tmp, "my-tool"), minimal=True)
            assert len(created) == 2
            names = [os.path.basename(p) for p in created]
            assert "pyproject.toml" in names
            assert "my_tool.py" in names

    def test_pyproject_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "test-proj")
            scaffold_project("test-proj", output_dir=out)
            content = Path(os.path.join(out, "pyproject.toml")).read_text()
            assert 'name = "test-proj"' in content
            assert '"tooli>=4.0"' in content

    def test_app_template_has_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "demo")
            scaffold_project("demo", output_dir=out)
            content = Path(os.path.join(out, "demo.py")).read_text()
            assert "Tooli" in content
            assert '@app.command("hello")' in content

    def test_from_typer_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Write a fake Typer source
            typer_src = os.path.join(tmp, "old_app.py")
            with open(typer_src, "w") as f:
                f.write("import typer\napp = typer.Typer()\n")

            out = os.path.join(tmp, "migrated")
            scaffold_project("migrated", output_dir=out, from_typer=typer_src)
            content = Path(os.path.join(out, "migrated.py")).read_text()
            assert "import tooli" in content
            assert "typer" not in content.lower() or "Tooli" in content


class TestTyperRewrite:
    def test_import_rewrite(self):
        source = "import typer\nfrom typer import Option\n"
        result = _rewrite_typer_imports(source)
        assert "import tooli" in result
        assert "from tooli import Option" in result

    def test_typer_class_rewrite(self):
        source = "app = typer.Typer(name='test')\n"
        result = _rewrite_typer_imports(source)
        assert "Tooli" in result
        assert "typer.Typer" not in result

    def test_option_argument_rewrite(self):
        source = "x: str = typer.Option('hello')\ny: str = typer.Argument('world')\n"
        result = _rewrite_typer_imports(source)
        assert "Option" in result
        assert "Argument" in result
        assert "typer.Option" not in result
        assert "typer.Argument" not in result
