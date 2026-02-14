"""Token-efficient AST outline extractor for Tooli.

`code-lens` is designed for agents that need structure fast, not implementation
noise. It scans a single Python file and returns a compact symbol outline that can
fit comfortably into a narrow context window.

Agent pain point solved:
- opening full source files in large projects is expensive and distracts from
  intent,
- output becomes inconsistent when regexes accidentally grab extra lines,
- downstream prompts fail when symbols are embedded in prose.

Communication contract:
- response is deterministic JSON-ready data,
- output can be filtered by `--output`, including `json`/`jsonl` modes,
- command examples are embedded for auto-discovery in `--help` and MCP metadata.

Example usage:
- `python code_lens.py outline main.py`
- `python code_lens.py outline main.py --detail detailed`
- `python code_lens.py outline main.py --max-depth 2`
- `python code_lens.py outline main.py --exclude-private`
- `python code_lens.py outline main.py --output jsonl`
"""

from __future__ import annotations

import ast
import os
from typing import Annotated, Any

from tooli import Argument, Option, Tooli
from tooli.annotations import Idempotent, ReadOnly
from tooli.errors import InputError, Suggestion

app = Tooli(name="code-lens", description="Extract structural outlines from Python files")


def _normalize_detail(value: str) -> str:
    normalized = value.lower().strip()
    if normalized not in {"concise", "detailed"}:
        raise InputError(
            message=f"Unsupported detail level: {value}",
            code="E1001",
            suggestion=Suggestion(
                action="set detail",
                fix="Use --detail concise or --detail detailed.",
                example="python code_lens.py outline main.py --detail detailed",
            ),
        )
    return normalized


def _validate_depth(value: int | None) -> int | None:
    if value is None:
        return None
    if value < 1:
        raise InputError(
            message="max-depth must be at least 1.",
            code="E1014",
            suggestion=Suggestion(
                action="increase max-depth",
                fix="Set --max-depth to a positive integer.",
                example="python code_lens.py outline main.py --max-depth 4",
            ),
            details={"max_depth": value},
        )
    if value > 20:
        raise InputError(
            message="max-depth is capped for safety at 20.",
            code="E1015",
            suggestion=Suggestion(
                action="reduce max-depth",
                fix="Use a smaller --max-depth unless deep nesting is truly required.",
                example="python code_lens.py outline main.py --max-depth 8",
            ),
            details={"max_depth": value},
        )
    return value


def _node_signature(node: ast.AST) -> str | None:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        return f"{prefix}{node.name}({ast.unparse(node.args)})"
    if isinstance(node, ast.ClassDef):
        if not node.bases:
            return node.name
        bases = ", ".join(ast.unparse(base) for base in node.bases)
        return f"{node.name}({bases})"
    return None


def _collect_outlines(
    nodes: list[ast.stmt],
    *,
    detail: str,
    include_private: bool,
    max_depth: int | None,
    prefix: str | None = None,
    depth: int = 0,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef)):
            continue

        if not include_private and node.name.startswith("_"):
            continue

        if max_depth is not None and depth >= max_depth:
            continue

        kind = "class" if isinstance(node, ast.ClassDef) else "function"
        qualified_name = ".".join([part for part in (prefix, node.name) if part])

        if detail == "concise":
            items.append(
                {
                    "kind": kind,
                    "name": node.name,
                    "qualified_name": qualified_name,
                    "line": node.lineno,
                }
            )
        else:
            payload: dict[str, Any] = {
                "kind": kind,
                "name": node.name,
                "qualified_name": qualified_name,
                "signature": _node_signature(node),
                "line": node.lineno,
                "docstring": ast.get_docstring(node),
            }
            if isinstance(node, ast.ClassDef):
                payload["decorator_count"] = len(node.decorator_list)
            items.append(payload)

        if isinstance(node, ast.ClassDef):
            items.extend(
                _collect_outlines(
                    node.body,
                    detail=detail,
                    include_private=include_private,
                    max_depth=max_depth,
                    prefix=qualified_name,
                    depth=depth + 1,
                )
            )

    return items


@app.command(
    annotations=ReadOnly | Idempotent,
    list_processing=True,
    paginated=True,
    cost_hint="low",
    examples=[
        {
            "args": ["outline", "path/to/main.py"],
            "description": "Concise symbol list for context-friendly planning",
        },
        {
            "args": [
                "outline",
                "path/to/main.py",
                "--detail",
                "detailed",
                "--max-depth",
                "3",
            ],
            "description": "Detailed signatures for dependency tracing",
        },
    ],
    error_codes={
        "E1000": "Bad file path provided.",
        "E1002": "File could not be read.",
        "E1003": "Python syntax invalid for AST parsing.",
        "E1014": "max-depth below allowed minimum.",
        "E1015": "max-depth exceeds safe limit.",
    },
)
def outline(
    file_path: Annotated[str, Argument(help="Python file to analyze")],
    detail: Annotated[str, Option(help="Output detail: concise or detailed")] = "concise",
    max_depth: Annotated[int | None, Option(help="Maximum symbol nesting depth to follow")] = None,
    exclude_private: Annotated[
        bool,
        Option("--exclude-private", "--no-exclude-private", help="Skip _private symbols"),
    ] = True,
) -> list[dict[str, Any]]:
    """Return a compact structure-only symbol outline.

    Agent guidance:
    - use `--detail concise` (default) when you only need names for routing,
    - use `--detail detailed` for automated interface checks,
    - add `--max-depth` to keep recursive class trees bounded,
    - this command intentionally omits function bodies to protect context budget.

    Output contract:
    - each symbol includes `kind`, `name`, `qualified_name`, and `line`,
    - detailed mode adds `signature` and optional `docstring`,
    - all output is stable and machine-friendly for `--output json`.
    """

    normalized_detail = _normalize_detail(detail)
    include_private = not exclude_private
    validated_depth = _validate_depth(max_depth)

    if not os.path.isfile(file_path):
        raise InputError(
            message=f"File not found or not a regular file: {file_path}",
            code="E1000",
            suggestion=Suggestion(
                action="provide valid file path",
                fix="Pass a readable Python file path.",
                example="python code_lens.py outline main.py",
            ),
        )

    try:
        with open(file_path, encoding="utf-8") as file:
            source_text = file.read()
    except OSError as exc:
        raise InputError(
            message=f"Unable to read file: {file_path}",
            code="E1002",
            suggestion=Suggestion(
                action="retry with readable file",
                fix="Verify file permissions and retry.",
                example=f"python code_lens.py outline {file_path}",
            ),
            details={"path": str(file_path)},
        ) from exc

    if not source_text.strip():
        raise InputError(
            message=f"Source file is empty: {file_path}",
            code="E1016",
            suggestion=Suggestion(
                action="check source file",
                fix="Provide a file with Python code to analyze.",
                example="python code_lens.py outline main.py",
            ),
            details={"path": str(file_path)},
        )

    try:
        tree = ast.parse(source_text)
    except SyntaxError as exc:
        raise InputError(
            message=f"Could not parse Python file '{file_path}': {exc}",
            code="E1003",
            suggestion=Suggestion(
                action="inspect syntax",
                fix="Fix syntax errors in the target file before rerunning outline.",
                example="python -m py_compile main.py",
            ),
            details={"path": str(file_path)},
        ) from exc

    return _collect_outlines(
        tree.body,
        detail=normalized_detail,
        include_private=include_private,
        max_depth=validated_depth,
    )


if __name__ == "__main__":
    app()
