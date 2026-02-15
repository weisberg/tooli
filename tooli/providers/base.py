"""Base provider interface for sourcing Tooli tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tooli.transforms import ToolDef


class Provider(ABC):
    """Base class for all tool providers."""

    @abstractmethod
    def get_tools(self) -> list[ToolDef]:
        """Return a list of tool definitions from this provider."""
        pass
