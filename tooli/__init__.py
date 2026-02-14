"""tooli — The agent-native CLI framework for Python."""

from __future__ import annotations

from typing import Annotated

from typer import Argument, Option

from tooli.app import Tooli
from tooli.input import SecretInput, StdinOr

__version__ = "0.1.0"
__all__ = [
    "Annotated",
    "Argument",
    "Option",
    "Tooli",
    "SecretInput",
    "StdinOr",
]
