# Tooli Scenarios: How Developer Tools Become Agent Skills

> From first function to team infrastructure — realistic scenarios for the tooli ecosystem.

---

## About This Document

This is the canonical scenarios document for the tooli framework. It describes how tooli-based CLI tools are built, discovered, composed, and governed by humans and AI agents working together.

**Sources consolidated:** `scenarios_cc.md`, `scenarios_gm.md`, `scenarios_cdx.md`. All original scenarios are accounted for — some are merged where they cover the same ground.

Scenarios are organized into two tiers based on what they demand from tooli itself:

- **Tier 1 (Core):** Requires only the decorator, structured output, JSON Schema, and structured errors. If you stripped tooli down to `@app.command()` with `--json` and `--schema`, these scenarios would still work.
- **Tier 2 (Platform):** Uses tooli's platform features — capabilities enforcement, behavioral annotations, MCP resources, multi-framework export, telemetry. Tooli ships all of these, but they layer on top of the core.

**Design principles:**

1. Every scenario starts with a real developer problem, not a feature.
2. Every scenario includes concrete code, structured output, and agent dialogue.
3. Every scenario identifies what it tests in tooli core vs. what it tests in the surrounding ecosystem.
4. Failure paths and guardrails are dramatized, not just mentioned.
5. Acceptance criteria are observable and testable.

---

## Source Coverage

| Source | Original Scenario | Status |
|---|---|---|
| `scenarios_cc.md` §1 | Solo Developer's Debugging Toolkit | **Scenario 1** (Tier 1) |
| `scenarios_cc.md` §2 | Platform Team's Internal Toolchain | **Scenario 2** (Tier 1, includes New Hire onboarding) |
| `scenarios_cc.md` §3 | Open-Source Ecosystem Effect | **Scenario 3** (Tier 1) |
| `scenarios_cc.md` §4 | Agent-Built Tool | **Scenario 4** (Tier 1) |
| `scenarios_cc.md` §5 | New Hire Onboarding | Folded into Scenario 2 Phase 5 |
| `scenarios_cc.md` §6 | Security Audit Workflow | **Scenario 6** (Tier 2) |
| `scenarios_cc.md` §7 | CI/CD Pipeline Integration | **Scenario 5** (Tier 1, includes versioned evolution) |
| `scenarios_cc.md` §8 | Cross-Team Marketplace | **Scenario 7** (Tier 2) |
| `scenarios_cc.md` §9 | Multi-Agent War Room | Folded into Scenario 2 Phase 6 |
| `scenarios_cc.md` §10 | Global Skill Mesh | **Scenario 9** (Tier 2) |
| `scenarios_cc.md` §11 | Customer Support Workflows | **Scenario 8** (Tier 2) |
| `scenarios_cc.md` §12 | Versioned Evolution | Folded into Scenario 5 Phase 3 |
| `scenarios_cdx.md` §9 | Resource-First Subagent Ops | **Scenario 10** (Tier 2) |
| `scenarios_gm.md` §1 | Lifecycle of a Skill | Merged into Scenario 1 |
| `scenarios_gm.md` §2 | Autonomous Self-Healing | Merged into Scenario 1 Phase 3 |
| `scenarios_gm.md` §3 | Multi-Agent Handoffs | Merged into Scenario 2 Phase 6 |
| `scenarios_gm.md` §4 | Agent as Tool Author | Merged into Scenario 4 |
| `scenarios_gm.md` §5 | Universal Skill Protocol | Merged into Scenario 9 |
| `scenarios_gm.md` §6 | Enterprise Governance | Merged into Scenario 6 |

---

## Personas

| Persona | Role | Relationship to Tools |
|---|---|---|
| **Maya** | Senior backend developer, on-call | Builds diagnostic tools to solve immediate operational pain |
| **Jordan** | Platform lead / SRE | Defines organizational workflows and rules in CLAUDE.md |
| **Alex** | Product engineer | Uses tools daily but didn't build them |
| **Priya** | New hire, first two weeks | Needs to get productive without memorizing CLI flags |
| **Sam** | Freelance developer | Installs tools from PyPI, rarely reads source code |
| **Dana** | Senior engineer, API lead | Works with Claude Code daily, notices repetitive analysis patterns |
| **Riku** | Security / compliance engineer | Enforces capability policies, reviews audit trails |
| **Elena** | CI maintainer | Needs stable, structured tool output for pipeline automation |
| **Leila** | Support engineer | Needs fast, safe, auditable customer remediation |
| **The Agent** | Claude Code | Discovers, invokes, composes, and authors tools |

---

## Shared Lifecycle

Every scenario follows the same progression. A tool can stop at any stage — not everything needs to become an org-wide resource.

```
1. PAIN        → A repeated task appears in real work
2. COMMAND     → A tooli command wraps it with typed inputs and structured output
3. INVOCATION  → An agent starts calling it via --json or MCP
4. REFINEMENT  → Failures and usage patterns drive improvements
5. SKILL       → Workflows are documented in CLAUDE.md or SKILL.md
6. RESOURCE    → High-frequency reads become MCP resources
7. MESH        → Export and AGENTS.md make the tool available across frameworks
```

The key transitions:
- **Pain → Command:** A human decides a task is worth wrapping in structure.
- **Command → Invocation:** The `{ok, result, error, meta}` envelope and JSON Schema make the tool machine-readable.
- **Invocation → Skill:** Documentation captures *when* and *why*, not just *what*.
- **Skill → Resource:** Frequently-read data becomes directly accessible without re-executing the command.

