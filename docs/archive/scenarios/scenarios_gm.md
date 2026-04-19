# Tooli & Claude Code: The Universal Skill Protocol

> Transforming tribal knowledge into executable agent skills — from the first function to the Global Skill Mesh.

This document serves as the **Visionary Scenario Guide** for the Tooli ecosystem. It describes the collaborative lifecycle between human developers, end-users, and autonomous agents (like Claude Code) using the `tooli` framework.

---

## The Cast (Personas)

| Persona | Role | Relationship to Tools |
|---|---|---|
| **Maya (The Architect)** | Senior Developer | Builds diagnostic tools to solve immediate operational pain. |
| **Priya (The New Hire)** | Junior Developer | Uses tools + agents to get productive without a steep learning curve. |
| **Jordan (The Platform Lead)** | SRE / DevOps | Defines organizational workflows and "Never" rules in CLAUDE.md. |
| **Riku (The Security Officer)** | Compliance / SecOps | Enforces company-wide policies, auth scopes, and capability allowlists. |
| **The Agent (Claude Code)** | Autonomous Teammate | Discovers, invokes, composes, and authors tools based on observed patterns. |

---

## Feature 1: The Lifecycle of a Skill
**Job to Be Done:** *When I'm paged for a production incident, I want to quickly identify the root cause so I can restore service without re-deriving my diagnostic pipelines from scratch.*

### Scenario 1: From Scratch Script to Team Infrastructure
**Context:** Maya keeps running the same complex `grep | jq` pipelines during outages.

- **Phase 1 (The Emergency):** Maya wraps her most-used pipeline in a `tooli` command: `loggrep errors`.
- **Phase 2 (The Discovery):** Claude Code sees `loggrep` in the MCP config. During a 502 error investigation, it autonomously invokes `loggrep errors --json`, finds the trace ID, and correlates the failure.
- **Phase 3 (The Crystallization):** Maya runs `tooli init --agent-bootstrap > SKILL.md`. The "Incident Triage" workflow is now permanent.
- **Phase 4 (The Team Legacy):** Two months later, Priya (the new hire) uses the same tool. Claude Code guides her through the "Maya-Standard" triage process.

**The Protocol Trace:**
> **Maya:** "The checkout service is 502ing. What's wrong?"
> **Claude Code:** *(invokes loggrep.errors via MCP)* "Found 47 errors. The timeline shows a connection pool exhaustion starting at 14:32. Checkout's retry logic amplified failing requests, exhausting the pool. Shall I check the payment gateway logs next?"

**Key Interactions (GWT):**
| Given | When | Then |
|---|---|---|
| Maya defines `loggrep errors` | An incident occurs | Maya has a structured CLI with `--json` for precise analysis. |
| `SKILL.md` is generated | Priya joins the team | Claude Code follows the "Incident Triage" workflow autonomously. |

---

## Feature 2: Autonomous Self-Healing
**Job to Be Done:** *When a tool call fails due to environmental factors, I want the agent to identify the fix and retry so that I am not interrupted for trivial issues.*

### Scenario 2: The Reflection Loop
**Context:** Claude Code is tasked with checking production logs for credential leaks.

- **Given** the user provides a GZipped log file that the tool cannot read by default.
- **When** Claude Code invokes `infra-audit scan-logs --source prod.log.gz`.
- **Then** Tooli returns a `ToolError` with code `E3001` (State Error) and a `suggestion` to use the `--decompress` flag.
- **And** the agent (using the **Reflection Pattern**) automatically retries with the flag, completing the task silently.

**Success Metric:** 70% reduction in "Human-in-the-Loop" interruptions for environmental failures.

---

## Feature 3: Strategic Multi-Agent Handoffs (v5.0)
**Job to Be Done:** *When performing complex architectural changes, I want my specialized agents to coordinate seamlessly so that the final output is verified and safe.*

