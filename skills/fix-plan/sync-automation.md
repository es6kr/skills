# Sync Automation

Stop-hook checkpoint that nudges a `sync` run when a tracker referencing PR/Issue numbers hasn't been checked against GitHub in a while — without the hook itself making any network call.

## Why

`sync` (see [sync.md](./sync.md)) only runs when someone explicitly invokes `/fix-plan` (or a role-scoped variant). A long-lived tracker that references many PR/Issue numbers can drift silently between invocations — a referenced PR merges, but the tracker keeps showing it as open/pending until the next manual `/fix-plan --pm` or `/fix-plan sync` call. This topic closes that gap the same way `es6kr`'s session-import-gap hook closes the RAG-store gap: a cheap, local, no-network Stop hook that only *nudges*, leaving the actual (potentially rate-limited) GitHub polling to the `sync` procedure itself.

## Design

| Property | Value |
|----------|-------|
| Hook event | `Stop` |
| Network calls inside the hook | **None** — the hook only reads local file state |
| Trigger signal | Wall-clock time since the last nudge for this specific tracker file, gated on the tracker actually referencing `PR #N` / `Issue #N` patterns |
| State | One checkpoint file per tracker path, storing the last-nudge Unix timestamp |
| Output | The same `{"decision":"block","reason":"<skill-trigger>...</skill-trigger>"}` envelope convention used by `next-trigger.sh` / `check-session-import-gap.sh` |

### Checkpoint file

`~/.claude/skills/fix-plan/.state/sync-checkpoint-<sha1-of-absolute-tracker-path>.ts` — a single Unix timestamp. Keyed by path hash (not session id) because sync drift is a property of the *tracker file*, not of any one session — multiple sessions working in the same workspace should share one checkpoint, not each nudge independently.

### Trigger conditions (all must hold)

1. The current turn's `cwd` (or a workspace root search, same discovery as `wip/resume.md` Step 0.6) contains a `.ralph/fix_plan.md` or `checklist.md`.
2. That file contains at least one `PR #<N>` / `Issue #<N>` reference in a non-`[BLOCKED]`-resolved, non-`## Completed` context (a cheap `grep`, not a parse).
3. The checkpoint file for that path is absent, or its stored timestamp is more than `THRESHOLD_HOURS` (default 24) old.
4. `stop_hook_active` is not set (same loop-prevention guard as every other Stop hook in this family).

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Call `gh pr view` / `gh api` from inside the Stop hook to check real state | The hook only reads a local timestamp file — all GitHub polling stays inside `sync`'s own batch-query procedure, invoked only when the nudge is acted on |
| 2 | Key the checkpoint by session id | Key by a hash of the tracker's absolute path — drift is a file property shared across sessions, not a per-session counter |
| 3 | Nudge on every Stop event once the threshold is crossed | Update the checkpoint file immediately when the nudge fires (same convention as `check-session-import-gap.sh`) so it doesn't refire every turn until the next threshold window |
| 4 | Nudge a tracker with zero PR/Issue references | Gate on the reference-presence grep first — a tracker with no external references cannot drift relative to GitHub |
| 5 | Silently skip the nudge in Ralph's own autonomous loop | Same threshold applies in Ralph mode too — a stale tracker inside an autonomous loop is just as costly, and the loop already invokes `/fix-plan` on its own cadence, which will pick up the nudge |

## Script

`resources/sync-checkpoint-nudge.sh` (Stop hook). Owned by this skill per the hook-ownership convention (domain-specific hook → domain skill, not the generic `hook-kit`).

## Self-check (before registering or modifying this hook)

1. Does the hook make any outbound network call? → If yes, it violates the core design property — move that logic into `sync.md`'s own procedure instead
2. Is the checkpoint keyed by tracker path (not session id)? → Session-keyed checkpoints would nudge once per session even for a tracker already nudged minutes ago from a different session
3. Does the hook gate on actual PR/Issue reference presence before nudging? → Without this gate, every long-lived tracker gets nudged regardless of whether it has anything to drift on

## See also

- [sync.md](./sync.md) — the actual GitHub polling procedure this topic nudges toward
- `es6kr` skill's `check-session-import-gap.sh` — the sibling Stop-hook pattern this design mirrors (local checkpoint, zero in-hook network calls, block-decision envelope)