Each step is optional. A tool can stay personal forever. But when it's useful enough to share, the framework makes sharing frictionless — because the structured interface was there from the first `@app.command()`.

---

## Tier 1: Core Framework Scenarios

These scenarios require only tooli's irreducible core: the `@app.command()` decorator, the `{ok, result, error, meta}` envelope, JSON Schema export via `--schema`, and structured error responses with `suggestion` fields. No MCP server, no SKILL.md generation, no export commands, no capabilities enforcement.

---

### Scenario 1: Diagnostic Skill Lifecycle

**Sources:** `scenarios_cc.md` §1, `scenarios_gm.md` §1, §2

#### Persona
**Maya**, a backend developer at a mid-size SaaS company, on-call this week.

#### Job to Be Done
*When I'm paged for a production incident, I want to quickly identify the root cause so I can restore service and get back to sleep.*

#### Context
Maya has bash one-liners involving `grep`, `jq`, `awk`, and `sed` that she runs during incidents. She keeps forgetting the exact incantation for correlating request IDs across microservice logs. Every incident, she re-derives the pipeline from scratch.

#### Journey

**Phase 1 — The Scratch Script (Day 1).** Maya wraps her most-used one-liner into a tooli command:

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

**Phase 2 — Claude Code Discovers It (Week 2).** Maya adds loggrep to her MCP config. During a debugging session:

> **Maya:** "The checkout service is returning 502s. What's in the logs from the last hour?"
>
> **Claude Code:** *(invokes loggrep.errors, then loggrep.timeline)*
>
> "Found 47 errors in the last hour. The timeline shows a connection pool exhaustion starting at 14:32, triggered by retry storms from the payment gateway. Checkout's retry logic amplified 12 failing requests into 47 connection attempts, exhausting the pool. Want me to check the payment gateway logs?"

Maya didn't teach Claude Code the three-step triage process (errors → timeline → correlate). The agent inferred the workflow from structured output — each result contains fields (`request_id`, `trace_id`) that naturally lead to the next command.

**Phase 3 — Self-Healing on Environmental Errors.** A teammate provides a gzipped log file. The tool can't read it:

```json
{
  "ok": false,
  "error": {
    "code": "E3001",
    "category": "state",
    "message": "Cannot read GZipped input. Use --decompress flag for .gz files.",
    "suggestion": {
      "action": "add_flag",
      "flag": "--decompress",
      "retry": true
    }
  }
}
```

Claude Code reads the structured error, sees `"retry": true` with a concrete suggestion, and retries with the flag automatically. The developer never sees the failure. This is the **reflection pattern** — environmental errors with deterministic fixes are handled silently.

Not all errors should be auto-retried. The agent distinguishes:
- **Auto-retry:** `"retry": true` with concrete suggestion (add flag, change format)
- **Escalate:** No suggestion, or suggestion requires human judgment
- **Block:** Capability denial or policy violation — never auto-retry

**Phase 4 — Team Adoption (Month 2).** Maya's teammates install loggrep. The team lead adds it to the project's CLAUDE.md:

```markdown
## Incident Response
- Always start with `loggrep errors` before manually grepping logs
- Use `loggrep correlate` for cross-service issues — don't trace by hand
```

New on-call engineers get Maya's debugging patterns without a knowledge transfer session. The tool didn't change — the human-authored documentation layer made it discoverable and teachable.

#### Tooli Features Exercised

| Feature | How It's Exercised |
|---|---|
| `@app.command()` with type hints | CLI with `--json` output from a decorated function |
| `{ok, result, error, meta}` envelope | Agent parses results, chains commands, handles errors |
| Structured errors with `suggestion` | Agent self-corrects without human help |
| `suggestion.retry` field | Agent distinguishes retryable vs. non-retryable errors |
| JSON Schema via `--schema` | Agent knows every flag without reading source code |

**Ecosystem note:** SKILL.md generation, MCP server, and MCP resources are all available but not required. The workflow was captured in a human-authored CLAUDE.md. If the team wants `loggrep://recent-errors`, that's a resource layer backed by the same command.

#### Key Interactions

| Given | When | Then |
|---|---|---|
| loggrep is in MCP config | Maya asks about recent errors | Agent invokes `loggrep errors` with appropriate time filter |
| `errors` output contains `request_id` fields | Agent needs the error sequence | Agent invokes `loggrep timeline` using the worst error's `request_id` |
| Tool receives a gzipped file | Error includes `"retry": true` and `--decompress` suggestion | Agent retries silently with the flag |
| Tool returns auth error with `"retry": false` | Agent reads the error category | Agent does NOT retry — explains the restriction to the user |
| `loggrep errors` returns empty list | Maya asks about errors | Agent suggests broadening time window or lowering level threshold |
| Invalid `--since` format | Agent sends malformed date | Structured error with `field: "since"` and correct format example |

#### Acceptance Criteria

1. Commands return stable `{ok, result, error, meta}` envelope in `--json` mode.
2. Environmental errors with `"retry": true` are auto-retried; auth/policy errors are not.
3. Schema export accurately describes all parameters and return types.
4. Failed retries escalate with full context (original error + retry error).

---

### Scenario 2: The Platform Team's Deployment Toolchain

**Sources:** `scenarios_cc.md` §2, §5, §9; `scenarios_gm.md` §3

