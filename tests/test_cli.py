"""Tests for the top-level Tooli launcher."""

from __future__ import annotations

from typer.testing import CliRunner

from tooli.cli import cli


def _build_example_app_file(
    tmp_path,
    *,
    app_name: str = "sample",
    app_variable: str = "app",
):
    module_path = tmp_path / "sample_tool_app.py"
    module_path.write_text(
        f'''
from tooli import Tooli

{app_variable} = Tooli(name="{app_name}")


@{app_variable}.command()
def greet(name: str) -> str:
    return f"hello {{name}}"
''',
        encoding="utf-8",
    )
    return module_path


def test_launcher_loads_file_app_and_invokes_mcp(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    called: dict[str, object] = {}

    def fake_serve_mcp(app_obj: object, **kwargs: object) -> None:
        called["name"] = app_obj.info.name
        called["kwargs"] = kwargs

    monkeypatch.setattr("tooli.cli.serve_mcp", fake_serve_mcp)

    app_module = _build_example_app_file(tmp_path=tmp_path, app_name="loaded")

    result = runner.invoke(
        cli,
        ["serve", str(app_module), "--transport", "stdio"],
        prog_name="tooli",
    )
    assert result.exit_code == 0
    assert called["name"] == "loaded"
    assert isinstance(called.get("kwargs"), dict)
    assert called["kwargs"].get("transport") == "stdio"  # type: ignore[index]
    assert called["kwargs"].get("defer_loading") is False  # type: ignore[index]


def test_launcher_supports_colon_app_selector(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    called: dict[str, str] = {}

    module_path = tmp_path / "picker.py"
    module_path.write_text(
        '''
from tooli import Tooli

primary = Tooli(name="primary-app")
secondary = Tooli(name="secondary-app")

@secondary.command()
def ping() -> str:
    return "pong"
''',
        encoding="utf-8",
    )

    def fake_serve_mcp(app_obj: object, **_: object) -> None:
        called["name"] = app_obj.info.name

    monkeypatch.setattr("tooli.cli.serve_mcp", fake_serve_mcp)
    result = runner.invoke(
        cli,
        ["serve", f"{module_path}:secondary", "--transport", "stdio"],
        prog_name="tooli",
    )

    assert result.exit_code == 0
    assert called["name"] == "secondary-app"
