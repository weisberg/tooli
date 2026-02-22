# Tooli Scenarios: How Developer Tools Become Agent Skills

> From first function to team infrastructure — realistic scenarios for the tooli ecosystem.

---

## About This Document

This is the canonical scenarios document for the tooli framework. It describes how tooli-based CLI tools are built, discovered, composed, and governed by humans and AI agents working together.

**Sources consolidated:** `scenarios_cc.md`, `scenarios_gm.md`, `scenarios_cdx.md`, and `scenarios_combined.md`. All original scenarios are accounted for — some are merged where they covered the same ground, and a few are deferred where they tested ecosystem capabilities beyond tooli's framework responsibilities.

**Design principles for this document:**

1. Every scenario starts with a real developer problem, not a feature.
2. Every scenario includes concrete code, structured output, and agent dialogue.
3. Every scenario identifies what it tests *in tooli core* vs. what it tests in the surrounding ecosystem.
4. Failure paths and guardrails are dramatized, not just mentioned.
5. Acceptance criteria are observable and testable.

---

## Source Coverage

| Source | Original Scenario | Status |
|---|---|---|
| `scenarios_cc.md` §1 | Solo Developer's Debugging Toolkit | **Scenario 1** |
| `scenarios_cc.md` §2 | Platform Team's Internal Toolchain | **Scenario 2** |
| `scenarios_cc.md` §3 | Open-Source Ecosystem Effect | **Scenario 3** |
| `scenarios_cc.md` §4 | Agent-Built Tool | **Scenario 5** |
| `scenarios_cc.md` §5 | New Hire Onboarding | **Scenario 6** |
| `scenarios_cc.md` §6 | Security Audit Workflow | **Scenario 4** |
| `scenarios_cc.md` §7 | CI/CD Pipeline Integration | **Scenario 7** (includes versioned evolution) |
| `scenarios_cc.md` §8 | Cross-Team Marketplace | **Scenario 8** |
| `scenarios_cc.md` §9 | Multi-Agent War Room | Folded into Scenario 2 |
| `scenarios_cc.md` §10 | Global Skill Mesh | Deferred (see §Deferred Scenarios) |
| `scenarios_cc.md` §11 | Customer Support Workflows | **Scenario 9** |
| `scenarios_cc.md` §12 | Versioned Evolution | Folded into Scenario 7 |
| `scenarios_gm.md` §1 | Lifecycle of a Skill | Merged into Scenario 1 |
| `scenarios_gm.md` §2 | Autonomous Self-Healing | Folded into Scenario 1 |
| `scenarios_gm.md` §3 | Multi-Agent Handoffs | Folded into Scenario 2 |
| `scenarios_gm.md` §4 | Agent as Tool Author | Merged into Scenario 5 |
| `scenarios_gm.md` §5 | Universal Skill Protocol | Deferred |
| `scenarios_gm.md` §6 | Enterprise Governance | Merged into Scenario 4 |
| `scenarios_cdx.md` §9 | Resource-First Subagent Ops | Pattern note in Scenario 2 |

---

## Personas