#### Persona
**Jordan** (platform lead) and **Alex** (product engineer) at a 200-person company.

**Priya** (new hire). *When I join the team, I want to be productive without memorizing every CLI flag and deployment step.*

#### Job to Be Done
*When deploying to production, I want confidence that nothing will break. When something goes wrong, I want deterministic recovery.*

#### Context
Five internal CLI tools exist: `deploy-pilot`, `config-vault`, `schema-check`, `feature-flags`, `health-check`. Engineers struggle to remember the correct order. Last month, someone promoted a canary without checking the migration validator.

#### Journey

**Phase 1 — The Individual Tools.** Each is a standalone tooli app:

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

**Phase 2 — The Human-Authored Orchestration Layer.** After the incident, Jordan writes a CLAUDE.md encoding the deployment workflow:

```markdown
## Deployment Workflow (MANDATORY ORDER)
1. `schema-check validate ./migrations --json`
2. `feature-flags check <flag> --json`
3. `config-vault diff <service> --env staging --env production --json`
4. `deploy-pilot canary <service> <version> --json`
5. `health-check watch <service> --duration 5m --json`
6. `deploy-pilot promote <service> --json` — ONLY if health-check passes

## Rules
- NEVER run `deploy-pilot promote` without `health-check watch` passing first
- NEVER skip `schema-check validate` for PRs touching `migrations/`
- Ask for human confirmation before `promote` and `rollback`
```

This is not generated by tooli. It's tribal knowledge that Jordan wrote by hand. Tooli's contribution is that every tool produces `{ok, result, meta}` envelopes, so the agent can read each step's output and decide whether to proceed.

**Phase 3 — What Engineers Experience.**

> **Alex:** "Deploy user-service v2.4.1 to production"
>
> **Claude Code:** *(reads CLAUDE.md, follows mandatory workflow)*
>
> "I see pending migrations. Starting with schema validation."
> *(invokes `schema-check validate ./migrations --json`)*
> "Migration is safe — additive column `users.preferred_locale`, no locks, backward compatible."
>
> *(invokes each subsequent step, reading structured output at each stage)*
>
> "Canary looks healthy — error rate 0.02% vs 0.03% baseline. P99 latency: 142ms (baseline: 148ms). Ready to promote. Should I proceed?"

Alex didn't memorize the workflow. The CLAUDE.md encoded it, and the tools' structured output gave the agent the information to make decisions at each step.

**Phase 4 — The Guardrail Moment.**

> **Junior:** "Just promote user-service, the canary's been running for a while"
>
> **Claude Code:** "I need to verify canary health before promoting — that's a mandatory step."
> *(invokes health-check, finds 2.3% error rate vs 0.03% baseline)*
> "The canary does NOT look healthy. The errors are `ConnectionRefused` from the cache layer. Should I rollback?"

The agent ran the check anyway and refused to promote when it failed.

**Phase 5 — The New Hire Experience (Month 2).** Priya joins the team. On day 3:

> **Priya:** "I've been assigned JIRA-4521 — a null pointer exception in the order service. Where do I start?"
>
> **Claude Code:** *(reads CLAUDE.md, sees available tools)*
> "Let me use the team's log analysis tool."
> *(invokes `loggrep errors /var/log/order-service/ --since 2026-02-18 --level error --json`)*
> "Found the NPE in `OrderProcessor.java:142` — `customer.address` is null for international orders."

Priya didn't need to know that `loggrep` exists, what flags to pass, or where logs are stored. She learns the CLI by watching the agent use it — the agent's invocations serve as live examples. By week 2, she's running commands directly:

```bash
loggrep errors /var/log/order-service/ --since "2h ago" --json | jq '.result[] | .message'
```

When she requests something unsafe:

> **Priya:** "Can I restart the production database?"
>
> **Claude Code:** "I can't do that — the CLAUDE.md says 'NEVER restart production databases without SRE approval.' I'd recommend asking in #sre, or I can check if `health-check` shows the connection pool issue."

**Phase 6 — Multi-Agent Coordination (Optional).** For complex multi-domain releases, the same tools support subagent delegation. An orchestrator delegates to specialized subagents — each invokes tools from its domain and reports back. The structured envelope makes routing deterministic. This coordination is an agent platform capability; tooli's contribution is the structured output that makes it reliable.

#### Tooli Features Exercised

| Feature | How It's Exercised |
|---|---|
| Structured output envelope | Agent reads each step's result to decide proceed/halt/rollback |
| Consistent `--json` across tools | Five independent tools compose through shared format |
| Error semantics | `"ok": false` triggers rollback workflows |
| JSON Schema | Agent discovers tool capabilities without human instruction; Priya's invocations double as examples |
| Structured errors with `suggestion.fix` | Priya's manual mistakes get helpful corrections |

**Ecosystem note:** The CLAUDE.md is human-authored — it encodes judgment, not just schema. Multi-agent coordination is the agent platform's job. MCP resources (`deploy://status/{service}`, `health://signals/{service}`) can be added for frequently-read state.

#### Key Interactions

