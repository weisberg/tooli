"""Local provider sourcing tools from a Tooli app."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tooli.providers.base import Provider
from tooli.transforms import ToolDef

if TYPE_CHECKING:
    from tooli.app import Tooli


class LocalProvider(Provider):
    """Sources tools from decorated functions in a Tooli app."""
    
    def __init__(self, app: Tooli) -> None:
        self.app = app
        
    def get_tools(self) -> list[ToolDef]:
        tools = []
        for cmd in self.app.registered_commands:
            tools.append(ToolDef(
                name=cmd.name or cmd.callback.__name__,
                callback=cmd.callback,
                help=cmd.help or cmd.callback.__doc__ or "",
                hidden=cmd.hidden,
                # Typer doesn't have tags on commands by default, 
                # but we might have added them in metadata.
                tags=getattr(cmd.callback, "__tooli_tags__", [])
            ))
        return tools
