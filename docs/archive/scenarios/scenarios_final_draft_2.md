# Tooli Scenarios: From Function to Agent Skill

> Realistic usage scenarios for tooli, grounded in what the framework actually does — and organized by what matters most.

This document merges and refines scenarios from three source documents (`scenarios_cc.md`, `scenarios_gm.md`, `scenarios_cdx.md`) into a single canonical reference. It is organized through a critical architectural lens: **what does tooli the CLI framework need to provide at its core, vs. what are platform features that build on that core?**

The guiding principle: tooli's irreducible job is to make it easy to write a CLI tool that agents can call with structured input and get structured output. Everything beyond that — capabilities enforcement, MCP resource promotion, multi-framework export, documentation generation — is valuable but layered on top. Scenarios are tiered accordingly.

---

## Source Coverage

| Source | Original Scenario | Status in This Document |
|---|---|---|
| `scenarios_cc.md` | 1: Solo Developer's Debugging Toolkit | **Scenario 1** (Tier 1) |
| `scenarios_cc.md` | 2: Platform Team's Internal Toolchain | **Scenario 2** (Tier 1, includes New Hire onboarding) |
| `scenarios_cc.md` | 3: Open-Source Ecosystem Effect | **Scenario 3** (Tier 1) |
| `scenarios_cc.md` | 4: Agent-Built Tool | **Scenario 4** (Tier 1) |
| `scenarios_cc.md` | 5: New Hire Onboarding Experience | Folded into Scenario 2 Phase 5 (same tools, different persona) |
| `scenarios_cc.md` | 6: Security Audit Workflow | **Scenario 6** (Tier 2) |
| `scenarios_cc.md` | 7: CI/CD Pipeline Integration | **Scenario 5** (Tier 1, includes versioned evolution) |
| `scenarios_cc.md` | 8: Cross-Team Tool Marketplace | **Scenario 7** (Tier 2) |
| `scenarios_cc.md` | 9: Multi-Agent War Room | Folded into Scenario 2 Phase 6 (coordination is the agent platform's job) |
| `scenarios_cc.md` | 10: Global Skill Mesh | **Scenario 9** (Tier 2) |
| `scenarios_cc.md` | 11: Customer Support Workflows | **Scenario 8** (Tier 2) |
| `scenarios_cc.md` | 12: Versioned Evolution | Folded into Scenario 5 Phase 3 (deprecation is a schema/error feature) |
| `scenarios_cdx.md` | 9: Resource-First Subagent Operations | **Scenario 10** (Tier 2) |
| `scenarios_gm.md` | 1: Lifecycle of a Skill | Merged into Scenario 1 |
| `scenarios_gm.md` | 2: Autonomous Self-Healing | Merged into Scenario 1 Phase 3 (structured error retry) |
| `scenarios_gm.md` | 3: Multi-Agent War Room | Merged into Scenario 2 Phase 6 |
| `scenarios_gm.md` | 4: Agent as Tool Author | Merged into Scenario 4 |
| `scenarios_gm.md` | 5: Global Skill Mesh | Merged into Scenario 9 |
| `scenarios_gm.md` | 6: Enterprise Governance | Merged into Scenario 6 |

---

## Personas

| Persona | Role | What They Need from Tooli |
|---|---|---|
| **Maya** | Backend developer, on-call engineer | Fast, structured CLI commands for incident diagnosis |
| **Jordan** | Platform lead | Structured output so documented workflows are reliable |
| **Alex** | Product engineer | CLI tools that agents can operate on her behalf |
| **Priya** | New hire (first two weeks) | Tools that are self-describing so the agent can guide her |
| **Sam** | Freelance dev, open-source consumer | Tools from different authors that compose via shared output format |
| **Dana** | Senior engineer, API developer | Consistent tool structure so agent-built tools match human-built ones |
| **Riku** | Security engineer | Capability declarations, structured audit metadata, and enforceable guardrails |
| **Elena** | CI maintainer | Machine-readable output for pipeline pass/fail decisions |
| **Leila** | Support engineer | Safe, auditable remediation workflows |
| **The Agent (Claude Code)** | Autonomous teammate | Discovers, invokes, composes, and authors tools based on observed patterns |

---

## Tier 1: Core Framework Scenarios

These scenarios require only tooli's irreducible core: the `@app.command()` decorator, the `{ok, result, error, meta}` envelope, JSON Schema export via `--schema`, and structured error responses with `suggestion` fields. No MCP server, no SKILL.md generation, no export commands, no capabilities enforcement. If you stripped tooli down to a decorator that produces structured CLI commands, these scenarios would still work.

---

### Scenario 1: The Solo Developer's Debugging Toolkit

**Sources:** `scenarios_cc.md` S1, `scenarios_gm.md` S1, S2

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

**What Maya notices:** She's spending less time re-deriving pipelines and more time actually diagnosing issues. The structured JSON output means she can pipe results into `jq` without fragile text parsing.

**Phase 2 — Claude Code Discovers It.** Maya adds loggrep to her project's MCP config. Claude Code reads the tool's schema and starts invoking it during debugging sessions:

> **Maya:** "The checkout service is returning 502s. What's in the logs from the last hour?"
>
> **Claude Code:** *(invokes `loggrep errors /var/log/checkout/ --since <1h ago> --level error --json`)*
>
> *(then invokes `loggrep timeline` using the worst error's `request_id`)*
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
    "suggestion": {
      "action": "add_flag",
      "flag": "--decompress",
      "retry": true
    }
  }
}
```

Claude Code reads the structured error, sees `"retry": true` with a concrete suggestion, adds the flag, and retries automatically. No human intervention required. This is the **reflection pattern** — the error envelope gives the agent enough information to self-correct.

Not all errors should be auto-retried. The agent distinguishes:

- **Auto-retry:** `"retry": true` with concrete suggestion (add flag, change format)
- **Escalate:** No suggestion, or suggestion requires human judgment
- **Block:** Capability denial, policy violation — never auto-retry

**Phase 4 — Team Adoption.** Maya's teammates see her using loggrep during shared debugging. They install it. The team lead adds guidance to the project's CLAUDE.md (a human-authored file, not generated by tooli):

```markdown
## Incident Response
- Use `loggrep errors` before manually grepping logs
- Use `loggrep correlate` for cross-service issues
```

New on-call engineers get the benefit of Maya's debugging patterns without a knowledge transfer session.

#### What Tooli Provides Here

- `@app.command()` with type hints → CLI with `--json` output
- Structured `{ok, result, error, meta}` envelope → agent can parse results and chain commands
- Structured errors with `suggestion` → agent self-corrects without human help
- JSON Schema via `--schema` → agent knows every flag without reading source code

#### What the Ecosystem Adds (Not Required)

- SKILL.md generation (the workflow was captured in a human-authored CLAUDE.md)
- MCP server (the agent platform handles tool registration)
- MCP resources (if the team wants `loggrep://recent-errors`, that's a resource layer backed by the same command)