| Given | When | Then |
|---|---|---|
| PR touches `migrations/` | Engineer requests deployment | Agent starts with `schema-check validate` per CLAUDE.md |
| `schema-check` returns `"safe": false` | Agent reads the result | Agent halts and explains the risk |
| `health-check watch` shows elevated error rate | Agent is about to promote | Agent refuses, shows diagnostics, suggests rollback |
| CLAUDE.md says "confirm before promote" | Health checks pass | Agent asks for explicit approval |
| `deploy-pilot promote` returns `"ok": false` | Promotion fails | Agent immediately invokes rollback per documented workflow |
| No migrations in PR | Engineer deploys | Agent skips `schema-check` — reads the condition, not just the rule |
| Priya has never used these tools | She asks about a production error | Agent uses loggrep on her behalf |
| Prohibited operation requested | Priya asks to restart prod DB | Agent cites guardrail, offers safe alternatives |

#### Acceptance Criteria

1. Promotion is blocked if schema risk is unresolved.
2. Healthy canary is required before promotion.
3. Rollback path is deterministic and auditable.
4. Tools work identically whether invoked by a human, an agent, or a CI pipeline.

---

### Scenario 3: Independent Tools That Compose

**Sources:** `scenarios_cc.md` §3

#### Persona
**Sam**, a freelance developer across multiple projects.

#### Job to Be Done
*When preparing a repository for release, I want multiple utility tools to work together reliably without custom glue code.*

#### Context
Sam has a pre-release checklist: lint docs, optimize images, check licenses, generate changelog. Each step uses a different tool. Sam frequently forgets a step.

#### Journey

**Phase 1 — Installing the Pieces.** Four tooli apps from PyPI, each by a different author:

```bash
pip install tooli-mdlint        # Markdown linter
pip install tooli-imgopt         # Image optimization
pip install tooli-license-scan   # License auditor
pip install tooli-changelog      # Changelog generator
```

None of the authors know each other. But because they all built on tooli, they share the `{ok, result, meta}` envelope, JSON Schema, structured errors, and `--dry-run` convention.

**Phase 2 — Emergent Composition.**

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
> *(fixes issues, then invokes `imgopt scan assets/ --dry-run --json`)*
> "6 images can be optimized, saving 2.3MB. Want me to apply?"
>
> *(after approval, invokes `imgopt optimize assets/ --json`)*
>
> *(invokes `changelog generate --from v2.0.0 --json`)*
>
> "Summary: Docs fixed, images optimized, changelog drafted. **Blocking:** 2 GPL dependencies need resolution."

**Phase 3 — Graceful Degradation.** Sam starts a new project without `tooli-imgopt`:

> **Claude Code:** "I have license-scan, mdlint, and changelog available, but not imgopt. I'll run the steps I can."

The agent doesn't fail. It reports the gap and continues.

#### Tooli Features Exercised

| Feature | How It's Exercised |
|---|---|
| Shared `{ok, result, meta}` envelope | Four unknown tools compose through format alone |
| Consistent `--json` mode | Every tool is machine-readable without per-tool parsers |
| Structured errors | Agent handles missing tools and failures gracefully |
| `--dry-run` convention | Agent previews before mutating |

#### Key Interactions

| Given | When | Then |
|---|---|---|
| `license-scan` finds conflicts | Agent is preparing a release | Agent surfaces blockers first, continues with non-blocking checks |
| `mdlint` returns fixable issues | Agent sees `"auto_fixable": true` | Agent fixes them directly without asking |
| `imgopt scan` in `--dry-run` mode | Agent reads output | Agent asks for confirmation before applying |
| Referenced tool not installed | Agent encounters the gap | Agent reports missing tool and continues with available ones |

#### Acceptance Criteria

1. Cross-tool composition uses structured outputs, not text scraping.
2. Missing tools are reported with installation guidance, not crashes.
3. Workflow remains robust under partial tool availability.

---

### Scenario 4: The Agent as Tool Author

**Sources:** `scenarios_cc.md` §4, `scenarios_gm.md` §4

#### Persona
**Dana**, a senior engineer building a customer-facing API.

#### Job to Be Done
*When I notice repeated manual analysis, I want it converted into a durable tool so my team's throughput compounds.*

#### Context
Dana has asked Claude Code to do the same API performance analysis four times: "Check which endpoints have response times over 500ms and cross-reference with missing caching headers." Each time, a slightly different script. Inconsistent auth handling, different output formats, no error handling for edge cases.

#### Journey

**Phase 1 — The Repetition Pattern (Weeks 1-4).** Four sessions, four similar scripts, each thrown away.

**Phase 2 — The Agent Proposes (Week 5).**

> **Dana:** "Check our API endpoints again, same analysis as before"
>
> **Claude Code:** "I've done this analysis 4 times and each time the script is slightly different. Want me to create a reusable tooli app?"

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

What the agent learned from four sessions: auth tokens are needed (session 2 failed), ETag and Last-Modified matter alongside Cache-Control (session 3), the combined analysis is the most common request (sessions 3 and 4), the threshold should be configurable (session 1 used 500ms, session 4 used 300ms).

**Phase 4 — Reuse Across the Team.** Dana's colleague Carlos works on a different service:

> **Carlos:** "I think our payment API has some slow endpoints, can you check?"
>
> **Claude Code:** *(sees api-audit in MCP, reads schema)* "I have the `api-audit` tool available. Want me to run a combined analysis?"

Carlos didn't know the tool existed. The agent discovered it from the schema and offered it.

#### Tooli Features Exercised

| Feature | How It's Exercised |
|---|---|
| Simple decorator API | Agent can scaffold a valid tool using only `@app.command()` and type hints |
| Type-hint-to-schema pipeline | Agent-authored tool is immediately self-describing |
| `{ok, result, error, meta}` envelope | Agent-authored output is automatically parseable by other agents |

