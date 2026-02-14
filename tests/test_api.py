"""Tests for HTTP API integration."""

from __future__ import annotations

import json
from tooli import Tooli
from tooli.testing import TooliTestClient


def test_api_export_openapi() -> None:
    """api export-openapi should output valid OpenAPI schema."""
    app = Tooli(name="test-api")

    @app.command()
    def compute(x: int, y: int) -> int:
        """Add two numbers."""
        return x + y

    client = TooliTestClient(app)
    result = client.invoke(["api", "export-openapi"])
    assert result.exit_code == 0
    
    schema = json.loads(result.output)
    assert schema["openapi"] == "3.1.0"
    assert "/compute" in schema["paths"]
    assert "x" in schema["paths"]["/compute"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]
