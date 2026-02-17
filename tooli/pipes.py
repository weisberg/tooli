"""Pipe contract definitions for composable command chains."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class PipeContract:
    """Describes the input or output pipe format of a command.

    Used to auto-infer composition patterns between commands and to
    render pipe documentation in SKILL.md.
    """

    format: Literal["json", "jsonl", "text", "csv"]
    schema: dict[str, Any] | None = None
    description: str = ""
    example: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for storage in CommandMeta."""
        result: dict[str, Any] = {"format": self.format}
        if self.schema is not None:
            result["schema"] = self.schema
        if self.description:
            result["description"] = self.description
        if self.example is not None:
            result["example"] = self.example
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipeContract:
        """Reconstruct from a plain dict."""
        return cls(
            format=data.get("format", "json"),
            schema=data.get("schema"),
            description=data.get("description", ""),
            example=data.get("example"),
        )


def pipe_contracts_compatible(
    output: dict[str, Any] | None,
    input_: dict[str, Any] | None,
) -> bool:
    """Check whether an output pipe contract is compatible with an input."""
    if output is None or input_ is None:
        return False
    return output.get("format") == input_.get("format")
