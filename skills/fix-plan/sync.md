# Sync

GitHub PR/Issue state polling. Reads `[ ]` items in fix_plan, finds PR/Issue number references, queries GitHub, and auto-checks `[x]` on MERGED PRs and CLOSED issues. PRs CLOSED-without-merge convert to `[BLOCKED:P2:external]` — see the rules table below.

## When to use

- Routine fix_plan housekeeping (run before [move](./move.md) to catch newly-merged work)
- Explicit `/fix-plan sync` invocation
- Stop-hook driven supervisor checks ("any PR merged since last loop?")

## Procedure

### 1. Extract PR/Issue numbers from `[ ]` items

Grep fix_plan for `PR #N`, `Issue #N`, or bare `#N` near a known issue/PR keyword. For each match, capture the number. When rewriting or updating the state of these items, ensure bare references (or raw `PR #N`) are rewritten to clickable Markdown links `[PR #N](URL)`.

**List-item block boundary (HARD STOP)**: before toggling any marker, read the item's full list block — its own line plus every directly-nested `  - ` sub-bullet immediately below it. A nested sub-bullet is an **independent completion unit**: it can carry its own `[ ]`/`[x]`/`[BLOCKED]` marker and its own PR/Issue reference, unrelated to the parent's. Toggling the parent to `[x]` because the parent's own reference resolved does not resolve a nested sub-bullet's reference — that sub-bullet needs its own state check against its own number.

| # | Don't | Do |
|---|-------|-----|
| 1 | Locate an item by grepping a unique substring in its top-level line, edit only that line | Read the matched line plus any `  - ` lines directly beneath it before editing — a nested sub-bullet with its own marker is a separate unit |
| 2 | Extract one number per grep match and stop there | Extract every PR/Issue number in the block, including ones that only appear in a nested sub-bullet |

### 2. Query GitHub state

**Batch per repo (default — avoids the N-call loop)**: when a tracker references many numbers (≥3) in the same repo, query them in one call per artifact type instead of looping `gh pr view` per number. This respects the external-API repeat-call limit (3+ identical calls need justification) and is dramatically faster on large trackers:

```bash
# All referenced PRs of one repo in a single call (include url)
gh pr list -R <owner>/<repo> --state all --limit 200 \
  --json number,state,mergedAt,url,title \
  --jq '.[] | select(.number|IN(41,44,45,47)) | "\(.number)\t\(.state)\t\(.mergedAt // "-")\t\(.url)"'

# All referenced issues of one repo in a single call (include url)
gh issue list -R <owner>/<repo> --state all --limit 200 \
  --json number,state,url,title \
  --jq '.[] | select(.number|IN(23,150,436)) | "\(.number)\t\(.state)\t\(.url)"'
```

Numbers absent from the batch output (older than the `--limit` window) fall back to per-item queries below.

**Per-item fallback** (few numbers, or absent from the batch window):

```bash
gh pr view <N> --json state,mergedAt,url -q '{state: .state, mergedAt: .mergedAt, url: .url}'
gh issue view <N> --json state,closedAt,url -q '{state: .state, closedAt: .closedAt, url: .url}'
```

(Try `gh pr view` first; on "not found" fall back to `gh issue view`. Both error → skip the entry. Note: a number can be a PR in one tracker line and an issue in another — the batch queries cover both artifact types separately, so run both when the reference kind is ambiguous.)

### 3. Auto-check rules

| GitHub state | fix_plan action |
|--------------|-----------------|
| PR `MERGED` | `[ ]` → `[x]` + timestamp from `mergedAt` |
| Issue `CLOSED` | `[ ]` → `[x]` + timestamp from `closedAt` |
| PR `OPEN` / Issue `OPEN` | No change |
| PR `CLOSED` without merge | `[ ]` → `[BLOCKED:P2:external]` with reason note "PR closed without merge — needs decision" |

### 4. Timestamp format

Use the same format as [format.md](./format.md) item state changes: `(YYYY-MM-DD HH:mm completed: sync)`. The `sync` keyword indicates this state change came from automated GitHub polling rather than a session-driven completion.

### 5. Chain into move

Items just synced to `[x]` are immediate candidates for the next [move](./move.md) cycle. The recommended sequence is `sync` → `move` so the freshly-merged items roll into Completed in the same pass.

### 6. Milestone-Boundary Sync (task.md ↔ plan-*.md ↔ fix_plan.md)

When executing deep tasks (`/fix-plan add --deep`, `/code-workflow`), real-time sub-step tool calls are tracked in `task.md` to avoid token churn on large files.