#### Key Interactions

| Given | When | Then |
|---|---|---|
| loggrep is available to the agent | Maya asks about recent errors | Agent invokes `loggrep errors` with appropriate time filter and `--json` |
| `errors` output contains `request_id` fields | Agent needs to understand the sequence | Agent invokes `loggrep timeline` using the `request_id` from the worst error |
| Tool receives a gzipped file it can't read | Agent reads the structured error | Agent retries with `--decompress` flag per the `suggestion` field |
| `loggrep errors` returns an empty list | Maya asks about errors | Agent reports no errors and suggests broadening time window — guided by structured empty response |
| Tool returns error with `"retry": true` | Agent reads the error | Agent retries silently with the suggested fix |
| Tool returns auth/policy error | Agent reads the error category | Agent does NOT retry, explains the restriction to the user |

#### Acceptance Criteria

1. Commands return the `{ok, result, error, meta}` envelope in `--json` mode.
2. Invalid inputs produce structured errors with actionable `suggestion` strings.
3. Schema export (`--schema`) accurately describes all parameters and return types.
4. Environmental errors with `"retry": true` are auto-retried by agents without human interruption.

---

### Scenario 2: The Platform Team's Deployment Toolchain

**Sources:** `scenarios_cc.md` S2, S5, S9; `scenarios_gm.md` S3

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
> "Migration is safe — additive column `users.preferred_locale`, no locks, backward compatible."
>
> *(invokes each subsequent step, reading structured output at each stage)*
>
> "Canary looks healthy — error rate 0.02% vs 0.03% baseline. P99 latency: 142ms (baseline: 148ms). Ready to promote. Should I proceed?"

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
> "Found the NPE. It's in `OrderProcessor.java:142` — the `customer.address` field is null when processing international orders."

