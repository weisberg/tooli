# Product Requirements Document: Tooli Extension

## 1. Introduction

This document outlines the product requirements for **Tooli**, a proposed extension to the Typer library designed to create the ultimate Command Line Interface (CLI) tool framework for AI agent development. The command line is the native environment for developers and a powerful interface for automation. As AI agents become more capable, they require tools that are not only powerful but also predictable, discoverable, and composable. Typer provides an excellent foundation with its type-safe, developer-friendly approach to CLI creation [1]. However, to meet the unique demands of AI agents, we must extend it with features inspired by the robust architecture of FastMCP [2], the timeless wisdom of the Unix philosophy [3], and the practical needs of modern agentic workflows [4, 5].

This PRD synthesizes extensive research into AI agent tool requirements, existing frameworks, and foundational software design principles to propose a comprehensive feature set that will make building agent-ready CLI tools simple, efficient, and robust.

## 2. Vision and Goals

### 2.1. Vision

To create a Typer extension that transforms CLI tool development for AI agents by seamlessly blending:

*   The **type-safe, Pythonic API** of Typer.
*   The **composable, extensible architecture** of FastMCP, including providers and transforms.
*   The **pipeline-friendly, interoperable design** of the Unix philosophy.
*   The **automated, self-describing documentation** required for agent discoverability (e.g., SKILL.md).
*   A suite of **agent-optimized features** like structured output, versioning, and telemetry.

The result will be a framework where developers can write simple, clean Python functions and, with minimal effort, expose them as powerful, agent-ready tools that are simultaneously human-friendly and machine-readable.

### 2.2. Goals

*   **Drastically reduce the complexity** of creating robust, agent-ready CLI tools.
*   **Promote best practices** in CLI and tool design by default.
*   **Enable seamless integration** with AI agent frameworks and the Model Context Protocol (MCP).
*   **Empower developers** to build tools that are discoverable, predictable, and composable.
*   **Bridge the gap** between human-friendly CLIs and machine-readable tool schemas.

### 2.3. Target Audience

*   **AI Agent Developers:** Building tools for agents to consume.
*   **Platform Engineers:** Creating internal tools and automation.
*   **DevOps Engineers:** Scripting and managing infrastructure.
*   **Python Developers:** Building any kind of CLI application who want to future-proof their tools for agentic use.

## 3. Core Architecture

We propose a three-layer design inspired by the composability of FastMCP, built on top of Typer and Click.

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface Layer                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │   CLI    │  │   MCP    │  │  HTTP API (FastAPI)  │  │
│  │ (Typer)  │  │  Server  │  │                      │  │
│  └──────────┘  └──────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ▲
┌─────────────────────────────────────────────────────────┐
│                  Transform Pipeline Layer                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │Namespace │  │ Version  │  │Visibility│  │ Custom │ │
│  │Transform │  │ Filter   │  │ Filter   │  │Transform│ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
└─────────────────────────────────────────────────────────┘
                          ▲
┌─────────────────────────────────────────────────────────┐
│                    Provider Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │  Local   │  │   File   │  │ Database │  │  API   │ │
│  │ Provider │  │  System  │  │ Provider │  │Provider│ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
└─────────────────────────────────────────────────────────┘
```

*   **Provider Layer:** The source of tools. This abstraction allows tools to be defined not just as decorated functions, but also sourced from files, databases, or external APIs.
*   **Transform Pipeline Layer:** A middleware system for the tool pipeline. Transforms can modify tools as they flow from providers to the user interface, enabling features like namespacing, versioning, and filtering.
*   **User Interface Layer:** The interface through which humans and agents interact with the tools. This can be a standard CLI, an MCP server, or an HTTP API.

## 4. Detailed Feature Requirements

### 4.1. Core Typer Extensions

These features extend Typer's core functionality to better support agentic and pipeline-based workflows.

#### FR-1.1: Enhanced Type System

The framework shall introduce new types to handle common CLI and agent interaction patterns.

*   **`StdinOr[T]`**: A type hint that allows a parameter to be populated from either a command-line argument or from `stdin`. This simplifies the creation of tools that work in Unix pipelines.
*   **`Output[T]`**: A type hint for function return values that enables automatic serialization to different formats (JSON, YAML, etc.) and validation against a Pydantic model `T`.
*   **`ExitCode`**: A standardized enum for exit codes (e.g., `ExitCode.SUCCESS`, `ExitCode.FILE_NOT_FOUND`) to promote consistent error handling.

**Example:**
```python
from tooli import Tooli, StdinOr, Output, ExitCode
from typing import Annotated