| Persona | Role | Relationship to Tools |
|---|---|---|
| **Maya** | Senior backend developer, on-call | Builds diagnostic tools to solve immediate operational pain |
| **Jordan** | Platform lead / SRE | Defines organizational workflows and rules in CLAUDE.md |
| **Alex** | Product engineer | Uses tools daily but didn't build them |
| **Sam** | Freelance developer | Installs tools from PyPI, rarely reads source code |
| **Dana** | Senior engineer, API lead | Works with Claude Code daily, notices repetitive analysis patterns |
| **Priya** | New hire, first two weeks | Needs to get productive without memorizing CLI flags |
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
6. RESOURCE    → High-frequency reads become MCP resources (ecosystem layer)
```

The key transitions:
- **Pain → Command:** A human decides a task is worth wrapping in structure.
- **Command → Invocation:** The `{ok, result, error, meta}` envelope and JSON Schema make the tool machine-readable.
- **Invocation → Skill:** Documentation captures *when* and *why*, not just *what*.

---

## Scenario 1: Diagnostic Skill Lifecycle

### Persona
**Maya**, a backend developer at a mid-size SaaS company, on-call this week.

### Job to Be Done
*When I'm paged for a production incident, I want to quickly identify the root cause so I can restore service and get back to sleep.*

### Context
Maya has bash one-liners involving `grep`, `jq`, `awk`, and `sed` that she runs during incidents. She keeps forgetting the exact incantation for correlating request IDs across microservice logs. Every incident, she re-derives the pipeline from scratch.

### Journey

#### Phase 1: The Scratch Script (Day 1)

Maya wraps her most-used one-liner into a tooli command:

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

#### Phase 2: Claude Code Discovers It (Week 2)

Maya adds loggrep to her MCP config. During a debugging session:

> **Maya:** "The checkout service is returning 502s. What's in the logs from the last hour?"
>
> **Claude Code:** *(invokes loggrep.errors, then loggrep.timeline)*
>
> "Found 47 errors in the last hour. The timeline shows a connection pool exhaustion starting at 14:32, triggered by retry storms from the payment gateway. Checkout's retry logic amplified 12 failing requests into 47 connection attempts, exhausting the pool. Want me to check the payment gateway logs?"

Maya didn't teach Claude Code the three-step triage process (errors → timeline → correlate). The agent inferred the workflow from structured output — each result contains fields (`request_id`, `trace_id`) that naturally lead to the next command.

#### Phase 3: Self-Healing on Environmental Errors

A teammate provides a gzipped log file. The tool can't read it:

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

#### Phase 4: Team Adoption (Month 2)

Maya's teammates install loggrep. The team lead adds it to the project's CLAUDE.md:

```markdown
## Incident Response
- Always start with `loggrep errors` before manually grepping logs
- Use `loggrep correlate` for cross-service issues — don't trace by hand
```

New on-call engineers get Maya's debugging patterns without a knowledge transfer session. The tool didn't change — the human-authored documentation layer made it discoverable and teachable.

### What This Tests in Tooli Core

| Tooli Feature | How It's Exercised |
|---|---|
| `@app.command()` with type hints | CLI with `--json` output from a decorated function |
| `{ok, result, error, meta}` envelope | Agent parses results, chains commands, handles errors |
| Structured errors with `suggestion` | Agent self-corrects without human help |
| `suggestion.retry` field | Agent distinguishes retryable vs. non-retryable errors |
| JSON Schema via `--schema` | Agent knows every flag without reading source code |

### Key Interactions

| Given | When | Then |
|---|---|---|
| loggrep is in MCP config | Maya asks about recent errors | Agent invokes `loggrep errors` with appropriate time filter |
| `errors` output contains `request_id` fields | Agent needs the error sequence | Agent invokes `loggrep timeline` using the worst error's `request_id` |
| Tool receives a gzipped file | Error includes `"retry": true` and `--decompress` suggestion | Agent retries silently with the flag |
| Tool returns auth error with `"retry": false` | Agent reads the error category | Agent does NOT retry — explains the restriction to the user |
| `loggrep errors` returns empty list | Maya asks about errors | Agent suggests broadening time window or lowering level threshold |
| Invalid `--since` format | Agent sends malformed date | Structured error with `field: "since"` and correct format example |

### Acceptance Criteria

1. Commands return stable `{ok, result, error, meta}` envelope in `--json` mode.
2. Environmental errors with `"retry": true` are auto-retried; auth/policy errors are not.
3. Schema export accurately describes all parameters and return types.
4. Failed retries escalate with full context (original error + retry error).

---

## Scenario 2: The Platform Team's Deployment Toolchain

### Persona
**Jordan** (platform lead) and **Alex** (product engineer) at a 200-person company.

### Job to Be Done
*When deploying to production, I want confidence that nothing will break. When something goes wrong, I want deterministic recovery.*

### Context
Five internal CLI tools exist: `deploy-pilot`, `config-vault`, `schema-check`, `feature-flags`, `health-check`. Engineers struggle to remember the correct order. Last month, someone promoted a canary without checking the migration validator.

### Journey

#### Phase 1: The Individual Tools

Each is a standalone tooli app with capabilities and handoffs:

```python
# deploy_pilot.py
@app.command(
    capabilities=["net:write", "process:exec"],
    handoffs=[
        {"command": "rollback", "when": "deployment health checks fail"},
        {"command": "promote", "when": "canary metrics are green after monitoring period"},
    ],
)
def canary(service: str, version: str, percentage: int = 5) -> dict:
    """Deploy a canary release to a percentage of traffic."""
    ...

@app.command(capabilities=["net:write", "process:exec"])
def promote(service: str) -> dict:
    """Promote canary to full traffic. Requires prior health check."""
    ...

@app.command(capabilities=["net:write", "process:exec"])
def rollback(service: str) -> dict:
    """Immediately rollback to previous version."""
    ...
