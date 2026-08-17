# Worktree Drift Sync

Mirroring the same fix across a repo's multiple worktrees (e.g. a primary checkout plus a mirror worktree used by another tool) is unsafe to do from a single upfront `git status` snapshot when the repo is under active concurrent editing (another session, a sync tool, a CI process). State can change **between** worktrees or **during** the fix, silently invalidating an earlier check.

## When to Use

- The same fix (a file rename, a path correction, a content patch) must be applied identically in 2+ worktrees of one repository
- Any of the worktrees is known to receive edits from outside the current session (another Claude Code session, Syncthing/chezmoi sync, a CI job, a teammate)
- A prior attempt to mirror a fix silently landed on stale content because the working tree changed after the last check

## Procedure

Per worktree, per fix:

1. **Re-verify immediately before applying** — `git status`, `git log -1 --format='%H %s'`, and `git diff` (or `git show` for the target file) on **this specific worktree**, right before editing. Do not reuse a check performed earlier in the turn or against a different worktree.
2. **Apply the fix** to this worktree only.
3. **Re-verify immediately before committing** — re-run the same checks. If the worktree's state changed between step 1 and step 3 (new commits, altered HEAD, unexpected working-tree diff), treat this as external concurrent activity, not a bug in your own fix — see the "Unexpected state" branch below.
4. Commit in this worktree, scoped only to the intended fix (never `git add -A`).
5. Move to the next worktree and repeat from step 1 — do not batch step 1 across all worktrees upfront.

### Unexpected state — don't self-correct silently

If step 1 or step 3 shows a HEAD, branch, or diff you did not expect:

| # | Don't | Do |
|---|-------|-----|
| 1 | Assume you misremembered the prior state and quietly proceed | Check `git reflog --date=iso -20` for that worktree — distinguish "my own recent operation" from "external activity" |
| 2 | Force the worktree back to the state you expected (`git reset --hard`, `git checkout -f`) | External concurrent activity is not an error to correct — report it and re-verify against the *current* state before continuing |
| 3 | Treat one worktree's clean state as proof the mirror worktree is equally clean | Each worktree shares the object store but not the working tree or HEAD — check each independently, every time |
| 4 | Give up and re-apply the fix from memory without checking whether it already landed | The external activity may have already applied (or superseded) your fix — diff the target file/lines before re-editing |

## Self-check (before committing a mirrored fix in any worktree)

1. Did I re-run `git status` / `git log -1` / `git diff` in **this** worktree within the last few tool calls, not carried over from another worktree or an earlier point in the turn?
2. If the state differs from what I expected, have I checked `git reflog` to attribute the change before acting on it?
3. Am I about to commit only the intended fix, or did unrelated concurrent changes creep into the staged diff (`git diff --cached --stat`)?
4. After this worktree, do 1+ mirror worktrees still need the same fix? If yes, restart from step 1 for each — do not assume the earlier worktree's verified state still holds.

## Related

- [worktree.md](./worktree.md) — acquiring/reusing a worktree in the first place
- [conflict-dry-run.md](./conflict-dry-run.md) — testing mergeability in an isolated worktree without touching the main tree
- [isolate-hunk.md](./isolate-hunk.md) — staging only your own edit when unrelated concurrent content shares the same tracked file
