# Engram × Claude Code — Daily Driver Setup

Ambient recall at session start + suggestion-first capture, for any
repository. Requires a running engram stack (see the repo README) and
Claude Code.

## 1. Register the engram MCP server (once, user scope)

```bash
claude mcp add --transport http --scope user engram http://localhost:8080/mcp
```

User scope makes the tools available in every project. Verify with
`claude mcp list` (should show `engram … ✔ Connected` while the stack is
running).

## 2. Install the SessionStart recall hook (once)

The hook injects the project's latest status snapshot and recent memories
at the start of every session, and stays silent when engram is down.

**Merge** (do not overwrite) the following into `~/.claude/settings.json` —
if you already have a `hooks` object or a `SessionStart` array, append the
hook entry to what's there:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /ABSOLUTE/PATH/TO/engram/integrations/claude-code/engram_recall.py"
          }
        ]
      }
    ]
  }
}
```

Replace the path with this repository's absolute location. Optional env
(set in your shell profile): `ENGRAM_API_URL` (default
`http://localhost:8000/api`), `ENGRAM_REST_API_KEY` (if the API is
secured), `ENGRAM_DOMAIN` (override domain resolution).

Smoke-test without starting a session:

```bash
echo '{"cwd": "'$PWD'", "source": "startup"}' \
  | python3 /ABSOLUTE/PATH/TO/engram/integrations/claude-code/engram_recall.py
```

With the stack running and memories present, this prints an
`<engram-context …>` block; with the stack stopped it prints nothing and
exits 0.

## 3. Install the /engram skill (once)

```bash
mkdir -p ~/.claude/skills
ln -s /ABSOLUTE/PATH/TO/engram/integrations/claude-code/skills/engram ~/.claude/skills/engram
```

(Or copy the directory instead of symlinking.)

## 4. Per-repository: pin the domain (optional)

By default a repo's domain is its root directory name (normalized to
`[a-z0-9-]`). To pin a different one, add a `.engram` file at the repo
root:

```
domain=my-project
```

Precedence: `ENGRAM_DOMAIN` env var → `.engram` marker → git root
directory name → cwd basename.

> **Trust note:** the `.engram` marker is repository-controlled — it decides
> which domain's memories get loaded into your session. When opening an
> untrusted repository, review its `.engram` file first, and don't let an
> untrusted project point at a sensitive domain. Recalled memories are
> injected as untrusted reference material (the hook labels them as such
> and excludes raw ingested document chunks), but domain selection is
> still yours to guard.

## 5. Daily loop

- **Start of day:** use the `start_day` MCP prompt for a cross-project
  briefing (it discovers projects via `list_domains`).
- **During work:** recall is ambient (the hook); `/engram search <query>`
  and `/engram store <text>` for explicit reads/writes.
- **Switching projects:** the `switch_project` MCP prompt.
- **End of a substantive session:** `/engram checkpoint` (or the
  `end_session` MCP prompt) — drafts a session delta + full status
  snapshot, stores only what you confirm.
- **Weekly:** the `weekly_review` MCP prompt aggregates the week's
  checkpoints per project and proposes status updates.

Conventions (tags, status snapshot contract) are documented in
`docs/workflows.md`.
