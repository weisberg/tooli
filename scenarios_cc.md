# Tooli + Claude Code: Skill Emergence Scenarios

> How developer tools become agent skills — from first function to ecosystem resource.

This document describes realistic scenarios showing how tooli-based CLI tools emerge as skills and resources within Claude Code. Each scenario follows a structured format:

- **Persona** — Who is involved and what is their role
- **Job to Be Done** — The underlying goal driving behavior (not the feature)
- **Context** — The situation and environment
- **Journey** — A phased narrative showing evolution over time
- **Key Interactions** — Concrete Given/When/Then moments between human, agent, and tool
- **Emergent Artifacts** — The tools, skills, and MCP resources that crystallize
- **What Emerged** — The outcome that no single step planned for

---

## Personas

| Persona | Description | Relationship to Tools |
|---|---|---|
| **Solo Dev** | Individual developer solving their own problems | Builds tools for themselves, discovers they're useful to agents |
| **Platform Engineer** | Builds internal tooling for an engineering org | Designs tools as organizational infrastructure |
| **Open-Source Author** | Publishes general-purpose utilities to PyPI | Builds for a community, never meets most users |
| **End User** | Installs tools, works with Claude Code daily | Consumes tools, rarely reads source code |
| **The Agent** | Claude Code operating within a project | Discovers, invokes, composes, and eventually authors tools |
| **Team Lead** | Manages a team, sets standards and workflows | Defines which tools are available and how they should be used |
| **New Hire** | Just joined a team, unfamiliar with internal tooling | Needs to get productive without memorizing every CLI flag |
| **Security Engineer** | Audits tool access, enforces compliance | Controls what tools can do and tracks what they did |
| **Support Engineer** | Resolves customer issues using internal diagnostics | Needs fast, safe, auditable remediation workflows |

---

## Shared Lifecycle

Every scenario in this document follows the same underlying progression. A tool may stop at any stage — not everything needs to become an org-wide resource — but the path is always available.

```
1. PAIN        → A repeated task appears in real developer or user work.
2. COMMAND     → A tooli command is created with typed inputs, metadata, and annotations.
3. INVOCATION  → Claude Code starts calling it in structured mode (--json or MCP).
4. REFINEMENT  → Usage data and failures drive command and documentation improvements.
5. SKILL       → The command becomes part of a reusable skill workflow (SKILL.md, CLAUDE.md).
6. RESOURCE    → High-value outputs are promoted to MCP resources for low-token, direct retrieval.
```

The key transitions:
- **Pain → Command:** A human decides a task is worth wrapping in structure.
- **Command → Skill:** Documentation captures not just *what* the tool does, but *when* and *why* to use it.
- **Skill → Resource:** Frequently-read data becomes directly accessible without re-executing the command.

---

## Scenario 1: The Solo Developer's Debugging Toolkit

### Persona
**Maya**, a backend developer at a mid-size SaaS company. She's on-call this week and frequently investigates production incidents by reading application logs.

### Job to Be Done
*When I'm paged for a production incident, I want to quickly identify the root cause so I can restore service and get back to sleep.*

### Context
Maya has a collection of bash one-liners she runs during incidents. They involve `grep`, `jq`, `awk`, and `sed` in various combinations. She keeps forgetting the exact incantation for correlating request IDs across microservice logs. Every incident, she re-derives the pipeline from scratch.

### Journey

#### Phase 1: The Scratch Script (Day 1)

Maya is tired of re-deriving her grep pipelines. During a calm afternoon, she wraps her most-used one-liner into a tooli command:

```python
# loggrep.py — started as a 20-line script
from tooli import Tooli, Annotated, Argument, Option
from tooli.annotations import ReadOnly

app = Tooli(name="loggrep", version="0.1.0")

@app.command(
    annotations=ReadOnly,
    capabilities=["fs:read"],
)
def errors(
    path: Annotated[str, Argument(help="Log file or directory")],
    since: Annotated[str, Option(help="ISO timestamp cutoff")] = "",
    level: Annotated[str, Option(help="Minimum level: warn|error|fatal")] = "error",
) -> list[dict]:
    """Extract structured error entries from application logs."""
    ...
```

She runs `loggrep errors /var/log/myapp/ --since 2026-02-20T00:00 --json` during the next outage. It works. She adds two more commands over the following week: `loggrep timeline` (event sequence reconstruction) and `loggrep correlate` (cross-service request tracing by trace ID).

**What Maya notices:** She's spending less time re-deriving pipelines and more time actually diagnosing issues. The structured JSON output means she can pipe results into `jq` without fragile text parsing.

#### Phase 2: Claude Code Discovers It (Week 2)

Maya adds loggrep to her project's MCP config:

```json
{
  "mcpServers": {
    "loggrep": {
      "command": "loggrep",
      "args": ["mcp", "serve", "--transport", "stdio"]
    }
  }
}
```

Now during a debugging session:

> **Maya:** "The checkout service is returning 502s. What's in the logs from the last hour?"

**Given** Claude Code has loggrep available as an MCP tool and can read its schema,
**When** Maya asks about production errors,
**Then** the agent invokes `loggrep errors /var/log/checkout/ --since <1h ago> --level error --json`, receives structured results, and summarizes them without Maya needing to remember the command syntax.

> **Claude Code:** *(invokes loggrep.errors, then loggrep.timeline)* "Found 47 errors in the last hour. The timeline shows a connection pool exhaustion starting at 14:32, triggered by a spike in retry loops from the payment gateway. Here's the sequence:"
>
> ```
> 14:32:01 payment-gw → checkout: timeout (retryable)
> 14:32:02 payment-gw → checkout: timeout (retry 1/3)
> 14:32:03 payment-gw → checkout: timeout (retry 2/3)
> ... (41 more retry storms from 12 concurrent requests)
> 14:32:18 checkout: connection pool exhausted (0/50 available)
> 14:32:18 checkout → client: 502 Bad Gateway
> ```
>
> "The payment gateway started timing out at 14:32. Checkout's retry logic amplified 12 failing requests into 47 connection attempts, exhausting the pool. Want me to check if the payment gateway logs show what caused the initial timeouts?"

**What Maya notices:** She didn't tell Claude Code about the three-step triage process (errors → timeline → correlate). The agent figured out the workflow from the tool's handoff metadata and the structured output of each step.

#### Phase 3: Skill Crystallization (Week 3)

Maya generates documentation that captures the workflows that emerged from actual use:

```bash
loggrep generate-skill --target claude-code > SKILL.md
loggrep generate-claude-md > CLAUDE.md
```

The SKILL.md captures **task-oriented workflows**:

```markdown
## Workflows

### Incident Triage
1. `loggrep errors ./logs --since <cutoff> --level error` — Get structured error list
2. `loggrep timeline ./logs --request-id <id>` — Reconstruct event sequence for worst error
3. `loggrep correlate ./logs --trace-id <id>` — Cross-service view of the failing request

### Post-Mortem Analysis
1. `loggrep errors ./logs --since <start> --until <end>` — Bounded error window
2. Pipe results to `loggrep correlate` for full distributed trace
3. Use `--level warn` to find precursor warnings before the error spike
```

Now every Claude Code session in that project starts with these skills loaded. The agent doesn't hallucinate flags — it reads the schema. It doesn't guess workflows — it follows the documented patterns.

#### Phase 4: Resource Promotion (Month 1)

The team finds that agents frequently re-fetch the same recent errors. Maya registers MCP resources for direct retrieval:

```
loggrep://recent-errors          → last hour of errors, structured
loggrep://request/{id}/timeline  → event sequence for a specific request
loggrep://service/{name}/health  → current error rate and top errors
```

Now agents can read `loggrep://recent-errors` directly without executing the command each time — lower latency, fewer tokens, same structure.

#### Phase 5: Team Adoption (Month 2)

Maya's teammate Raj sees her using loggrep during a shared debugging session. He installs it. Within a week, three more teammates are using it. The team lead adds it to the project's standard CLAUDE.md:

