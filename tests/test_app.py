"""Tests for the core Tooli application class."""

from __future__ import annotations

from typing import Annotated

from typer.testing import CliRunner

from tooli import Argument, Option, Tooli


def test_tooli_creates_basic_app() -> None:
    """Tooli instance should be usable as a CLI app."""
    app = Tooli(name="test-app")
    assert app.info.name == "test-app"


def test_tooli_stores_version() -> None:
    """Tooli should store version metadata."""
    app = Tooli(name="test-app", version="1.2.3")
    assert app.version == "1.2.3"


def test_tooli_default_version() -> None:
    """Tooli should default to 0.0.0 version."""
    app = Tooli(name="test-app")
    assert app.version == "0.0.0"


def test_tooli_stores_config() -> None:
    """Tooli should store agent-specific configuration."""
    app = Tooli(
        name="test-app",
        default_output="json",
        mcp_transport="http",
        skill_auto_generate=True,
        permissions={"fs": "read"},
    )
    assert app.default_output == "json"
    assert app.mcp_transport == "http"
    assert app.skill_auto_generate is True
    assert app.permissions == {"fs": "read"}


def test_command_decorator_works() -> None:
    """@app.command() should work identically to Typer's."""
    app = Tooli(name="test-app")

    @app.command()
    def hello(name: Annotated[str, Argument(help="Name to greet")]) -> None:
        print(f"Hello {name}")

    runner = CliRunner()
    result = runner.invoke(app, ["world"])
    assert result.exit_code == 0
    assert "Hello world" in result.output


def test_command_with_options() -> None:
    """Commands with Options should parse correctly."""
    app = Tooli(name="test-app")

    @app.command()
    def greet(
        name: Annotated[str, Argument(help="Name to greet")],
        greeting: Annotated[str, Option(help="Greeting to use")] = "Hello",
    ) -> None:
        print(f"{greeting} {name}")

    runner = CliRunner()
    result = runner.invoke(app, ["world", "--greeting", "Hi"])
    assert result.exit_code == 0
    assert "Hi world" in result.output


def test_single_command_app() -> None:
    """A Tooli app with a single command should work without subcommands."""
    app = Tooli(name="test-app")

    @app.command()
    def main(name: Annotated[str, Argument(help="Name")]) -> None:
        print(f"Hello {name}")

    runner = CliRunner()
    result = runner.invoke(app, ["world"])
    assert result.exit_code == 0
    assert "Hello world" in result.output


def test_multi_command_app() -> None:
    """A Tooli app with multiple commands should use subcommand names."""
    app = Tooli(name="test-app")

    @app.command()
    def hello(name: Annotated[str, Argument(help="Name")]) -> None:
        print(f"Hello {name}")

    @app.command()
    def goodbye(name: Annotated[str, Argument(help="Name")]) -> None:
        print(f"Goodbye {name}")

    runner = CliRunner()
    result = runner.invoke(app, ["hello", "world"])
    assert result.exit_code == 0
    assert "Hello world" in result.output

    result = runner.invoke(app, ["goodbye", "world"])
    assert result.exit_code == 0
    assert "Goodbye world" in result.output


def test_help_output() -> None:
    """--help should work on Tooli apps."""
    app = Tooli(name="test-app", help="A test application")

    @app.command()
    def hello(name: Annotated[str, Argument(help="Name to greet")]) -> None:
        """Say hello to someone."""
        print(f"Hello {name}")

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Say hello to someone" in result.output
    assert "Name to greet" in result.output


def test_imports() -> None:
    """Key symbols should be importable from tooli."""
    from tooli import Annotated, Argument, Option, Tooli

    assert Tooli is not None
    assert Annotated is not None
    assert Option is not None
    assert Argument is not None