```

#### Phase 2: The Human-Authored Orchestration Layer

After the incident, Jordan writes a CLAUDE.md encoding the deployment workflow:

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

#### Phase 3: What Engineers Experience

> **Alex:** "Deploy user-service v2.4.1 to production"
>
> **Claude Code:** *(reads CLAUDE.md, follows mandatory workflow)*
>
> "I see pending migrations. Starting with schema validation."
> *(invokes each step, reading structured output to decide proceed/halt)*
>
> "Canary looks healthy — error rate 0.02% vs 0.03% baseline. Ready to promote. Should I proceed?"

Alex didn't memorize the workflow. The CLAUDE.md encoded it, and the tools' structured output gave the agent the information to make decisions at each step.

#### Phase 4: The Guardrail Moment

> **Junior:** "Just promote user-service, the canary's been running for a while"
>
> **Claude Code:** "I need to verify canary health before promoting — that's a mandatory step."
> *(invokes health-check, finds 2.3% error rate vs 0.03% baseline)*
> "The canary does NOT look healthy. The errors are `ConnectionRefused` from the cache layer. Should I rollback?"

The agent ran the check anyway and refused to promote when it failed.

#### Note: Multi-Agent Coordination

For complex multi-domain releases (DB migrations + security patches + config changes), the same tools support subagent delegation. An orchestrator agent delegates to specialized subagents — each invokes tools from its domain and reports back. The structured envelope and `handoffs` metadata make routing deterministic. The orchestrator reads each result and decides next steps without hallucinating workflows.

This coordination is an agent platform capability. Tooli's contribution is the structured output and handoff metadata that make it reliable.

#### Note: Resource Promotion

Teams that find agents repeatedly re-fetching the same data can promote high-frequency reads to MCP resources (`deploy://status/{service}`, `health://signals/{service}`). This is an MCP server concern — tooli's contribution is producing structured, cacheable command output that resource layers can wrap.

### What This Tests in Tooli Core

| Tooli Feature | How It's Exercised |
|---|---|
| Structured output envelope | Agent reads each step's result to decide proceed/halt/rollback |
| `capabilities` declarations | Tools declare what permissions they need |
| `handoffs` metadata | Agent knows what to do next without guessing |
| Consistent `--json` across tools | Five independent tools compose through shared format |
| Error semantics | `"ok": false` triggers rollback workflows |

### Key Interactions

| Given | When | Then |
|---|---|---|
| PR touches `migrations/` | Engineer requests deployment | Agent starts with `schema-check validate` per CLAUDE.md |
| `schema-check` returns `"safe": false` | Agent reads the result | Agent halts and explains the risk |
| `health-check watch` shows elevated error rate | Agent is about to promote | Agent refuses, shows diagnostics, suggests rollback |
| CLAUDE.md says "confirm before promote" | Health checks pass | Agent asks for explicit approval |
| `deploy-pilot promote` returns `"ok": false` | Promotion fails | Agent immediately invokes rollback per documented workflow |
| No migrations in PR | Engineer deploys | Agent skips `schema-check` — reads the condition, not just the rule |

### Acceptance Criteria

1. Promotion is blocked if schema risk is unresolved.
2. Healthy canary is required before promotion.
3. Rollback path is deterministic and auditable.
4. Commands return stable structured output for both CLI and MCP paths.

---

## Scenario 3: Independent Tools That Compose

### Persona
**Sam**, a freelance developer across multiple projects.

### Job to Be Done
*When preparing a repository for release, I want multiple utility tools to work together reliably without custom glue code.*

### Context
Sam has a pre-release checklist: lint docs, optimize images, check licenses, generate changelog. Each step uses a different tool. Sam frequently forgets a step.

### Journey

#### Phase 1: Installing the Pieces

Four tooli apps from PyPI, each by a different author:

```bash
pip install tooli-mdlint        # Markdown linter
pip install tooli-imgopt         # Image optimization
pip install tooli-license-scan   # License auditor
pip install tooli-changelog      # Changelog generator
```

None of the authors know each other. But because they all built on tooli, they share the `{ok, result, meta}` envelope, JSON Schema, structured errors, and behavioral annotations.

#### Phase 2: Emergent Composition

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

#### Phase 3: Graceful Degradation

Sam starts a new project without `tooli-imgopt`:

> **Claude Code:** "I have license-scan, mdlint, and changelog available, but not imgopt. I'll run the steps I can."

The agent doesn't fail. It reports the gap and continues.

### What This Tests in Tooli Core

| Tooli Feature | How It's Exercised |
|---|---|
| Shared `{ok, result, meta}` envelope | Four unknown tools compose through format alone |
| Consistent `--json` mode | Every tool is machine-readable without per-tool parsers |
| Structured errors | Agent handles missing tools and failures gracefully |
| Behavioral annotations | `Destructive` on `imgopt optimize` triggers confirmation |
| `--dry-run` convention | Agent previews before mutating |

