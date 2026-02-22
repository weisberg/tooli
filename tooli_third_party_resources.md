# Tooli Third-Party Resources



## Anthropic

### Claude Code Features

https://platform.claude.com/cookbook/

#### Programmatic Tool Calling (PTC): https://platform.claude.com/cookbook/tool-use-programmatic-tool-calling-ptc

#### Tool Search with Embeddings: https://github.com/anthropics/claude-cookbooks/blob/main/tool_use/tool_search_with_embeddings.ipynb

### Claude Code: https://github.com/anthropics/claude-code

### Skills: https://github.com/anthropics/skills

Looking through the `anthropics/skills` repository, several specific implementations and architectural debates align perfectly with the mission of building an agent-focused, token-efficient CLI library that delivers "batteries-included" capabilities under a stripped-down Unix philosophy:

**1. The `xlsx` Skill (The Unix Approach to Data Processing)**

The `skills/xlsx` package is a prime example of separating agent reasoning from execution overhead. Instead of forcing the model to manipulate complex spreadsheet XML directly within its context window, the skill offloads the heavy lifting to localized Python scripts using libraries like `pandas` and `openpyxl`. By piping structured data manipulation commands to small, focused utilities (such as the `scripts/recalc.py` script for handling formula recalculation and error catching), it delivers powerful business and data analysis capabilities while keeping token consumption remarkably lean.