### Scenario 3: The Multi-Agent War Room
**Context:** A "Release Day" scenario involving security scans and infrastructure canary deployments.

- **Given** an Orchestrator Agent is running a "Security Audit" workflow.
- **When** the Security Agent detects a vulnerability and sees a `handoff` suggestion for `patch-pilot`.
- **Then** the Orchestrator delegates the next step to the Infra Agent using the **v5.0 Python API** for zero-latency, in-process execution.

**Key Interactions (GWT):**
| Given | When | Then |
|---|---|---|
| Command includes `handoffs` metadata | A threat is detected | The agent receives a deterministic suggestion for the next logical step. |
| v5.0 Python API is available | A handoff occurs | Agents exchange `TooliResult` objects in-memory, bypassing shell overhead. |

**PTC Outcome:** Incident response time reduced from minutes to seconds through deterministic handoffs.

---

## Feature 4: The Agent as a Tool Author
**Job to Be Done:** *When I am performing repetitive manual tasks, I want my agent to proactively build the automation I need so that our internal capability library grows automatically.*

### Scenario 4: The Proactive Capability Builder
**Context:** Claude Code notices the developer is manually checking monorepo dependency versions 5 times a day.

- **Given** an agent identifies a repeated task pattern.
- **When** the agent proposes: *"I've noticed this pattern; should I scaffold a `dep-audit` tool for us?"*
- **Then** the agent uses `tooli init` to create a permanent, high-quality skill that remains in the repo long after the session ends.

**Success Metric:** The agent transitions from "Task Doer" to "Capability Builder," increasing the team's long-term leverage.

---

## Feature 5: The Universal Skill Protocol (Ecosystem)
**Job to Be Done:** *When our project scales, I want our tools to be usable across different frameworks (LangChain, OpenAI, ADK) without rewriting them.*

### Scenario 5: The Global Skill Mesh
**Context:** A project needs to scale its internal tools into a dashboard powered by LangChain and OpenAI.

- **Given** a Tooli app with a rich set of cloud-provisioning commands.
- **When** the developer runs `tooli export --target langchain` and `tooli export --target openai`.
- **Then** Tooli generates typed Python wrappers that map the CLI commands to `@tool` definitions automatically.
- **And** the tools are discovered via the `AGENTS.md` and `llms.txt` Universal Protocol.

**PTC Outcome:** Tools become "Universal Assets," usable by any agent, on any platform, at any time.

---

## Feature 6: Enterprise Governance (Strict Mode)
**Job to Be Done:** *When we use autonomous agents in production, I want to control exactly what they can access so that we maintain our security posture and regulatory compliance.*

### Scenario 6: The Security Sentry (Riku’s Watch)
**Context:** Regulatory requirements mandate that tools only access what they explicitly declare.

- **Phase 1 (Lockdown):** Riku sets `TOOLI_ALLOWED_CAPABILITIES="fs:read,net:read"`.
- **Phase 2 (The Block):** An agent tries to run `env-cleanup prune` (which requires `fs:write`). Tooli blocks the invocation *before* it runs.
- **Phase 3 (The Audit):** Riku reviews the telemetry. He sees the `caller_id="claude-code"`, the `session_id`, and exactly why the `fs:write` capability was denied.

**Key Interactions (GWT):**
| Given | When | Then |
|---|---|---|
| STRICT mode is active | Tool requests `fs:write` | Invocation is blocked with a structured error explaining the gap. |
| Telemetry is enabled | Any tool is invoked | A full audit trail is generated with caller and capability metadata. |

---

## Summary of the PTC Vision
In the Tooli-powered future:
1.  **Skills** are the shared language between humans and machines.
2.  **Resources** are the live organs of the project's state.
3.  **Protocols (Tooli)** are the connective tissue that ensures safety, structure, and speed.
4.  **PTC** is no longer just "chatting with an AI"—it is the orchestrated movement of a highly capable, multi-agent team.
