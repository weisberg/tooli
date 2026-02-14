"""Tests for dry-run support."""

from __future__ import annotations

import json
from typer.testing import CliRunner

from tooli import Tooli, dry_run_support, record_dry_action


def test_dry_run_support_returns_action_plan_as_result() -> None:
    app = Tooli(name="dry-run-app")

    @app.command()
    @dry_run_support
    def create(path: str) -> dict:
        record_dry_action("create_file", path)
        return {"written": path}

    runner = CliRunner()
    normal = runner.invoke(app, ["create", "/tmp/output.txt", "--json"])
    dry_run = runner.invoke(app, ["create", "/tmp/output.txt", "--dry-run", "--json"])

    assert normal.exit_code == 0
    normal_payload = json.loads(normal.output)
    assert normal_payload["ok"] is True
    assert normal_payload["result"] == {"written": "/tmp/output.txt"}
    assert normal_payload["meta"].get("dry_run") is False

    assert dry_run.exit_code == 0
    dry_run_payload = json.loads(dry_run.output)
    assert dry_run_payload["ok"] is True
    assert dry_run_payload["meta"].get("dry_run") is True
    assert dry_run_payload["result"] == [
        {"action": "create_file", "target": "/tmp/output.txt", "details": {}},
    ]


def test_dry_run_support_can_be_used_without_context() -> None:
    # record_dry_action should be safe when no Tooli command context is active.
    record_dry_action("noop", "/tmp/example")
