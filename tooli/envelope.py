"""JSON envelope models for Tooli structured output."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EnvelopeMeta(BaseModel):
    tool: str
    version: str
    duration_ms: int = Field(ge=0)
    dry_run: bool = False
    warnings: list[str] = Field(default_factory=list)


class Envelope(BaseModel):
    ok: bool
    result: Any | None = None
    meta: EnvelopeMeta