Priya didn't know loggrep exists. She didn't need to. She learns the CLI by watching the agent use it — the agent's invocations serve as live examples. By week 2, she's running commands directly.

> **Priya:** "Can I restart the production database? The connection pool seems stale."
>
> **Claude Code:** "I can't do that — the CLAUDE.md rules say 'NEVER restart production databases without SRE approval.' I'd recommend asking in the #sre channel, or I can check if `health-check` shows the connection pool issue."

**Phase 6 — Multi-Agent Coordination (Optional).** For complex releases touching multiple domains, the team uses Claude Code's subagent capability:

> **Release Lead:** "Deploy v5.0 to production. This release has DB migrations, a new API, and a security patch."
>
> **Orchestrator Agent:** "This is a multi-domain release. I'll coordinate specialized agents for each area."
> *(delegates security scan, migration validation, and config check to subagents in parallel)*
> *(synthesizes results)* "Pre-flight complete. CVE patched, migrations validated, config verified. Ready to start the canary. Should I proceed?"

The subagent coordination is handled by the agent platform, not by tooli. Tooli's contribution is that each tool produces structured output that any orchestration layer can consume.

#### What Tooli Provides Here

- Structured output that agents can parse and reason about at each workflow step
- Structured errors that let agents decide proceed/halt/rollback
- JSON Schema so agents know exact parameter signatures
- Consistent envelope format across five independent tools

#### What the Ecosystem Adds (Not Required)

