# Sync

GitHub PR/Issue state polling. Reads `[ ]` items in fix_plan, finds PR/Issue number references, queries GitHub, and auto-checks `[x]` on MERGED PRs and CLOSED issues. PRs CLOSED-without-merge convert to `[BLOCKED:P2:external]` — see the rules table below.

## When to use

- Routine fix_plan housekeeping (run before [move](./move.md) to catch newly-merged work)
- Explicit `/fix-plan sync` invocation
- Stop-hook driven supervisor checks ("any PR merged since last loop?")

## Procedure

### 1. Extract PR/Issue numbers from `[ ]` items

Grep fix_plan for `PR #N`, `Issue #N`, or bare `#N` near a known issue/PR keyword. For each match, capture the number. When rewriting or updating the state of these items, ensure bare references (or raw `PR #N`) are rewritten to clickable Markdown links `[PR #N](URL)`.

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

## Secondary-tracker sync cadence

When a project mirrors its backlog into a second external tracker (a project-management tool, issue tracker, etc.) alongside GitHub, run that tracker's own sync in the same cadence as this GitHub sync — poll both together rather than letting them drift independently.

The fix-plan skill stays vendor-agnostic here too: no tracker name is hardcoded. Dispatch via `--secondary-sync=<skill>:<topic>` (same caller-supplied receiver pattern as `--archive=<skill>:<topic>` — see the top-level Configuration table). The caller wires this to whichever skill owns that tracker's sync script (e.g., a project-management-tool skill's own dry-run sync command); this skill only documents the cadence contract.

| # | Don't | Do |
|---|-------|-----|
| 1 | Run only the GitHub sync and assume the secondary tracker stays current on its own | If `--secondary-sync` is configured, run it in the same pass as this GitHub sync |
| 2 | Hardcode a specific tracker's domain/skill name into this file | Dispatch through the abstract `--secondary-sync=<skill>:<topic>` flag; the receiver owns vendor specifics |

## Sync-specific prohibitions

| # | Don't | Do |
|---|-------|-----|
| 1 | Auto-`[x]` an `OPEN` PR / Issue | Only act on MERGED / CLOSED state |
| 2 | On GitHub API error, mark the item BLOCKED | Do not change the item's state on uncertain input; include the API error as a separate line in the sync report so the user can see what failed |
| 3 | Run sync without reporting how many items changed | Report changed-item count to the user. Zero changes → "no changes" |
| 4 | Re-sync items already `[x]` | Sync only operates on `[ ]` entries |

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
