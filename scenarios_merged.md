# Tooli Scenarios: From Function to Agent Skill

> Realistic usage scenarios for tooli, grounded in what the framework should actually do.

This document merges and edits scenarios from three source documents (`scenarios_cc.md`, `scenarios_gm.md`, `scenarios_cdx.md`), filtered through a critical lens: **what does tooli the CLI framework actually need to enable, vs. what belongs to the ecosystem around it?**

The guiding principle: tooli's job is to make it easy to write a CLI tool that agents can call with structured input and get structured output. Everything beyond that — documentation generation, MCP serving, multi-framework export, enterprise governance — is either a separate tool, a human-authored config file, or platform infrastructure that consumes tooli's output.

Scenarios are organized into three tiers based on what they demand from tooli itself.

---

## Source Coverage

| Source | Original Scenario | Status in This Document |
|---|---|---|
| `scenarios_cc.md` | 1: Solo Developer's Debugging Toolkit | **Scenario 1** (core) |
| `scenarios_cc.md` | 2: Platform Team's Internal Toolchain | **Scenario 2** (core, CLAUDE.md is human-authored) |
| `scenarios_cc.md` | 3: Open-Source Ecosystem Effect | **Scenario 3** (core) |
| `scenarios_cc.md` | 4: Agent-Built Tool | **Scenario 4** (core) |
| `scenarios_cc.md` | 5: New Hire Onboarding Experience | Folded into Scenario 2 (same deployment tools, different persona) |
| `scenarios_cc.md` | 6: Security Audit Workflow | **Scenario 6** (ecosystem, capability enforcement) |
| `scenarios_cc.md` | 7: CI/CD Pipeline Integration | **Scenario 5** (core) |
| `scenarios_cc.md` | 8: Cross-Team Tool Marketplace | **Scenario 7** (ecosystem, registry is separate) |
| `scenarios_cc.md` | 9: Multi-Agent War Room | Folded into Scenario 2 (subagent coordination is the agent platform's job) |
| `scenarios_cc.md` | 10: Global Skill Mesh | **Cut** (multi-framework export is not tooli's job) |
| `scenarios_cc.md` | 11: Customer Support Workflows | **Scenario 8** (ecosystem, shows Destructive annotations) |
| `scenarios_cc.md` | 12: Versioned Evolution | Folded into Scenario 5 (deprecation is a schema/error feature) |
| `scenarios_gm.md` | 1: Lifecycle of a Skill | Merged into Scenario 1 |
| `scenarios_gm.md` | 2: Autonomous Self-Healing | Merged into Scenario 1 (structured error retry) |
| `scenarios_gm.md` | 3: Multi-Agent War Room | Merged into Scenario 2 |
| `scenarios_gm.md` | 4: Agent as Tool Author | Merged into Scenario 4 |
| `scenarios_gm.md` | 5: Global Skill Mesh | **Cut** |
| `scenarios_gm.md` | 6: Enterprise Governance | Merged into Scenario 6 |
| `scenarios_cdx.md` | 1-10 | These were already merges of the above; superseded by this document |

### What Was Cut and Why

Two major scenario clusters were removed entirely:

**Global Skill Mesh / Multi-Framework Export.** The premise is that `tooli export --target langchain/openai/adk` generates framework-specific wrappers from a single tool definition. This is a compelling vision but it's not a CLI framework feature — it's a separate code-generation tool that reads JSON Schema. Tooli should export JSON Schema via `--schema`. A separate `tooli-export` or community tool can generate LangChain `@tool` wrappers, OpenAI function definitions, or ADK YAML from that schema. Bundling this in tooli means tracking every API change from every LLM provider, which is an unbounded maintenance burden.

**Resource-First Subagent Operations.** MCP resources (`loggrep://recent-errors`, `deploy://status/{service}`) are a real and valuable pattern, but they're an MCP server concern, not a CLI framework concern. Tools like FastMCP already handle resource registration. Tooli's contribution is making the underlying commands produce structured output that a resource layer can cache. The scenarios below reference resources where relevant but don't require tooli to implement them.

---

## Personas

| Persona | Role | What They Need from Tooli |
|---|---|---|
| **Maya** | Backend developer, on-call engineer | Fast, structured CLI commands for incident diagnosis |
| **Jordan** | Platform lead | Structured output so CLAUDE.md workflows are reliable |
| **Alex** | Product engineer | CLI tools that agents can operate on her behalf |
| **Priya** | New hire | Tools that are self-describing so the agent can guide her |
| **Sam** | Freelance dev, open-source consumer | Tools from different authors that compose via shared output format |
| **Dana** | Senior engineer, API developer | Consistent tool structure so agent-built tools match human-built ones |
| **Riku** | Security engineer | Capability declarations and structured audit metadata |
| **Elena** | CI maintainer | Machine-readable output for pipeline pass/fail decisions |

---

## Tier 1: Core Framework Scenarios

These scenarios require only tooli's irreducible core: the decorator, structured output, JSON Schema export, and structured errors. No SKILL.md generation, no MCP server, no export commands.

---

### Scenario 1: The Solo Developer's Debugging Toolkit

**Sources:** `scenarios_cc.md` §1, `scenarios_gm.md` §1, §2

#### Persona and Job to Be Done

**Maya**, a backend developer on-call rotation. *When I'm paged for a production incident, I want structured diagnosis so I can restore service without re-deriving shell pipelines from scratch.*

#### Context

Maya has a collection of bash one-liners she runs during incidents — `grep`, `jq`, `awk`, `sed` in various combinations. She keeps forgetting the exact incantation for correlating request IDs across microservice logs. Every incident, she re-derives the pipeline.

#### Journey

**Phase 1 — The Scratch Script.** Maya wraps her most-used pipeline into a tooli command during a calm afternoon:

```python
from tooli import Tooli, Annotated, Argument, Option

app = Tooli(name="loggrep", version="0.1.0")

@app.command()
def errors(
    path: Annotated[str, Argument(help="Log file or directory")],
    since: Annotated[str, Option(help="ISO timestamp cutoff")] = "",
    level: Annotated[str, Option(help="Minimum level: warn|error|fatal")] = "error",
) -> list[dict]:
    """Extract structured error entries from application logs."""
    ...
```

She runs `loggrep errors /var/log/myapp/ --since 2026-02-20T00:00 --json` during the next outage. It works. She adds `loggrep timeline` and `loggrep correlate` over the following week.

**Phase 2 — Claude Code Discovers It.** Maya adds loggrep to her project's MCP config (the MCP serving is handled by the agent platform, not by tooli itself). Claude Code reads the tool's schema and starts invoking it during debugging sessions:

> **Maya:** "The checkout service is returning 502s. What's in the logs from the last hour?"
>
> **Claude Code:** *(invokes `loggrep errors /var/log/checkout/ --since <1h ago> --level error --json`)*
>
> "Found 47 errors in the last hour. The timeline shows connection pool exhaustion starting at 14:32, triggered by retry storms from the payment gateway. Checkout's retry logic amplified 12 failing requests into 47 connection attempts, exhausting the pool. Want me to check the payment gateway logs?"

Maya didn't teach Claude Code the three-step triage process (errors → timeline → correlate). The agent inferred the workflow from the structured output — each result contains fields (`request_id`, `trace_id`) that naturally lead to the next command.

**Phase 3 — The Error Recovery Loop.** A teammate provides a gzipped log file. The tool can't read it by default:

```json
{
  "ok": false,
  "error": {
    "code": "E3001",
    "category": "state",
    "message": "Cannot read gzipped file without --decompress flag",
    "suggestion": "Retry with --decompress flag"
  }
}
```

Claude Code reads the structured error, adds the flag, and retries automatically. No human intervention required. This is the **reflection pattern** — the error envelope gives the agent enough information to self-correct.

**Phase 4 — Team Adoption.** Maya's teammates see her using loggrep during shared debugging. They install it. The team lead adds guidance to the project's CLAUDE.md (a human-authored file, not generated by tooli):

```markdown
## Incident Response
- Use `loggrep errors` before manually grepping logs
- Use `loggrep correlate` for cross-service issues
```

New on-call engineers get the benefit of Maya's debugging patterns without a knowledge transfer session.

#### What Tooli Provided

- `@app.command()` with type hints → CLI with `--json` output
- Structured `{ok, result, error, meta}` envelope → agent can parse results and chain commands
- Structured errors with `suggestion` → agent self-corrects without human help
- JSON Schema via `--schema` → agent knows every flag without reading source code

#### What Tooli Did Not Need to Provide

- SKILL.md generation (the workflow was captured in a human-authored CLAUDE.md)
- MCP server (the agent platform handles tool registration)
- MCP resources (if the team wants `loggrep://recent-errors`, that's a FastMCP resource backed by the same command)

#### Key Interactions

| Given | When | Then |
|---|---|---|
| loggrep is available to the agent | Maya asks about recent errors | Agent invokes `loggrep errors` with appropriate time filter and `--json` |
| `errors` output contains `request_id` fields | Agent needs to understand the sequence | Agent invokes `loggrep timeline` using the `request_id` from the worst error |
| Tool receives a gzipped file it can't read | Agent reads the structured error | Agent retries with `--decompress` flag per the `suggestion` field |
| `loggrep errors` returns an empty list | Maya asks about errors | Agent reports no errors and suggests broadening time window — guided by structured empty response |

#### Acceptance Criteria

1. Commands return the `{ok, result, error, meta}` envelope in `--json` mode.
2. Invalid inputs produce structured errors with actionable `suggestion` strings.
3. Schema export (`--schema`) accurately describes all parameters and return types.

---

### Scenario 2: The Platform Team's Deployment Toolchain

**Sources:** `scenarios_cc.md` §2, §5, §9; `scenarios_gm.md` §3

#### Persona and Job to Be Done

**Jordan** (platform lead) and **Alex** (product engineer). *When deploying to production, I want confidence that nothing will break, and when something does go wrong, I want deterministic recovery.*

**Priya** (new hire). *When I join the team, I want to be productive without memorizing every CLI flag and deployment step.*

#### Context

The platform team has built five independent CLI tools over the past year: `deploy-pilot` (canary orchestration), `config-vault` (encrypted config management), `schema-check` (DB migration validator), `feature-flags` (flag management), `health-check` (service dependency monitor). Engineers struggle to remember the correct order of operations. Last month, someone promoted a canary without checking the migration validator, causing a schema mismatch in production.

#### Journey

**Phase 1 — The Individual Tools.** Each tool is a standalone tooli app. The critical features are structured output and clear error semantics:

```python
# deploy_pilot.py
@app.command()
def canary(service: str, version: str, percentage: int = 5) -> dict:
    """Deploy a canary release to a percentage of traffic."""
    ...

@app.command()
def promote(service: str) -> dict:
    """Promote canary to full traffic. Requires prior health check."""
    ...

@app.command()
def rollback(service: str) -> dict:
    """Immediately rollback to previous version."""
    ...
```

**Phase 2 — The Human-Authored Orchestration Layer.** After the schema mismatch incident, Jordan writes a project-level CLAUDE.md that encodes deployment knowledge as rules:

```markdown
## Deployment Workflow (MANDATORY ORDER)
1. `schema-check validate ./migrations --json` — Validate DB changes first
2. `feature-flags check <flag> --json` — Verify feature flag state
3. `config-vault diff <service> --env staging --env production --json` — Check config drift
4. `deploy-pilot canary <service> <version> --json` — Start canary at 5%
5. `health-check watch <service> --duration 5m --json` — Monitor canary health
6. `deploy-pilot promote <service> --json` — Promote ONLY if health-check passes

## Rules
- NEVER run `deploy-pilot promote` without `health-check watch` passing first
- NEVER skip `schema-check validate` for PRs touching `migrations/`
- Ask for human confirmation before `promote` and `rollback`
```

This is not generated by tooli. It's tribal knowledge that Jordan wrote by hand. Tooli's contribution is that every tool in this workflow produces `{ok, result, meta}` envelopes, so the agent can read the output of each step and decide whether to proceed.

**Phase 3 — What Engineers Experience.** Alex (product engineer) deploys:

> **Alex:** "Deploy user-service v2.4.1 to production"
>
> **Claude Code:** *(reads CLAUDE.md, follows mandatory workflow)*
>
> "I see pending migrations in this PR. Starting with schema validation."
> *(invokes `schema-check validate ./migrations --json`)*
> "Migration is safe — additive column, no locks, backward compatible."
>
> *(invokes each subsequent step, reading structured output at each stage)*
>
> "Canary looks healthy — error rate 0.02% vs 0.03% baseline. Ready to promote. Should I proceed?"

Alex didn't memorize the deployment workflow. The CLAUDE.md encoded it, and the tools' structured output let the agent make decisions at each step.

**Phase 4 — The Guardrail Moment.** A junior engineer tries to skip steps:

> **Junior:** "Just promote user-service, the canary's been running for a while"
>
> **Claude Code:** "I need to verify canary health before promoting — that's a mandatory step."
> *(invokes `health-check watch user-service --duration 1m --json`)*
> "Health check shows elevated error rate: 2.3% vs 0.03% baseline. I won't promote."
>
> "The errors are `ConnectionRefused` from the cache layer. Recommended: rollback the canary and check cache connection config."

**Phase 5 — The New Hire Experience.** Two months later, Priya joins the team. On day 3, she's assigned a bug fix:

> **Priya:** "I've been assigned JIRA-4521 — a null pointer exception in the order service. Where do I start?"
>
> **Claude Code:** *(reads CLAUDE.md, sees available tools)*
> "Let me use the team's log analysis tool."
> *(invokes `loggrep errors /var/log/order-service/ --since 2026-02-18 --level error --json`)*
> "Found the NPE. It's in `OrderProcessor.java:142`..."

Priya didn't know loggrep exists. She didn't need to. She learns the CLI by watching the agent use it — the agent's invocations serve as live examples. By week 2, she's running commands directly.

#### What Tooli Provided

- Structured output that agents can parse and reason about at each workflow step
- Structured errors that let agents decide proceed/halt/rollback
- JSON Schema so agents know exact parameter signatures
- Consistent envelope format across five independent tools

#### What Tooli Did Not Need to Provide

- CLAUDE.md generation (Jordan wrote this by hand — it encodes judgment, not just schema)
- Workflow orchestration (the agent platform handles sequencing from the CLAUDE.md)
- Multi-agent coordination (if subagents are used, that's the agent platform's routing)

#### Key Interactions

| Given | When | Then |
|---|---|---|
| PR touches `migrations/` | Engineer requests deployment | Agent starts with `schema-check validate` per CLAUDE.md rules |
| `schema-check` returns `"safe": false, "reason": "table lock"` | Agent reads the result | Agent halts deployment and explains the risk |
| `health-check watch` shows elevated error rate | Agent is about to promote | Agent refuses to promote, shows diagnostics, suggests rollback |
| Priya has never used these tools | She asks about a production error | Agent uses tools on her behalf and explains each step |
| Priya wants to learn the CLI directly | She asks about a specific flag | Agent shows the schema and gives a concrete example |

#### Acceptance Criteria

1. All five tools produce stable `{ok, result, error, meta}` envelopes.
2. Error responses include enough context for agents to decide proceed/halt/rollback.
3. Schema export accurately reflects all parameters so agents never hallucinate flags.
4. Tools work identically whether invoked by a human, an agent, or a CI pipeline.

---

### Scenario 3: Independent Tools That Compose

**Sources:** `scenarios_cc.md` §3

#### Persona and Job to Be Done

**Sam**, a freelance developer. *When preparing a repository for release, I want multiple utility tools to work together reliably without custom glue code.*

#### Context

Sam has a pre-release checklist: lint docs, optimize images, check licenses, generate changelog. Each step uses a different tool with different output formats. Sam frequently forgets a step or runs them in the wrong order.

#### Journey

**Phase 1 — Installing the Pieces.** Sam installs four tooli apps from PyPI, each built by a different author who doesn't know the others exist:

```
tooli-mdlint        — Markdown linter with structured diagnostics
tooli-imgopt        — Image optimization with dry-run support
tooli-license-scan  — Dependency license auditor
tooli-changelog     — Changelog generator from git history
```

Because they all built on tooli, they share the `{ok, result, meta}` envelope, JSON Schema export, and structured error responses.

**Phase 2 — Emergent Composition.** Sam registers all four as tools available to Claude Code and asks:

> **Sam:** "Prepare this repo for the v3.0 release"
>
> **Claude Code:** *(reads schemas of all four tools)*
>
> "Starting with compliance — license issues are blocking."
>
> *(invokes `license-scan audit --json`)*
> "Found 2 GPL-3.0 dependencies conflicting with your MIT license."
>
> *(invokes `mdlint check docs/ --json`)*
> "Found 6 issues — 4 broken links, 2 heading hierarchy violations. I can fix these."
>
> *(fixes markdown issues, then invokes `imgopt scan assets/ --dry-run --json`)*
> "6 images can be optimized, saving 2.3MB. Want me to apply?"
>
> *(after approval, invokes `imgopt optimize assets/ --json`)*
>
> *(invokes `changelog generate --from v2.0.0 --json`)*
>
> "Summary: Docs fixed, images optimized, changelog drafted. **Blocking:** 2 GPL dependencies need resolution."

**Phase 3 — Graceful Degradation.** Sam starts a new project without `tooli-imgopt` installed:

> **Claude Code:** "I have license-scan, mdlint, and changelog available, but not imgopt. I'll run the steps I can. You may want to install `tooli-imgopt` for image optimization."

The agent doesn't fail. It reports the gap and continues.

#### What Tooli Provided

- The shared `{ok, result, meta}` envelope — the universal connector between tools that don't know about each other
- Consistent `--json` mode — every tool is machine-readable without per-tool parsers
- Structured errors — agents handle failures gracefully instead of crashing the workflow
- Consistent `--dry-run` convention for mutative operations

#### Key Interactions

| Given | When | Then |
|---|---|---|
| Four independent tools share the envelope format | Agent composes a workflow | Agent chains tools using structured output, no text scraping |
| `license-scan` finds blocking issues | Agent is preparing a release | Agent surfaces blockers first, continues with non-blocking checks |
| `imgopt scan` is run with `--dry-run` | Agent reads the output | Agent presents the plan and asks for confirmation before mutating |
| A referenced tool is not installed | Agent encounters the gap | Agent reports the missing tool with install guidance and continues |

#### Acceptance Criteria

1. Tools from different authors compose through the shared envelope format alone.
2. Missing tools produce clear gaps, not crashes.
3. Mutative operations support `--dry-run` so agents can preview before applying.

---

### Scenario 4: The Agent as Tool Author

**Sources:** `scenarios_cc.md` §4, `scenarios_gm.md` §4

#### Persona and Job to Be Done

**Dana**, a senior engineer. *When I notice a repeated manual analysis, I want it converted into a durable, reusable tool so the work compounds.*

#### Context

Over the past month, Dana has asked Claude Code to do the same API performance analysis four times: check which endpoints have response times over 500ms and cross-reference with missing caching headers. Each time, Claude Code writes a fresh ad-hoc script. The scripts are slightly different each time — inconsistent timeout handling, different output formats, no error handling for endpoints that require auth.

#### Journey

**Phase 1 — The Repetition Pattern.** Four sessions, four similar scripts, each thrown away.

**Phase 2 — The Agent Proposes.** On the fifth request:

> **Claude Code:** "I've done this analysis 4 times and each time the script is slightly different. Want me to create a reusable tooli app for this?"
>
> **Dana:** "Yes, make it a tooli app"

**Phase 3 — The Agent Authors.** Claude Code generates a complete tool, incorporating lessons from all four sessions:

```python
from tooli import Tooli, Annotated, Argument, Option

app = Tooli(name="api-audit", version="0.1.0")

@app.command()
def slow_endpoints(
    base_url: Annotated[str, Argument(help="Base URL of the API")],
    threshold_ms: Annotated[int, Option(help="Response time threshold in ms")] = 500,
    endpoints_file: Annotated[str, Option(help="File listing endpoints to check")] = "endpoints.txt",
    auth_token: Annotated[str | None, Option(help="Bearer token")] = None,
) -> list[dict]:
    """Find API endpoints with response times above threshold."""
    ...

@app.command()
def cache_audit(
    base_url: Annotated[str, Argument(help="Base URL of the API")],
    endpoints_file: Annotated[str, Option(help="File listing endpoints to check")] = "endpoints.txt",
    auth_token: Annotated[str | None, Option(help="Bearer token")] = None,
) -> list[dict]:
    """Check caching headers on API endpoints."""
    ...

@app.command()
def suggest_fixes(
    base_url: Annotated[str, Argument(help="Base URL of the API")],
    threshold_ms: Annotated[int, Option(help="Response time threshold")] = 500,
    auth_token: Annotated[str | None, Option(help="Bearer token")] = None,
) -> list[dict]:
    """Cross-reference slow endpoints with missing cache headers."""
    ...
```

What the agent learned from the four sessions: auth tokens are needed (session 2 failed without them), ETag and Last-Modified matter alongside Cache-Control (session 3), the combined analysis is the most common request (sessions 3 and 4), and the threshold should be configurable (session 1 used 500ms, session 4 used 300ms).

**Phase 4 — Reuse.** Dana adds `api-audit` to her environment. Next time:

> **Dana:** "Check our staging API health"
>
> **Claude Code:** *(reads api-audit schema, invokes `suggest-fixes`)*
> "Found 3 endpoints that are both slow and uncached..."

A different engineer on the team discovers the tool and starts using it without knowing Dana built it (or rather, that Claude Code built it with Dana's approval).

#### What Tooli Provided

- A simple enough framework that an agent can scaffold a tool correctly
- Type hints → schema pipeline means the agent-authored tool is immediately self-describing
- The `{ok, result, error, meta}` envelope means the agent-authored tool's output is automatically parseable by other agents

#### Key Interactions

| Given | When | Then |
|---|---|---|
| Agent has done the same analysis 4 times | Developer asks for it a 5th time | Agent proposes creating a reusable tool |
| Developer approves tool creation | Agent generates the tool | Tool incorporates lessons from all prior sessions (auth, headers, configurability) |
| Tool is available to the team | A different engineer asks about API performance | Agent discovers and uses the tool |
| `slow-endpoints` fails for authenticated endpoints | Auth token not provided | Structured error with `suggestion` tells the agent to ask for the token |

#### Acceptance Criteria

1. An agent can scaffold a valid tooli app using only the decorator API and type hints.
2. The agent-authored tool produces the same structured output as a human-authored tool.
3. The tool is immediately usable by other agents via schema discovery.

---

### Scenario 5: CI/CD as a First-Class Consumer

**Sources:** `scenarios_cc.md` §7, §12

#### Persona and Job to Be Done

**Elena**, a CI maintainer. *When PRs are opened, I want structured checks and actionable failures so both the pipeline and agents can diagnose issues without regex parsing.*

#### Context

Most CI linters output unstructured text that CI pipelines parse with regex. When a new version changes the output format, the parser breaks. The team wants CI checks that produce stable, structured output.

#### Journey

**Phase 1 — Structured CI Steps.** The team's CI workflow calls tooli apps with `--json`:

```yaml
# .github/workflows/ci.yml
jobs:
  quality:
    steps:
      - name: Check documentation
        run: mdlint check docs/ --json > mdlint-results.json

      - name: Audit licenses
        run: license-scan audit --json > license-results.json

      - name: Validate schemas
        run: schema-check validate ./migrations --json > schema-results.json

      - name: Post results
        run: python scripts/post_ci_results.py
```

Because every tool produces `{ok, result, meta}`, the result-posting script is trivial:

```python
import json, sys
for results_file in sys.argv[1:]:
    data = json.load(open(results_file))
    if not data["ok"]:
        print(f"::error::{data['error']['message']}")
        if data["error"].get("suggestion"):
            print(f"::notice::Fix: {data['error']['suggestion']}")
```

No per-tool parsing. No regex. The envelope format is the CI contract.

**Phase 2 — Agent-Aware CI Feedback.** When CI fails, developers ask Claude Code:

> **Developer:** "CI failed on my PR, what's wrong?"
>
> **Claude Code:** *(reads CI output, recognizes the envelope format)*
> "The `license-scan` step failed. Dependency `chart-renderer` v3.0 changed its license from MIT to BSL-1.1. The tool suggests pinning to v2.9 or evaluating BSL terms. Want me to pin it?"

**Phase 3 — Versioned Evolution.** A tool maintainer needs to rename `--format` to `--output-format`. Instead of a breaking change, they add deprecation metadata:

```python
@app.command()
def run(
    source: str,
    format: Annotated[str, Option(help="[DEPRECATED] Use --output-format")] = "csv",
    output_format: Annotated[str | None, Option(help="Output format: csv|parquet|json")] = None,
) -> dict:
    """Export data from source."""
    actual_format = output_format or format
    ...
```

When the old flag is eventually removed, the tool returns a structured error with migration instructions instead of a cryptic "unrecognized option" message:

```json
{
  "ok": false,
  "error": {
    "code": "E1001",
    "message": "Parameter '--format' was removed in v3.0.0. Use '--output-format' instead.",
    "suggestion": "Replace --format with --output-format"
  }
}
```

Agents that read the schema see the deprecation and auto-migrate. CI pipelines detect the warning in the envelope metadata. The transition is smooth for both humans and machines.

#### What Tooli Provided

- The `{ok, result, error, meta}` envelope as a stable CI contract
- Structured errors with `suggestion` fields that become GitHub annotations
- Deprecation metadata in the schema so consumers can auto-migrate
- Consistent behavior whether the caller is a human, an agent, or a CI runner

#### Key Interactions

| Given | When | Then |
|---|---|---|
| CI runs tools with `--json` | A step fails | CI posts the structured error message, not a wall of text |
| Tool provides `suggestion` | CI formats results | Suggestion appears as a GitHub annotation on the PR |
| Developer asks agent about CI failure | Agent reads structured CI output | Agent extracts error and suggestion directly from the envelope |
| Command has deprecation metadata | Agent reads schema | Agent uses the new flag automatically |
| Deprecated flag is removed entirely | Old invocation uses `--format` | Structured error with exact replacement, not cryptic CLI error |

#### Acceptance Criteria

1. CI never depends on text scraping for tooli command outputs.
2. Deprecation metadata is visible in schema export and error responses.
3. Breaking changes produce structured migration guidance, not crashes.

---

## Tier 2: Ecosystem Scenarios

These scenarios are realistic but require capabilities beyond tooli's core — capability enforcement, audit telemetry, tool registries. They represent patterns where tooli's structured output is *consumed by* platform infrastructure, not patterns where tooli *provides* that infrastructure.

---

### Scenario 6: Capability Enforcement and Security Audit

**Sources:** `scenarios_cc.md` §6, `scenarios_gm.md` §6

#### Persona and Job to Be Done

**Riku**, a security engineer. *When autonomous agents run tools in our environment, I want to control exactly what they can access and audit what they did.*

#### Context

Regulatory requirements mandate that tools only access what they explicitly declare. The security team needs enforcement without making developers' lives harder.

#### What This Requires From Tooli

Tooli's contribution here is limited but important: **capability declarations on commands.** If a command declares its required capabilities in its metadata, an enforcement layer outside tooli can check the declaration against an allowlist.

```python
@app.command(capabilities=["fs:read", "net:read"])
def scan_logs(path: str) -> list[dict]:
    """Scan logs for credential leaks."""
    ...
```

The schema export includes `capabilities: ["fs:read", "net:read"]`. An external enforcement layer — an MCP proxy, a shell wrapper, an enterprise policy engine — reads the capabilities from the schema and decides whether to allow the invocation.

#### What This Does Not Require From Tooli

Tooli does not need to implement the enforcement. It does not need `TOOLI_ALLOWED_CAPABILITIES`, `TOOLI_STRICT_MODE`, or telemetry collection. These are platform concerns. Tooli's job is to make the declaration available in the schema. The platform's job is to enforce it.

This is the "declare-then-enforce" pattern: the tool declares what it needs, the environment declares what it allows, and the gap produces a structured error. The error comes from the enforcement layer, not from tooli itself.

#### Key Interactions

| Given | When | Then |
|---|---|---|
| Command declares `capabilities: ["fs:write"]` | Enforcement layer checks against allowlist | Invocation blocked with structured error (from enforcement layer) |
| Capability declarations are in schema export | Security team audits tool permissions | All required capabilities are visible via `--schema` |
| Agent receives a capability denial | Agent is in the middle of a workflow | Agent explains the block and suggests contacting the security team |

#### Acceptance Criteria

1. `capabilities` are included in JSON Schema export.
2. Capability declarations are per-command, not per-app.
3. Tooli does not implement enforcement — it provides the metadata that enforcement layers consume.

---

### Scenario 7: Cross-Team Tool Discovery

**Sources:** `scenarios_cc.md` §8

#### Persona and Job to Be Done

**Staff engineer** coordinating multiple teams. *When a capability I need already exists on another team, I want to find and use their tool instead of rebuilding it.*

#### Context

Fifteen engineering teams have each built 2-3 tooli apps. The data team has `data-lint`. The frontend team has `bundle-audit`. The infra team has `tf-check`. Nobody knows what other teams have built.

#### What This Requires From Tooli

Tooli provides consistent, machine-readable metadata per tool: name, description, command signatures, parameter types, capability declarations. All of this is available via `--schema`. A separate tool registry — which could be as simple as a shared repository that collects `--schema` output from every team's tools — makes this searchable.

#### What This Does Not Require From Tooli

Tooli does not need to build a registry, a `tool-marketplace` command, or a discovery protocol. The registry is a separate service. Tooli's contribution is that every tool's schema is consistently structured, so the registry can index them uniformly.

#### Key Interactions

| Given | When | Then |
|---|---|---|
| Every tooli app produces consistent schema via `--schema` | Registry indexes all schemas | Developer or agent searches for tools by capability or keyword |
| Registry returns a matching tool | Agent reads the schema | Agent evaluates safety and offers to use it |
| Two teams have similar tools | Agent needs to choose | Agent compares capabilities and descriptions from schemas |

#### Acceptance Criteria

1. Schema export is complete enough for a registry to index (name, description, commands, parameters, capabilities).
2. Schema format is stable across tooli versions.
3. No tooli-side registry infrastructure is required.

---

### Scenario 8: Customer Support Workflows

**Sources:** `scenarios_cc.md` §11

#### Persona and Job to Be Done

**Leila**, a support engineer. *When a customer reports an issue, I want to diagnose the root cause and apply safe remediation without accidentally making things worse.*

#### Context

Support tickets follow patterns: account locked, quota exceeded, payment failed. Each has a diagnostic step and a remediation step. Remediation is often destructive (resetting state, clearing caches) and must be audited.

#### Journey

**Phase 1 — The Tools.**

```python
@app.command()
def diagnose(
    account_id: Annotated[str, Argument(help="Customer account ID")],
) -> dict:
    """Diagnose account issues and suggest remediation."""
    ...

@app.command()
def quota_reset(
    account_id: Annotated[str, Argument(help="Customer account ID")],
    reason: Annotated[str, Option(help="Audit reason for the reset")],
) -> dict:
    """Reset account quota to default limits. Requires reason for audit trail."""
    ...
```

**Phase 2 — Agent-Guided Triage.**

> **Leila:** "Customer acme-corp says they can't upload files"
>
> **Claude Code:** *(invokes `acct-tools diagnose acme-corp --json`)*
> "Root cause: storage quota exceeded. 847MB in orphaned temp files from a failed bulk import."
>
> "I can reset the quota with `quota-reset`, but it's a destructive action that requires a reason for audit. Should I proceed?"
>
> **Leila:** "Yes, reason is orphaned temp files from bulk import"
>
> **Claude Code:** *(invokes `acct-tools quota-reset acme-corp --reason "orphaned temp files from bulk import" --json`)*
> "Done. 847MB freed. New usage: 91.5%."

The `reason` parameter is mandatory — the tool enforces audit trail requirements through its own parameter validation, not through a separate governance layer. The schema tells the agent that `reason` is required. The structured output includes before/after state for the audit record.

#### What Tooli Provided

- Mandatory parameters enforced via type system (no `reason` = validation error)
- Structured output with before/after state for audit trails
- Clear parameter descriptions so agents explain what they're about to do

#### Key Interactions

| Given | When | Then |
|---|---|---|
| Customer reports upload failure | Leila describes the symptom | Agent runs `diagnose` and identifies root cause |
| `quota-reset` requires `reason` parameter | Agent proposes the action | Agent explains it requires a reason and asks for one |
| Reset completed | Agent confirms | Result includes before/after state in structured output |
| Unknown account ID provided | Agent runs `diagnose` | Structured error with `suggestion` tells agent the expected format |

#### Acceptance Criteria

1. Mandatory parameters are enforced by the type system and surfaced in schema.
2. Destructive operations produce output that serves as an audit record (actor, reason, timestamp, before/after).
3. Error responses for bad input include enough information for the agent to ask the user for corrections.

---

## Patterns Across All Scenarios

### 1. Structured Output Is the Universal Connector

The `{ok, result, meta}` envelope isn't decorative — it's the API contract that makes everything else possible. Agents parse it. CI pipelines parse it. Other tools parse it. When output is structured, composition is free. This is tooli's single most important feature.

### 2. Errors Are a First-Class Interface

Every scenario includes a failure path. In every case, the structured error with a `suggestion` field is what lets the agent recover without human intervention. The error envelope is as important as the success envelope.

### 3. Schema Is the Discovery Mechanism

Agents don't need SKILL.md, AGENTS.md, or generated documentation to use tooli apps. They need the JSON Schema from `--schema`. The schema tells them every parameter, every type, every default. Documentation adds context (when to use this, what workflow it belongs to), but the schema is the minimum viable discovery mechanism.

### 4. Documentation Is a Human Concern

CLAUDE.md files, deployment runbooks, onboarding guides — these are written by humans who understand the *why*, not just the *what*. Tooli's job is to make the tools self-describing enough that human-authored documentation can reference them concisely. The documentation layer should not be generated by the CLI framework.

### 5. The Tool Lifecycle Is Real but Doesn't Need Framework Support at Every Stage

Every source document describes the same progression: pain → script → tooli command → agent invocation → team workflow → organizational resource. This lifecycle is real. But tooli only needs to be excellent at the "tooli command" and "agent invocation" stages. The "team workflow" stage is a CLAUDE.md written by a human. The "organizational resource" stage is an MCP resource or registry managed by infrastructure. Tooli enables the lifecycle by producing great structured output. It doesn't need to manage the lifecycle.

### 6. Tooli-Powered Tools Are Framework-Agnostic by Default

Because tooli exports JSON Schema and produces a standard envelope, the tools in these scenarios already work with any agent that can call a CLI and parse JSON. No `--export langchain` needed. Any framework that can invoke a subprocess and read stdout gets structured output. Any framework that can read JSON Schema gets parameter discovery. Tooli's universality comes from its simplicity, not from generating wrapper code for every platform.

---

## What Isn't Here and Why

**Multi-agent subagent orchestration.** Scenarios 2 and the source documents describe orchestrator agents delegating to specialized subagents. This is a real pattern, but it's the agent platform's responsibility (Claude Code's subagent routing, LangGraph's graph execution, etc.). Tooli's contribution is that each tool produces structured output that any orchestration layer can consume. Tooli does not need a Python API for in-process agent-to-agent calls.

**MCP resource promotion.** Several source scenarios describe promoting frequently-read data to MCP resources (`loggrep://recent-errors`, `deploy://status/{service}`). This is valuable but it's an MCP server concern. FastMCP handles resource registration. Tooli's contribution is that the underlying commands produce structured, cacheable output.

**Global Skill Mesh / multi-framework export.** The source documents envision `tooli export --target langchain/openai/adk` generating framework-specific wrappers. This is a separate code-generation tool that reads JSON Schema, not a CLI framework feature. Building it into tooli means tracking API changes from every LLM provider indefinitely.

**Enterprise governance and telemetry.** Capability enforcement, invocation telemetry, and audit logging are platform infrastructure. Tooli's role is to declare capabilities in the schema so enforcement layers can consume them.

---

## Scenario Author Checklist

Before adding new scenarios:

1. Does the scenario have a named persona with a clear Job to Be Done?
2. Does it specify what tooli *the framework* provides vs. what the *ecosystem* provides?
3. Are failure paths explicitly dramatized with structured error responses?
4. Are acceptance criteria observable and testable against tooli's core API?
5. Does it include concrete code, JSON output, or agent dialogue?
6. Does it show something the existing scenarios don't already cover?
7. Would the scenario still work if tooli had no SKILL.md generator, no MCP server, and no multi-format export?