- CLAUDE.md (Jordan wrote this by hand — it encodes judgment, not just schema)
- Workflow orchestration (the agent platform handles sequencing from the CLAUDE.md)
- Multi-agent coordination (subagent routing is the agent platform's job)

#### Key Interactions

| Given | When | Then |
|---|---|---|
| PR touches `migrations/` | Engineer requests deployment | Agent starts with `schema-check validate` per CLAUDE.md rules |
| `schema-check` returns `"safe": false, "reason": "table lock"` | Agent reads the result | Agent halts deployment and explains the risk |
| `health-check watch` shows elevated error rate | Agent is about to promote | Agent refuses to promote, shows diagnostics, suggests rollback |
| CLAUDE.md says "Ask for human confirmation before promote" | Health checks pass | Agent presents metrics and asks for explicit approval |
| Priya has never used these tools | She asks about a production error | Agent uses tools on her behalf and explains each step |
| Prohibited operation requested | Priya asks to restart production DB | Agent cites guardrail and blocks, offering safe alternatives |
| Engineer asks to skip schema-check | No migrations in PR | Agent skips (the rule says "for PRs touching migrations/") — it reads the condition, not just the rule |

#### Acceptance Criteria

1. All five tools produce stable `{ok, result, error, meta}` envelopes.
2. Error responses include enough context for agents to decide proceed/halt/rollback.
3. Schema export accurately reflects all parameters so agents never hallucinate flags.
4. Tools work identically whether invoked by a human, an agent, or a CI pipeline.

---

### Scenario 3: Independent Tools That Compose

**Sources:** `scenarios_cc.md` S3

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

Because they all built on tooli, they share the `{ok, result, meta}` envelope, JSON Schema export, structured error responses, and `--dry-run` convention for mutative operations.

**Phase 2 — Emergent Composition.** Sam registers all four as tools available to Claude Code:

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

#### What Tooli Provides Here

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

**Sources:** `scenarios_cc.md` S4, `scenarios_gm.md` S4

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

A different engineer discovers the tool and starts using it without knowing Dana built it (or rather, that Claude Code built it with Dana's approval).

#### What Tooli Provides Here

- A simple enough framework that an agent can scaffold a tool correctly
- Type hints → schema pipeline means the agent-authored tool is immediately self-describing
- The `{ok, result, error, meta}` envelope means the agent-authored tool's output is automatically parseable by other agents

#### Key Interactions

| Given | When | Then |
|---|---|---|
| Agent has done the same analysis 4 times | Developer asks for it a 5th time | Agent proposes creating a reusable tool |
| Developer approves tool creation | Agent generates the tool | Tool incorporates lessons from all prior sessions (auth, headers, configurability) |
| Tool is available to the team | A different engineer asks about API performance | Agent discovers and uses the tool via schema |
| `slow-endpoints` fails for authenticated endpoints | Auth token not provided | Structured error with `suggestion` tells the agent to ask for the token |

#### Acceptance Criteria

1. An agent can scaffold a valid tooli app using only the decorator API and type hints.
2. The agent-authored tool produces the same structured output as a human-authored tool.
3. The tool is immediately usable by other agents via schema discovery.

---

### Scenario 5: CI/CD as a First-Class Consumer

**Sources:** `scenarios_cc.md` S7, S12

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

#### What Tooli Provides Here

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
| PR changes command signature | CI compares schema to baseline | Breaking change detected before merge |

#### Acceptance Criteria

1. CI never depends on text scraping for tooli command outputs.
2. Deprecation metadata is visible in schema export and error responses.
3. Breaking changes produce structured migration guidance, not crashes.

---

## Tier 2: Platform Feature Scenarios

These scenarios build on the core but use tooli's platform features — capabilities enforcement, annotations (`Destructive`, `ReadOnly`), MCP resource promotion, multi-framework export, telemetry, and documentation generation. Tooli ships all of these features, but they layer on top of the core. A tool that only uses the core (Tier 1) works fine. A tool that uses these features gets additional safety, discoverability, and operational power.

---

### Scenario 6: Capability Enforcement and Security Audit

**Sources:** `scenarios_cc.md` S6, `scenarios_gm.md` S6

#### Persona and Job to Be Done

**Riku**, a security engineer. *When autonomous agents run tools in our environment, I want to control exactly what they can access and audit what they did.*

#### Context

Regulatory requirements mandate that tools only access what they explicitly declare. The security team needs enforcement without making developers' lives harder.

#### Journey

**Phase 1 — Capability Declarations.** Commands declare what they need:

```python
@app.command(capabilities=["fs:read", "net:read"])
def scan_logs(path: str) -> list[dict]:
    """Scan logs for credential leaks."""
    ...
```

The schema export includes `capabilities: ["fs:read", "net:read"]`. This is the **declare-then-enforce** pattern: the tool declares what it needs, the environment declares what it allows.

**Phase 2 — Capability Lockdown.** Riku sets an environment-level restriction:

```bash
export TOOLI_ALLOWED_CAPABILITIES="fs:read,net:read,db:read"
```

A developer installs a tool that writes temporary files:

```python
@app.command(capabilities=["fs:read", "fs:write"])
def analyze(path: str) -> dict:
    """Analyze code and write report to disk."""
    ...
```

**Given** `TOOLI_ALLOWED_CAPABILITIES` does not include `fs:write`,
**When** the tool is invoked,
**Then** tooli blocks the invocation *before the function body runs*:

```json
{
  "ok": false,
  "error": {
    "code": "E2002",
    "category": "auth",
    "message": "Capability 'fs:write' is not in the allowed set. Allowed: fs:read, net:read, db:read",
    "suggestion": {
      "action": "contact_admin",
      "fix": "Request 'fs:write' capability approval from your security team"
    }
  }
}
```

The agent handles this gracefully:

> **Claude Code:** "The `code-analyzer` tool needs `fs:write` permission, but your environment only allows `fs:read`, `net:read`, and `db:read`. This is a security policy restriction — I can't override it. You'll need to request `fs:write` approval from your security team."

**Phase 3 — Dry-Run Preview.** For destructive operations, agents preview before executing:

```python
@app.command(
    annotations=Destructive,
    capabilities=["fs:read", "fs:write"],
)
@dry_run_support
def prune(path: str, older_than: str = "30d") -> dict:
    """Delete files older than the specified age."""
    ...
```

> **Claude Code:** *(invokes `env-cleanup prune /tmp --older-than 7d --dry-run --json`)*
> "Dry-run complete. 142 files (847MB) would be deleted. Shall I proceed?"

**Phase 4 — Audit Trail.** Every tooli invocation includes caller metadata in telemetry:

```json
{
  "tool": "code-analyzer.analyze",
  "caller_id": "claude-code",
  "session_id": "sess_abc123",
  "capabilities_requested": ["fs:read", "fs:write"],
  "capabilities_blocked": ["fs:write"],
  "timestamp": "2026-02-20T14:32:01Z"
}
```

Riku can reconstruct exactly which tools were invoked, by which agent, with which capabilities, and which were blocked — all from structured telemetry.

#### What Tooli Provides Here

- `capabilities=` declarations on `@app.command()` — per-command, not per-app
- `TOOLI_ALLOWED_CAPABILITIES` enforcement (STRICT mode) — blocks before function body runs
- `Destructive` annotation + `@dry_run_support` — preview before mutating
- Caller metadata via `TOOLI_CALLER` convention — telemetry knows who called what
- Structured errors with remediation guidance for blocked actions

#### Key Interactions

| Given | When | Then |
|---|---|---|
| STRICT mode with limited allowlist | Tool requests `fs:write` | Invocation blocked with structured error explaining the gap |
| Agent receives a capability denial | Agent is mid-workflow | Agent explains the block and suggests contacting security team |
| Dry-run requested on destructive command | Command executes | Plan returned, no side effects |
| Approved execution completes | Audit trail generated | Record includes actor, capability scope, and result |

#### Acceptance Criteria

1. Policy enforcement occurs before mutative function body execution.
2. All blocked actions return machine-actionable remediation.
3. Security reporting can reconstruct allowed and denied attempts.
4. `capabilities` are included in JSON Schema export.

---

### Scenario 7: Cross-Team Tool Discovery

**Sources:** `scenarios_cc.md` S8

#### Persona and Job to Be Done

**Staff engineer** coordinating multiple teams. *When a capability I need already exists on another team, I want to find and use their tool instead of rebuilding it.*

#### Context

Fifteen engineering teams have each built 2-3 tooli apps. The data team has `data-lint`. The frontend team has `bundle-audit`. The infra team has `tf-check`. Nobody knows what other teams have built.

#### Journey

**Phase 1 — The Discovery Problem.** A developer needs CSV validation:

> **Developer:** "I need to validate our API's CSV export"
>
> **Claude Code:** *(searches tool-registry)* "Found `data-lint` from the Data Engineering team. It has a `validate-csv` command. It's read-only and safe. Want me to add it?"

**Phase 2 — The Registry.** Tooli provides consistent, machine-readable metadata per tool via `--schema`: name, description, command signatures, parameter types, capability declarations. A separate tool registry (which could be as simple as a shared repo that collects `--schema` output) makes this searchable.

The DevEx team built the registry itself as a tooli app:

```python
app = Tooli(name="tool-registry", version="1.0.0")

@app.command(annotations=ReadOnly)
def search(
    query: Annotated[str, Argument(help="Search query")],
    team: Annotated[str | None, Option(help="Filter by team")] = None,
) -> list[dict]:
    """Search the internal tool registry for matching tools."""
    ...
```

**Phase 3 — Cross-Repo Boundaries.**

> **Claude Code:** "The `infra-provision` command needs `net:write` in the `payments-service` repo, but I'm operating in `api-gateway`. Cross-repo mutations are blocked by policy. I can prepare a summary for the Payments team."

#### What Tooli Provides Here

- Consistent schema export that registries can index uniformly
- Stable schema format across versions
- Capability declarations that help agents evaluate safety before use

#### What the Ecosystem Adds

- The registry itself (a separate service that indexes `--schema` output)
- Cross-repo policy enforcement

#### Key Interactions

| Given | When | Then |
|---|---|---|
| Every tooli app produces consistent schema | Registry indexes all schemas | Developer or agent searches by capability or keyword |
| Registry returns a matching tool | Agent reads the schema | Agent evaluates safety and offers to use it |
| Two teams have similar tools | Agent needs to choose | Agent compares capabilities and descriptions |
| Wrong-repo mutative action attempted | Policy check | Block with actionable guidance |

#### Acceptance Criteria

1. Schema export is complete enough for registry indexing (name, description, commands, parameters, capabilities).
2. Schema format is stable across tooli versions.
3. Cross-team tool selection is deterministic and explainable.

---

### Scenario 8: Customer Support Workflows

**Sources:** `scenarios_cc.md` S11

#### Persona and Job to Be Done

**Leila**, a support engineer. *When a customer reports an issue, I want to diagnose the root cause and apply safe remediation without accidentally making things worse.*

#### Context

Support tickets follow patterns: account locked, quota exceeded, payment failed. Each has a diagnostic step and a remediation step. Remediation is often destructive (resetting state, clearing caches) and must be audited.

#### Journey

**Phase 1 — The Tools.**

```python
@app.command(annotations=ReadOnly, capabilities=["db:read"])
def diagnose(
    account_id: Annotated[str, Argument(help="Customer account ID")],
) -> dict:
    """Diagnose account issues and suggest remediation."""
    ...

@app.command(annotations=Destructive, capabilities=["db:write"])
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

The `reason` parameter is mandatory — the tool enforces audit trail requirements through its own parameter validation. The structured output includes before/after state for the audit record.

#### What Tooli Provides Here

- Mandatory parameters enforced via type system (no `reason` = validation error)
- `Destructive` annotation signals agents to require confirmation
- Structured output with before/after state for audit trails
- `ReadOnly` annotation on `diagnose` tells agents it's safe to run without asking

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
3. Error responses include enough information for agents to ask users for corrections.

---

### Scenario 9: The Global Skill Mesh

**Sources:** `scenarios_cc.md` S10, `scenarios_gm.md` S5

#### Persona and Job to Be Done

**Architect** building a production LangGraph workflow that needs to use tools originally built for Claude Code. *When I've built a tool that works in Claude Code, I want it to work everywhere — LangChain, OpenAI Agents, Google ADK — without rewriting it for each framework.*

#### Context

A startup has built their internal tooling on tooli and Claude Code. They're expanding to a multi-framework architecture. They don't want to maintain four copies of every tool.

#### Journey

**Phase 1 — Export.**

```bash
cloud-provisioner export --target langchain > langchain_tools.py
cloud-provisioner export --target openai > openai_tools.py
cloud-provisioner export --target adk > adk_agent.yaml
cloud-provisioner export --target python > typed_api.py
```

The LangChain export generates `@tool`-decorated functions that call the tooli app underneath. The OpenAI export generates `@function_tool` wrappers. The ADK export generates YAML agent config using MCP.

**Phase 2 — Universal Documentation.**

```bash
cloud-provisioner generate-agents-md > AGENTS.md
```

AGENTS.md follows the GitHub Copilot / OpenAI Codex convention, making the tool discoverable by any agent that reads repository documentation.

**Phase 3 — Caller Metadata Across Frameworks.** Each generated wrapper sets `TOOLI_CALLER` appropriately:

```python
# Generated LangChain wrapper
os.environ["TOOLI_CALLER"] = "langchain"
result = app.call("provision", region="us-east-1", size="medium")
```

This means Riku's telemetry (Scenario 6) shows *which framework* invoked each tool.

#### What Tooli Provides Here

- `export --target` command — generates framework-specific wrappers from one tool definition
- `generate-agents-md` — universal documentation format
- `TOOLI_CALLER` convention — consistent caller metadata across all frameworks
- `app.call()` Python API — in-process invocation for generated wrappers

#### What to Consider

This is tooli's most opinionated platform feature. It means tracking API changes from LLM providers. An alternative approach: tooli exports JSON Schema via `--schema`, and separate community tools generate framework-specific wrappers from that schema. Tooli ships export today, but the JSON Schema is the durable contract — if export falls behind a framework update, the schema remains the stable fallback.

#### Key Interactions

| Given | When | Then |
|---|---|---|
| Tooli app with multiple commands | Architect runs `export --target langchain` | Generated Python file has `@tool` wrappers with proper type annotations |
| Generated wrappers use `app.call()` | LangChain agent invokes a tool | In-process call with `TOOLI_CALLER=langchain` |
| AGENTS.md generated | GitHub Copilot reads the repo | Copilot discovers tools without framework-specific setup |
| Tool author updates a command | Re-export generated | Wrappers regenerate — all frameworks get the update |

#### Acceptance Criteria

1. Generated targets are syntactically valid and framework-appropriate.
2. Error behavior is predictable across targets.
3. Target generation supports whole-app and single-command output.
4. Caller metadata is consistent across all generated wrappers.

---

### Scenario 10: Resource-First Subagent Operations

**Sources:** `scenarios_cdx.md` S9

#### Persona and Job to Be Done

**Reliability subagent** operating under strict context-window limits. *When investigating system state, I want direct resource reads so I don't waste tokens parsing large command output.*

#### Context

Read-heavy diagnostic workflows often re-run commands unnecessarily. A subagent checking service health might invoke `health-check status --json` five times in a session, each time receiving the full output and burning context tokens.

#### Journey

**Phase 1 — Identifying High-Frequency Reads.** The SRE team notices agents repeatedly call the same commands:

```
health-check status api-gateway --json       (called 8x in one session)
loggrep errors /var/log/api/ --since 1h      (called 5x in one session)
deploy-pilot status checkout-service --json   (called 6x in one session)
```

**Phase 2 — Promoting to MCP Resources.** The team promotes high-frequency read paths:

```
incident://open                    → list of open incidents
health://status/{service}          → current health signals
loggrep://recent-errors            → last hour of errors, structured
deploy://status/{service}          → canary state, version, traffic split
```

Resources are bounded (max payload size) and schema-consistent (same structure as command output).

**Phase 3 — Resource-First Operating Pattern.** Agents adopt a hierarchy:

1. **Read resource first** — if URI exists and data is fresh.
2. **Execute command** — if resource is stale or write operation needed.
3. **Fall back** — if resource read fails, invoke underlying command.

> **Reliability Agent:** *(reads `health://status/checkout-service` — 200 tokens)*
> "Health is green. Error rate: 0.02%. No action needed."
>
> *(Without resources, this would have been: invoke `health-check status --json` → 2000-token response → parse → extract the 200 tokens actually needed)*

**Phase 4 — Staleness and Fallback.**

> **Reliability Agent:** "The `health://status/checkout-service` resource is 15 minutes old and we're in an active incident. I'll run the command directly for fresh data."

#### What Tooli Provides Here

- MCP resource auto-registration via `mcp serve`
- `skill://` resources for tool documentation
- Structured, schema-consistent output that resource layers can cache

#### What the Ecosystem Adds

- Resource freshness policies
- Caching infrastructure (FastMCP or similar)

#### Key Interactions

| Given | When | Then |
|---|---|---|
| Resource URI exists | Data is needed | Agent reads resource directly (low token cost) |
| Resource is stale | Active incident requires freshness | Agent executes underlying command |
| Resource read fails | Retryable error | Agent falls back to command with retry |
| Multiple resources needed | Agent investigates an incident | Agent reads resources in parallel — lower latency |

#### Acceptance Criteria

1. Resources are bounded and schema-consistent with command output.
2. Read-heavy sessions show lower command invocation counts.
3. Resource fallback paths are deterministic.

---

## Patterns Across All Scenarios

### 1. Structured Output Is the Universal Connector

The `{ok, result, meta}` envelope isn't decorative — it's the API contract that makes everything else possible. Agents parse it. CI pipelines parse it. Other tools parse it. When output is structured, composition is free. This is tooli's single most important feature.

### 2. Errors Are a First-Class Interface

Every scenario includes a failure path. In every case, the structured error with a `suggestion` field is what lets the agent recover without human intervention. The error envelope is as important as the success envelope.

### 3. Schema Is the Minimum Viable Discovery Mechanism

Agents don't need SKILL.md, AGENTS.md, or generated documentation to use tooli apps. They need the JSON Schema from `--schema`. The schema tells them every parameter, every type, every default. Documentation adds context (when to use this, what workflow it belongs to), but the schema is the minimum that makes agent invocation work.

### 4. Documentation Is a Human Concern (That Tooli Can Assist)

CLAUDE.md files, deployment runbooks, onboarding guides — these encode *judgment*, not just schema. Jordan wrote the deployment workflow by hand because he understands *why* schema-check comes before canary. Tooli can generate SKILL.md and CLAUDE.md as starting points, but the most valuable documentation is human-authored. The framework should make tools self-describing enough that human documentation can reference them concisely.

### 5. The Tool Lifecycle Is Real

Every scenario describes the same progression: pain → script → tooli command → agent invocation → team workflow → organizational resource. The lifecycle is real. Tooli provides value at every stage — the decorator and envelope at the core, documentation generators to accelerate sharing, MCP resources for efficiency, export for portability — but a tool can stop at any stage and still be useful.

### 6. Tools Are Framework-Agnostic by Default

Because tooli exports JSON Schema and produces a standard envelope, the tools in these scenarios already work with any agent that can call a CLI and parse JSON. No export needed for basic interop. Any framework that can invoke a subprocess and read stdout gets structured output. The `export` command adds convenience for deeper framework integration, but the universality comes from the protocol, not from generated wrappers.

### 7. The Agent Operates at Multiple Levels

- **Consumer:** Discovers and invokes tools (all scenarios)
- **Operator:** Follows documented workflows, making decisions at each step (Scenarios 2, 8)
- **Teacher:** Shows users how tools work by using them (Scenario 2 Phase 5)
- **Author:** Creates new tools from observed patterns (Scenario 4)
- **Gatekeeper:** Enforces safety rules and asks for confirmation (Scenarios 2, 6, 8)
- **Self-healer:** Retries with structured suggestions on environmental failures (Scenario 1 Phase 3)

### 8. The Human Stays in Control

In every scenario, the human decides which tools to install, what workflows to document, when to approve destructive actions, and what capabilities to allow. The agent amplifies human capability without replacing human judgment.

---

## The Tool Lifecycle

```
1. PAIN        Ad-hoc script       Only the developer benefits, knowledge is session-bound
                    |
2. COMMAND     tooli app            --json envelope, schema, type-safe — core value starts here
                    |
3. INVOCATION  MCP / CLI / API      Agent starts calling it in structured mode
                    |
4. REFINEMENT  Iteration            Usage data and failures drive improvements
                    |
5. SKILL       SKILL.md + CLAUDE.md Workflows, guardrails, team knowledge captured
                    |
6. RESOURCE    MCP resource URIs    Low-token direct retrieval, cached state
                    |
7. MESH        export + AGENTS.md   Cross-framework, cross-team, searchable
```

Each step is optional. A tool can stay personal forever. But when it's useful enough to share, the framework makes sharing frictionless — because the structured interface was there from the first `@app.command()`.

---

## What Isn't Here and Why

**Autonomous self-healing as a standalone scenario.** The reflection pattern (error → suggestion → auto-retry) is important but it's a property of all scenarios, not a separate one. It's demonstrated in Scenario 1 Phase 3 and referenced throughout. The structured error envelope with `suggestion.retry` makes this work everywhere.

**Multi-agent orchestration as a tooli feature.** Scenarios 2 and 7 describe orchestrator agents delegating to specialized subagents. This is a real pattern, but it's the agent platform's responsibility (Claude Code's subagent routing, LangGraph's graph execution, etc.). Tooli's contribution is that each tool produces structured output that any orchestration layer can consume.

**Enterprise governance and telemetry as standalone infrastructure.** Capability enforcement, invocation telemetry, and audit logging are demonstrated in Scenario 6. Tooli ships these features (STRICT mode, TOOLI_CALLER, capability declarations), but they are consumed by enterprise infrastructure — policy engines, audit systems, compliance tools — that lives outside tooli.

---

## Scenario Author Checklist

Before adding new scenarios:

1. Does the scenario have a named persona with a clear Job to Be Done?
2. Does it specify what tooli *the framework* provides vs. what the *ecosystem* adds?
3. Are failure paths explicitly dramatized with structured error responses?
4. Are acceptance criteria observable and testable?
5. Does it include concrete code, JSON output, or agent dialogue?
6. Does it show something the existing scenarios don't already cover?
7. **Core test:** Would the scenario still work if tooli had no SKILL.md generator, no MCP server, and no export? If yes, it's Tier 1. If no, it's Tier 2.

---

## Backlog of Scenario Candidates

1. Compliance evidence collection for audit season (SOC 2 artifact gathering)
2. Cost optimization agent for cloud spend anomalies
3. Data-quality repair flows with preview and rollback
4. Incident postmortem generation from timeline resources
5. Security response chain: detect → map → contain with mandatory approvals
6. Multi-tenant policy simulation before feature rollout

---

## References

Scenario structure informed by:
- [Atlassian - User Stories](https://www.atlassian.com/agile/project-management/user-stories)
- [Cucumber - Better Gherkin](https://cucumber.io/docs/bdd/better-gherkin/)
- [Cucumber - Example Mapping](https://cucumber.io/docs/bdd/example-mapping/)
- [Agile Alliance - INVEST](https://agilealliance.org/glossary/invest/)
- [Agile Alliance - Three Cs](https://agilealliance.org/glossary/three-cs/)
- [Agile Alliance - Given-When-Then](https://agilealliance.org/glossary/given-when-then/)
- [Jobs to Be Done Framework (Product School)](https://productschool.com/blog/product-fundamentals/jtbd-framework)
- [Journey Mapping 101 (Nielsen Norman Group)](https://www.nngroup.com/articles/journey-mapping-101/)
