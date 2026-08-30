# Send — Deliver Work to a Running Orca Terminal

Find a running agent session by title, activity, or worktree, and deliver a prompt to it.
Four stages, always in this order: **list → filter → disambiguate → deliver**.

## When to Use

- "Send this to the Claude session working on X"
- "Hand this off to the agent titled Y"
- "Tell the antigravity session in worktree Z to do this"

**Not for**: full ownership handoffs where you stop monitoring afterward (use
[launch.md](./launch.md)'s `worktree create --agent --prompt`), or structured multi-agent
coordination — task DAGs, ask/reply, worker_done waits (use Orca's own `orchestration` skill:
`ORCA skills get orchestration`). This topic covers the simple case: one prompt, one
terminal, no tracking.

## Step 1 — List

```bash
ORCA terminal list --json
```

Returns every terminal Orca knows about, each with `handle`, `title`, `preview` (a tail
excerpt of recent output), `worktreeId`, `worktreePath`, `branch`, `tabId`, `leafId`,
`connected`, `writable`, `orphaned`, `lastOutputAt`. There is **no agent-kind or
launch-agent field** — the only way to tell what a terminal is running is `title` (the
session's custom title, if one was set, prefixed with a status glyph) and `preview`.

## Step 2 — Filter

Use `scripts/resolve-terminal.sh <title-regex> <preview-regex>` rather than filtering by
hand — it also applies the self-exclusion and liveness rules below, which are easy to get
wrong inline.

```bash
scripts/resolve-terminal.sh "Claude Code" "impl"
```

The script always applies these filters, in order:

1. **Self-exclusion (HARD STOP).** Reads `ORCA_PANE_KEY` (Orca sets this inside every
   managed terminal as `<tabId>:<leafId>`) and drops any terminal whose `tabId`+`leafId`
   match it. If `ORCA_PANE_KEY` is unset, the script refuses to run (exit 2) — this session
   is not inside an Orca-managed terminal, and `send` must not run in that case. Without this
   guard, a session could target its own pane and inject a prompt into its own input, which
   makes it act on its own text as if another agent had sent it.
2. **Liveness.** `connected && writable && !orphaned`, always required — never overridable.
3. **Title / preview regex.** Case-insensitive. The status glyph Orca prefixes onto titles
   (a filled or half-filled circle, a dot, etc.) is stripped before matching, so a
   `title-regex` of `"Claude Code"` matches a raw title of `"◐ Claude Code"`.

For worktree- or branch-scoped filtering, post-filter the script's JSON output on
`worktreePath` / `branch` — those fields pass through unmodified.

## Step 3 — Disambiguate (HARD STOP)

| Candidate count | Action |
|---|---|
| **0** | Stop. Report the filter used and the full unfiltered terminal list. Do not loosen the filter on your own guess. |
| **1** | Proceed to Step 4. |
| **2+** | **AskUserQuestion is mandatory.** One option per candidate, each labeled with its `title` and described with the `previewTail`, `worktreePath`, and a relative time from `lastOutputAt`. |

**Never auto-select on "most recent activity" or any other heuristic when there are 2+
candidates.** Live runs of this skill have observed multiple terminals sharing the exact
same title (e.g. three terminals all titled plainly `Claude Code`, distinguished only by
`handle` and `preview`) — picking the most-recently-active one is a guess, not a
disambiguation, and a wrong guess means an unrelated session starts acting on unrelated
work. Recovering from that (the wrong session may start editing files or committing) costs
far more than one extra AskUserQuestion round trip.

## Step 4 — Deliver

```bash
ORCA terminal read --terminal <handle> --json
ORCA terminal wait --terminal <handle> --for tui-idle --timeout-ms 300000 --json
ORCA terminal send --terminal <handle> --text "<message>" --enter --json
```

- `terminal read` first — check what the target is actually doing before sending. Don't send
  blind.
- `terminal wait --for tui-idle` **always** takes `--timeout-ms`; omitting it is a bug, not a
  convenience.
- Handles are runtime-scoped and can go stale (Orca restart, terminal closed and reopened).
  If a call returns `terminal_handle_stale`, re-run `terminal list` and resolve a fresh
  handle for the same session — don't retry the stale one, and don't guess which new handle
  replaced it without matching on title/worktree again.

## Send vs Orchestration

| Situation | Use |
|---|---|
| One free-form prompt, no tracking needed | `terminal send` — this topic |
| Full handoff, stop monitoring afterward | `launch.md` → `worktree create --agent --prompt` |
| Task DAG, ask/reply, `worker_done`/escalation waits, coordinator loop | Orca's `orchestration` skill (`ORCA skills get orchestration`) — not reimplemented here |