### Key Interactions

| Given | When | Then |
|---|---|---|
| `license-scan` finds conflicts | Agent is preparing a release | Agent surfaces blockers first, continues with non-blocking checks |
| `mdlint` returns fixable issues | Agent sees `"auto_fixable": true` | Agent fixes them directly without asking |
| `imgopt scan` in `--dry-run` mode | Agent reads `Destructive` annotation on `optimize` | Agent asks for confirmation before applying |
| Referenced tool not installed | Agent encounters the gap | Agent reports missing tool and continues with available ones |

### Acceptance Criteria

1. Cross-tool composition uses structured outputs, not text scraping.
2. Missing tools are reported with installation guidance, not crashes.
3. Workflow remains robust under partial tool availability.

---

## Scenario 4: Security and Capability Governance

### Persona
**Riku**, a security engineer at a fintech company.

### Job to Be Done
*When autonomous tools run in our environment, I want to control what they can access and audit what they did.*

### Context
Regulatory requirements mandate that tools only access what they explicitly declare, and that access is logged.

### Journey

#### Phase 1: Capability Lockdown

Riku sets a company-wide policy:

```bash
export TOOLI_ALLOWED_CAPABILITIES="fs:read,net:read,db:read"
```

Any tool declaring capabilities outside the allowlist is blocked at invocation time.

#### Phase 2: The Block Event

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

#### Phase 3: Dry-Run Preview

For tools that support it, agents preview destructive operations:

> **Claude Code:** *(invokes `env-cleanup prune /tmp --older-than 7d --dry-run --json`)*
> "142 files (847MB) would be deleted. Shall I proceed?"

#### Phase 4: Audit Trail

Every invocation includes structured telemetry:

```json
{
  "tool": "code-analyzer.analyze",
  "caller_id": "claude-code",
  "capabilities_requested": ["fs:read", "fs:write"],
  "capabilities_blocked": ["fs:write"],
  "timestamp": "2026-02-20T14:32:01Z"
}
```

Riku can reconstruct exactly what happened from structured data, not log scraping.

### What This Tests in Tooli Core

| Tooli Feature | How It's Exercised |
|---|---|
| `capabilities` declarations | Per-command capability requirements in schema |
| Capability enforcement | Invocation blocked before function body runs |
| Structured auth errors | Machine-actionable remediation guidance |
| `--dry-run` support | Preview destructive operations without side effects |
| Caller metadata in envelope | Telemetry distinguishes human vs. agent vs. CI |

**Boundary note:** The enforcement mechanism (checking capabilities against an allowlist) can live in tooli itself or in an external policy layer. Tooli's minimum contribution is making capability declarations available in the schema. Whether tooli also enforces them is an implementation choice — but the declare-then-enforce pattern works either way.

### Key Interactions

| Given | When | Then |
|---|---|---|
| Strict mode with limited allowlist | Tool requests `fs:write` | Blocked with structured error explaining the gap |
| Agent receives capability denial | Agent is mid-workflow | Agent explains the block, suggests contacting security |
| Telemetry enabled | Any tool invoked | Record includes caller, capabilities, outcome |
| Dry-run on destructive command | Command executes | Plan returned, no side effects |
| Security team approves capability | Env var updated | Tool works on next invocation — no code changes |

### Acceptance Criteria

1. Policy enforcement occurs before mutative function body execution.
2. Blocked actions return machine-actionable remediation.
3. Security reporting can reconstruct allowed and denied attempts.
4. Dry-run produces complete preview with no side effects.

---

## Scenario 5: The Agent as Tool Author

### Persona
**Dana**, a senior engineer building a customer-facing API.

### Job to Be Done
*When I notice repeated manual analysis, I want it converted into a durable tool so my team's throughput compounds.*

### Context
Dana has asked Claude Code to do the same API performance analysis four times: "Check which endpoints have response times over 500ms and cross-reference with missing caching headers." Each time, a slightly different script. Inconsistent auth handling, different output formats, no error handling for edge cases.

### Journey

#### Phase 1: The Repetition Pattern (Weeks 1-4)

Four sessions, four similar scripts, each thrown away.

#### Phase 2: The Agent Proposes (Week 5)

> **Dana:** "Check our API endpoints again, same analysis as before"
>
> **Claude Code:** "I've done this analysis 4 times and each time the script is slightly different. Want me to create a reusable tooli app?"