**2. The Push for "Executable Agent Skills" (Issue #157)**

A major theme in the repository is the transition from "Instruction-Only" READMEs to true executable capabilities. Issue #157 explicitly addresses the "batteries-included" philosophy: reducing the friction of an agent having to generate temporary code and ask a human to run it. By establishing executable manifests, agents can trigger local scripts safely and reproducibly without manual intervention—a fundamental pattern for a robust CLI tool.

**3. The `skill-creator` Refactoring Debate (Issue #202)**

The community's active push to refactor the `skill-creator` heavily reflects an anti-bloat ethos. Discussions argue aggressively against verbose, "educational" prompting in favor of strictly imperative instructions, noting that "the context window is a public good." Adopting this concise structure (relying on minimal YAML frontmatter and progressive disclosure via external files) ensures the framework doesn't waste tokens on redundant explanations or conversational filler.

**4. The Proposed `skill-debugger` (Issue #267)**

When running localized agentic tasks, silent failures or conflicting tool triggers are common. The proposed `skill-debugger` was built around a strict "Concise is Key" principle, using far fewer lines and words than other meta-skills to provide a systematic checklist for diagnosing execution failures. Incorporating a similarly lean diagnostic loop is vital for an agent framework that needs to fail gracefully and self-heal without flooding the terminal output.

**5. Exposing Skills as MCP Servers (Issue #16)**

There is a strategic move to convert standalone skills into Model Context Protocol (MCP) servers. This represents a highly modular API integration strategy. By wrapping capabilities (such as the `calculator-mcp-server`) in strict validation schemas, the tools become standardized, pluggable nodes. Agents can dynamically discover and query these nodes, keeping the core CLI library lightweight while easily scaling its capabilities across different environments.



### Claude Plugins: https://github.com/anthropics/claude-plugins-official

Reviewing the `anthropics/claude-plugins-official` repository through the lens of building a token-efficient, "batteries-included" CLI agent anchored in the Unix philosophy reveals several structural patterns and specific implementations that perfectly match that mission.

Here is how the official Claude Code plugins align with the goal of creating a lean, capable, and anti-bloat CLI experience:

**1. Context Forking & Sub-Agent Orchestration**

Long-running terminal sessions are the enemy of token efficiency. Plugins emerging in this ecosystem (and architectural approaches like `workflow-orchestrator`) rely on breaking tasks down and delegating them to sub-agents with forked, localized contexts. Instead of the main agent holding the entire history of a complex refactor, it dispatches a specialized worker to execute the task and only returns the final diff or success state to the main orchestrator. This prevents context degradation and keeps the primary CLI loop incredibly fast.

**2. Token-Efficient Dynamic Retrieval (`context7`)**

Rather than front-loading massive API references or relying on the model's base training (which can lead to hallucinations), plugins like `context7` dynamically fetch exactly the up-to-date documentation needed for a specific framework or library. For a lightweight CLI, this "just-in-time" knowledge retrieval ensures you only spend tokens on the exact information required for the current execution step.

**3. The Unix Philosophy in Action (`commit-commands` & `code-simplifier`)**

The repository strictly avoids monolithic "do-everything" tools. Plugins like `commit-commands` (which strictly enforces consistent git history and conventional commits) or `code-simplifier` (which specifically measures cyclomatic complexity) do exactly one thing well. By composing these single-purpose tools, the agent can achieve complex, automated workflows without needing a massive, bloated system prompt.

**4. True Environmental Awareness (`typescript-lsp`)**

One of the most powerful plugins in the repository is `typescript-lsp`. Instead of feeding raw text files into the context window and forcing the model to guess about types and dependencies, this plugin hooks directly into the local Language Server Protocol. This means the agent gets deterministic, native code intelligence (like go-to-definition and precise error diagnostics). Giving the CLI agent actual awareness of the local environment is vastly more efficient and accurate than prompt-based guessing.

**5. Passive Guardrails (`security-guidance`)**

For an autonomous CLI tool to be safe, it needs guardrails that don't constantly interrupt the user. The `security-guidance` plugin runs passively alongside the agent's code generation, scanning for vulnerabilities like hardcoded secrets or auth bypasses. This ensures robust, secure output without requiring the primary agent to waste valuable reasoning tokens explicitly thinking about security policies on every single turn.

**6. Headless Execution (`playwright`)**

To be truly "batteries-included," the CLI must be able to verify its own work. The `playwright` plugin allows the agent to spin up a headless browser, navigate to a local dev server, interact with the UI, and run tests autonomously. This closes the execution loop entirely within the terminal, allowing the agent to self-heal based on actual environmental feedback rather than relying on a human to test the code and paste the errors back in.

#### Knowledge Work Plugins: https://github.com/anthropics/knowledge-work-plugins



### Claude Cookbooks: https://github.com/anthropics/claude-cookbooks/

The Claude Cookbooks and related Anthropic repositories contain several recipes that directly align with the mission of building an agent-focused, token-efficient CLI library. To provide "batteries-included agent smarts" while maintaining a stripped-down, anti-bloat Unix philosophy, the following recipes are the most relevant:

**1. Programmatic Tool Calling (PTC) (`tool_use/programmatic_tool_calling_ptc.ipynb`)**

This cookbook is foundational for reducing round-trips and context bloat. It demonstrates how to let the model write code that executes tool calls programmatically within a local secure environment. Instead of passing massive amounts of irrelevant context back and forth, the data is filtered locally. This aligns perfectly with achieving token-aware output and keeping the execution loop lean.

**2. Tool Search & Dynamic Loading (`tool_use/tool_search_with_embeddings.ipynb` & `tool_use/tool_search_alternate_approaches.ipynb`)**

Rather than front-loading hundreds of tool definitions into the context window, these recipes show how to use semantic search or a `describe_tool` function to discover capabilities on the fly. This maps directly to token-efficient searching and ensures the module remains a lightweight, drop-in replacement without the heavy overhead of large system prompts.

**3. Memory & Context Editing (`tool_use/memory_cookbook.ipynb`)**

Long-running local tools require strict token management to prevent context exhaustion. This recipe details features like `clear_tool_uses` and extended thinking management, which automatically prune old tool results. Implementing these context-editing strategies is critical for preventing crashes during complex, multi-step workflows.

**4. Agent Governance & Policy Enforcement (`issues/384` & governance discussions)**

When creating CLI tools that operate locally and make decisions, establishing strict boundaries is vital. The governance patterns covering policy enforcement (restricting tool arguments), threat detection, and audit trails provide a strong blueprint for implementing native human-in-the-loop guardrails and robust semantic error handling.

**5. Extracting Structured JSON (`tool_use/extracting_structured_json.ipynb`)**

For a CLI functioning inside Unix-style environments, native pipeline streaming requires predictable, structured data passing. This recipe covers how to force the model to generate strict, parsable schemas, which is essential for piping agent results to other local commands and triggering semantic error handling when a pipeline fails.

**6. Autonomous Coding Agent Pattern (`claude-quickstarts/autonomous-coding-agent`)**

While located in the quickstarts repository, this pattern showcases a dual-agent setup (an orchestrator and a worker) that handles local file operations, persists progress via Git, and works through incremental features. It serves as a highly relevant reference architecture for features like self-healing file editing and creating agents that operate efficiently directly on the local filesystem.



### Courses: https://github.com/anthropics/courses



### Claude Agent SDK Python: https://github.com/anthropics/claude-agent-sdk-python



### Claude Code Action (GitHub CI/CCD): https://github.com/anthropics/claude-code-action



## OpenAI

### OpenAI Cookbook: https://github.com/openai/openai-cookbook