At **major phase boundaries** (Phase 2 Plan authoring, Phase 3 Review disposition, Phase 4 TDD completion, Phase 5 verification), synchronize state across all 3 surfaces:
- `task.md`: Current execution step marked `[x]`
- `plan-*.md`: Section 3 Layered Roadmap / Progress Checklist marked `[x]`
- `fix_plan.md`: Task status updated with model + timestamp metadata `(YYYY-MM-DD, <Model> <SessionID8>; completed: YYYY-MM-DD, <Model> <SessionID8>)`
- `/cleanup`: Final verification ensuring zero sync gap across all 3 files.

## Secondary-tracker sync cadence

When a project mirrors its backlog into a second external tracker (a project-management tool, issue tracker, etc.) alongside GitHub, run that tracker's own sync in the same cadence as this GitHub sync — poll both together rather than letting them drift independently.

The fix-plan skill stays vendor-agnostic here too: no tracker name is hardcoded. Dispatch via `--secondary-sync=<skill>:<topic>` (same caller-supplied receiver pattern as `--archive=<skill>:<topic>` — see the top-level Configuration table). The caller wires this to whichever skill owns that tracker's sync script (e.g., a project-management-tool skill's own dry-run sync command); this skill only documents the cadence contract.

**Example receiver — `../backlog/scripts/plane_sync.py`**: parses `- [<marker>] [<IDENT>-<seq>] <title> -> Plane (<issue URL>)` index lines (the format `backlog`'s Phase-3 migration produces), and maps each issue's `state_detail.group` back onto the fix_plan marker — `completed` -> `[x]`, `cancelled` -> `[BLOCKED:P2:external]`, mirroring this file's own MERGED/CLOSED-without-merge rules above. Non-terminal states and API errors leave the line untouched, same as the GitHub rules table. It also runs the reverse leg (`--push-done`: local `[x]` -> Plane Done) and a report-only P0-P3 priority-drift check — never `DELETE`s a Plane issue. See `backlog/SKILL.md` "Plane Issue DELETE Prohibition & Priority Mapping (HARD STOP)" for the full rule.

### Auto-supplying the secondary-sync receiver from a workspace profile

`--secondary-sync` is caller-supplied, but the caller should not have to remember it per workspace. When the workspace ships a resolvable Plane profile — `scripts/workspace_profile.py --json` returns a **non-empty `plane_host`** for the current cwd (config lives in `~/.config/plane-backlog/config.json`) — the caller MUST auto-supply `--secondary-sync=plane-backlog:sync` on every `/fix-plan` sync / default invocation for that workspace, matching the generic "auto-supply available vendor dispatch" contract. A workspace that has adopted Plane as its canonical backlog (its local tracker demoted to an index) is signalled precisely by that profile; skipping the dispatch silently reverts sync to GitHub-only and lets the local index drift from the canonical tracker.

Degrade cleanly when the profile exists but its token env resolves empty (`plane_token` blank): emit one report line that Plane sync is wired but skipped for want of credentials, and continue the GitHub sync — do not fail the whole pipeline.

| # | Don't | Do |
|---|-------|-----|
| 1 | Run only the GitHub sync and assume the secondary tracker stays current on its own | If `--secondary-sync` is configured, run it in the same pass as this GitHub sync |
| 2 | Hardcode a specific tracker's domain/skill name into this file | Dispatch through the abstract `--secondary-sync=<skill>:<topic>` flag; the receiver owns vendor specifics |
| 3 | Require the user to type `--secondary-sync` by hand every run when a Plane profile is already configured for the workspace | Detect a non-empty `plane_host` via `workspace_profile.py` and auto-supply `--secondary-sync=plane-backlog:sync`; if the token is absent, wire-but-skip with a report line |

## Sync-specific prohibitions

| # | Don't | Do |
|---|-------|-----|
| 1 | Auto-`[x]` an `OPEN` PR / Issue | Only act on MERGED / CLOSED state |
| 2 | On GitHub API error, mark the item BLOCKED | Do not change the item's state on uncertain input; include the API error as a separate line in the sync report so the user can see what failed |
| 3 | Run sync without reporting how many items changed | Report changed-item count to the user. Zero changes → "no changes" |
| 4 | Re-sync items already `[x]` | Sync only operates on `[ ]` entries |
| 5 | Apply the batch query result to only a hand-picked high-signal subset of the extracted numbers (e.g. just the P0/P1 items) | Apply the rules table (step 3) to **every** number the batch query returned, one tracker line at a time — batching is an API-call-count optimization (step 2), not a license to skip applying results to lower-priority lines |

## Report format

```text
Sync result:
- 3 items auto-`[x]` (PR #41 MERGED, PR #44 MERGED, Issue #23 CLOSED)
- 1 item converted to BLOCKED (PR #38 closed without merge)
- 2 items unchanged (PR #45 OPEN, PR #47 OPEN)
```

## See also

- [github-flow](../github-flow/) (depends-on) — `gh` CLI conventions
- [format.md](./format.md) — marker semantics
- [move.md](./move.md) — chain target for `[x]` entries produced here