#### Phase 3: The Agent Authors

Claude Code generates a complete tool, incorporating lessons from all four sessions:

```python
app = Tooli(name="api-audit", version="0.1.0")

@app.command(
    capabilities=["net:read"],
    handoffs=[
        {"command": "suggest-fixes", "when": "slow endpoints found without caching"},
    ],
)
def slow_endpoints(
    base_url: Annotated[str, Argument(help="Base URL of the API")],
    threshold_ms: Annotated[int, Option(help="Response time threshold in ms")] = 500,
    auth_token: Annotated[str | None, Option(help="Bearer token")] = None,
) -> list[dict]:
    """Find API endpoints with response times above threshold."""
    ...

@app.command(capabilities=["net:read"])
def cache_audit(
    base_url: Annotated[str, Argument(help="Base URL of the API")],
    auth_token: Annotated[str | None, Option(help="Bearer token")] = None,
) -> list[dict]:
    """Check caching headers on API endpoints."""
    ...

@app.command(capabilities=["net:read"])
def suggest_fixes(
    base_url: Annotated[str, Argument(help="Base URL of the API")],
    threshold_ms: Annotated[int, Option(help="Response time threshold")] = 500,
    auth_token: Annotated[str | None, Option(help="Bearer token")] = None,
) -> list[dict]:
    """Cross-reference slow endpoints with missing cache headers."""
    ...
```

What the agent learned from four sessions: auth tokens are needed (session 2 failed), ETag and Last-Modified matter alongside Cache-Control (session 3), the combined analysis is the most common request (sessions 3 and 4), the threshold should be configurable (session 1 used 500ms, session 4 used 300ms).

#### Phase 4: Reuse Across the Team

Dana's colleague Carlos works on a different service:

> **Carlos:** "I think our payment API has some slow endpoints, can you check?"
>
> **Claude Code:** *(sees api-audit in MCP, reads schema)* "I have the `api-audit` tool available. Want me to run a combined analysis?"

Carlos didn't know the tool existed. The agent discovered it from the schema and offered it.

### What This Tests in Tooli Core

| Tooli Feature | How It's Exercised |
|---|---|
| Simple decorator API | Agent can scaffold a valid tool using only `@app.command()` and type hints |
| Type-hint-to-schema pipeline | Agent-authored tool is immediately self-describing |
| `{ok, result, error, meta}` envelope | Agent-authored output is automatically parseable by other agents |
| `handoffs` metadata | Agent connects `slow-endpoints` → `suggest-fixes` |

### Key Interactions

| Given | When | Then |
|---|---|---|
| Agent has done same analysis 4 times | Developer asks a 5th time | Agent proposes creating a reusable tool |
| Developer approves | Agent generates the tool | Tool incorporates auth, headers, configurable threshold |
| Tool registered in MCP | Different engineer asks about API performance | Agent discovers and uses it |
| `slow-endpoints` fails without auth | Auth token not provided | Structured error with `field: "auth_token"` prompts agent to ask user |

### Acceptance Criteria

1. An agent can scaffold a valid tooli app using only the decorator API and type hints.
2. Agent-authored tools produce the same structured output as human-authored tools.
3. The tool is immediately discoverable by other agents via schema.

---

## Scenario 6: The New Hire Onboarding Experience

### Persona
**Priya**, joined the team two days ago. Experienced developer, unfamiliar with internal tools.

### Job to Be Done
*When I start a new job, I want to be productive quickly so I can contribute and feel like I belong.*

### Context
Priya's team has six internal tooli apps, a detailed CLAUDE.md, and established workflows. The previous onboarding was a 40-page Confluence doc that was always out of date.

### Journey

#### Phase 1: The First Task (Day 3)

> **Priya:** "I've been assigned JIRA-4521 — a null pointer exception in the order service. Where do I start?"
>
> **Claude Code:** *(reads CLAUDE.md, sees available tools)*
> "Let me use the team's log analysis tool."
>
> *(invokes `loggrep errors /var/log/order-service/ --since 2026-02-18 --level error --json`)*
>
> "Found the NPE in `OrderProcessor.java:142` — `customer.address` is null for international orders. The fix is a null check. Want me to write it?"

Priya didn't need to know that `loggrep` exists, what flags to pass, or where logs are stored.

#### Phase 2: The First Deployment (Day 3, continued)

> **Priya:** "The fix looks good. How do I deploy?"
>
> **Claude Code:** "This team uses a multi-step deployment process. I'll walk you through it."
>
> *(follows deployment workflow from CLAUDE.md, explains each step)*
>
> "Canary is healthy — error rate dropped from 0.4% to 0.01%. Your fix is working. Ready to promote?"

