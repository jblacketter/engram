# Workflows: Lead/Reviewer Collaboration

This document describes how lead and reviewer agents collaborate on projects using this framework.

> **Note**: Agent names are configured in `tagteam.yaml`. Read that file to see which agent is the lead and which is the reviewer for your project.

## Roles

| Role | Responsibilities |
|------|------------------|
| **Lead** | Planning phases, implementing code, creating handoffs |
| **Reviewer** | Reviewing plans and implementations, providing feedback |
| **Arbiter** | Breaking ties, making final decisions, approving phases (typically Human) |

## Phase Workflow

Each phase follows this pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│                        PLANNING CYCLE                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Lead: /handoff-plan create [phase]                            │
│      │                                                          │
│      ▼                                                          │
│   Lead: /handoff-handoff plan [phase]  ► Reviewer: /handoff-review plan │
│      │                                          │               │
│      │◄─────────────────────────────────────────┘               │
│      │  (feedback in docs/handoffs/[phase]_plan_feedback.md)    │
│      ▼                                                          │
│   Lead: /handoff-handoff read [phase]                           │
│      │                                                          │
│      ├── If APPROVED ──────────────────────────────────►        │
│      │                                                          │
│      └── If CHANGES REQUESTED ─► Lead: /handoff-plan update [phase] │
│                                          │                      │
│                                          └──► (repeat cycle)    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     IMPLEMENTATION CYCLE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Lead: /handoff-implement start [phase]                        │
│      │                                                          │
│      ▼                                                          │
│   [Lead implements the phase]                                   │
│      │                                                          │
│      ▼                                                          │
│   Lead: /handoff-implement complete [phase]                     │
│      │                                                          │
│      ▼                                                          │
│   Lead: /handoff-handoff impl [phase]  ► Reviewer: /handoff-review impl │
│      │                                          │               │
│      │◄─────────────────────────────────────────┘               │
│      │  (feedback in docs/handoffs/[phase]_impl_feedback.md)    │
│      ▼                                                          │
│   Lead: /handoff-handoff read [phase]                           │
│      │                                                          │
│      ├── If APPROVED ──────────────────────────────────►        │
│      │                                                          │
│      └── If CHANGES REQUESTED ─► Lead fixes issues              │
│                                          │                      │
│                                          └──► (repeat cycle)    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    /handoff-phase complete [phase]
                              │
                              ▼
                    Start next phase...
```

## Available Skills

| Skill | Purpose | Who Uses |
|-------|---------|----------|
| `/handoff-plan` | Create/update phase plans | Lead |
| `/handoff-handoff` | Create handoff documents | Lead |
| `/handoff-review` | Review plans or implementations | Reviewer |
| `/handoff-implement` | Start/track/complete implementation | Lead |
| `/handoff-phase` | Manage phase lifecycle | Both |
| `/handoff-status` | Check project status | Both |
| `/handoff-decide` | Log decisions | Both |
| `/handoff-escalate` | Escalate to human | Both |
| `/handoff-sync` | Generate sync summary for sessions | Both |
| `/handoff-cycle` | Automated review cycles (reduces copy-paste) | Both |

## Handoff Process

### From Lead to Reviewer
1. Lead completes work (plan or implementation)
2. Lead creates handoff document with `/handoff-handoff`
3. Human switches to reviewer session
4. Reviewer reads sync with `/handoff-sync reviewer`
5. Reviewer reviews with `/handoff-review`
6. Reviewer saves feedback

### From Reviewer to Lead
1. Reviewer saves feedback to `docs/handoffs/[phase]_[type]_feedback.md`
2. Human switches to lead session
3. Lead reads sync with `/handoff-sync lead`
4. Lead reads feedback with `/handoff-handoff read [phase]`
5. Lead incorporates feedback or explains why not

## Decision Authority

| Decision Type | Who Decides |
|---------------|-------------|
| Technical approach within a phase | Lead |
| Accepting/rejecting review feedback | Lead |
| Blocking implementation issues | Reviewer can flag, lead decides |
| Architecture affecting multiple phases | Requires consensus or Human |
| Disagreements after 2 review cycles | Human (Arbiter) |
| Scope changes to requirements | Human |

## Session Transitions

When switching between lead and reviewer:

1. Generate sync summary: `/handoff-sync` or `/handoff-sync [lead|reviewer]`
2. The sync summary captures current state
3. In new session, read the sync file: `docs/sync_state.md`
4. Continue work based on sync state

## Quick Reference

**Starting a new phase:**
```
/handoff-phase list           # See all phases
/handoff-plan create [phase]  # Create the plan
/handoff-handoff plan [phase] # Send to reviewer
```

**Reviewing:**
```
/handoff-sync reviewer        # Get context
/handoff-review plan [phase]  # Or /handoff-review impl [phase]
```

**After review (Lead):**
```
/handoff-handoff read [phase] # See feedback
/handoff-plan update [phase]  # Incorporate changes
```

**Implementing:**
```
/handoff-implement start [phase]
[do the work]
/handoff-implement complete [phase]
/handoff-handoff impl [phase]
```

## Automated Review Cycle (Alternative)

Use `/handoff-cycle` to reduce manual copy-paste during multi-round reviews. Instead of creating separate handoff/feedback files each round, both agents work from a single cycle document.

### Cycle Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTOMATED REVIEW CYCLE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Lead: /handoff-cycle start [phase] plan                       │
│      │                                                          │
│      ▼                                                          │
│   (Human switches to reviewer terminal)                         │
│      │                                                          │
│      ▼                                                          │
│   Reviewer: /handoff-cycle [phase]                              │
│      │                                                          │
│      ├── APPROVE ────────────────────────────────────────►      │
│      │                                                          │
│      └── REQUEST_CHANGES                                        │
│              │                                                  │
│              ▼                                                  │
│      (Human switches to lead terminal)                          │
│              │                                                  │
│              ▼                                                  │
│      Lead: /handoff-cycle [phase]  ─► address feedback          │
│              │                                                  │
│              └──► (repeat until approved or stale)              │
│                                                                 │
│   5+ stale rounds (no progress) ─► Auto-escalate to human       │
└─────────────────────────────────────────────────────────────────┘
```

