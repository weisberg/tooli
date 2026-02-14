"""Tests for context confirmation and prompt handling."""

from __future__ import annotations

import io
import json
import types

import pytest
import typer
from typer.testing import CliRunner

from tooli import Tooli
from tooli.context import _open_tty_prompt_stream, _prompt_device_path, _read_confirmation_response
from tooli.errors import InputError


def test_prompt_device_path_uses_expected_platform_devices(monkeypatch) -> None:
    """Prompt device should be platform-specific."""
    from tooli import context

    monkeypatch.setattr(context, "os", types.SimpleNamespace(name="posix"))
    assert _prompt_device_path() == "/dev/tty"

    monkeypatch.setattr(context, "os", types.SimpleNamespace(name="nt"))
    assert _prompt_device_path() == "CON"


def test_open_tty_prompt_stream_falls_back_on_unavailable_device(monkeypatch) -> None:
    """Missing console/tty device should return None."""
    from tooli import context

    monkeypatch.setattr(context, "open", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("missing device")))
    monkeypatch.setattr(context, "os", types.SimpleNamespace(name="posix"))
    assert context._open_tty_prompt_stream() is None


def test_tty_stream_opened_with_platform_path(monkeypatch) -> None:
    """Open prompt stream should use the platform-specific path."""
    from tooli import context

    calls: dict[str, str] = {}

    def _fake_open(path: str, *args: object, **kwargs: object) -> io.StringIO:
        calls["path"] = path
        return io.StringIO()

    monkeypatch.setattr(context, "open", _fake_open)
    monkeypatch.setattr(context, "os", types.SimpleNamespace(name="nt"))

    stream = context._open_tty_prompt_stream()
    assert stream is not None
    assert calls["path"] == "CON"


def test_read_confirmation_response_rejects_invalid_input() -> None:
    """Invalid confirmation values should raise structured input errors."""
    with pytest.raises(InputError) as exc_info:
        _read_confirmation_response("Proceed?", io.StringIO("maybe\n"), default=False)

    assert exc_info.value.code == "E1008"


def test_confirm_falls_back_with_input_error_if_prompt_device_unavailable(monkeypatch) -> None:
    """Non-tty confirmation should surface InputError when prompt device is unavailable."""
    app = Tooli(name="test-app")

    @app.command()
    def confirm(ctx: typer.Context) -> str:
        return "confirmed" if ctx.obj.confirm("Proceed?") else "denied"

    monkeypatch.setattr("tooli.context._open_tty_prompt_stream", lambda: None)
    result = CliRunner().invoke(app, ["confirm"])
    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "E1007"
