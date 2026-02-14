# Tooli: a PRD for the AI-native CLI framework

**Tooli** extends Python's Typer to produce CLI tools that are simultaneously human-friendly and machine-consumable by AI agents. Every decorated function becomes a CLI command, an MCP tool, and a self-documenting schema — from a single function definition. This document specifies the architecture, API surface, and implementation plan for a senior engineer to build it.

The core insight driving this PRD is a gap in the ecosystem: **no existing project auto-generates AI tool schemas from typed CLI command definitions**. FastMCP converts Python functions to MCP tools. [GitHub](https://github.com/liuhahi/fastmcp) Typer converts Python functions to CLI commands. But nothing bridges the two worlds — converting a single typed Python function into both a rich CLI interface *and* an AI-discoverable tool with JSON schemas, structured output, and agent-safe execution. Tooli fills this gap by extending Typer's proven decorator-to-CLI pipeline with FastMCP's schema generation approach, producing tools optimized for the emerging agent-driven development workflow.

Research across Claude Code, OpenAI Codex CLI, Cursor, and Aider reveals that AI agents consume CLI tools through persistent bash sessions with `--json` output modes, parse stdout/stderr for results, and struggle with interactive prompts, unpredictable output sizes, and unfamiliar flag conventions. Meanwhile, the MCP protocol provides typed tool schemas [Stytch](https://stytch.com/blog/model-context-protocol-introduction/) with `inputSchema`, behavioral annotations, and structured error reporting [PyPI +2](https://pypi.org/project/fastmcp/) — but requires building separate server infrastructure. [Medium](https://abvijaykumar.medium.com/model-context-protocol-deep-dive-part-3-1-3-hands-on-implementation-522ecd702b0d) Tooli eliminates this tradeoff entirely.

---

## The problem: CLI tools weren't designed for AI agents

AI coding agents invoke thousands of CLI commands daily. Claude Code's bash tool, Codex CLI's sandboxed executor, and Cursor's YOLO mode all rely on the same fragile pipeline: the agent generates a shell command string, executes it, and parses unstructured text output. This fails in predictable ways.

**Interactive commands hang** because agents cannot navigate prompts, pagers, or password dialogs. Claude Code's internal prompt explicitly prohibits `git rebase -i`, `vim`, and `less`. [pierce](https://pierce.dev/notes/under-the-hood-of-claude-code) **Unfamiliar CLIs cause guessing** — agents trained on well-documented tools like `git` and `aws` will hallucinate flags for internal or niche tools. [AnythingLLM +2](https://docs.anythingllm.com/agent-not-using-tools) **Unstructured output wastes tokens** — a benchmark comparing Playwright CLI vs MCP found CLI delivered **10–100x lower token usage** because CLI allows selective queries (`--last 10`) while MCP dumps full context. [Supatest Blog](https://supatest.ai/blog/playwright-mcp-vs-cli-ai-browser-automation) **Error messages lack actionability** — agents that receive "Error: invalid input" cannot self-correct, while structured errors with suggestions enable automatic recovery. [APXML +2](https://apxml.com/courses/langchain-production-llm/chapter-2-sophisticated-agents-tools/agent-error-handling)

The MCP protocol solves many of these problems with typed `inputSchema` definitions, [Modelcontextprotocol](https://modelcontextprotocol.info/docs/concepts/tools/) `isError` flags, [Modelcontextprotocol](https://modelcontextprotocol.info/docs/concepts/tools/) and behavioral `annotations` [Obot AI](https://obot.ai/resources/learning-center/mcp-tools/) [modelcontextprotocol](https://modelcontextprotocol.info/docs/concepts/tools/) like `readOnlyHint` and `destructiveHint`. [Medium +2](https://abvijaykumar.medium.com/model-context-protocol-deep-dive-part-3-1-3-hands-on-implementation-522ecd702b0d) But building an MCP server is separate infrastructure requiring a different mental model from CLI development. Most developers already have Typer or Click CLIs. They need a bridge, not a rewrite.

---

## Architecture: Typer's pipeline extended with a schema layer

Typer's internal architecture is remarkably well-suited for this extension. When `@app.command()` decorates a function, Typer stores the function reference and metadata in a `CommandInfo` object *without mutating the original function*. At invocation time, `get_command(app)` converts Typer metadata into Click `Command` objects [Typer](https://typer.tiangolo.com/tutorial/using-click/) via `get_click_type()`, which maps Python type annotations to Click parameter types. The function remains callable as plain Python. [Typer](https://typer.tiangolo.com/tutorial/testing/)

Tooli intercepts this pipeline at a critical junction. The same type annotations that Typer routes through `get_click_type()` are simultaneously routed through Pydantic's `model_json_schema()` to produce JSON Schema definitions compatible with MCP's `inputSchema` and OpenAI's function-calling format. This dual-path architecture means a single function definition produces CLI parameters, JSON schemas, help text, and tool descriptions.

```
┌─────────────────────────────────────────────────────────┐
│                   @agent.command()                       │
│              Python function + type hints                │
└───────────┬──────────────────────┬──────────────────────┘
            │                      │
            ▼                      ▼
   ┌────────────────┐    ┌──────────────────┐
   │  Typer Pipeline │    │  Schema Pipeline  │
   │  get_click_type │    │  func_metadata()  │
   │  → Click params │    │  → Pydantic model │
   │  → CLI parser   │    │  → JSON Schema    │
   └───────┬────────┘    └────────┬──────────┘
           │                      │
           ▼                      ▼
   ┌────────────────┐    ┌──────────────────┐
   │   CLI Output    │    │   Agent Output    │
   │  Human-readable │    │  MCP tool schema  │
   │  Rich formatting│    │  SKILL.md gen     │
   │  Shell complete  │    │  JSON/JSONL out   │
   └────────────────┘    └──────────────────┘
```

The key architectural decisions are:

**1. Subclass, don't fork.** Tooli subclasses `Typer`, `TyperCommand`, and `TyperGroup` rather than forking Typer. The `cls` parameter on `Typer()` already supports custom subclasses. [Typer](https://typer.tiangolo.com/tutorial/using-click/) This ensures compatibility with the existing Typer ecosystem and future Typer updates.

**2. Pydantic as the schema backbone.** FastMCP's proven pipeline — `inspect.signature()` → dynamic Pydantic `BaseModel` → `model_json_schema()` — is the industry-standard path from type hints to JSON Schema. Instructor, Marvin, FastAPI, and FastMCP all use this approach. Tooli adopts it directly, with FastMCP's `$ref` dereferencing for client compatibility.

**3. Dual-channel output by default.** Every command automatically supports `--output json|text|jsonl` and TTY auto-detection. Data flows to stdout; progress, diagnostics, and errors flow to stderr. [TheLinuxCode](https://thelinuxcode.com/viewing-progress-of-commands-using-pipe-viewer-pv-in-linux/) When `--output json` is active, stderr errors are also structured JSON.

**4. Functions remain directly callable.** Typer's defining advantage over Click — that decorated functions remain unmodified — is preserved. [Typer](https://typer.tiangolo.com/tutorial/using-click/) Any Tooli command can be called as a Python function, invoked via CLI, called through MCP, or tested with `CliRunner`, all from the same definition.

---

## Core API design

### The `Tooli` class and `@agent.command()` decorator

```python
from tooli import Tooli, AgentContext, Annotated, Option, Argument
from tooli.annotations import ReadOnly, Idempotent, Destructive
from pydantic import Field
from pathlib import Path
from enum import Enum

agent = Tooli(
    name="file-tools",
    description="File manipulation utilities for development workflows",
    version="1.2.0",
    # Agent-specific configuration
    default_output="auto",         # auto|json|text|jsonl
    mcp_transport="stdio",         # stdio|http|sse
    skill_auto_generate=True,      # Generate SKILL.md on install
    permissions={
        "filesystem": "read-write",
        "network": "none",
    },
)

class OutputFormat(str, Enum):
    TABLE = "table"
    CSV = "csv"
    MARKDOWN = "markdown"

@agent.command(
    annotations=ReadOnly | Idempotent,  # Behavioral hints for agents
    examples=[                           # Few-shot examples for SKILL.md
        {"args": ["--pattern", "*.py", "--root", "/project"], 
         "description": "Find all Python files in a project"},
        {"args": ["--pattern", "test_*", "--max-depth", "3"],
         "description": "Find test files within 3 directories deep"},
    ],
    error_codes={"E3001": "No files matched the pattern"},
    timeout=60.0,
)
def find_files(
    pattern: Annotated[str, Argument(help="Glob pattern to match files")] ,
    root: Annotated[Path, Option(
        help="Root directory to search from",
        exists=True, file_okay=False, resolve_path=True,
    )] = Path("."),
    max_depth: Annotated[int, Option(
        help="Maximum directory depth to traverse",
        min=1, max=100,
    )] = 10,
    include_hidden: Annotated[bool, Option(
        help="Include hidden files and directories"
    )] = False,
    output_format: Annotated[OutputFormat, Option(
        help="Format for displaying results"
    )] = OutputFormat.TABLE,
) -> list[dict]:
    """Find files matching a glob pattern in a directory tree.

    Recursively searches from the root directory using the specified
    glob pattern. Respects .gitignore rules by default unless
    --include-hidden is specified.
    """
    results = []
    for path in root.rglob(pattern):
        if not include_hidden and any(p.startswith('.') for p in path.parts):
            continue
        results.append({
            "path": str(path),
            "size": path.stat().st_size,
            "modified": path.stat().st_mtime,
        })
    return results
```

The critical design choice here is the **return value**. Standard Typer commands print to stdout and return `None`. Tooli commands return typed values. The framework intercepts the return value through a custom `TyperCommand.invoke()` override and routes it through the output system:

- **Human mode** (TTY, no `--output` flag): Render with Rich tables, formatted text, colors.
- **JSON mode** (`--output json` or piped): Serialize return value as JSON to stdout.
- **JSONL mode** (`--output jsonl`): One JSON object per line for streaming.
- **MCP mode** (invoked via MCP): Return as `structuredContent` in MCP response.

### The output routing system

```python
class TooliCommand(TyperCommand):
    """Extended TyperCommand that captures return values and routes output."""
    
    def invoke(self, ctx: click.Context) -> Any:
        # Determine output mode
        output_mode = self._resolve_output_mode(ctx)
        
        # Execute the command function
        try:
            result = ctx.invoke(self.callback, **ctx.params)
        except ToolError as e:
            return self._handle_tool_error(e, output_mode)
        except Exception as e:
            return self._handle_unexpected_error(e, output_mode)
        
        # Route output based on mode
        match output_mode:
            case OutputMode.JSON:
                self._emit_json(result, ctx)
            case OutputMode.JSONL:
                self._emit_jsonl(result, ctx)
            case OutputMode.HUMAN:
                self._emit_human(result, ctx)
            case OutputMode.MCP:
                return result  # MCP handler serializes
    
    def _resolve_output_mode(self, ctx: click.Context) -> OutputMode:
        # Explicit flag takes priority
        if ctx.params.get("output") == "json":
            return OutputMode.JSON
        if ctx.params.get("output") == "jsonl":
            return OutputMode.JSONL
        # TTY detection
        if not sys.stdout.isatty():
            return OutputMode.JSON  # Default to JSON when piped
        # Environment variable override
        if os.environ.get("TYPER_AGENT_OUTPUT") == "json":
            return OutputMode.JSON
        return OutputMode.HUMAN
```

### Global flags injected automatically

Every Tooli command receives these flags without the developer declaring them:

```
--output, -o       Output format: auto|json|jsonl|text [default: auto]
--quiet, -q        Suppress non-essential output
--verbose, -v      Increase verbosity (stackable: -vvv)
--dry-run          Show planned actions without executing
--no-color         Disable colored output (also respects NO_COLOR env)
--timeout          Maximum execution time in seconds
--idempotency-key  Unique key for idempotent retry detection
```

These are injected via a `@agent.callback()` that runs before any subcommand, storing values in the Click context. The developer never sees them in their function signature.

---

## Schema generation pipeline

The schema pipeline converts a Tooli command function into multiple output formats from a single source of truth. The implementation mirrors FastMCP's `func_metadata()` approach:

```python
def generate_tool_schema(func: Callable, command_info: CommandInfo) -> ToolSchema:
    """Generate MCP-compatible tool schema from a decorated function."""
    sig = inspect.signature(func)
    
    # Build dynamic Pydantic model from function parameters
    fields = {}
    for name, param in sig.parameters.items():
        # Skip injected parameters (AgentContext, etc.)
        if _is_injected_type(param.annotation):
            continue
        
        field_type = param.annotation
        field_kwargs = {"description": _extract_param_help(command_info, name)}
        
        # Extract constraints from Annotated metadata
        if hasattr(field_type, '__metadata__'):
            for meta in field_type.__metadata__:
                if isinstance(meta, (Option, Argument)):
                    if meta.min is not None: field_kwargs["ge"] = meta.min
                    if meta.max is not None: field_kwargs["le"] = meta.max
        
        if param.default is not inspect.Parameter.empty:
            field_kwargs["default"] = param.default
        
        fields[name] = (field_type, Field(**field_kwargs))
    
    # Create dynamic Pydantic model
    ArgModel = create_model(f"{func.__name__}Args", **fields)
    
    # Generate JSON Schema and dereference $refs
    raw_schema = ArgModel.model_json_schema()
    input_schema = dereference_refs(raw_schema)
    
    return ToolSchema(
        name=command_info.name or func.__name__,
        title=_extract_title(func),
        description=func.__doc__ or "",
        input_schema=input_schema,
        output_schema=_generate_output_schema(sig.return_annotation),
        annotations=_extract_annotations(command_info),
        examples=command_info.examples or [],
    )
```

**Type mapping** covers the full spectrum needed for CLI tools:

| Python Type | CLI Representation | JSON Schema | MCP Schema |
|---|---|---|---|
| `str` | `TEXT` | `{"type": "string"}` | `{"type": "string"}` |
| `int` | `INTEGER` | `{"type": "integer"}` | `{"type": "integer"}` |
| `float` | `FLOAT` | `{"type": "number"}` | `{"type": "number"}` |
| `bool` | `--flag/--no-flag` | `{"type": "boolean"}` | `{"type": "boolean"}` |
| `Path` | `PATH` (with validation) | `{"type": "string", "format": "path"}` | `{"type": "string"}` |
| `Enum` | `[choice1\|choice2]` | `{"enum": ["choice1","choice2"]}` | `{"enum": [...]}` |
| `list[str]` | Multiple values | `{"type": "array", "items": {"type": "string"}}` | Same |
| `Optional[T]` | Optional parameter | `{"anyOf": [T_schema, {"type": "null"}]}` | Same |
| `Literal["a","b"]` | `[a\|b]` | `{"enum": ["a","b"]}` | `{"enum": ["a","b"]}` |
| Pydantic `BaseModel` | JSON string argument | Full nested object schema | Same |

The `$ref` dereferencing step is essential. FastMCP found that VS Code Copilot and Claude Desktop fail to process JSON Schemas containing `$ref` entries. The pipeline inlines all references, producing self-contained schemas that every MCP client can parse.

---

## Structured error handling with agent self-correction

Research into rustc's structured diagnostics, Elm's human-friendly errors, and MCP's error reporting pattern reveals that **error quality directly determines agent recovery success**. The PALADIN paper (ICLR 2026) found that agents with targeted error feedback needed fewer than one additional step on average to recover.

Tooli implements a three-layer error system:

### The `ToolError` exception hierarchy

```python
class ToolError(Exception):
    """Base error that agents can reason about."""
    code: str                    # Stable identifier: "E1001"
    category: ErrorCategory      # input|auth|state|runtime|internal
    message: str                 # Human-readable explanation
    suggestion: Suggestion | None  # Actionable fix
    is_retryable: bool           # Can the agent retry?
    details: dict | None         # Additional context

class InputError(ToolError):
    """E1xxx: Input validation failures."""
    category = ErrorCategory.INPUT

class StateError(ToolError):
    """E3xxx: Precondition or state failures."""  
    category = ErrorCategory.STATE

class Suggestion:
    action: str        # "retry_with_modified_input" | "use_different_tool" | "abort"
    fix: str           # What to do differently
    example: str | None  # Concrete corrected example
    applicability: str   # "machine_applicable" | "maybe_incorrect" | "has_placeholders"
```

### Error output format

When `--output json` is active or stdout is piped, errors emit structured JSON to stderr:

```json
{
  "error": {
    "code": "E3001",
    "category": "state",
    "message": "No files matched pattern '*.rs' in /project/src",
    "suggestion": {
      "action": "retry_with_modified_input",
      "fix": "The directory contains .py files. Try pattern '*.py' instead.",
      "example": "find-files '*.py' --root /project/src",
      "applicability": "maybe_incorrect"
    },
    "is_retryable": true,
    "details": {
      "pattern": "*.rs",
      "root": "/project/src",
      "available_extensions": [".py", ".txt", ".md"]
    }
  }
}
```

The exit code scheme follows BSD `sysexits.h` conventions with extensions:

| Exit Code | Meaning | Agent Action |
|---|---|---|
| **0** | Success | Process result |
| **1** | General runtime error | Read error, may retry |
| **2** | Usage/argument error | Fix arguments and retry |
| **64** | Command line usage error | Fix syntax |
| **65** | Data format error | Fix input data |
| **66** | Cannot open input | Check file path |
| **69** | Service unavailable | Retry with backoff |
| **73** | Cannot create output file | Check permissions |
| **75** | Temporary failure (retryable) | Retry immediately |
| **77** | Permission denied | Request escalation |
| **78** | Configuration error | Check config |

This scheme is paired with structured stderr messages so agents get both the machine-parseable exit code and the actionable error details. The dual rendering approach — inspired by rustc's `rendered` field — ensures human developers see the same quality of error messages as agents.

---

## MCP server auto-generation

The highest-leverage feature in Tooli is **automatic MCP server generation** from existing CLI definitions. A developer adds one line and their CLI becomes an MCP server:

```python
agent = Tooli(name="file-tools")

# ... define commands as normal ...

if __name__ == "__main__":
    agent()  # Normal CLI mode

# Meanwhile, elsewhere or via CLI flag:
# $ file-tools --serve-mcp stdio
# $ file-tools --serve-mcp http --port 8080
```

### Implementation

The `Tooli` class 