#### Phase 3: The Guardrail Moment

> **Priya:** "Can I restart the production database? The connection pool seems stale."
>
> **Claude Code:** "I can't do that — the CLAUDE.md says 'NEVER restart production databases without SRE approval.' I'd recommend asking in #sre, or I can check if `health-check` shows the connection pool issue."

#### Phase 4: Building Confidence (Week 2)

Priya starts using tools directly:

```bash
loggrep errors /var/log/order-service/ --since "2h ago" --json | jq '.result[] | .message'
```

She learned the CLI from watching the agent use it — the agent's invocations served as live examples.

### What This Tests in Tooli Core

| Tooli Feature | How It's Exercised |
|---|---|
| JSON Schema | Agent discovers tool capabilities without human instruction |
| Structured output | Agent explains what happened at each step |
| Structured errors with `suggestion.fix` | Priya's manual mistakes get helpful corrections |
| Consistent CLI interface | Agent invocations double as human-readable examples |

### Key Interactions

| Given | When | Then |
|---|---|---|
| Priya has never used loggrep | She asks about a production error | Agent uses loggrep on her behalf |
| Priya has never deployed | She asks how to deploy | Agent follows full workflow, explaining each step |
| Prohibited operation requested | Priya asks to restart prod DB | Agent cites guardrail, offers safe alternatives |
| Priya passes a wrong flag | Tool returns structured error | `suggestion.fix` tells her the correct flag |
| Successful workflow completes | Agent summarizes | Next-step options are explicit |

### Acceptance Criteria

1. Core workflows are executable by new hires without undocumented steps.
2. Guardrails are visible during execution, not hidden in static docs.
3. Agent guidance is traceable to skill documentation.

---

## Scenario 7: CI/CD as a First-Class Consumer

### Persona
**Elena**, CI maintainer. **Tool Maintainer** evolving a command's interface.

### Job to Be Done
*When PRs are opened, I want structured checks and actionable failures so CI and agents can diagnose without regex parsing.*

*When I need to make breaking changes to a tool, I want a safe migration path so existing automations don't fail.*

### Context
CI linters output unstructured text parsed with fragile regex. The team wants stable, structured output. Additionally, the `data-export` tool needs to rename `--format` to `--output-format` without breaking dozens of existing agent workflows.

### Journey

#### Phase 1: Structured CI Steps

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

#### Phase 2: Agent-Aware CI Feedback

> **Developer:** "CI failed on my PR, what's wrong?"
>
> **Claude Code:** *(reads CI output, recognizes envelope format)*
> "The `license-scan` step failed: `chart-renderer` v3.0 changed from MIT to BSL-1.1. The tool suggests pinning to v2.9. Want me to do that?"

#### Phase 3: Versioned Deprecation

The `data-export` maintainer renames a flag with a migration window:

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

Agents reading the schema see the deprecation and auto-migrate to the new flag. Old agents still work — the deprecated flag functions but emits a warning in envelope metadata. CI detects the deprecation as a warning, not a failure.

When the old flag is eventually removed, the tool returns a structured migration error:

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

#### Phase 4: Schema Drift Detection

CI validates that tool schemas haven't changed in breaking ways:

**Given** a PR changes a command's parameter signature,
**When** CI runs `mytool --schema` and compares to committed baseline,
**Then** schema drift is detected before merge — preventing silent breaks in agent workflows.

### What This Tests in Tooli Core

| Tooli Feature | How It's Exercised |
|---|---|
| `{ok, result, error, meta}` envelope | Stable CI contract — one parser for all tools |
| Structured errors with `suggestion` | CI posts fix guidance as GitHub annotations |
| Deprecation metadata in schema | Agents auto-migrate, CI warns during migration window |
| Structured migration errors | Removed flags produce helpful errors, not cryptic failures |
| `--schema` export | CI compares schemas across versions to detect drift |

### Key Interactions

| Given | When | Then |
|---|---|---|
| CI runs tools with `--json` | A step fails | CI posts structured error, not wall of text |
| Tool provides `suggestion.fix` | CI formats result | Suggestion appears as GitHub annotation |
| Command has deprecation metadata | Agent reads schema | Agent uses the new flag automatically |
| Old agent uses deprecated flag | Command still supports it | Warning in envelope, command still works |
| Deprecated flag removed | Old invocation uses `--format` | Structured error with exact replacement |
| PR changes command signature | CI compares to baseline | Schema drift flagged before merge |

### Acceptance Criteria

