"""Tests for optional telemetry collection."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from tooli import Tooli
from tooli.telemetry_pipeline import DEFAULT_TELEMETRY_FILE


def test_telemetry_disabled_by_default(tmp_path, monkeypatch) -> None:
    """Telemetry should be disabled when neither env nor explicit setting is set."""
    monkeypatch.delenv("TOOLI_TELEMETRY", raising=False)
    storage_dir = tmp_path / "telemetry-disabled"

    app = Tooli(name="telemetry-app", telemetry_storage_dir=storage_dir)

    @app.command()
    def ping() -> dict:
        return {"ok": True}

    @app.command()
    def noop() -> None:
        return None

    result = CliRunner().invoke(app, ["ping", "--text"])
    assert result.exit_code == 0
    assert not (storage_dir / DEFAULT_TELEMETRY_FILE).exists()


def test_telemetry_can_be_enabled_explicitly(tmp_path) -> None:
    """Explicit Tooli(telemetry=True) should enable event collection."""
    storage_dir = tmp_path / "telemetry-enabled"
    app = Tooli(name="telemetry-tool", telemetry=True, telemetry_storage_dir=storage_dir)

    @app.command()
    def success() -> dict[str, str]:
        return {"status": "ok"}

    @app.command()
    def fail() -> None:
        raise ValueError("boom")

    runner = CliRunner()
    run_success = runner.invoke(app, ["success", "--text"])
    run_fail = runner.invoke(app, ["fail", "--text"])
    assert run_success.exit_code == 0
    assert run_fail.exit_code == 70

    events_file = storage_dir / DEFAULT_TELEMETRY_FILE
    events = [json.loads(line) for line in events_file.read_text().splitlines() if line.strip()]

    assert len(events) == 2
    by_command = {event["command"].rsplit(".", 1)[-1]: event for event in events}

    success_event = by_command["success"]
    failure_event = by_command["fail"]

    assert success_event["app"] == "telemetry-tool"
    assert success_event["command"] == "telemetry-tool.success"
    assert success_event["success"] is True
    assert success_event["exit_code"] == 0
    assert isinstance(success_event["duration_ms"], int)

    assert failure_event["app"] == "telemetry-tool"
    assert failure_event["success"] is False
    assert failure_event["error_code"] == "E5000"
    assert failure_event["error_category"] == "internal"
    assert failure_event["exit_code"] == 70

    for event in events:
        assert event["command"].startswith("telemetry-tool.")
        assert set(event).issuperset({
            "schema_version",
            "recorded_at",
            "app",
            "command",
            "success",
            "duration_ms",
            "exit_code",
            "error_code",
            "error_category",
        })
        assert "args" not in event
        assert "result" not in event
