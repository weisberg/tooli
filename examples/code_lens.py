"""Token-efficient AST outline extractor for Tooli.

This example exists to show how agents can ask for high-signal structure instead of
large source dumps. It is intended to be used before deeper file edits, and it is
safe to run in non-interactive pipelines because all output is structured data.

Use cases:
- quickly map function/class names before opening a large file,
- feed outlines into downstream tools (summaries, dependency tracing, etc.),
- preserve context budget by avoiding function bodies and comments by default.
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
    detail: str,
    prefix: str | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for node in nodes:
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef | ast.ClassDef):
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            if detail == "concise":
                items.append(
                    {
                        "kind": kind,
                        "name": node.name,
                        "qualified_name": ".".join([part for part in [prefix, node.name] if part]),
                        "line": node.lineno,
                    }
                )
            else:
                signature = _node_signature(node)
                docstring = ast.get_docstring(node)
                payload: dict[str, Any] = {
                    "kind": kind,
                    "name": node.name,
                    "qualified_name": ".".join([part for part in [prefix, node.name] if part]),
                    "signature": signature,
                    "line": node.lineno,
                    "docstring": docstring,
                }
                if isinstance(node, ast.ClassDef):
                    payload["decorator_count"] = len(node.decorator_list)
                items.append(payload)

            if isinstance(node, ast.ClassDef):
                items.extend(
                    _collect_outlines(
                        node.body,
                        detail=detail,
                        prefix=".".join([part for part in [prefix, node.name] if part]),
                    )
                )

    return items


@app.command(
    annotations=ReadOnly | Idempotent,
    list_processing=True,
    paginated=True,
    cost_hint="low",
    examples=[
        {"args": ["outline", "path/to/main.py"], "description": "Get concise symbols only"},
        {
            "args": ["outline", "path/to/main.py", "--detail", "detailed"],
            "description": "Get signatures + docstrings for richer follow-up prompts",
        },
    ],
    error_codes={
        "E1000": "Bad file path provided.",
        "E1002": "File could not be read.",
        "E1003": "Python syntax invalid for AST parsing.",
    },
)
def outline(
    file_path: Annotated[str, Argument(help="Python file to analyze")],
    detail: Annotated[str, Option(help="Output detail: concise or detailed")] = "concise",
) -> list[dict[str, Any]]:
    """Return a compact structural outline for a Python file.

    Agent guidance:
    - Use `--detail concise` (default) to minimize tokens when you need only symbol names.
    - Use `--detail detailed` when a downstream step needs signatures and docstrings.
    - Use pagination flags (`--limit`, `--cursor`) when this file has deep nesting.
    """

    normalized_detail = _normalize_detail(detail)

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

    return _collect_outlines(tree.body, detail=normalized_detail)


if __name__ == "__main__":
    app()
