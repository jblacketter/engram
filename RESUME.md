# Resume Here

*Last updated: 2026-07-12 — revival roadmap complete.*

## Where things stand

All five revival phases (9–13) are **approved through full lead/reviewer
tagteam cycles** (lead: claude, reviewer: codex). 487 backend tests green.
Full history: `docs/roadmap.md` (statuses), `docs/handoffs/*.jsonl` (review
rounds), `docs/decision_log.md` (decisions), `docs/adoption-log.md`
(usage evidence + open decision gate).

What engram now is: semantic memory (hybrid search, MCP + REST) **plus**
the agent-OS layer built in the revival — ambient session recall,
suggestion-first checkpoints, identity/onboarding, per-agent domain
scoping, and scheduled maintenance.

## First-use setup (what's left)

Everything is installed on this Mac except your real identity:

1. `.venv/bin/python manage.py init_identity`
2. Edit `~/.engram/identity/identity.md` (who you are, house rules for
   agents) and `~/.engram/identity/projects/<domain>.md` per project;
   delete the `example.md` placeholders; `git init` the directory.
   *(Known friction: this lives outside the project — see Future ideas.)*
3. `.venv/bin/python manage.py sync_identity`

## Starting the stack (after a reboot)

```bash
cd ~/projects/engram
docker compose up -d db
.venv/bin/python manage.py runserver 8000 &
.venv/bin/python -m mcp_server &
```

Already installed and persistent: SessionStart recall hook
(`~/.claude/settings.json`), `/engram` skill (`~/.claude/skills/engram`),
MCP registration (user scope, `claude mcp list` → engram).

## Daily loop

- New Claude Code session in any repo → hook auto-injects that project's
  status + recent memories (silent if engram is down).
- End of a substantive session → `/engram checkpoint` (drafts, you
  confirm, it stores).
- `start_day` / `switch_project` / `weekly_review` MCP prompts.
- After a few days of real use across ≥2 projects, add a line to
  `docs/adoption-log.md` — that unlocks the deferred project-model
  decision (soft tags vs workspace column).

## Remaining user-assisted steps

- **Windows/WSL2 deployment:** copy-paste checklist in
  `docs/deploy-windows-lan.md` ("Deployment checklist (revival roadmap)").
- **Agent keys** when other tools connect:
  `manage.py agent_keys create <name> --default-domain <slug>`
  (restart the MCP server after the first key).
- **Scheduled maintenance:** cron/launchd snippets in `docs/workflows.md`
  ("Automations"), or the compose `scheduler` profile in prod.

## Resuming the tagteam workflow

`/handoff status` orients both agents. The roadmap queue is empty
(`tagteam roadmap queue`); to run a new phase, add it to `docs/roadmap.md`
(status: Not Started) and `/handoff start <slug>`.

## Future ideas (captured 2026-07-12, not yet planned)

- **Dashboard for the agent-OS layer** (candidate Phase 14): the existing
  React dashboard shows raw memories/analytics, but nothing surfaces the
  revival-layer concepts — per-project status snapshots, checkpoints,
  adoption trial, identity files, agent keys, digest history. A
  status-centric view could make daily use much more tangible.
- **Identity-location friction:** markdown files outside the project
  (`~/.engram/identity`) are awkward to work with day-to-day. Options to
  explore in the dashboard phase: edit identity/project files through the
  dashboard, or rethink where the identity repo lives.