```markdown
## Incident Response Tools
- loggrep is available via MCP for log analysis
- Always start with `loggrep errors` before manually grepping logs
- Use `loggrep correlate` for cross-service issues — don't trace by hand
- For repeated reads, prefer `loggrep://recent-errors` resource over re-running the command
```

**What emerged:** A personal scratch script became team infrastructure. The tool didn't change — the documentation layer (SKILL.md, CLAUDE.md) made it discoverable and teachable. New on-call engineers get the benefit of Maya's debugging patterns without a knowledge transfer session.

### Emergent Artifacts

| Type | Artifact |
|---|---|
| Tools | `loggrep errors`, `loggrep timeline`, `loggrep correlate` |
| Skill | "Incident Triage" workflow in SKILL.md |
| Resources | `loggrep://recent-errors`, `loggrep://request/{id}/timeline`, `loggrep://service/{name}/health` |
| Contract | CLAUDE.md rules for when to use loggrep vs. manual grep |

### Key Interactions

| Given | When | Then |
|---|---|---|
| loggrep is in MCP config | Maya asks about recent errors | Agent invokes `loggrep errors` with appropriate time filter |
| `loggrep errors` returns a list with `request_id` fields | Agent needs to understand the error sequence | Agent invokes `loggrep timeline` using the `request_id` from the worst error |
| Timeline shows cross-service failure | Agent needs the full distributed trace | Agent invokes `loggrep correlate` with the `trace_id` from the timeline |
| SKILL.md documents the Incident Triage workflow | A new on-call engineer asks "what happened last night?" | Agent follows the documented three-step workflow without guidance |
| `loggrep errors` returns an empty list | Maya asks about errors | Agent reports "no errors found" and suggests broadening the time window or lowering the level threshold — guided by the tool's structured empty response |
| Agent needs current error rate | Data was fetched recently | Agent reads `loggrep://service/checkout/health` resource instead of re-running the command |

---

## Scenario 2: The Platform Team's Internal Toolchain

### Persona
**Platform Team** at a 200-person engineering company. They maintain internal infrastructure and developer experience tools. **Jordan** is the platform lead, **Alex** is a product engineer who uses the tools daily but didn't build them.

### Job to Be Done
*When I need to deploy a service to production, I want confidence that nothing will break so I can ship without anxiety.*

*When a deployment goes wrong, I want to recover quickly so the impact to customers is minimized.*

### Context
The platform team has built five internal CLI tools over the past year. Each solves one problem well, but engineers struggle to remember the correct order of operations for deployments. Last month, someone promoted a canary without checking the migration validator, causing a schema mismatch in production.

### Journey

#### Phase 1: The Individual Tools

```
deploy-pilot    — canary deployment orchestrator
config-vault    — encrypted config management
schema-check    — DB migration validator
feature-flags   — flag management CRUD
health-check    — service dependency monitor
```

Each is a standalone tooli app with capabilities and handoffs that declare how they relate to each other:

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

@app.command(
    annotations=Destructive,
    capabilities=["net:write", "process:exec"],
)
def promote(service: str) -> dict:
    """Promote canary to full traffic. Requires prior health check."""
    ...

@app.command(
    annotations=Destructive,
    capabilities=["net:write", "process:exec"],
)
def rollback(service: str) -> dict:
    """Immediately rollback to previous version."""
    ...
```

```python
# schema_check.py
@app.command(
    capabilities=["db:read", "fs:read"],
    handoffs=[
        {"command": "deploy-pilot canary", "when": "migration is safe to apply"},
    ],
    delegation_hint="Run this before any deployment that includes DB migrations",
)
def validate(migration_dir: str) -> dict:
    """Validate pending migrations against the live schema."""
    ...
```

#### Phase 2: The Orchestration Layer (CLAUDE.md)

After the schema mismatch incident, Jordan writes a project-level CLAUDE.md that encodes the deployment workflow as a contract:

```markdown
## Available Internal Tools

All tools support `--json` for structured output and `TOOLI_CALLER=claude-code`.

### Deployment Workflow (MANDATORY ORDER)
1. `schema-check validate ./migrations` — Validate DB changes first
2. `feature-flags check <flag>` — Verify feature flag state
3. `config-vault diff <service> --env staging --env production` — Check config drift
4. `deploy-pilot canary <service> <version>` — Start canary at 5%
5. `health-check watch <service> --duration 5m` — Monitor canary health
6. `deploy-pilot promote <service>` — Promote ONLY if health-check passes

### Rollback Workflow
1. `deploy-pilot rollback <service>` — Immediate rollback
2. `health-check watch <service>` — Verify recovery
3. Notify #incidents channel

### Rules
- NEVER run `deploy-pilot promote` without `health-check watch` passing first
- NEVER skip `schema-check validate` for PRs touching `migrations/`
- ALWAYS run `config-vault diff` before canary to catch config drift
- Ask for human confirmation before `promote` and `rollback`
```

#### Phase 3: What Engineers Experience

**Alex** (product engineer) is deploying:

> **Alex:** "Deploy user-service v2.4.1 to production"
>
> **Claude Code:** *(reads CLAUDE.md, sees mandatory deployment workflow)*
> "I see there are pending migrations in this PR. Starting with schema validation."
> *(invokes schema-check validate ./migrations --json)*
> "Migration is safe — additive column `users.preferred_locale`, no locks, backward compatible."
>
> *(invokes feature-flags check new-checkout-flow --json)*
> "Flag `new-checkout-flow` is OFF in production, consistent with this PR."
>
> *(invokes config-vault diff user-service --env staging --env production --json)*
> "No config drift detected between staging and production."
>
> *(invokes deploy-pilot canary user-service v2.4.1 --json)*
> "Canary deployed at 5% traffic."
>
> *(invokes health-check watch user-service --duration 5m --json)*
> "All health checks green for 5 minutes. Error rate: 0.02% (baseline: 0.03%). P99 latency: 142ms (baseline: 148ms). No anomalies."
>
> "Canary looks healthy — metrics are at or better than baseline. Ready to promote to full traffic. Should I proceed?"

**Alex doesn't know the deployment workflow by heart.** She didn't need to. The CLAUDE.md encoded Jordan's operational knowledge, and the tools' structured output gave the agent everything it needed to make decisions at each step.

#### Phase 4: The Guardrail Moment

Two weeks later, a junior engineer tries to take a shortcut:

> **Junior:** "Just promote user-service, the canary's been running for a while"
>
> **Claude Code:** "I need to verify the canary health before promoting — that's a mandatory step. Let me check."
> *(invokes health-check watch user-service --duration 1m --json)*
> "Health check shows elevated error rate: 2.3% (baseline: 0.03%). The canary does NOT look healthy. I won't promote."
>
> "The errors are `ConnectionRefused` from the cache layer. This suggests the new version has a cache connection issue. Recommended next steps:"
> 1. `deploy-pilot rollback user-service` — Rollback the canary
> 2. Check cache connection config in the new version
>
> "Should I rollback?"

**Given** the CLAUDE.md says "NEVER promote without health-check passing,"
**When** an engineer asks to skip the check,
**Then** the agent runs the check anyway and refuses to promote when it fails — providing actionable diagnostics instead.

#### Phase 5: Resources for Live State

The team promotes frequently-read deployment state to MCP resources:

```
deploy://status/{service}     → current deployment state (canary %, version, health)
health://signals/{service}    → real-time error rate, latency percentiles
schema://diff/{service}       → pending migration analysis
```

Agents read `deploy://status/user-service` to check if a canary is already running before starting a new one — no command execution needed.

### Emergent Artifacts

| Type | Artifact |
|---|---|
| Tools | `schema-check validate`, `deploy-pilot canary/promote/rollback`, `health-check watch`, `config-vault diff`, `feature-flags check` |
| Skill | Deployment Workflow and Rollback Workflow in CLAUDE.md |
| Resources | `deploy://status/{service}`, `health://signals/{service}`, `schema://diff/{service}` |
| Guardrails | "NEVER promote without health-check" enforced by agent behavior |

### What Emerged

The deployment workflow started as tribal knowledge in Jordan's head. It became a CLAUDE.md contract. Now 200 engineers follow the same process, enforced not by a CI gate (which only catches what you test for) but by an agent that understands the *intent* behind each step. The agent doesn't just run commands in order — it reads the output of each step and decides whether to proceed, adapting to what it finds.

### Key Interactions

