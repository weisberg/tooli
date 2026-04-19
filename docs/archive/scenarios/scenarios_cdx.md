# Tooli + Claude Code: Unified PTC Scenarios (Master Document)

This is the canonical combined scenarios document for Tooli in Claude Code Project Team Collaboration (PTC).

It is designed to combine:

1. Narrative realism and journey depth.
2. Strategic clarity for platform-scale adoption.
3. Testable acceptance criteria for engineering execution.

---

## Document Goals

1. Keep all relevant scenarios in one source of truth.
2. Preserve the intent of existing scenario documents.
3. Standardize every scenario in a consistent, high-quality format.
4. Make each scenario usable by product, engineering, security, and documentation teams.

---

## Source Coverage Matrix

Every scenario from `scenarios_cc.md` and `scenarios_gm.md` is included below.

| Source File | Original Scenario | Covered In This Document |
|---|---|---|
| `scenarios_cc.md` | Scenario 1: The Solo Developer's Debugging Toolkit | Scenario 1 |
| `scenarios_cc.md` | Scenario 2: The Platform Team's Internal Toolchain | Scenario 2 |
| `scenarios_cc.md` | Scenario 3: The Open-Source Ecosystem Effect | Scenario 4 |
| `scenarios_cc.md` | Scenario 4: The Agent-Built Tool | Scenario 5 |
| `scenarios_cc.md` | Scenario 5: The New Hire Onboarding Experience | Scenario 6 |
| `scenarios_cc.md` | Scenario 6: The Security Audit Workflow | Scenario 3 |
| `scenarios_cc.md` | Scenario 7: The CI/CD Pipeline Integration | Scenario 7 |
| `scenarios_cc.md` | Scenario 8: The Cross-Team Tool Marketplace | Scenario 8 |
| `scenarios_gm.md` | Story 1: The Lifecycle of a Diagnostic Skill | Scenario 1 |
| `scenarios_gm.md` | Story 2: The Multi-Agent "War Room" | Scenario 2 |
| `scenarios_gm.md` | Story 3: The Autonomous Sentry | Scenario 3 |
| `scenarios_gm.md` | Story 4: The Agent as a Proactive Co-Architect | Scenario 5 |
| `scenarios_gm.md` | Story 5: The Global Skill Mesh | Scenario 10 |

Additional high-value scenarios introduced in prior `scenarios_cdx.md` are retained and expanded:

1. Resource-first subagent operations (Scenario 9).
2. Cross-repo contract hardening details inside Scenario 8.

---

## Scenario Format Standard

Each scenario uses the same structure:

1. Lineage: where it came from.
2. Persona and Job to Be Done.
3. Context and Journey.
4. Key Given/When/Then interactions.
5. Acceptance Criteria.
6. Emergent Skills and Resources.
7. PTC Value and Operational Signals.

---

## Shared PTC Lifecycle

1. Repeated work appears in developer or user activity.
2. A Tooli command is created with typed parameters and metadata.
3. Agents invoke commands via stable envelopes (`ok`, `result`, `error`, `meta`).
4. Workflow patterns become reusable skills in generated docs.
5. High-frequency reads become MCP resources.
6. CI and usage feedback refine contracts over time.

---

## Scenario 1: Diagnostic Skill Lifecycle

### Lineage
`scenarios_cc.md` Scenario 1 + `scenarios_gm.md` Story 1

### Persona
Maya, a backend on-call engineer.

### Job to Be Done
When incidents happen, I want fast, structured diagnosis so I can restore service without rebuilding shell pipelines.

### Context
Maya repeatedly runs ad hoc `grep`, `awk`, and `sed` commands and cannot reliably reproduce the same analysis.

### Journey
1. Maya and Claude Code create `ops-log errors`.
2. They add `ops-log timeline` and `ops-log correlate` after repeated requests.
3. The tool is exposed through MCP (`mcp serve --transport stdio`).
4. Workflow is codified in generated skill docs and reused by the team.

### Key Interactions (Given/When/Then)
1. Given `ops-log` is available in MCP, when Maya asks for last-hour errors, then agent invokes `ops-log errors --since ... --json`.
2. Given response items contain request IDs, when sequence analysis is needed, then agent invokes `ops-log timeline`.
3. Given trace IDs are available, when cross-service diagnosis is needed, then agent invokes `ops-log correlate`.

### Acceptance Criteria
1. Commands return stable structured output for both CLI and MCP paths.
2. Invalid filters produce actionable, retryable error payloads.
3. Generated docs capture the triage workflow in task-oriented order.