### Cycle Commands

| Command | Description |
|---------|-------------|
| `/handoff-cycle start [phase] plan` | Start a plan review cycle |
| `/handoff-cycle start [phase] impl` | Start an implementation review cycle |
| `/handoff-cycle [phase]` | Continue (auto-detects your role and turn) |
| `/handoff-cycle status [phase]` | View current status |
| `/handoff-cycle abort [phase]` | Cancel with a reason |

### Reviewer Actions

- **APPROVE**: Accept the submission, end the cycle
- **REQUEST_CHANGES**: Provide feedback, continue to next round
- **NEED_HUMAN**: Pause the cycle for human input
- **ABORT**: Cancel the cycle

### When to Use Cycle vs Manual

**Use `/handoff-cycle` when:**
- Expecting multiple review rounds
- Want to reduce file creation overhead
- Prefer one command per turn

**Use manual handoff/review when:**
- Simple one-round reviews
- Need detailed structured feedback
- Prefer separate files for each interaction

---

# Daily Driver: Engram in Everyday Sessions

How engram integrates into daily Claude Code work. Setup instructions live
in `integrations/claude-code/README.md`; this section defines the
conventions.

## Tag conventions

| Tag | Meaning |
|-----|---------|
| `domain:<slug>` | Which project a memory belongs to (one per memory) |
| `project:<slug>` | Optional finer-grained scope within a domain |
| `type:project-status` | A full project-status snapshot (newest per domain is canonical) |
| `type:checkpoint` | A session delta: decisions, learnings, open threads |
| `type:note` | An explicit ad-hoc memory (`/engram store`) |

Domain resolution (hook and skill): `ENGRAM_DOMAIN` env var → `.engram`
marker (`domain=<slug>`, found by upward walk from cwd) → git root
directory name (a `.git` file or directory both count — worktrees have a
file) → cwd basename; slugs normalize to `[a-z0-9-]`.

**Trust note:** a repository-controlled `.engram` file selects which
domain is loaded into the session — review it when opening untrusted
repositories, and never let an untrusted project point at a sensitive
domain. The hook injects recalled memories with an explicit
untrusted-reference warning, sanitizes markup so content cannot escape the
context envelope, and excludes raw `ingested` document chunks from ambient
recall (they remain reachable via explicit search).

## The status snapshot contract

A `type:project-status` memory is always a **full snapshot**, never a
delta:

```markdown
# Status: <domain>
Goal: <one-line project goal>
State: <current state, 1-3 lines>
Recent: <progress since last snapshot>
Blockers: <blockers / open questions, or "none">
Next: <next actions>
Updated: <YYYY-MM-DD> | Evidence: <checkpoint memory id(s) or "manual">
```

Retrieval is deterministic, not semantic: latest snapshot via
`GET /api/memories/?tags=domain:<d>,type:project-status&limit=1` (or the
equivalent `list_recent_memories` call); recent **non-status, non-ingested**
activity via `tags=domain:<d>&exclude_tags=type:project-status,ingested&limit=5`.
Raw ingested document chunks are excluded from ambient recall for safety
(prompt-injection risk) and noise; they remain available through explicit
search.

## The daily loop

1. **Session start (ambient):** the SessionStart hook injects the latest
   status snapshot + recent memories for the repo's domain. Silent when
   engram is down or the domain is empty.
2. **Start of day:** `start_day` MCP prompt — cross-project briefing
   (discovers projects via `list_domains`).
3. **During work:** `/engram search <query>`, `/engram store <text>`;
   recall stays ambient.
4. **Project switch:** `switch_project` MCP prompt.
5. **End of a substantive session:** `/engram checkpoint` (or the
   `end_session` prompt) — drafts a checkpoint + updated full snapshot,
   stores only what you confirm. **Capture is manual and suggestion-first;
   nothing writes without confirmation.**
6. **Weekly:** `weekly_review` prompt — aggregates the week's checkpoints
   per project (time-bounded via `list_recent_memories(after=...)`) and
   proposes snapshot updates.

## Adoption tracking

Real-world usage is logged in `docs/adoption-log.md`. The Phase 12
(agent-scoping) project-model decision is gated on that log: meaningful use
across at least two projects confirmed by the human, or an explicit
"insufficient evidence — deferred" entry.