1. CI never depends on text scraping for tooli outputs.
2. Deprecated flags work with warnings during migration window.
3. Removal produces structured migration errors, not cryptic failures.
4. Schema drift is detectable via `--schema` comparison.

---

## Scenario 8: Cross-Team Tool Discovery

### Persona
**Staff engineer** coordinating multiple teams. **DevEx team** maintains a shared registry.

### Job to Be Done
*When a capability exists on another team, I want to find and use their tool instead of rebuilding it.*

### Context
Fifteen teams, each with 2-3 tooli apps. The data team has `data-lint`. The infra team has `tf-check`. Nobody knows what other teams have built.

### Journey

#### Phase 1: The Discovery Problem

> **Developer:** "I need to validate our API's CSV export"
>
> **Claude Code:** "I don't have a CSV tool in this project. Let me check the registry."
>
> *(invokes `tool-registry search "csv validate" --json`)*
>
> "Found `data-lint` from Data Engineering with a `validate-csv` command. It's read-only and safe to run. Want me to add it?"

#### Phase 2: The Registry Itself Is a Tooli App

```python
app = Tooli(name="tool-registry", version="1.0.0")

@app.command(capabilities=["net:read"])
def search(
    query: Annotated[str, Argument(help="Search query")],
    team: Annotated[str | None, Option(help="Filter by team")] = None,
) -> list[dict]:
    """Search the internal tool registry."""
    ...
```

The registry indexes every tooli app's `--schema` output, making capabilities searchable across the org.

#### Phase 3: Agent-Mediated Discovery

The pattern becomes: developer describes a need → agent searches registry → agent installs and uses the tool — all in one session.

### What This Tests in Tooli Core

| Tooli Feature | How It's Exercised |
|---|---|
| JSON Schema via `--schema` | Registry indexes tool metadata from schema output |
| Consistent schema format | Tools from different teams are uniformly searchable |
| `capabilities` in schema | Agent evaluates safety before recommending a tool |

**Boundary note:** The registry is a separate service, not a tooli feature. Tooli's contribution is that every tool produces consistent, complete schema output that a registry can index.

### Key Interactions

| Given | When | Then |
|---|---|---|
| Developer describes a need | No matching tool in current config | Agent searches registry |
| Registry returns a match | Agent reads capabilities | Agent evaluates safety and offers to install |
| Registry returns multiple matches | Agent must choose | Agent compares capabilities and team ownership |
| Tool installed mid-session | Original request pending | Agent uses newly installed tool to complete the task |

### Acceptance Criteria

1. Schema export is complete enough for registry indexing (name, description, commands, parameters, capabilities).
2. Schema format is stable across tooli versions.
3. Cross-team tool selection is deterministic from metadata.

---

## Scenario 9: Customer Support Workflows

### Persona
**Leila**, a support engineer resolving customer issues.

### Job to Be Done
*When a customer reports an issue, I want to diagnose and safely remediate so I resolve tickets quickly without making things worse.*

### Context
Support tickets follow patterns: account locked, quota exceeded, payment failed. Each has a diagnostic and a remediation step. Remediation is often destructive and must be audited.

### Journey

#### Phase 1: The Tools

```python
@app.command(capabilities=["db:read"])
def diagnose(
    account_id: Annotated[str, Argument(help="Customer account ID")],
) -> dict:
    """Diagnose account issues and suggest remediation."""
    ...

@app.command(capabilities=["db:write"])
def quota_reset(
    account_id: Annotated[str, Argument(help="Customer account ID")],
    reason: Annotated[str, Option(help="Audit reason for the reset")],
) -> dict:
    """Reset account quota. Requires reason for audit trail."""
    ...
```

#### Phase 2: Agent-Guided Triage

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

#### Phase 3: The Runbook Becomes a Skill

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

### What This Tests in Tooli Core

| Tooli Feature | How It's Exercised |
|---|---|
| Mandatory parameters via type system | `reason` is required — no reason means validation error |
| Structured output with before/after state | Audit trail built from command output |
| Error responses for bad input | Agent asks user for corrections when account ID is invalid |
| `capabilities` declarations | `db:write` on destructive commands enables governance |

### Key Interactions

| Given | When | Then |
|---|---|---|
| Customer reports upload failure | Leila describes symptom | Agent runs `diagnose`, identifies root cause |
| `quota-reset` requires `reason` | Agent proposes remediation | Agent explains it requires a reason, asks for one |
| Reset completed | Agent confirms | Result includes before/after state |
| Diagnosis shows legitimate usage | Agent reads result | Agent suggests plan upgrade instead of reset |
| Unknown account ID | Agent runs `diagnose` | Structured error tells agent the expected format |