### Emergent Skills and Resources
- Skill: Incident triage.
- Resources: `ops-log://recent-errors`, `ops-log://request/{id}`.

### PTC Value and Operational Signals
- Faster MTTR.
- Fewer agent retries due to stable command contracts.

---

## Scenario 2: Multi-Agent Platform War Room

### Lineage
`scenarios_cc.md` Scenario 2 + `scenarios_gm.md` Story 2

### Persona
Jordan (platform lead), Alex (product engineer), Claude Code orchestrator.

### Job to Be Done
When deploying to production, I want deterministic sequencing and rollback behavior so release risk is controlled.

### Context
Schema checks, deployment commands, and health verification exist in separate tools and can be misordered.

### Journey
1. Team standardizes `schema-check`, `deploy-pilot`, and `health-watch`.
2. Metadata and handoffs define likely follow-up actions.
3. Orchestrator delegates specialized steps to subagents.
4. Python API calls are used for in-process orchestration where needed.

### Key Interactions (Given/When/Then)
1. Given pending migrations, when release begins, then `schema-check` runs before canary.
2. Given canary started, when watch window is active, then `health-watch` gates promotion.
3. Given degraded metrics, when thresholds are crossed, then rollback handoff is executed.

### Acceptance Criteria
1. Promotion is blocked if schema risk is unresolved.
2. Healthy canary is required before promotion.
3. Rollback path is deterministic and auditable.

### Emergent Skills and Resources
- Skill: Release promotion war-room workflow.
- Resources: `schema://diff`, `deploy://status`, `health://signals`.

### PTC Value and Operational Signals
- Lower production incident rate from deployment flow errors.
- Shorter coordination time across specialized agents.

---

## Scenario 3: Autonomous Sentry and Security Audit

### Lineage
`scenarios_cc.md` Scenario 6 + `scenarios_gm.md` Story 3

### Persona
Riku, security-focused platform engineer.

### Job to Be Done
When autonomous tools run potentially dangerous actions, I want enforceable guardrails and auditable behavior.

### Context
Destructive operations can be initiated by agents and must obey strict policy and approval controls.

### Journey
1. Commands are annotated with `Destructive` and capability declarations.
2. Strict policy mode blocks unsafe execution without approvals.
3. Agents run dry-run previews first.
4. Security audit reports are built from structured telemetry and policy outcomes.

### Key Interactions (Given/When/Then)
1. Given strict mode and missing approval, when destructive command executes, then action is blocked with explicit reason.
2. Given dry-run requested, when command executes, then plan is returned and no side effects occur.
3. Given approved execution, when command completes, then audit trail records actor, capability scope, and result.

### Acceptance Criteria
1. Policy enforcement occurs before mutative function body execution.
2. All blocked actions return machine-actionable remediation.
3. Security reporting can reconstruct allowed and denied attempts.

### Emergent Skills and Resources
- Skill: Safe mutation with HITL.
- Resources: `security://active-incidents`, `env-cleanup://pending-deletions`.

### PTC Value and Operational Signals
- Reduced unauthorized mutations.
- Clear compliance evidence for agent-driven actions.

---

## Scenario 4: Open-Source Ecosystem Composition

### Lineage
`scenarios_cc.md` Scenario 3

### Persona
Sam, open-source user combining tools from multiple authors.

### Job to Be Done
When preparing a release, I want multiple utility tools to compose reliably without custom glue code.

### Context
Tools come from different repositories and evolve independently.

### Journey
1. User installs several Tooli apps from package registries.
2. Each app is exposed to Claude Code through MCP.
3. Agent composes a release workflow across linting, license checks, optimization, and changelog generation.
4. Missing tool cases degrade gracefully rather than failing hard.

### Key Interactions (Given/When/Then)
1. Given multiple apps in MCP config, when user asks for release prep, then agent composes a multi-tool sequence.
2. Given one referenced tool missing, when sequence runs, then agent reports gap and continues with available tools.
3. Given dry-run support on mutative steps, when user requests preview, then agent shows planned changes first.

### Acceptance Criteria
1. Cross-tool composition uses structured outputs, not text scraping.
2. Missing dependencies are reported with actionable installation guidance.
3. Workflow remains robust under partial tool availability.

### Emergent Skills and Resources
- Skill: Release hygiene pipeline.
- Resources: tool-specific status resources (for example, `changelog://draft`).

### PTC Value and Operational Signals
- Faster release readiness.
- Lower error rate from ad hoc scripts.

---

## Scenario 5: Agent as Proactive Co-Architect

### Lineage
`scenarios_cc.md` Scenario 4 + `scenarios_gm.md` Story 4