| Given | When | Then |
|---|---|---|
| PR touches `migrations/` | Engineer requests deployment | Agent starts with `schema-check validate` before anything else |
| `schema-check` returns `"safe": false, "reason": "table lock"` | Agent reads the result | Agent halts deployment and explains the risk, suggesting migration alternatives |
| `health-check watch` shows elevated error rate | Agent is about to promote | Agent refuses to promote, shows diagnostics, suggests rollback |
| CLAUDE.md says "Ask for human confirmation before promote" | Health checks pass | Agent presents metrics summary and asks for explicit approval |
| `deploy-pilot promote` returns `"ok": false` | Promotion fails | Agent immediately invokes `deploy-pilot rollback` per the rollback workflow |
| Engineer asks to skip schema-check | No migrations in PR | Agent skips schema-check (the rule says "for PRs touching migrations/") — it reads the condition, not just the rule |

---

## Scenario 3: The Open-Source Ecosystem Effect

### Persona
**Sam**, a freelance developer who works on 5-6 different client projects. They don't build CLI tools — they install them. **Multiple open-source authors** who don't know each other, each solving one niche problem.

### Job to Be Done
*When I'm preparing a repository for release, I want all the hygiene tasks done correctly so I don't ship embarrassing mistakes (broken links, unoptimized images, license violations).*

### Context
Sam has a pre-release checklist they run manually: lint the docs, optimize images, check licenses, generate changelog. Each step uses a different tool with different output formats. Sam frequently forgets a step or runs them in the wrong order.

### Journey

#### Phase 1: Installing the Pieces

Sam discovers four tooli apps on PyPI, each built by a different author:

```bash
pip install tooli-mdlint      # Author: @docsmith — Markdown linter with structured diagnostics
pip install tooli-imgopt       # Author: @pixelcrush — Image optimization with dry-run support
pip install tooli-license-scan # Author: @compliance-tools — Dependency license auditor
pip install tooli-changelog    # Author: @releasecraft — Changelog generator from git history
```

Each tool was built independently. None of the authors have heard of each other. But because they all built on tooli, they share:
- The `{ok, result, meta}` envelope format
- JSON Schema for every command
- Behavioral annotations (ReadOnly, Destructive, Idempotent)
- Structured error responses with suggestions
- `--dry-run` support where applicable

Sam registers all four as MCP servers:

```json
{
  "mcpServers": {
    "mdlint":       { "command": "mdlint",       "args": ["mcp", "serve", "--transport", "stdio"] },
    "imgopt":       { "command": "imgopt",        "args": ["mcp", "serve", "--transport", "stdio"] },
    "license-scan": { "command": "license-scan",  "args": ["mcp", "serve", "--transport", "stdio"] },
    "changelog":    { "command": "changelog",     "args": ["mcp", "serve", "--transport", "stdio"] }
  }
}
```

#### Phase 2: Emergent Composition

> **Sam:** "Prepare this repo for the v3.0 release"

**Given** four independent tooli apps are available via MCP,
**When** Sam asks for release preparation,
**Then** Claude Code reads each tool's schema, identifies relevant commands, and composes a multi-tool workflow:

> **Claude Code:**
>
> *(reads schemas of all four tools, identifies relevant commands)*
>
> "I'll run through the release preparation checklist. Starting with compliance — license issues are blocking, so I want to surface those first."
>
> *(invokes license-scan audit --json)*
> "Found 2 dependencies with GPL-3.0 licenses that conflict with your MIT license:
> - `pdf-renderer` v2.1 (GPL-3.0) — used in `src/export.py`
> - `graph-layout` v1.0 (GPL-3.0-only) — used in `src/visualization.py`
>
> These need to be resolved before release. I'll flag them and continue with the other checks."
>
> *(invokes mdlint check docs/ --json)*
> "Found 6 issues in the docs:
> - 4 broken links (2 are references to renamed files in this PR)
> - 2 heading hierarchy violations (H1 → H3 skip in CONTRIBUTING.md)
>
> I can fix the broken links and heading issues now."
>
> *(fixes the markdown issues, then invokes imgopt scan assets/ --dry-run --json)*
> "6 images can be optimized, saving 2.3MB total:
> - `hero.png`: 1.8MB → 420KB (WebP conversion)
> - `architecture.png`: 340KB → 128KB (lossless recompression)
> - 4 screenshots: minor savings
>
> Want me to apply the optimizations?"
>
> *(Sam approves, agent invokes imgopt optimize assets/ --json)*
> "Images optimized. Total savings: 2.3MB."
>
> *(invokes changelog generate --from v2.0.0 --json)*
> "Generated changelog from 47 commits across 3 months. Here's the draft."
>
> "Release preparation summary:
> - Docs: 6 issues fixed
> - Images: 2.3MB saved
> - Changelog: drafted
> - **Blocking:** 2 GPL-3.0 dependencies need resolution before release
>
> The license issue with `pdf-renderer` and `graph-layout` needs a manual decision — want to replace them with MIT-compatible alternatives, or add a license exception?"

#### Phase 3: The Workflow Becomes a Skill

Sam creates a project CLAUDE.md that captures this workflow:

```markdown
## Release Preparation

Run these tools in order before every release:

1. `license-scan audit` — Check for license conflicts (blocking if found)
2. `mdlint check docs/` — Lint documentation (auto-fixable)
3. `imgopt scan assets/ --dry-run` — Preview image optimization (confirm before applying)
4. `changelog generate --from <last-tag>` — Generate changelog draft
5. Commit all changes

### Rules
- License conflicts are BLOCKING — do not proceed to release with unresolved conflicts
- Always dry-run imgopt before applying — some image conversions change format
- Changelog should be reviewed by human before committing
```

#### Phase 4: Cross-Project Learning

Sam starts a new client project that doesn't have `tooli-imgopt` installed. When they ask to prepare a release:

> **Claude Code:** "I have license-scan, mdlint, and changelog available, but not imgopt. I'll run the steps I can. You may want to install `tooli-imgopt` if image optimization is needed for this project."

**Given** the CLAUDE.md references imgopt but it's not in MCP config,
**When** the agent runs the release workflow,
**Then** it gracefully skips the missing tool and tells the user about the gap — rather than failing or hallucinating.

### Emergent Artifacts

| Type | Artifact |
|---|---|
| Tools | `license-scan audit`, `mdlint check`, `imgopt scan/optimize`, `changelog generate` |
| Skill | "Release Preparation" workflow in CLAUDE.md |
| Resources | `license-scan://audit/latest` (cached compliance snapshot), `changelog://draft/latest` |
| Pattern | "Resource-first, command-second" — agents read cached results before re-running |

### What Emerged

Four tools built by strangers, for different purposes, became a cohesive release workflow — not because anyone designed it that way, but because they all spoke the same protocol. The "integration layer" isn't a framework or an orchestrator. It's the envelope format, the schemas, and the human who wrote a CLAUDE.md connecting the dots.

### Key Interactions

| Given | When | Then |
|---|---|---|
| license-scan returns `"conflicts": [{"license": "GPL-3.0"}]` | Agent is preparing a release | Agent marks this as blocking and continues with non-blocking checks |
| mdlint returns fixable issues | Agent sees `"auto_fixable": true` on each diagnostic | Agent fixes them directly without asking |
| imgopt scan returns changes in `--dry-run` mode | Agent reads the `Destructive` annotation on `optimize` | Agent asks for confirmation before applying (dry-run first, then confirm) |
| changelog returns a draft | CLAUDE.md says "reviewed by human before committing" | Agent presents the draft and waits for approval |
| Tool is referenced in CLAUDE.md but not in MCP config | Agent tries to invoke it | Agent skips gracefully and informs the user |

---

## Scenario 4: The Agent-Built Tool

### Persona
**Dana**, a senior engineer building a customer-facing REST API. She works with Claude Code daily and often asks it to analyze API performance.

### Job to Be Done
*When I notice performance issues in my API, I want to quickly identify which endpoints are slow and why so I can fix them before customers notice.*

### Context
Over the past month, Dana has asked Claude Code to do the same analysis four times: "Check which of our API endpoints have response times over 500ms and cross-reference with the ones that don't have caching headers." Each time, Claude Code writes a fresh ad-hoc script with `requests` and manual JSON parsing. The scripts work but are slightly different each time — inconsistent timeout handling, different output formats, no error handling for endpoints that require auth.

