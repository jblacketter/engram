# Daily-Driver Adoption Log

Dated, per-project notes on real engram usage. This log is the evidence
base for the Phase 12 (agent-scoping) project-model decision checkpoint:
that decision requires either the human's confirmation of meaningful use
across **at least two projects** (recorded here), or an explicit
"insufficient evidence — decision deferred" entry. A single demo does not
satisfy the gate.

Log entries should note: date, project/domain, what was used (hook recall,
checkpoint, prompts, search), and any friction (wrong recalls, noisy
injection, missing context, tag confusion).

---

## 2026-07-11 — trial opened (engram)

Daily-driver tooling shipped and demonstrated in-cycle: hook recall,
checkpoint flow, and prompts exercised in the `engram` domain; second-repo
install verified in `tagteam`. **This is mechanics verification, not
adoption evidence.** The one-week trial across ≥2 projects starts now and
runs in parallel with Phase 11.

## 2026-07-12 — Phase 12 gate: insufficient evidence, decision deferred

The project-model decision checkpoint (soft `domain:` tags vs first-class
workspace column) came due at the start of agent-scoping. The daily-driver
trial opened 2026-07-11 — no meaningful multi-project usage exists yet, so
per the gate: **insufficient evidence — decision deferred. Soft domain
tags remain the project model pending trial data.** Revisit condition: the
human confirms meaningful use across ≥2 projects in this log. Per-agent
authorization (AgentKey + domain binding) proceeds independently; keys
bind to domain tags today and would bind to workspace values identically
if the model later hardens.