### Persona
Priya (tech lead), Claude Code (co-architect).

### Job to Be Done
When repeated work appears, I want the agent to convert it into durable tooling so team throughput compounds.

### Context
Repeated manual analyses consume attention and are not shareable.

### Journey
1. Agent detects repeated task pattern across sessions.
2. Agent proposes a new Tooli app/command (`tooli init`, typed options, metadata).
3. Developer approves and reviews tests.
4. New command enters normal team workflows.

### Key Interactions (Given/When/Then)
1. Given repeated prompts, when threshold is reached, then agent proposes tool extraction.
2. Given approval, when scaffolding runs, then command includes examples and annotations.
3. Given published tool, when similar task reappears, then workflow uses command instead of bespoke code.

### Acceptance Criteria
1. New tool has clear input/output contract and failure semantics.
2. Generated docs are sufficient for another engineer to use the command correctly.
3. Repeated task cost decreases after adoption.

### Emergent Skills and Resources
- Skill: Capability-building loop.
- Resource: task-specific state resource (for example, `release://draft/latest`).

### PTC Value and Operational Signals
- Agent contribution shifts from one-off execution to reusable capability creation.

---

## Scenario 6: New Hire Onboarding Experience

### Lineage
`scenarios_cc.md` Scenario 5

### Persona
New engineer in first two weeks.

### Job to Be Done
When joining a team, I want safe, guided execution of operational tasks without memorizing every command.

### Context
Traditional onboarding depends on stale docs and ad hoc verbal transfer.

### Journey
1. Repository includes generated skill docs and project instructions.
2. New engineer asks Claude Code for help with deployment or incident tasks.
3. Agent runs documented workflows and explains decisions.
4. Engineer learns via live, reproducible command traces.

### Key Interactions (Given/When/Then)
1. Given first deployment request, when engineer asks agent, then documented workflow is followed.
2. Given prohibited operation, when requested, then agent cites guardrail and blocks unsafe path.
3. Given successful workflow, when summarized, then next-step options are explicit.

### Acceptance Criteria
1. Core workflows are executable by new hires without undocumented steps.
2. Guardrails are visible during execution, not hidden in static docs.
3. Agent guidance is traceable back to skill documentation.

### Emergent Skills and Resources
- Skill: Onboarding by execution.
- Resource: context-specific readiness resources.

### PTC Value and Operational Signals
- Faster onboarding.
- Less mentor time for repetitive operational walkthroughs.

---

## Scenario 7: CI/CD Contracted Pipeline

### Lineage
`scenarios_cc.md` Scenario 7

### Persona
Elena, CI maintainer and release engineer.

### Job to Be Done
When PRs are opened, I want structured checks and actionable failures so both CI and agents can diagnose quickly.

### Context
Regex parsing of plain-text tool output is brittle and expensive.

### Journey
1. CI steps call Tooli commands in machine mode.
2. Failures include structured error data and suggestions.
3. Claude Code reads CI output and proposes direct fixes.
4. Teams adopt schema and docs drift checks as merge gates.

### Key Interactions (Given/When/Then)
1. Given CI executes Tooli commands, when checks fail, then error envelope includes fix guidance.
2. Given developer asks agent about failure, when agent reads CI output, then it proposes concrete remediation.
3. Given command signature drift, when CI runs, then contract mismatch is surfaced before merge.

### Acceptance Criteria
1. CI never depends on fragile screen scraping for Tooli command outputs.
2. Breaking command changes are detected by contract checks.
3. PR diagnostics are machine-actionable and human-readable.

### Emergent Skills and Resources
- Skill: CI failure triage loop.
- Resource: CI status and artifact pointers.

### PTC Value and Operational Signals
- Faster failure-to-fix cycle.
- Lower CI maintenance overhead.

---

## Scenario 8: Cross-Team Tool Marketplace and Cross-Repo Mesh

### Lineage
`scenarios_cc.md` Scenario 8

### Persona
Staff engineer coordinating multiple teams and repositories.

### Job to Be Done
When capabilities exist across teams, I want discoverable and interoperable tool contracts so effort is reused instead of duplicated.

### Context
Teams duplicate utilities because discoverability and trust are weak.

### Journey
1. Teams publish tools with clear metadata and generated docs.
2. A discovery registry/tool index is exposed as a skill.
3. Claude Code selects tools based on context, capability declarations, and repo boundaries.
4. Fallback and handoff behavior is explicit across repositories.