### Journey

#### Phase 1: The Repetition Pattern (Week 1-4)

Session 1: Claude Code writes a 40-line script that hits each endpoint and measures response time.
Session 2: Dana asks again, Claude Code writes a similar script but forgets the auth header.
Session 3: Dana asks again, adds "also check if they return cache-control headers."
Session 4: Dana asks again, says "same thing as last time."

Each script is thrown away after use. The knowledge of *how to do this analysis* exists only in conversation history that expires.

#### Phase 2: The Agent Recognizes the Pattern (Week 5)

> **Dana:** "Check our API endpoints again, same analysis as before"
>
> **Claude Code:** "I've done this analysis 4 times across recent sessions, and each time I write a slightly different script. Want me to create a reusable tool for this? As a tooli app, it would be available in every future session with consistent behavior."
>
> **Dana:** "Yes, make it a tooli app"

```bash
tooli init api-audit --description "API endpoint health and configuration auditor"
```

#### Phase 3: The Agent Authors a Tool

Claude Code generates a complete tooli app, informed by the patterns from all four previous sessions:

```python
# api_audit/app.py
from tooli import Tooli, Annotated, Argument, Option
from tooli.annotations import ReadOnly, Idempotent
from tooli.errors import InputError

app = Tooli(
    name="api-audit",
    description="API endpoint health and configuration auditor",
    version="0.1.0",
)

@app.command(
    annotations=ReadOnly | Idempotent,
    capabilities=["net:read"],
    handoffs=[
        {"command": "suggest-fixes", "when": "slow endpoints found without caching"},
    ],
)
def slow_endpoints(
    base_url: Annotated[str, Argument(help="Base URL of the API")],
    threshold_ms: Annotated[int, Option(help="Response time threshold in ms")] = 500,
    endpoints_file: Annotated[str, Option(help="File listing endpoints to check")] = "endpoints.txt",
    auth_token: Annotated[str | None, Option(help="Bearer token for authenticated endpoints")] = None,
) -> list[dict]:
    """Find API endpoints with response times above threshold."""
    ...

@app.command(
    annotations=ReadOnly | Idempotent,
    capabilities=["net:read"],
)
def cache_audit(
    base_url: Annotated[str, Argument(help="Base URL of the API")],
    endpoints_file: Annotated[str, Option(help="File listing endpoints to check")] = "endpoints.txt",
    auth_token: Annotated[str | None, Option(help="Bearer token for authenticated endpoints")] = None,
) -> list[dict]:
    """Check caching headers (Cache-Control, ETag, Last-Modified) on API endpoints."""
    ...

@app.command(
    annotations=ReadOnly,
    capabilities=["net:read"],
    delegation_hint="Use this after running slow-endpoints and cache-audit separately, or as a single combined analysis",
)
def suggest_fixes(
    base_url: Annotated[str, Argument(help="Base URL of the API")],
    threshold_ms: Annotated[int, Option(help="Response time threshold in ms")] = 500,
    auth_token: Annotated[str | None, Option(help="Bearer token for authenticated endpoints")] = None,
) -> list[dict]:
    """Cross-reference slow endpoints with missing cache headers and suggest fixes."""
    slow = app.call("slow-endpoints", base_url=base_url, threshold_ms=threshold_ms, auth_token=auth_token).unwrap()
    uncached = app.call("cache-audit", base_url=base_url, auth_token=auth_token).unwrap()
    uncached_paths = {e["path"] for e in uncached if not e.get("has_cache_control")}
    suggestions = []
    for endpoint in slow:
        if endpoint["path"] in uncached_paths:
            suggestions.append({
                "path": endpoint["path"],
                "response_ms": endpoint["response_ms"],
                "suggestion": "Add Cache-Control header — this endpoint is slow and uncached",
                "priority": "high",
            })
    return suggestions
```

**What the agent learned from the four previous sessions:**
- Auth tokens are needed (session 2 failed without them)
- Cache-Control isn't the only caching header — ETag and Last-Modified matter too (session 3 refinement)
- The combined analysis (`suggest-fixes`) is the most common request (sessions 3 and 4)
- The threshold should be configurable, not hardcoded (session 1 used 500ms, session 4 used 300ms)

#### Phase 4: The Feedback Loop (Week 6)

Dana adds api-audit to her MCP config. Next time she asks:

