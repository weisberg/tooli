"""Transform pipeline for Tooli tool surfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolDef:
    """A portable definition of a Tooli command, used by transforms and providers."""
    name: str
    callback: Callable[..., Any]
    help: str = ""
    hidden: bool = False
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class Transform(ABC):
    """Base class for all tool transforms."""
    
    @abstractmethod
    def apply(self, tools: list[ToolDef]) -> list[ToolDef]:
        """Apply the transform to a list of tool definitions."""
        pass


class NamespaceTransform(Transform):
    """Prepends a prefix to all tool names."""
    
    def __init__(self, prefix: str, separator: str = "_") -> None:
        self.prefix = prefix
        self.separator = separator
        
    def apply(self, tools: list[ToolDef]) -> list[ToolDef]:
        return [
            ToolDef(
                name=f"{self.prefix}{self.separator}{tool.name}",
                callback=tool.callback,
                help=tool.help,
                hidden=tool.hidden,
                tags=list(tool.tags),
                metadata=dict(tool.metadata),
            )
            for tool in tools
        ]


class VisibilityTransform(Transform):
    """Filters tools based on their tags or hidden status."""
    
    def __init__(
        self, 
        include_tags: list[str] | None = None, 
        exclude_tags: list[str] | None = None,
        include_hidden: bool = False
    ) -> None:
        self.include_tags = set(include_tags or [])
        self.exclude_tags = set(exclude_tags or [])
        self.include_hidden = include_hidden
        
    def apply(self, tools: list[ToolDef]) -> list[ToolDef]:
        filtered: list[ToolDef] = []
        for tool in tools:
            if not self.include_hidden and tool.hidden:
                continue
            
            tool_tags = set(tool.tags)
            
            if self.exclude_tags and (tool_tags & self.exclude_tags):
                continue
                
            if self.include_tags and not (tool_tags & self.include_tags):
                continue
                
            filtered.append(tool)
        return filtered
