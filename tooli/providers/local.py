"""Local provider sourcing tools from a Tooli app."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tooli.command_meta import get_command_meta
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
            meta = get_command_meta(cmd.callback)
            tools.append(ToolDef(
                name=cmd.name or cmd.callback.__name__,  # type: ignore[union-attr]
                callback=cmd.callback,  # type: ignore[arg-type]
                help=cmd.help or cmd.callback.__doc__ or "",
                hidden=cmd.hidden,
                tags=list(getattr(meta, "tags", [])),
            ))
        return tools
