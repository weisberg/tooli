"""Shared test fixtures for tooli tests."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from tooli import Tooli


@pytest.fixture
def runner() -> CliRunner:
    """Provide a CLI test runner."""
    return CliRunner()


@pytest.fixture
def app() -> Tooli:
    """Provide a fresh Tooli app instance for testing."""
    return Tooli(name="test-app", help="A test application")