### Key Interactions (Given/When/Then)
1. Given similar tool names across teams, when agent chooses one, then rationale cites context and capabilities.
2. Given one MCP endpoint unavailable, when fallback is needed, then equivalent CLI path is used and logged.
3. Given wrong-repo mutative action, when attempted, then policy blocks and directs handoff.

### Acceptance Criteria
1. Tool discovery is queryable and structured.
2. Cross-team command selection is deterministic and explainable.
3. Repo boundary violations are blocked with actionable guidance.

### Emergent Skills and Resources
- Skill: Organization-wide capability discovery.
- Resources: tool registry resources and project capability maps.

### PTC Value and Operational Signals
- Reduced duplicated tooling.
- Faster cross-team execution.

---

## Scenario 9: Resource-First Subagent Operations

### Lineage
Retained and expanded from prior `scenarios_cdx.md`

### Persona
Reliability subagent operating under strict token limits.

### Job to Be Done
When investigating state, I want direct resource reads so I do not waste tokens parsing large command output.

### Context
Read-heavy workflows often rerun commands unnecessarily.

### Journey
1. Developers identify high-frequency read paths.
2. Paths are promoted to MCP resources.
3. Agents adopt resource-first, command-second operating pattern.

### Key Interactions (Given/When/Then)
1. Given resource URI exists, when data is needed, then agent reads resource directly.
2. Given stale resource concern, when freshness required, then agent executes underlying command explicitly.
3. Given resource read failure, when retryable, then agent retries using suggestion metadata.

### Acceptance Criteria
1. Resources are bounded and schema-consistent.
2. Read-heavy sessions show lower command invocation counts.
3. Resource fallback paths are deterministic.

### Emergent Skills and Resources
- Skill: Token-efficient diagnostic loop.
- Resources: `incident://open`, `incident://{id}`, `service://deps`.

### PTC Value and Operational Signals
- Lower context-window pressure.
- Faster analysis latency.

---

## Scenario 10: Global Skill Mesh Through Export Targets

### Lineage
`scenarios_gm.md` Story 5

### Persona
Architecture lead integrating multiple agent frameworks.

### Job to Be Done
When moving across frameworks, I want one tool contract to export everywhere so capabilities remain portable.

### Context
Teams use different orchestration stacks (OpenAI Agents SDK, LangChain, ADK, Python API).

### Journey
1. Core commands are authored once in Tooli.
2. Export generation creates framework-specific wrappers/config:
   - `export --target openai`
   - `export --target langchain`
   - `export --target adk`
   - `export --target python`
3. Generated integrations preserve caller metadata and envelope semantics.
4. Teams reuse the same business logic across orchestrators.

### Key Interactions (Given/When/Then)
1. Given a Tooli app, when target export is generated, then wrapper code is runnable for the selected framework.
2. Given subprocess wrappers, when invoked, then caller env var is set consistently.
3. Given import-mode wrappers, when invoked, then app-level call path preserves structured success/failure behavior.

### Acceptance Criteria
1. Generated targets are syntactically valid and framework-appropriate.
2. Error behavior is predictable across targets.
3. Target generation supports whole-app and single-command output.

### Emergent Skills and Resources
- Skill: Write once, operate across agent ecosystems.
- Resource: portable wrapper modules/config artifacts.

### PTC Value and Operational Signals
- Faster framework adoption.
- Lower integration duplication cost.

---

## Backlog Seeds

1. Support operations skill: diagnose -> verify -> remediate with customer-safe audit trails.
2. Security response chain: detect -> map -> contain with mandatory approvals.
3. Data quality repair loop with preview and rollback.
4. Versioned deprecation and migration workflows for long-lived agents.
5. Cost anomaly triage as a multi-agent playbook.

---

## Scenario Author Checklist

Before adding new scenarios, verify:

1. Role, goal, and benefit are explicit.
2. At least one failure path and one guardrail are specified.
3. Acceptance criteria are observable and testable.
4. Emergent skills/resources are named concretely.
5. PTC value is measurable (speed, safety, quality, scale).
6. Behavior is documented over implementation details.

---

## References (Best-Practice Sources)

1. Atlassian - User Stories: https://www.atlassian.com/agile/project-management/user-stories
2. Cucumber - Better Gherkin: https://cucumber.io/docs/bdd/better-gherkin/
3. Cucumber - Example Mapping: https://cucumber.io/docs/bdd/example-mapping/
4. Agile Alliance - INVEST: https://agilealliance.org/glossary/invest/
5. Agile Alliance - Three Cs: https://agilealliance.org/glossary/three-cs/
6. Agile Alliance - Given-When-Then: https://agilealliance.org/glossary/given-when-then/