> **Dana:** "Check our staging API health"
>
> **Claude Code:** *(reads api-audit SKILL.md, sees suggest-fixes as the combined analysis)*
> *(invokes api-audit suggest-fixes https://staging.example.com --auth-token $API_TOKEN --json)*
>
> "Found 3 endpoints that are both slow and uncached:
>
> | Endpoint | Response Time | Suggestion |
> |---|---|---|
> | `/api/v2/reports/summary` | 1,240ms | Add Cache-Control — response changes daily at most |
> | `/api/v2/search` | 890ms | Add Cache-Control with short TTL — results change frequently |
> | `/api/v2/org/members` | 620ms | Add Cache-Control — membership changes infrequently |
>
> The `/reports/summary` endpoint is the highest priority — it's the slowest and the response is highly cacheable."

Dana never told the agent about the tool. The agent built the tool, and now a future instance of the agent uses it. **The knowledge survived the session boundary** — crystallized from ephemeral conversation into a permanent, discoverable, structured skill.

#### Phase 5: Another Engineer Finds It (Month 2)

Dana's colleague Carlos is working on a different service:

> **Carlos:** "I think our payment API has some slow endpoints, can you check?"
>
> **Claude Code:** *(sees api-audit in MCP, reads its schema)* "I have the `api-audit` tool available. Want me to run a combined analysis on the payment API?"

Carlos didn't know the tool existed. The agent discovered it, understood it from the schema, and offered it as a solution.

### Emergent Artifacts

| Type | Artifact |
|---|---|
| Tools | `api-audit slow-endpoints`, `api-audit cache-audit`, `api-audit suggest-fixes` |
| Skill | Combined analysis workflow in SKILL.md |
| Resource | `api-audit://latest/{service}` (cached last analysis result) |
| Pattern | Agent as tool author — session knowledge crystallized into permanent skill |

### Key Interactions

| Given | When | Then |
|---|---|---|
| Agent has done the same analysis 4 times | Developer asks for it a 5th time | Agent proposes creating a reusable tool |
| Developer approves tool creation | Agent generates the tool | Tool incorporates auth handling (from session 2 failure), multiple cache headers (from session 3 refinement), and configurable threshold (from session 4 difference) |
| Tool is registered in MCP config | A different engineer asks about API performance | Agent discovers the tool and offers to use it |
| `suggest-fixes` returns an empty list | Developer asks for slow endpoint analysis | Agent reports "all endpoints are within threshold" — structured empty response, not silence |
| `slow-endpoints` returns errors for authenticated endpoints | Auth token not provided | Agent sees the structured error with `field: "auth_token"` and asks the user for the token |

---

## Scenario 5: The New Hire Onboarding Experience

### Persona
**Priya**, a new hire who joined the team two days ago. She's an experienced developer but unfamiliar with the team's internal tools, deployment process, and codebase conventions.

### Job to Be Done
*When I start a new job, I want to be productive quickly so I can contribute to the team and feel like I belong.*

### Context
Priya's team has six internal tooli apps, a detailed CLAUDE.md, and established workflows. The previous onboarding process involved a 40-page Confluence doc that was always out of date. Most people learned by asking colleagues, who were often busy.

### Journey

#### Phase 1: The First Task (Day 3)

Priya is assigned her first bug fix. She needs to find the relevant service, understand the error, fix it, and deploy.

> **Priya:** "I've been assigned JIRA-4521 — a null pointer exception in the order service. Where do I start?"
>
> **Claude Code:** *(reads CLAUDE.md, sees available tools and workflows)*
> "Let me help you investigate. I'll use the team's log analysis tool to find the error."
>
> *(invokes loggrep errors /var/log/order-service/ --since 2026-02-18 --level error --json)*
>
> "Found the NPE. It's in `OrderProcessor.java:142` — the `customer.address` field is null when processing international orders. Here's the stack trace and the 3 most recent occurrences."
>
> *(reads the code at the location)*
>
> "The fix is straightforward — add a null check before accessing `customer.address.country`. Want me to write the fix?"

Priya didn't need to know that `loggrep` exists, how to use it, what flags to pass, or where the logs are stored. The agent handled all of that because the tool's schema described it and the CLAUDE.md told the agent when to use it.

#### Phase 2: The First Deployment (Day 3, continued)

> **Priya:** "The fix looks good. How do I deploy this?"
>
> **Claude Code:** "This team uses a multi-step deployment process. I'll walk you through it — the tools handle most of it automatically."
>
> *(follows the deployment workflow from CLAUDE.md)*
> *(invokes schema-check validate — no migrations, skips quickly)*
> *(invokes deploy-pilot canary order-service v1.7.2)*
> *(invokes health-check watch order-service --duration 5m)*
>
> "Canary is healthy. Here's what happened at each step:
> 1. Schema check: No DB migrations in this PR, so validation passed immediately
> 2. Canary deploy: Running at 5% traffic with your fix
> 3. Health check: Error rate dropped from 0.4% to 0.01% — your fix is working
>
> Ready to promote to full traffic. Should I proceed?"

**Given** Priya has never deployed before on this team,
**When** she asks how to deploy,
**Then** the agent follows the team's documented workflow end-to-end, explaining each step as it goes — acting as both tool operator and onboarding guide simultaneously.

#### Phase 3: Building Confidence (Week 2)

By her second week, Priya starts using the tools directly:

```bash
loggrep errors /var/log/order-service/ --since "2h ago" --json | jq '.result[] | .message'
```

She didn't read a tutorial. She learned the CLI from watching the agent use it — the agent's invocations served as live examples. When she forgets a flag:

> **Priya:** "How do I filter loggrep results by request ID?"
>
> **Claude Code:** *(invokes loggrep timeline --schema)*
> "Use `loggrep timeline <path> --request-id <id>`. The timeline command reconstructs the event sequence for a specific request."

### Emergent Artifacts

| Type | Artifact |
|---|---|
| Skill | Reusable onboarding workflow — agent operates tools and explains each step |
| Contract | CLAUDE.md guardrails visible to both agent and human from day 1 |
| Pattern | Agent as live teacher — invocations double as examples |

### What Emerged

The tools and CLAUDE.md together became the onboarding system. Priya never read the 40-page Confluence doc. Instead:
- The agent showed her how things work by doing them
- The tool schemas gave the agent (and Priya) accurate information about every flag and option
- The CLAUDE.md workflows meant Priya followed the same process as a 5-year veteran on day 3
- The structured output meant the agent could explain what happened at each step

### Key Interactions

| Given | When | Then |
|---|---|---|
| Priya has never used loggrep | She asks about a production error | Agent uses loggrep on her behalf and presents the results in context |
| Priya has never deployed on this team | She asks how to deploy | Agent follows the full deployment workflow, explaining each step |
| Priya wants to learn the CLI directly | She asks about a specific flag | Agent shows the schema and gives a concrete example |
| Priya makes a mistake in a manual command | She passes a wrong flag | Tool returns a structured error with `suggestion.fix` that tells her the correct flag |

---

## Scenario 6: The Security Audit Workflow

### Persona
**Riku**, a security engineer at a fintech company. **The Agent** operates under strict capability constraints set by the compliance team.

### Job to Be Done
*When we use third-party tools in our development process, I want to control exactly what they can access so we maintain our security posture and regulatory compliance.*

### Context
The company uses several tooli apps in their Claude Code environment. Regulatory requirements mandate that tools can only access what they explicitly declare, and that access is logged. The security team needs to enforce this without making developers' lives harder.

### Journey

#### Phase 1: Capability Lockdown

Riku sets a company-wide environment variable in the CI and development environments:

```bash
export TOOLI_ALLOWED_CAPABILITIES="fs:read,net:read,db:read"
```

This runs tooli in STRICT mode. Any tool that declares capabilities outside the allowlist is blocked at invocation time.

#### Phase 2: The Block Event

A developer installs a new tool that writes temporary files:

```python
@app.command(capabilities=["fs:read", "fs:write"])
def analyze(path: str) -> dict:
    """Analyze code and write report to disk."""
    ...
```

**Given** `TOOLI_ALLOWED_CAPABILITIES` does not include `fs:write`,
**When** the developer (or Claude Code) tries to invoke the tool,
**Then** tooli blocks the invocation and returns a structured error:

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

The developer doesn't get a cryptic permission error. They get a structured message that tells them exactly what's blocked and who to talk to.

The agent handles this gracefully too:

> **Claude Code:** "The `code-analyzer` tool needs `fs:write` permission, but your environment only allows `fs:read`, `net:read`, and `db:read`. This is a security policy restriction — I can't override it. You'll need to request `fs:write` approval from your security team, or check if the tool has a read-only analysis mode."

#### Phase 3: Audit Trail

Riku reviews the telemetry data. Every tooli invocation includes caller metadata:

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

**Given** tooli records invocation metadata with caller and capability information,
**When** Riku runs an audit report,
**Then** he can see exactly which tools were invoked, by which agent, with which capabilities, and which were blocked — all from structured telemetry, not log scraping.

#### Phase 4: Selective Unlocking

After reviewing the tool's source code, Riku approves `fs:write` for the project. The developer's workflow resumes without any code changes to the tool.

### Emergent Artifacts

| Type | Artifact |
|---|---|
| Tools | Any tooli app with declared capabilities |
| Resource | `security://audit-log` (structured invocation log for compliance review) |
| Contract | `TOOLI_ALLOWED_CAPABILITIES` as an environment-level security policy |
| Pattern | Declare-then-enforce — tools declare needs, environment declares limits, gap produces structured errors |

### Key Interactions

| Given | When | Then |
|---|---|---|
| STRICT mode with limited allowlist | Tool requests `fs:write` | Invocation blocked with structured error explaining the gap |
| Agent receives a capability denial | Agent is in the middle of a workflow | Agent explains the block to the user and suggests contacting security team |
| Telemetry is enabled | Any tool is invoked (blocked or not) | Invocation recorded with caller, capabilities, and outcome |
| Security team approves new capability | Environment variable updated | Tool works on next invocation — no code changes needed |

---

## Scenario 7: The CI/CD Pipeline Integration

### Persona
**Build System**, a GitHub Actions workflow that runs on every pull request. **Developer** who asks Claude Code about CI failures.

### Job to Be Done
*When a PR is opened, I want automated quality checks that produce machine-readable results so the CI pipeline can make pass/fail decisions and leave actionable PR comments.*

### Context
Most CI linters output unstructured text that CI pipelines parse with regex. When a new version changes the output format, the parser breaks. The team wants CI checks that produce stable, structured output.

### Journey

#### Phase 1: Structured CI Steps

The team's CI workflow calls tooli apps with `TOOLI_CALLER=github-actions`:

```yaml
# .github/workflows/ci.yml
jobs:
  quality:
    steps:
      - name: Check documentation
        run: |
          TOOLI_CALLER=github-actions mdlint check docs/ --json > mdlint-results.json

      - name: Audit licenses
        run: |
          TOOLI_CALLER=github-actions license-scan audit --json > license-results.json

      - name: Validate schemas
        run: |
          TOOLI_CALLER=github-actions schema-check validate ./migrations --json > schema-results.json

      - name: Post results
        run: python scripts/post_ci_results.py
```

Because every tool produces `{ok, result, meta}`, the result-posting script is 20 lines:

```python
import json, sys

for results_file in sys.argv[1:]:
    data = json.load(open(results_file))
    if not data["ok"]:
        print(f"::error::{data['error']['message']}")
        if data["error"].get("suggestion"):
            print(f"::notice::Fix: {data['error']['suggestion']['fix']}")
```

No per-tool parsing. No regex. The envelope format is the API contract.

#### Phase 2: Agent-Aware CI Feedback

When CI fails, developers ask Claude Code about it:

> **Developer:** "CI failed on my PR, what's wrong?"
>
> **Claude Code:** *(reads the CI output, recognizes tooli envelope format)*
> "The `license-scan` step failed:
>
> Dependency `chart-renderer` v3.0 has changed its license from MIT to BSL-1.1 (Business Source License). This is incompatible with your project's MIT license.
>
> The tool suggests: 'Pin to `chart-renderer` v2.9 (MIT) or evaluate the BSL-1.1 terms with your legal team.'
>
> Want me to pin the dependency to v2.9?"

#### Phase 3: Schema Drift Detection

As the toolchain evolves, CI also validates that tool schemas haven't changed in breaking ways:

**Given** a PR changes a command's parameter signature,
**When** CI runs `mytool --schema` and compares to the committed schema,
**Then** schema drift is detected and flagged — preventing silent breaks in agent workflows that depend on the old signature.

### Emergent Artifacts

| Type | Artifact |
|---|---|
| Tools | Same tools used by humans and agents, now also by CI |
| Pattern | Envelope format as CI contract — one parser for all tools |
| Resource | CI result artifacts as structured JSON, readable by agents |
| Contract | `TOOLI_CALLER=github-actions` distinguishes CI from human/agent usage in telemetry |

### Key Interactions

| Given | When | Then |
|---|---|---|
| CI runs tools with `--json` | A step fails | CI posts the structured error message, not a wall of text |
| Tool provides `suggestion.fix` | CI formats the result | Fix suggestion appears as a GitHub annotation on the PR |
| `TOOLI_CALLER=github-actions` | Tool is invoked in CI | Caller metadata in telemetry shows CI usage patterns |
| Developer asks agent about CI failure | Agent reads structured CI output | Agent extracts the error and suggestion directly from the envelope |
| PR changes command signature | CI compares schema to baseline | Schema drift detected and flagged before merge |

---

## Scenario 8: The Cross-Team Tool Marketplace

### Persona
**Engineering Org** with 15 teams. Each team has built 2-3 tooli apps for their domain. **DevEx Team** maintains a shared tool registry.

### Job to Be Done
*When I need a capability that another team has already built, I want to discover and use their tool without reading their codebase so I don't waste time rebuilding something that exists.*

### Context
Teams have been building tooli apps organically. The data team has a `data-lint` tool. The frontend team has a `bundle-audit` tool. The infra team has `tf-check` for Terraform validation. Nobody knows what other teams have built.

### Journey

#### Phase 1: The Discovery Problem

A developer on the API team needs to validate some CSV output:

> **Developer:** "I need to validate that our API's CSV export has the right columns and types"
>
> **Claude Code:** "I don't have a CSV validation tool available in this project's MCP config. Let me check what's available."
>
> *(invokes tool-registry search "csv validate" --json)*
>
> "Found `data-lint` from the Data Engineering team. It has a `validate-csv` command that checks column types, required fields, and format compliance. It's read-only and safe to run. Want me to add it to your MCP config?"

#### Phase 2: The Registry as a Skill

The DevEx team built the registry itself as a tooli app:

```python
# tool_registry/app.py
app = Tooli(name="tool-registry", description="Internal tool discovery service", version="1.0.0")

@app.command(
    annotations=ReadOnly,
    capabilities=["net:read"],
)
def search(
    query: Annotated[str, Argument(help="Search query for tool discovery")],
    team: Annotated[str | None, Option(help="Filter by team")] = None,
) -> list[dict]:
    """Search the internal tool registry for matching tools."""
    ...

@app.command(
    annotations=ReadOnly,
    capabilities=["net:read"],
)
def info(
    tool_name: Annotated[str, Argument(help="Tool name to get details for")],
) -> dict:
    """Get detailed information about a tool including schema and usage examples."""
    ...
```

The registry indexes every tooli app's manifest (`generate-skill --format manifest`), making tool schemas, capabilities, and examples searchable across the org.

#### Phase 3: Agent-Mediated Tool Discovery

The pattern becomes: developer describes a problem → agent searches registry → agent installs and uses the tool — all in one session.

> **Developer:** "I need to check if our Terraform changes will affect the staging environment"
>
> **Claude Code:** *(searches tool-registry for "terraform")*
> "The Infrastructure team has `tf-check` with a `plan-audit` command that analyzes Terraform plan output for risky changes. It declares `capabilities: ["fs:read"]` — read-only, safe to run."
>
> *(adds tf-check to MCP config, invokes tf-check plan-audit ./terraform/plan.json --json)*
>
> "The Terraform plan includes 2 resource deletions and 1 security group modification. `tf-check` flagged the security group change as high-risk: it opens port 22 to 0.0.0.0/0. Want me to show the details?"

### Emergent Artifacts

| Type | Artifact |
|---|---|
| Tools | `tool-registry search/info`, plus every team's registered tools |
| Resource | `registry://tools` (complete tool catalog), `registry://tool/{name}` (individual tool metadata) |
| Skill | "Discover → Install → Use" workflow, entirely agent-mediated |
| Pattern | Org-wide tool vocabulary from shared naming conventions and capability tags |

### Key Interactions

| Given | When | Then |
|---|---|---|
| Developer describes a need | No matching tool in current MCP config | Agent searches tool-registry for matching capabilities |
| Registry returns a matching tool | Agent reads the tool's capabilities and annotations | Agent evaluates safety (ReadOnly = safe to try) and offers to install |
| Tool is installed mid-session | Developer's original request is still pending | Agent uses the newly installed tool to complete the original task |
| Registry returns multiple matches | Agent needs to choose | Agent compares capabilities, annotations, and team ownership to recommend the best fit |
| Two repos have similarly named commands | Agent must disambiguate | Agent explains the difference by capability and context, recommends one |

---

## Scenario 9: The Multi-Agent War Room

### Persona
**Release Lead** coordinating a complex deployment. Multiple specialized Claude Code agents (subagents) each operate a different tool domain. An **Orchestrator** agent coordinates the overall workflow.

### Job to Be Done
*When we're deploying a critical release that touches multiple services, I want specialized agents handling each domain so that no single agent needs to hold the full context and each can focus on what it does best.*

### Context
The v5.0 release involves database migrations, a new API version, updated feature flags, and a security patch. No single agent can hold all the context efficiently. The team uses Claude Code's subagent capability to divide the work.

### Journey

#### Phase 1: The Orchestrator Delegates

> **Release Lead:** "Deploy v5.0 to production. This release has DB migrations, a new API, and a security patch."
>
> **Orchestrator Agent:** "This is a multi-domain release. I'll coordinate specialized agents for each area."
>
> *(delegates to Security Agent)* "Run a vulnerability scan on the v5.0 dependencies."
> *(delegates to Infra Agent)* "Validate the DB migrations against the live schema."
> *(delegates to Config Agent)* "Check feature flag and config state for the v5.0 release."

#### Phase 2: Agents Use Tools Independently

Each subagent invokes tools from its domain using the Python API for speed:

> **Security Agent:** *(running `vuln-scan audit --json` via `app.call()`)* "Found a high-priority CVE in `xml-parser` v2.3. The tool's handoff metadata points to `patch-pilot` for automated patching."
>
> **Infra Agent:** *(running `schema-check validate ./migrations --json`)* "Migrations are safe — two additive columns, no locks."
>
> **Config Agent:** *(running `feature-flags check v5-api --json` and `config-vault diff --json`)* "Feature flag `v5-api` is OFF in production as expected. No config drift."

#### Phase 3: The Orchestrator Synthesizes

> **Orchestrator Agent:** "Security found a CVE. Let me check if it's blocking."
>
> *(reads Security Agent's result, sees the `handoffs` metadata pointing to `patch-pilot`)*
>
> "The CVE in `xml-parser` has an available patch. @Infra-Agent, apply the patch using `patch-pilot` via the Python API — stay in-process for speed, don't shell out."
>
> **Infra Agent:** *(running `app.call("apply-patch", package="xml-parser", target="2.3.1")`)* "Patch applied. `xml-parser` updated to v2.3.1."
>
> **Orchestrator Agent:** "All checks clear. Proceeding with canary deployment."
>
> *(to Release Lead)* "Pre-flight complete. CVE patched, migrations validated, config verified. Ready to start the canary. Should I proceed?"

#### Phase 4: Human Decision Point

The release lead reviews the summary and approves. The orchestrator delegates the actual deployment to the Infra Agent, which follows the standard deployment workflow from CLAUDE.md.

### Emergent Artifacts

| Type | Artifact |
|---|---|
| Tools | `vuln-scan`, `patch-pilot`, `schema-check`, `feature-flags`, `config-vault`, `deploy-pilot` |
| Skill | "Multi-domain release" orchestration workflow |
| Resources | `deploy://status/{service}`, `security://scan/latest`, `schema://diff/{service}` |
| Pattern | Agent delegation — orchestrator reads handoff metadata to route between subagents |

### What Emerged

Multi-agent coordination becomes deterministic and safe. The orchestrator doesn't hallucinate workflows — it reads handoff metadata from each tool to decide what happens next. The Python API (`app.call()`) keeps inter-agent communication in-process, avoiding the overhead of CLI parsing. Each agent operates within its domain's tools and capabilities, and the human stays at the decision points.

### Key Interactions

| Given | When | Then |
|---|---|---|
| Release touches multiple domains | Release lead requests deployment | Orchestrator delegates to specialized subagents |
| `vuln-scan` returns a CVE with handoff to `patch-pilot` | Orchestrator reads the result | Orchestrator routes the patching task to Infra Agent using the handoff metadata |
| All pre-flight checks pass | Orchestrator synthesizes results | Orchestrator presents summary and asks for human approval before deploying |
| One subagent finds a blocking issue | Orchestrator is coordinating | Orchestrator halts the pipeline and explains which domain found the problem |
| Subagents use `app.call()` instead of CLI | High-frequency inter-agent calls | In-process invocation avoids CLI parsing overhead, stays typed |

---

## Scenario 10: The Global Skill Mesh

### Persona
**Architect** building a production LangGraph workflow that needs to use tools originally built for Claude Code. **Open-source author** whose tooli app is used across multiple agent frameworks.

### Job to Be Done
*When I've built a tool that works in Claude Code, I want it to work everywhere — LangChain, OpenAI Agents, Google ADK — without rewriting it for each framework.*

### Context
A startup has built their internal tooling on tooli and Claude Code. They're expanding to a multi-framework architecture where some workflows run on LangChain, some on OpenAI, and some stay on Claude Code. They don't want to maintain four copies of every tool.

### Journey

#### Phase 1: The Portability Moment

> **Architect:** "We need our `cloud-provisioner` tools to work inside our LangChain-based internal dashboard."
>
> **Claude Code:** "I can generate framework-specific wrappers for that. Let me show you what's available."
>
> ```bash
> cloud-provisioner export --target langchain > langchain_tools.py
> cloud-provisioner export --target openai > openai_tools.py
> cloud-provisioner export --target adk > adk_agent.yaml
> cloud-provisioner export --target python > typed_api.py
> ```
>
> "The LangChain export generates `@tool`-decorated functions that call the tooli app underneath. The OpenAI export generates `@function_tool` wrappers. The ADK export generates a YAML agent config that uses MCP. And the Python export generates typed wrapper functions with full type annotations."

#### Phase 2: Universal Documentation

```bash
cloud-provisioner generate-agents-md > AGENTS.md
```

The AGENTS.md follows the GitHub Copilot / OpenAI Codex convention, making the tool discoverable by any agent that reads repository documentation — not just Claude Code.

#### Phase 3: The Mesh Forms

The same tool is now consumed via:
- **Claude Code:** MCP server, direct SKILL.md-guided invocation
- **LangChain dashboard:** Generated `@tool` wrappers calling `app.call()`
- **OpenAI agents:** Generated `@function_tool` wrappers with subprocess calls
- **Google ADK agent:** YAML config pointing to `mcp serve --transport stdio`
- **GitHub Copilot:** AGENTS.md documentation for discoverability

The tool logic lives in one place. The interface layer is generated.

### Emergent Artifacts

| Type | Artifact |
|---|---|
| Tools | Any tooli app with `export` builtin |
| Skill | Cross-framework skill — one definition, multiple consumers |
| Resources | `skill://` resources accessible via MCP from any framework |
| Docs | AGENTS.md (universal), SKILL.md (Claude), CLAUDE.md (Claude Code) |
| Pattern | "Write once, export everywhere" — tools as universal assets |

### What Emerged

Tools become **framework-agnostic assets**. The tool author writes one Python function with tooli decorators. The `export` command generates the glue code for every framework. The AGENTS.md makes it discoverable by any agent that can read a repository. This is the Global Skill Mesh — tools portable across any agent, any platform, any time.

### Key Interactions

| Given | When | Then |
|---|---|---|
| Tooli app with multiple commands | Architect runs `export --target langchain` | Generated Python file has `@tool` wrappers for each command with proper type annotations |
| Generated wrappers use `app.call()` in import mode | LangChain agent invokes a tool | In-process call with `TOOLI_CALLER=langchain`, no subprocess overhead |
| Generated wrappers use subprocess in CLI mode | OpenAI agent invokes a tool | Subprocess call with `--json` and `TOOLI_CALLER=openai-agents-sdk` |
| AGENTS.md generated | GitHub Copilot reads the repo | Copilot discovers tools from AGENTS.md without any framework-specific setup |
| Tool author updates a command | Re-export generated | Wrappers regenerate — all frameworks get the update |

---

## Scenario 11: Customer Support Workflows

### Persona
**Leila**, a support engineer resolving customer issues. She uses internal diagnostic and remediation tools to investigate account problems.

### Job to Be Done
*When a customer reports an issue, I want to diagnose the root cause and apply a safe remediation so that I resolve tickets quickly without accidentally making things worse.*

### Context
Repeated support tickets follow similar patterns: account locked, quota exceeded, payment failed, data sync stalled. Each pattern has a diagnostic and a remediation step. The remediation is often destructive (resetting state, clearing caches) and must be audited for compliance.

### Journey

#### Phase 1: The Diagnostic Tools

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

#### Phase 2: Agent-Guided Triage

> **Leila:** "Customer acme-corp says they can't upload files"
>
> **Claude Code:** *(invokes acct-diagnose acme-corp --json)*
> "Root cause: storage quota exceeded. Account `acme-corp` is at 100.0% of their 10GB limit. They have 847MB in orphaned temporary files from a failed bulk import."
>
> "Two options:
> 1. `quota-reset acme-corp --reason 'orphaned temp files from bulk import'` — clears the orphaned files (Destructive, requires your confirmation)
> 2. Ask the customer to clean up manually
>
> Option 1 would free 847MB immediately. Should I proceed?"

**Given** `quota-reset` is marked `Destructive`,
**When** the agent proposes it,
**Then** it requires Leila's explicit confirmation and a reason string — which becomes part of the audit trail.

> **Leila:** "Yes, go ahead"
>
> **Claude Code:** *(invokes acct-diagnose quota-reset acme-corp --reason "orphaned temp files from bulk import" --json)*
> "Quota reset complete. 847MB freed. New usage: 91.5% (9.15GB / 10GB). The customer should be able to upload files now."

#### Phase 3: The Runbook Becomes a Skill

```markdown
## Support Workflows

### Storage Quota Issues
1. `acct-diagnose <account_id>` — Identify root cause
2. If orphaned files: `quota-reset <account_id> --reason <reason>` (requires confirmation)
3. If legitimate usage: suggest plan upgrade to customer

### Rules
- ALWAYS run `acct-diagnose` before any remediation
- ALWAYS provide a reason for `quota-reset` (audit requirement)
- NEVER reset quota without understanding root cause
```

### Emergent Artifacts

| Type | Artifact |
|---|---|
| Tools | `acct-diagnose`, `quota-reset`, `usage-audit` |
| Skill | "Storage Quota Issues" runbook in CLAUDE.md |
| Resource | `support://account/{id}/state` (current account diagnostics) |
| Contract | Mandatory `reason` field on all destructive support operations for audit trail |

### Key Interactions

| Given | When | Then |
|---|---|---|
| Customer reports upload failure | Leila describes the symptom | Agent runs `acct-diagnose` and identifies root cause |
| Diagnosis shows orphaned files | Agent proposes `quota-reset` | Agent explains it's destructive, requires confirmation and reason |
| Unknown account ID | Agent runs `acct-diagnose` | Structured error with `field: "account_id"` tells agent the exact format expected |
| Reset completed | Agent confirms the action | Result includes audit trail: actor, reason, timestamp, before/after state |

---

## Scenario 12: Versioned Evolution Without Agent Breakage

### Persona
**Tool Maintainer** who needs to evolve a command's interface without breaking the agents and CI pipelines that depend on it.

### Job to Be Done
*When I need to make breaking changes to a tool, I want a safe migration path so that existing agent automations don't fail unexpectedly.*

### Context
The `data-export` tool's `run` command needs to replace its `--format csv` flag with a more flexible `--output-format csv|parquet|json` flag. Dozens of agent workflows and CI pipelines pass `--format csv`. A sudden rename would break them silently.

### Journey

#### Phase 1: Versioned Deprecation

The maintainer introduces a new command version and marks the old flag deprecated:

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
    """Export data from source."""
    actual_format = output_format or format
    ...
```

#### Phase 2: Agent Auto-Migration

**Given** a command has deprecation metadata,
**When** Claude Code reads the schema and sees `"deprecated": "Use --output-format instead of --format"`,
**Then** the agent uses the new flag automatically:

> **Claude Code:** *(reading schema for `data-export run`)* "I see `--format` is deprecated in favor of `--output-format`. I'll use the new flag."
>
> *(invokes `data-export run source.db --output-format parquet --json`)*

Old agents that haven't been updated still work — the deprecated flag still functions, it just emits a warning in the envelope metadata.

#### Phase 3: CI Detection

CI runs schema validation and detects the deprecation:

```json
{
  "warnings": [
    "Parameter --format is deprecated since v2.0.0. Use --output-format instead."
  ]
}
```

The CI pipeline flags this as a warning (not a failure), giving teams time to migrate.

#### Phase 4: Removal With Safety Net

When the maintainer removes the old flag entirely:

**Given** an old agent invocation uses `--format`,
**When** the flag no longer exists,
**Then** the tool returns a structured error with migration instructions — not a cryptic "unrecognized option" error:

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

### Emergent Artifacts

| Type | Artifact |
|---|---|
| Pattern | Versioned deprecation with structured migration guidance |
| Contract | Schema includes deprecation metadata readable by agents and CI |
| Resource | `tool://schema/v1/...`, `tool://schema/v2/...` for version-aware discovery |

### Key Interactions

| Given | When | Then |
|---|---|---|
| Command has deprecation metadata | Agent reads schema | Agent uses the new flag automatically |
| Old agent uses deprecated flag | Command still supports it | Warning in envelope, command still works |
| CI detects deprecated flag usage | Schema check runs | Warning flagged, not blocking, with migration instructions |
| Deprecated flag is removed | Old agent sends `--format` | Structured error with exact replacement, not cryptic CLI error |

---

## The Patterns

### What Emerges Across All Twelve Scenarios

#### 1. Tools Start as Solutions to Real Problems
Nobody sets out to build "an ecosystem." Maya builds loggrep because she's tired of re-deriving grep pipelines at 3am. Dana's api-audit exists because she kept asking the same question. The platform team's tools each solve one specific operational pain point.

#### 2. Structured Output Is the Universal Connector
The `{ok, result, meta}` envelope isn't just a nice format — it's the API contract that makes everything else possible. Agents parse it. CI pipelines parse it. Other tools parse it. When output is structured, composition is free.

#### 3. Metadata Enables Discovery Without Documentation
Schemas tell agents what arguments a tool accepts. Capabilities tell agents (and security systems) what permissions are needed. Annotations tell agents whether it's safe to run without asking. Handoffs tell agents what to do next. Deprecation metadata tells agents how to migrate. The tool describes itself.

#### 4. SKILL.md Captures Workflows, Not Just Commands
Individual commands are useful. Workflows — the knowledge of which commands to run in what order and why — are transformative. SKILL.md and CLAUDE.md are where tribal knowledge becomes institutional knowledge.

#### 5. Resources Reduce Repetition
When agents frequently re-fetch the same data, promoting it to an MCP resource (`loggrep://recent-errors`, `deploy://status/{service}`) eliminates redundant command execution. The optimization is: resource-first, command-second.

#### 6. Composition Is Emergent, Not Designed
The open-source tools in Scenario 3 were never designed to work together. The deployment tools in Scenario 2 were designed independently and connected through CLAUDE.md. The agent figures out how to combine tools from their metadata and the documented workflows. No orchestration framework required.

#### 7. The Agent Operates at Multiple Levels
- **Consumer:** Discovers and invokes existing tools (all scenarios)
- **Operator:** Follows documented workflows, making decisions at each step (Scenarios 2, 5, 11)
- **Teacher:** Shows users how tools work by using them (Scenario 5)
- **Author:** Creates new tools from observed patterns (Scenario 4)
- **Gatekeeper:** Enforces safety rules and asks for confirmation before irreversible actions (Scenarios 2, 6, 11)
- **Orchestrator:** Delegates to specialized subagents across tool domains (Scenario 9)

#### 8. The Human Stays in Control
In every scenario, the human decides which tools to install, what workflows to document, when to approve destructive actions, and what capabilities to allow. The agent amplifies human capability without replacing human judgment.

### The Tool Lifecycle

```
1. PAIN        Ad-hoc script       • One-off, unstructured, session-bound
                    │
2. COMMAND     tooli app            • --json envelope, schema, capabilities, handoffs
                    │
3. INVOCATION  MCP / CLI / API      • Agent starts calling it, structured mode
                    │
4. REFINEMENT  Iteration            • Usage data and failures drive improvements
                    │
5. SKILL       SKILL.md + CLAUDE.md • Workflows, guardrails, agent-operated
                    │
6. RESOURCE    MCP resource URIs    • Low-token direct retrieval, cached state
                    │
7. MESH        export + AGENTS.md   • Cross-framework, cross-team, searchable
```

Each step is optional. A tool can stay personal forever. But when it's useful enough to share, the framework makes sharing frictionless — because the structured interface was there from the first `@app.command()`.

---

## The Vision

1. **Skills** are the shared language between humans and machines.
2. **Resources** are live windows into the project's state.
3. **Protocols** (the tooli envelope, schemas, capabilities) are the connective tissue that ensures safety, structure, and speed.
4. **PTC** is not chatting with an AI — it is the orchestrated movement of a capable, multi-agent team, operating tools with precision, governed by human intent.

---

## Checklist for Future Scenario Authors

Use this checklist before adding new scenarios to this file:

1. Does the scenario have a named persona with a clear Job to Be Done?
2. Is the journey multi-phase, showing evolution over time (not just a snapshot)?
3. Are acceptance criteria observable and testable (Given/When/Then)?
4. Are failure paths and guardrails explicitly dramatized (not just mentioned)?
5. Does the scenario identify emergent MCP resources, not just tool commands?
6. Does it show concrete code, JSON output, or agent dialogue (not just abstract description)?
7. Is the PTC value explicit — speed, safety, quality, onboarding, compliance, or scale?
8. Does the scenario introduce something the other scenarios don't already cover?

---

## Backlog of Scenario Candidates

1. Compliance evidence collection for audit season (SOC 2 artifact gathering)
2. Cost optimization agent for cloud spend anomalies
3. Data-quality repair flows with preview and rollback
4. Incident postmortem generation from timeline resources
5. Multi-tenant policy simulation before feature rollout

---

## References

Scenario structure informed by:
- [User Stories: Best Practices & Examples (Inflectra)](https://www.inflectra.com/Ideas/Topic/User-Stories.aspx)
- [Given-When-Then Acceptance Criteria (ProductMonk)](https://www.productmonk.io/p/given-when-then-acceptance-criteria)
- [Jobs to Be Done Framework (Product School)](https://productschool.com/blog/product-fundamentals/jtbd-framework)
- [Writing Good User Stories: 10 Tips (Beyond the Backlog)](https://beyondthebacklog.com/2025/04/24/writing-good-user-stories/)
- [Acceptance Criteria for User Stories (AltexSoft)](https://www.altexsoft.com/blog/acceptance-criteria-purposes-formats-and-best-practices/)
- [Journey Mapping 101 (Nielsen Norman Group)](https://www.nngroup.com/articles/journey-mapping-101/)
- [Gherkin Scenarios (Business Analysis Experts)](https://www.businessanalysisexperts.com/gherkin-user-stories-given-when-then-examples/)
