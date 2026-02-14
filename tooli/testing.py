"""Test utilities for Tooli applications."""

from __future__ import annotations

import json
from typing import Any

from typer.testing import CliRunner, Result

from tooli.app import Tooli


class TooliTestClient:
    """Wrapper around CliRunner with Tooli-specific assertions."""

    def __init__(self, app: Tooli) -> None:
        self.app = app
        self.runner = CliRunner()

    def invoke(self, *args: Any, **kwargs: Any) -> Result:
        return self.runner.invoke(self.app, *args, **kwargs)

    def assert_json_envelope(self, result: Result) -> dict[str, Any]:
        """Verify output matches Tooli JSON envelope shape."""
        assert result.exit_code == 0
        try:
            payload = json.loads(result.output)
            assert "ok" in payload
            assert "result" in payload
            assert "meta" in payload
            assert "tool" in payload["meta"]
            assert "version" in payload["meta"]
            return payload
        except (json.JSONDecodeError, KeyError, AssertionError) as e:
            raise AssertionError(f"Invalid JSON envelope: {e}
Output: {result.output}") from e

    def assert_exit_code(self, result: Result, expected_code: int) -> None:
        """Verify exit code."""
        assert result.exit_code == expected_code, f"Expected exit code {expected_code}, got {result.exit_code}. Output: {result.output}"