#### Key Interactions

| Given | When | Then |
|---|---|---|
| Agent has done same analysis 4 times | Developer asks a 5th time | Agent proposes creating a reusable tool |
| Developer approves | Agent generates the tool | Tool incorporates auth, headers, configurable threshold |
| Tool registered in MCP | Different engineer asks about API performance | Agent discovers and uses it |
| `slow-endpoints` fails without auth | Auth token not provided | Structured error with `field: "auth_token"` prompts agent to ask user |

#### Acceptance Criteria

1. An agent can scaffold a valid tooli app using only the decorator API and type hints.
2. Agent-authored tools produce the same structured output as human-authored tools.
3. The tool is immediately discoverable by other agents via schema.

---

### Scenario 5: CI/CD as a First-Class Consumer

**Sources:** `scenarios_cc.md` §7, §12

#### Persona
**Elena**, CI maintainer. **Tool Maintainer** evolving a command's interface.

#### Job to Be Done
*When PRs are opened, I want structured checks and actionable failures so CI and agents can diagnose without regex parsing.*

*When I need to make breaking changes to a tool, I want a safe migration path so existing automations don't fail.*

#### Context
CI linters output unstructured text parsed with fragile regex. The team wants stable, structured output. Additionally, the `data-export` tool needs to rename `--format` to `--output-format` without breaking dozens of existing agent workflows.

#### Journey

**Phase 1 — Structured CI Steps.**

```yaml
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

The result-posting script is trivial because every tool uses the same envelope:

```python
import json, sys
for results_file in sys.argv[1:]:
    data = json.load(open(results_file))
    if not data["ok"]:
        print(f"::error::{data['error']['message']}")
        if data["error"].get("suggestion"):
            print(f"::notice::Fix: {data['error']['suggestion']['fix']}")
```

No per-tool parsing. No regex.

**Phase 2 — Agent-Aware CI Feedback.**

> **Developer:** "CI failed on my PR, what's wrong?"
>
> **Claude Code:** *(reads CI output, recognizes envelope format)*
> "The `license-scan` step failed: `chart-renderer` v3.0 changed from MIT to BSL-1.1. The tool suggests pinning to v2.9. Want me to do that?"

**Phase 3 — Versioned Deprecation.** The `data-export` maintainer renames a flag with a migration window:

```python
@app.command(
    deprecated="Use --output-format instead of --format",
    deprecated_version="2.0.0",
)
def run(
    source: str,
    format: Annotated[str, Option(help="[DEPRECATED] Use --output-format")] = "csv",
    output_format: Annotated[str | None, Option(help="Output format: csv|parquet|json")] = None,
) -> dict:
    actual_format = output_format or format
    ...
```

Agents reading the schema see the deprecation and auto-migrate. Old agents still work — the deprecated flag functions but emits a warning. CI detects the deprecation as a warning, not a failure.

When the old flag is removed, the tool returns a structured migration error:

```json
{
  "ok": false,
  "error": {
    "code": "E1001",
    "message": "Parameter '--format' was removed in v3.0.0. Use '--output-format' instead.",
    "suggestion": {
      "action": "fix_argument_or_option",
      "fix": "Replace --format with --output-format",
      "example": "data-export run source.db --output-format csv"
    }
  }
}
```

**Phase 4 — Schema Drift Detection.** CI validates that tool schemas haven't changed in breaking ways:

**Given** a PR changes a command's parameter signature,
**When** CI runs `mytool --schema` and compares to committed baseline,
**Then** schema drift is detected before merge — preventing silent breaks in agent workflows.

#### Tooli Features Exercised

| Feature | How It's Exercised |
|---|---|
| `{ok, result, error, meta}` envelope | Stable CI contract — one parser for all tools |
| Structured errors with `suggestion` | CI posts fix guidance as GitHub annotations |
| Deprecation metadata in schema | Agents auto-migrate, CI warns during migration window |
| Structured migration errors | Removed flags produce helpful errors, not cryptic failures |
| `--schema` export | CI compares schemas across versions to detect drift |

#### Key Interactions

| Given | When | Then |
|---|---|---|
| CI runs tools with `--json` | A step fails | CI posts structured error, not wall of text |
| Tool provides `suggestion.fix` | CI formats result | Suggestion appears as GitHub annotation |
| Command has deprecation metadata | Agent reads schema | Agent uses the new flag automatically |
| Old agent uses deprecated flag | Command still supports it | Warning in envelope, command still works |
| Deprecated flag removed | Old invocation uses `--format` | Structured error with exact replacement |
| PR changes command signature | CI compares to baseline | Schema drift flagged before merge |

#### Acceptance Criteria

1. CI never depends on text scraping for tooli outputs.
2. Deprecated flags work with warnings during migration window.
3. Removal produces structured migration errors, not cryptic failures.
4. Schema drift is detectable via `--schema` comparison.

---

## Tier 2: Platform Feature Scenarios

These scenarios use tooli's platform features — capabilities enforcement, behavioral annotations (`Destructive`, `ReadOnly`), MCP resources, multi-framework export, telemetry, and documentation generation. Tooli ships all of these, but they layer on top of the core. A tool that only uses the core (Tier 1) works fine. A tool that uses these features gets additional safety, discoverability, and operational power.

---

### Scenario 6: Capability Enforcement and Security Audit

**Sources:** `scenarios_cc.md` §6, `scenarios_gm.md` §6

#### Persona
**Riku**, a security engineer at a fintech company.

#### Job to Be Done
*When autonomous tools run in our environment, I want to control what they can access and audit what they did.*

#### Context
Regulatory requirements mandate that tools only access what they explicitly declare, and that access is logged.

#### Journey

**Phase 1 — Capability Declarations.**

```python
@app.command(capabilities=["fs:read", "net:read"])
def scan_logs(path: str) -> list[dict]:
    """Scan logs for credential leaks."""
    ...
