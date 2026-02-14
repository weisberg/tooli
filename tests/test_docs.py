"""Tests for documentation generators."""

from __future__ import annotations

import os
from tooli import Tooli
from tooli.testing import TooliTestClient


def test_docs_llms_generation() -> None:
    app = Tooli(name="test-docs")

    @app.command()
    def hello() -> str:
        """Say hello."""
        return "world"

    client = TooliTestClient(app)
    # The command writes files to current directory
    try:
        result = client.invoke(["docs", "llms"])
        assert result.exit_code == 0
        assert os.path.exists("llms.txt")
        assert os.path.exists("llms-full.txt")
        
        with open("llms.txt") as f:
            content = f.read()
            assert "# test-docs" in content
            assert "- [hello](llms-full.txt#hello)" in content
    finally:
        if os.path.exists("llms.txt"):
            os.remove("llms.txt")
        if os.path.exists("llms-full.txt"):
            os.remove("llms-full.txt")


def test_docs_man_generation() -> None:
    app = Tooli(name="test-man")

    @app.command()
    def greet() -> str:
        """Greet user."""
        return "hi"

    client = TooliTestClient(app)
    try:
        result = client.invoke(["docs", "man"])
        assert result.exit_code == 0
        assert os.path.exists("test-man.1")
        
        with open("test-man.1") as f:
            content = f.read()
            assert ".TH TEST-MAN" in content
            assert ".SH NAME" in content
            assert "greet" in content
    finally:
        if os.path.exists("test-man.1"):
            os.remove("test-man.1")
