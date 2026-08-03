# Publish

Package a working-tree change (in-place edit or uncommitted diff) into its own branch + draft PR against a staging-base branch, watch CI, transition to ready, get a content-review ask, then merge — the full sequence, not just the commit.

## When to Use

- The change is a scoped, working-tree edit (not yet its own commit) that needs to land as an independent PR
- The target repo uses a staging-base branch model (`next-fix`/`next-feat` → `main`, or any CI-gate-only integration branch) — see `merge.md`'s CI-gate-only exception for how to detect this
- Repeated 2+ times in a session (e.g., multiple independent skill-file fixes each needing their own PR) — doing this by hand each time is what this topic replaces

## Procedure

1. **Branch from the staging base** (not from a possibly-stale local branch): `git fetch origin <staging-base>` → `git branch <topic-branch> origin/<staging-base>`
2. **Isolate the change into its own worktree** — avoids disturbing the main working tree's other in-progress edits: `git worktree add .worktrees/<topic-branch> <topic-branch>` (per `git-repo/worktree.md` — check for a reusable existing worktree first)
3. **Bring the change into the worktree**: if it's an existing commit, cherry-pick it; if it's an uncommitted working-tree diff, copy the exact files (`cp <path-in-main-tree> <path-in-worktree>`), verify with `git diff --stat` before committing
4. **Commit** (Conventional Commit tag, see `commit-message-discipline.md`)
5. **Push + draft PR** against the staging base (`gh pr create --base <staging-base> --draft`) — see `pr.md`
6. **CI watch → ready transition** — see `pr.md` Step 7.5 (same task, not deferred)
7. **Pre-merge content-review ask** — see `merge.md`'s CI-gate-only exception: present the PR URL even with conditions satisfied, since no other review mechanism ran
8. **Merge** — see `merge.md`. If the repo requires a different account for merge permission (org-repo mismatch with the acting account), switch via `gh auth switch --user <account>`, merge, then switch back immediately
9. **Sync the main working tree** — if the main tree still holds the now-committed-elsewhere diff, reset it (`git checkout -- <files>`) to avoid a stale duplicate

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Branch from local `HEAD` when the local branch has diverged from the staging base | Always branch from `origin/<staging-base>` fresh (step 1) — avoids carrying unrelated local drift into the new PR |
| 2 | `cp` a working-tree diff into a new worktree then leave the original uncommitted in the main tree | Step 9 — reset the main tree's copy once the content is safely committed elsewhere, to avoid two divergent copies of the same edit |
| 3 | Skip step 7 because steps 5-6 already ran cleanly | Step 7 is independent of CI status — it exists specifically for staging-base PRs where CI-gate-only means no other review touchpoint ever showed the content to a human |
| 4 | Batch multiple unrelated skill-file changes into one branch/PR | One topic-branch per logical change (same split criteria as `commit-tidy`) — keeps each PR's content-review ask (step 7) meaningful |

## Related

- `merge.md` — condition checks + CI-gate-only exception (step 7's source)
- `pr.md` — draft default + Step 7.5 CI-watch/ready (steps 5-6's source)
- `git-repo/worktree.md` — worktree reuse-before-create discipline (step 2)
- `commit-tidy/message-discipline.md` — commit message conventions (step 4)