app = Tooli()

@app.command()
def process(
    input_data: Annotated[StdinOr[Path], typer.Argument(help="Input file or stdin")],
    output: Annotated[Output[ProcessedData], typer.Option("--output", "-o")] = None
) -> ExitCode:
    """Process data from file or stdin."""
    # ...
    return ExitCode.SUCCESS
```

#### FR-1.2: Bash Compatibility Decorators

The framework shall provide decorators to easily make tools compatible with bash and Unix conventions.

*   **`@bash_compatible`**: A decorator to enable common Unix behaviors:
    *   `silent_success=True`: Suppress output on successful execution.
    *   `detect_tty=True`: Automatically enable/disable colored output.
    *   `handle_sigpipe=True`: Gracefully handle broken pipe errors.

#### FR-1.3: Structured Output

The framework shall provide a decorator for automatic structured output.

*   **`@structured_output`**: A decorator that adds a `--output` flag to a command, allowing the user to specify the output format (e.g., `json`, `yaml`, `table`, `csv`). The framework will handle the serialization of the return value.

### 4.2. FastMCP-Inspired Features

These features bring the powerful, composable architecture of FastMCP to the Typer ecosystem.

#### FR-2.1: Provider System

The framework shall support a provider system for sourcing tools from various locations.

*   **`LocalProvider`**: The default provider, sourcing tools from decorated functions.
*   **`FileSystemProvider`**: Sources tools from a directory of Python files, with optional hot-reloading for development.
*   **Extensible Provider API**: A clear API for creating custom providers (e.g., `DatabaseProvider`, `APIProvider`).

#### FR-2.2: Transform Pipeline

The framework shall implement a transform pipeline to modify tools before they are exposed.

*   **`Namespace`**: A transform to add a prefix to tool names, preventing collisions.
*   **`VersionFilter`**: A transform to filter tools based on their version.
*   **`Visibility`**: A transform to hide or show tools based on tags.

#### FR-2.3: Tool Versioning

The framework shall support versioning of tools.

*   **`@app.command(version="1.0.0")`**: A decorator argument to specify the version of a tool.
*   The framework will default to exposing the latest version of a tool.
*   A mechanism will be provided to call a specific version of a tool.

#### FR-2.4: Authorization

The framework shall provide a mechanism for adding authorization to tools.

*   **`@app.command(auth=require_scopes("admin"))`**: A decorator argument to specify authorization requirements.

### 4.3. Automatic Documentation Generation

This is a cornerstone feature, enabling tools to be self-describing for both humans and agents.

#### FR-3.1: SKILL.md Generation

The framework shall be able to automatically generate a `SKILL.md` file from a Typer application, following the format specified in the Manus skills system [5].

*   **`app.generate_skill_md()`**: A method that inspects the Typer app (docstrings, type hints, decorators) to generate a complete `SKILL.md` file.
*   The generated file will include:
    *   YAML frontmatter with `name` and `description`.
    *   A markdown body with synopsis, arguments, options, examples, and exit codes.
*   The generation process will be customizable through decorator arguments, allowing developers to provide agent-specific descriptions and examples.

#### FR-3.2: MCP and OpenAPI Schema Generation

The framework shall be able to generate machine-readable schemas for tools.

*   **`app.generate_mcp_server()`**: A method to generate a FastMCP server from the Typer app.
*   **`app.generate_openapi_schema()`**: A method to generate an OpenAPI schema, enabling the creation of HTTP APIs from the CLI tools.

#### FR-3.3: Man Page Generation

The framework shall be able to generate standard Unix man pages.

*   **`app.generate_man_page()`**: A method to generate a man page from the Typer app.

### 4.4. Agent-Optimized Features

These features are specifically designed to improve the interaction between agents and CLI tools.

#### FR-4.1: Telemetry and Usage Tracking

The framework shall provide an optional, opt-in telemetry system.

*   This will allow developers to track tool usage, errors, and performance, providing valuable data for improving tools and for agents to learn which tools are most effective.

#### FR-4.2: Dry Run Mode

The framework shall provide support for a `--dry-run` mode.

*   **`@dry_run_support`**: A decorator that adds a `--dry-run` flag and an `app.is_dry_run()` method, allowing tools to simulate execution without making changes.

#### FR-4.3: Progress Reporting

The framework shall provide a mechanism for reporting progress of long-running operations to `stderr`, so as not to pollute `stdout`.

## 5. Implementation Roadmap

### Phase 1: Core Foundation (MVP)

1.  **Enhanced Type System:** Implement `StdinOr`, `Output`, and `ExitCode`.
2.  **Bash Compatibility:** Implement `@bash_compatible` decorator.
3.  **Structured Output:** Implement `@structured_output` decorator.
4.  **Basic SKILL.md Generation:** Implement `app.generate_skill_md()` with basic docstring and type hint parsing.

### Phase 2: FastMCP Integration

1.  **Provider System:** Implement `LocalProvider` and `FileSystemProvider`.
2.  **Transform Pipeline:** Implement `Namespace` and `VersionFilter` transforms.
3.  **Tool Versioning:** Implement `@app.command(version=...)`.
4.  **MCP Server Generation:** Implement `app.generate_mcp_server()`.

### Phase 3: Agent Optimization and Documentation

1.  **Advanced SKILL.md Generation:** Enhance `app.generate_skill_md()` with support for examples, exit codes, and bundled resources.
2.  **Dry Run Mode:** Implement `@dry_run_support`.
3.  **Progress Reporting:** Implement progress reporting to `stderr`.
4.  **Man Page and OpenAPI Generation:** Implement `app.generate_man_page()` and `app.generate_openapi_schema()`.

### Phase 4: Advanced Features

1.  **Authorization:** Implement `@app.command(auth=...)`.
2.  **Telemetry:** Implement opt-in telemetry system.
3.  **Packaging and Distribution:** Create tools for packaging and distributing `tooli` tools.

## 6. Success Metrics

### 6.1. Developer Experience

*   **Time to create an agent-ready tool:** Measured in minutes, aiming for a >75% reduction compared to manual implementation.
*   **Lines of code:** Aim for a 50% reduction in boilerplate code for creating agent-ready tools.
*   **Adoption:** Number of projects using `tooli`.

### 6.2. Agent Performance

*   **Tool Discovery Rate:** Percentage of tools successfully discovered and understood by agents via generated documentation.
*   **Tool Execution Success Rate:** Percentage of successful tool executions by agents.
*   **Error Recovery Rate:** Percentage of tool failures from which an agent can successfully recover using the provided error messages.

### 6.3. Community and Ecosystem

*   Number of custom providers and transforms contributed by the community.
*   Number of `tooli` tools published to package repositories.

## 7. References

[1] Tiangolo. (2026). _Typer_. [https://typer.tiangolo.com/](https://typer.tiangolo.com/)

[2] Lowin, J. (2026). _What's New in FastMCP 3.0_. [https://www.jlowin.dev/blog/fastmcp-3-whats-new](https://www.jlowin.dev/blog/fastmcp-3-whats-new)

[3] Raymond, E. S. (2003). _The Art of Unix Programming_. Addison-Wesley Professional.

[4] Prasad, A., Firshman, B., Tashian, C., & Parish, E. (2023). _Command Line Interface Guidelines_. [https://clig.dev/](https://clig.dev/)

[5] Manus AI. (2026). _Skill Creator Guide_. `/home/ubuntu/skills/skill-creator/SKILL.md`