```

The schema export includes `capabilities: ["fs:read", "net:read"]`. This is the **declare-then-enforce** pattern: the tool declares what it needs, the environment declares what it allows.

**Phase 2 — Capability Lockdown.** Riku sets a company-wide policy:

```bash
export TOOLI_ALLOWED_CAPABILITIES="fs:read,net:read,db:read"
```

A developer installs a tool that writes files:

```python
@app.command(capabilities=["fs:read", "fs:write"])
def analyze(path: str) -> dict:
    """Analyze code and write report to disk."""
    ...
```

Invocation is blocked *before the function body runs*:

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

The agent handles it gracefully:

> **Claude Code:** "The `code-analyzer` tool needs `fs:write` permission, but your environment only allows read operations. You'll need to request approval from your security team, or check if the tool has a read-only mode."

**Phase 3 — Dry-Run Preview.** For tools that support it, agents preview destructive operations:

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
> "142 files (847MB) would be deleted. Shall I proceed?"

**Phase 4 — Audit Trail.** Every invocation includes structured telemetry:

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

Riku can reconstruct exactly what happened from structured data, not log scraping.

#### Tooli Features Exercised

| Feature | How It's Exercised |
|---|---|
| `capabilities` declarations | Per-command capability requirements in schema |
| Capability enforcement (STRICT mode) | Invocation blocked before function body runs |
| Structured auth errors | Machine-actionable remediation guidance |
| `Destructive` annotation + `@dry_run_support` | Preview destructive operations without side effects |
| Caller metadata (`TOOLI_CALLER`) | Telemetry distinguishes human vs. agent vs. CI |

**Boundary note:** The enforcement mechanism (checking capabilities against an allowlist) can live in tooli itself or in an external policy layer. Tooli ships STRICT mode, but the minimum contribution is making capability declarations available in the schema. The declare-then-enforce pattern works either way.

#### Key Interactions

| Given | When | Then |
|---|---|---|
| Strict mode with limited allowlist | Tool requests `fs:write` | Blocked with structured error explaining the gap |
| Agent receives capability denial | Agent is mid-workflow | Agent explains the block, suggests contacting security |
| Telemetry enabled | Any tool invoked | Record includes caller, capabilities, outcome |
| Dry-run on destructive command | Command executes | Plan returned, no side effects |
| Security team approves capability | Env var updated | Tool works on next invocation — no code changes |

#### Acceptance Criteria

1. Policy enforcement occurs before mutative function body execution.
2. Blocked actions return machine-actionable remediation.
3. Security reporting can reconstruct allowed and denied attempts.
4. Dry-run produces complete preview with no side effects.

---

### Scenario 7: Cross-Team Tool Discovery

**Sources:** `scenarios_cc.md` §8

#### Persona
**Staff engineer** coordinating multiple teams. **DevEx team** maintains a shared registry.

#### Job to Be Done
*When a capability exists on another team, I want to find and use their tool instead of rebuilding it.*

#### Context
Fifteen teams, each with 2-3 tooli apps. The data team has `data-lint`. The infra team has `tf-check`. Nobody knows what other teams have built.

#### Journey

**Phase 1 — The Discovery Problem.**

> **Developer:** "I need to validate our API's CSV export"
>
> **Claude Code:** "I don't have a CSV tool in this project. Let me check the registry."
> *(invokes `tool-registry search "csv validate" --json`)*
> "Found `data-lint` from Data Engineering with a `validate-csv` command. It's read-only and safe. Want me to add it?"

**Phase 2 — The Registry Itself Is a Tooli App.**

```python
app = Tooli(name="tool-registry", version="1.0.0")

@app.command(annotations=ReadOnly, capabilities=["net:read"])
def search(
    query: Annotated[str, Argument(help="Search query")],
    team: Annotated[str | None, Option(help="Filter by team")] = None,
) -> list[dict]:
    """Search the internal tool registry."""
    ...
