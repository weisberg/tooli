"""Metadata container for Tooli command callbacks."""

from __future__ import annotations

from collections.abc import Callable  # noqa: TC003
from dataclasses import dataclass, field
from typing import Any

from tooli.annotations import ToolAnnotation  # noqa: TC001
from tooli.auth import AuthContext  # noqa: TC001
from tooli.security.policy import SecurityPolicy


@dataclass
class CommandMeta:
    """All Tooli metadata for a registered command callback.

    Attached as a single ``__tooli_meta__`` attribute on the callback
    function, replacing the previous 20+ individual ``setattr`` calls.
    """

    # App-level
    app: Any | None = None
    app_name: str = "tooli"
    app_version: str = "0.0.0"
    default_output: str = "auto"
    telemetry_pipeline: Any = None
    invocation_recorder: Any = None
    security_policy: SecurityPolicy = SecurityPolicy.OFF
    auth_context: AuthContext | None = None

    # Command-level
    annotations: ToolAnnotation | None = None
    examples: list[dict[str, Any]] = field(default_factory=list)
    error_codes: dict[str, str] = field(default_factory=dict)
    timeout: float | None = None
    cost_hint: str | None = None
    human_in_the_loop: bool = False
    auth: list[str] = field(default_factory=list)
    list_processing: bool = False
    paginated: bool = False
    version: str | None = None
    hidden: bool = False
    deprecated: bool = False
    deprecated_message: str | None = None
    max_tokens: int | None = None
    supports_dry_run: bool = False
    requires_approval: bool = False
    danger_level: str | None = None
    allow_python_eval: bool = False
    output_example: Any | None = None
    output_schema: dict[str, Any] | None = None
    secret_params: list[str] = field(default_factory=list)


def get_command_meta(callback: Callable[..., Any] | None) -> CommandMeta:
    """Retrieve CommandMeta from a callback, with safe defaults."""
    if callback is None:
        return CommandMeta()
    meta = getattr(callback, "__tooli_meta__", None)
    if isinstance(meta, CommandMeta):
        return meta
    return CommandMeta()


@dataclass
class ResourceMeta:
    """Metadata for MCP resource registrations."""

    uri: str
    description: str | None = None
    mime_type: str | None = None
    name: str | None = None
    hidden: bool = False
    tags: list[str] = field(default_factory=list)


@dataclass
class PromptMeta:
    """Metadata for MCP prompt registrations."""

    name: str
    description: str | None = None
    hidden: bool = False


def get_resource_meta(callback: Callable[..., Any] | None) -> ResourceMeta | None:
    """Read resource metadata from callback, when present."""
    if callback is None:
        return None
    meta = getattr(callback, "__tooli_resource_meta__", None)
    if isinstance(meta, ResourceMeta):
        return meta
    return None


def get_prompt_meta(callback: Callable[..., Any] | None) -> PromptMeta | None:
    """Read prompt metadata from callback, when present."""
    if callback is None:
        return None
    meta = getattr(callback, "__tooli_prompt_meta__", None)
    if isinstance(meta, PromptMeta):
        return meta
    return None
