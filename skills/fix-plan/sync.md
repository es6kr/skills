# Sync

GitHub PR/Issue state polling → auto-check `[ ]` → `[x]` on MERGED/CLOSED.

> **Scaffold placeholder** — Content migration from `ralph/fix-plan.md` (sections L370-408) in progress. See plan `~/.agents/docs/generated/plan-fix-plan-migration.md` §4 for migration matrix.

## Planned Content

### Procedure

1. **Extract PR/Issue numbers**: grep fix_plan.md `[ ]` items for `PR #N` or `#N` patterns
2. **Query GitHub state** for each number:
   ```bash
   gh pr view <N> --json state,mergedAt -q '{state: .state, mergedAt: .mergedAt}'
   gh issue view <N> --json state,closedAt -q '{state: .state, closedAt: .closedAt}'
   ```
3. **Auto-check rules**:

   | GitHub state | fix_plan action |
   |--------------|-----------------|
   | PR `MERGED` | `[ ]` → `[x]` + timestamp (`mergedAt`) |
   | Issue `CLOSED` | `[ ]` → `[x]` + timestamp (`closedAt`) |
   | PR `OPEN` / Issue `OPEN` | No change |
   | PR `CLOSED` (not merged) | `[BLOCKED]` + reason "PR closed without merge" |

4. **Timestamp format**: same as item state change — `(YYYY-MM-DD HH:mm completed: sync)`

5. **Completed move chain**: items synced to `[x]` are eligible for the next [move](./move.md) cycle

### Sync-specific prohibitions

- Never auto-`[x]` an `OPEN` PR/Issue
- On GitHub API failure, skip the item (do not change state on error)
- Report changed-item count to the user (zero changes → "no changes")

## See Also

- [github-flow](../github-flow/) (depends-on) for `gh` CLI conventions
- [move](./move.md) for next-step Completed handling