```

The registry indexes every tooli app's `--schema` output, making capabilities searchable across the org.

**Phase 3 — Cross-Repo Boundaries.**

> **Claude Code:** "The `infra-provision` command needs `net:write` in the `payments-service` repo, but I'm operating in `api-gateway`. Cross-repo mutations are blocked by policy. I can prepare a summary for the Payments team."

#### Tooli Features Exercised

| Feature | How It's Exercised |
|---|---|
| JSON Schema via `--schema` | Registry indexes tool metadata from schema output |
| Consistent schema format | Tools from different teams are uniformly searchable |
| `capabilities` in schema | Agent evaluates safety before recommending a tool |
| `ReadOnly` annotation | Agent knows the registry search is safe to run unprompted |

**Boundary note:** The registry is a separate service, not a tooli feature. Tooli's contribution is that every tool produces consistent, complete schema output that a registry can index.

#### Key Interactions

| Given | When | Then |
|---|---|---|
| Developer describes a need | No matching tool in current config | Agent searches registry |
| Registry returns a match | Agent reads capabilities | Agent evaluates safety and offers to install |
| Registry returns multiple matches | Agent must choose | Agent compares capabilities and team ownership |
| Tool installed mid-session | Original request pending | Agent uses newly installed tool to complete the task |
| Wrong-repo mutative action attempted | Policy check | Block with actionable guidance |

#### Acceptance Criteria

1. Schema export is complete enough for registry indexing (name, description, commands, parameters, capabilities).
2. Schema format is stable across tooli versions.
3. Cross-team tool selection is deterministic from metadata.

---

### Scenario 8: Customer Support Workflows

**Sources:** `scenarios_cc.md` §11

#### Persona
**Leila**, a support engineer resolving customer issues.

#### Job to Be Done
*When a customer reports an issue, I want to diagnose and safely remediate so I resolve tickets quickly without making things worse.*

#### Context
Support tickets follow patterns: account locked, quota exceeded, payment failed. Each has a diagnostic and a remediation step. Remediation is often destructive and must be audited.

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
    """Reset account quota. Requires reason for audit trail."""
    ...
```

**Phase 2 — Agent-Guided Triage.**

> **Leila:** "Customer acme-corp says they can't upload files"
>
> **Claude Code:** *(invokes `acct-tools diagnose acme-corp --json`)*
> "Root cause: storage quota exceeded. 847MB in orphaned temp files from a failed bulk import."
>
> "I can reset the quota, but it's a destructive action that requires a reason for audit. Should I proceed?"
>
> **Leila:** "Yes, reason is orphaned temp files from bulk import"
>
> **Claude Code:** *(invokes `acct-tools quota-reset acme-corp --reason "orphaned temp files" --json`)*
> "Done. 847MB freed. New usage: 91.5%."

The `reason` parameter is mandatory — the tool enforces audit trail requirements through its type system. The structured output includes before/after state for the audit record.

**Phase 3 — The Runbook Becomes a Skill.**

```markdown
## Support: Storage Quota Issues
1. `acct-tools diagnose <id>` — Identify root cause
2. If orphaned files: `quota-reset <id> --reason <reason>` (requires confirmation)
3. If legitimate usage: suggest plan upgrade

### Rules
- ALWAYS diagnose before any remediation
- ALWAYS provide a reason for quota-reset (audit requirement)
- NEVER reset quota without understanding root cause
```

#### Tooli Features Exercised

| Feature | How It's Exercised |
|---|---|
| Mandatory parameters via type system | `reason` is required — no reason means validation error |
| `ReadOnly` / `Destructive` annotations | Agent knows `diagnose` is safe; `quota-reset` requires confirmation |
| Structured output with before/after state | Audit trail built from command output |
| `capabilities` declarations | `db:write` on destructive commands enables governance |

#### Key Interactions

| Given | When | Then |
|---|---|---|
| Customer reports upload failure | Leila describes symptom | Agent runs `diagnose`, identifies root cause |
| `quota-reset` requires `reason` | Agent proposes remediation | Agent explains it requires a reason, asks for one |
| Reset completed | Agent confirms | Result includes before/after state |
| Diagnosis shows legitimate usage | Agent reads result | Agent suggests plan upgrade instead of reset |
| Unknown account ID | Agent runs `diagnose` | Structured error tells agent the expected format |

#### Acceptance Criteria

1. Diagnosis always precedes remediation.
2. Destructive actions require explicit confirmation and audit reason.
3. Audit trail records actor, reason, timestamp, before/after state.

---

### Scenario 9: The Global Skill Mesh

**Sources:** `scenarios_cc.md` §10, `scenarios_gm.md` §5

#### Persona
**Architect** building a production LangGraph workflow that needs tools originally built for Claude Code.

#### Job to Be Done
*When I've built a tool that works in Claude Code, I want it to work everywhere — LangChain, OpenAI Agents, Google ADK — without rewriting it for each framework.*

#### Context
A startup built their internal tooling on tooli and Claude Code. They're expanding to a multi-framework architecture and don't want to maintain four copies of every tool.

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

This means Riku's telemetry (Scenario 6) shows *which framework* invoked each tool — across the entire mesh.

#### Tooli Features Exercised

| Feature | How It's Exercised |
|---|---|
| `export --target` | Generates framework-specific wrappers from one tool definition |
| `generate-agents-md` | Universal documentation format for multi-framework discovery |
| `TOOLI_CALLER` convention | Consistent caller metadata across all frameworks |
| `app.call()` Python API | In-process invocation for generated wrappers |

**Important consideration:** This is tooli's most opinionated platform feature. It means tracking API changes from LLM providers. The JSON Schema via `--schema` is the durable contract — if a specific export target falls behind a framework update, the schema remains the stable fallback. A separate `tooli-export` package could also fill this role, reading `--schema` output independently of the framework.

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

**Sources:** `scenarios_cdx.md` §9

#### Persona
**Reliability subagent** operating under strict context-window limits.

#### Job to Be Done
*When investigating system state, I want direct resource reads so I don't waste tokens parsing large command output.*

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
> *(Without resources: invoke `health-check status --json` → 2000-token response → parse → extract the 200 tokens actually needed)*

**Phase 4 — Staleness and Fallback.**

> **Reliability Agent:** "The `health://status/checkout-service` resource is 15 minutes old and we're in an active incident. I'll run the command directly for fresh data."

