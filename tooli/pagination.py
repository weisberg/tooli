"""Pagination and output-shaping helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from tooli.errors import InputError


def _parse_filter_expression(filter_spec: str) -> tuple[str, str]:
    if "=" not in filter_spec:
        raise InputError(
            message=f"Invalid --filter format: {filter_spec!r}. Expected key=value.",
            code="E1001",
        )
    key, value = filter_spec.split("=", 1)
    return key, value


@dataclass(frozen=True)
class PaginationParams:
    """Normalized pagination and filtering options from CLI flags."""

    limit: int | None = None
    cursor: int = 0
    fields: list[str] = field(default_factory=list)
    filter: str | None = None
    max_items: int | None = None

    @classmethod
    def from_flags(
        cls,
        *,
        limit: int | None,
        cursor: str | None,
        fields: str | None,
        filter: str | None,
        max_items: int | None,
        select: str | None = None,
    ) -> PaginationParams:
        """Build normalized params from CLI flag values."""
        cursor_value = 0
        if cursor is not None:
            try:
                cursor_value = int(cursor)
            except ValueError as exc:
                raise InputError(
                    message=f"Invalid --cursor value: {cursor!r}. Expected an integer.",
                    code="E1001",
                ) from exc
            if cursor_value < 0:
                raise InputError(message="--cursor must be >= 0.", code="E1001")

        fields_value = fields or select or ""
        parsed_fields = [part.strip() for part in fields_value.split(",") if part.strip()]
        filter_value = filter.strip() if filter is not None else None
        if filter_value == "":
            filter_value = None

        return cls(
            limit=limit,
            cursor=cursor_value,
            fields=parsed_fields,
            filter=filter_value,
            max_items=max_items,
        )

    def filter_expr(self) -> tuple[str, str] | None:
        """Return key/value filter pair if `--filter` was provided."""
        if not self.filter:
            return None
        return _parse_filter_expression(self.filter)

    def should_filter_fields(self) -> bool:
        return len(self.fields) > 0