### Acceptance Criteria

1. Diagnosis always precedes remediation.
2. Destructive actions require explicit confirmation and audit reason.
3. Audit trail records actor, reason, timestamp, before/after state.

---

## Patterns Across All Scenarios

### 1. Structured Output Is the Universal Connector

The `{ok, result, meta}` envelope isn't decorative — it's the API contract that makes everything else possible. Agents parse it. CI parses it. Other tools parse it. When output is structured, composition is free. This is tooli's single most important feature.

### 2. Errors Are a First-Class Interface

Every scenario includes a failure path. Structured errors with `suggestion` and `retry` fields are what let agents self-correct (Scenario 1), enforce guardrails (Scenario 2), guide migrations (Scenario 7), and explain security blocks (Scenario 4). The error envelope is as important as the success envelope.

### 3. Schema Is the Minimum Viable Discovery

Agents don't need generated documentation to use tooli apps. They need JSON Schema from `--schema`. The schema tells them every parameter, type, and default. Documentation adds context (*when* and *why*), but the schema is the minimum viable discovery mechanism that makes everything from onboarding (Scenario 6) to cross-team discovery (Scenario 8) work.

### 4. Workflow Documentation Is a Human Concern

CLAUDE.md files, deployment runbooks, support playbooks — these are written by humans who understand the *why*, not just the *what*. Jordan's deployment workflow (Scenario 2), Sam's release checklist (Scenario 3), and Leila's support runbook (Scenario 9) all encode judgment that can't be generated from a schema. Tooli's job is to make tools self-describing enough that human-authored docs can reference them concisely.

### 5. Composition Is Emergent, Not Designed

Sam's open-source tools (Scenario 3) were built by strangers. The deployment tools (Scenario 2) were built independently and connected through CLAUDE.md. The agent figures out how to combine tools from their metadata and documented workflows. No orchestration framework required.

### 6. The Agent Operates at Multiple Levels

- **Consumer:** Discovers and invokes tools (all scenarios)
- **Operator:** Follows documented workflows, making decisions at each step (Scenarios 2, 6, 9)
- **Teacher:** Shows users how tools work by using them (Scenario 6)
- **Author:** Creates new tools from observed patterns (Scenario 5)
- **Gatekeeper:** Enforces safety rules before irreversible actions (Scenarios 2, 4, 9)
- **Self-healer:** Retries with structured suggestions on environmental failures (Scenario 1)

### 7. The Human Stays in Control

In every scenario, the human decides which tools to install, what workflows to document, when to approve destructive actions, and what capabilities to allow. The agent amplifies human capability without replacing human judgment.

---

## Deferred Scenarios

These scenarios were present in the source documents but are deferred from this version. They describe real patterns, but they test ecosystem capabilities beyond tooli's framework responsibilities.

### Global Skill Mesh / Multi-Framework Export

**Source:** `scenarios_cc.md` §10, `scenarios_gm.md` §5

The vision: `tooli export --target langchain/openai/adk` generates framework-specific wrappers. This is compelling but it's a code-generation tool that reads JSON Schema, not a CLI framework feature. Tooli exports JSON Schema via `--schema`. A separate tool (or community contribution) can generate LangChain `@tool` wrappers, OpenAI function definitions, or ADK YAML from that schema. Building this into tooli means tracking every API change from every LLM provider — an unbounded maintenance burden.

**What to build instead:** A standalone `tooli-export` package that reads `--schema` output and generates wrappers. It can evolve independently and support non-tooli tools too.

### Resource-First Subagent Operations

**Source:** `scenarios_cdx.md` §9

MCP resources (`loggrep://recent-errors`, `deploy://status/{service}`) are a real and valuable optimization for read-heavy workflows. But they're an MCP server concern, not a CLI framework concern. FastMCP handles resource registration. Tooli's contribution — already exercised in every other scenario — is producing structured, cacheable command output that a resource layer can wrap.

**What to build instead:** Documentation recipes showing how to wrap tooli commands as MCP resources using FastMCP.

---

## Checklist for Future Scenario Authors

Before adding new scenarios:

1. Does the scenario have a named persona with a clear Job to Be Done?
2. Is the journey multi-phase, showing evolution over time?
3. Is at least one failure path explicitly dramatized?
4. Does it identify what it tests in tooli core vs. the surrounding ecosystem?
5. Are acceptance criteria observable and testable?
6. Does it include concrete code, JSON output, or agent dialogue?
7. Does it introduce something the existing scenarios don't already cover?