#### Tooli Features Exercised

| Feature | How It's Exercised |
|---|---|
| MCP resource auto-registration | `mcp serve` exposes commands as resources |
| `skill://` resources | Tool documentation available via MCP read |
| Structured, schema-consistent output | Resource layers cache the same structure the command produces |

**Boundary note:** Resource freshness policies and caching infrastructure (FastMCP or similar) are ecosystem concerns. Tooli's contribution is producing structured, cacheable command output that resource layers can wrap. Documentation recipes showing how to wrap tooli commands as MCP resources would make this pattern more accessible.

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

The `{ok, result, meta}` envelope isn't decorative — it's the API contract that makes everything else possible. Agents parse it. CI parses it. Other tools parse it. When output is structured, composition is free. This is tooli's single most important feature.

### 2. Errors Are a First-Class Interface

Every scenario includes a failure path. Structured errors with `suggestion` and `retry` fields are what let agents self-correct (Scenario 1), enforce guardrails (Scenario 2), guide migrations (Scenario 5), and explain security blocks (Scenario 6). The error envelope is as important as the success envelope.

### 3. Schema Is the Minimum Viable Discovery

Agents don't need generated documentation to use tooli apps. They need JSON Schema from `--schema`. The schema tells them every parameter, type, and default. Documentation adds context (*when* and *why*), but the schema is the minimum viable discovery mechanism that makes everything from onboarding (Scenario 2) to cross-team discovery (Scenario 7) work.

### 4. Workflow Documentation Is a Human Concern

CLAUDE.md files, deployment runbooks, support playbooks — these are written by humans who understand the *why*, not just the *what*. Jordan's deployment workflow (Scenario 2), Sam's release checklist (Scenario 3), and Leila's support runbook (Scenario 8) all encode judgment that can't be generated from a schema. Tooli can generate SKILL.md and CLAUDE.md as starting points, but the most valuable documentation is human-authored.

### 5. The Tool Lifecycle Is Real but Doesn't Require Framework Support at Every Stage

Every scenario describes the same progression: pain → script → tooli command → agent invocation → team workflow → resource → mesh. This lifecycle is real. Tooli provides value at every stage — decorator and envelope at the core, doc generators to accelerate sharing, MCP resources for efficiency, export for portability — but a tool can stop at any stage and still be useful. The framework enables the lifecycle without managing it.

### 6. Tools Are Framework-Agnostic by Default

Because tooli exports JSON Schema and produces a standard envelope, these tools already work with any agent that can call a CLI and parse JSON. No export needed for basic interop. The `export` command adds convenience for deeper framework integration, but the universality comes from the protocol's simplicity, not from generated wrappers.

### 7. Composition Is Emergent, Not Designed

Sam's open-source tools (Scenario 3) were built by strangers. The deployment tools (Scenario 2) were built independently and connected through CLAUDE.md. The agent figures out how to combine tools from their metadata and documented workflows. No orchestration framework required.

### 8. The Agent Operates at Multiple Levels

- **Consumer:** Discovers and invokes tools (all scenarios)
- **Operator:** Follows documented workflows, making decisions at each step (Scenarios 2, 8)
- **Teacher:** Shows users how tools work by using them (Scenario 2 Phase 5)
- **Author:** Creates new tools from observed patterns (Scenario 4)
- **Gatekeeper:** Enforces safety rules before irreversible actions (Scenarios 2, 6, 8)
- **Self-healer:** Retries with structured suggestions on environmental failures (Scenario 1)

### 9. The Human Stays in Control

In every scenario, the human decides which tools to install, what workflows to document, when to approve destructive actions, and what capabilities to allow. The agent amplifies human capability without replacing human judgment.

---

## What Isn't Here and Why

**Autonomous self-healing as a standalone scenario.** The reflection pattern (error → suggestion → auto-retry) is important but it's a property of all scenarios, not a separate one. It's demonstrated in Scenario 1 Phase 3 and referenced throughout. The structured error envelope with `suggestion.retry` makes this work everywhere.

**Multi-agent subagent orchestration as a tooli feature.** Scenarios 2 and 7 describe orchestrator agents delegating to specialized subagents. This is a real pattern, but it's the agent platform's responsibility. Tooli's contribution is that each tool produces structured output any orchestration layer can consume. Tooli does not need a Python API for agent-to-agent calls — though `app.call()` is available for in-process invocation where useful.

**Enterprise governance as standalone infrastructure.** Capability enforcement, invocation telemetry, and audit logging are demonstrated in Scenario 6. Tooli ships these features (STRICT mode, TOOLI_CALLER, capability declarations), but they are consumed by enterprise infrastructure — policy engines, audit systems, compliance tools — that lives outside tooli.

---

## Scenario Author Checklist

Before adding new scenarios:

1. Does the scenario have a named persona with a clear Job to Be Done?
2. Is the journey multi-phase, showing evolution over time?
3. Is at least one failure path explicitly dramatized?
4. Does it identify what it tests in tooli core vs. the surrounding ecosystem?
5. Are acceptance criteria observable and testable?
6. Does it include concrete code, JSON output, or agent dialogue?
7. Does it introduce something the existing scenarios don't already cover?
8. **Core test:** Would the scenario still work if tooli had no SKILL.md generator, no MCP server, and no export? If yes, it's Tier 1. If no, it's Tier 2.

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
