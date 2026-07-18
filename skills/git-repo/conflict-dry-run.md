# Conflict Dry-Run

Test whether a merge or cherry-pick would apply cleanly, without touching the (possibly dirty) main working tree.

## When to Use

- Verifying a commit will cherry-pick cleanly onto another branch before actually doing it
- Checking whether two branches (e.g. a staging branch and `main`) would conflict before opening a promotion PR
- Any dry-run test where the main working tree has uncommitted changes you must not disturb

## Why Not the Main Working Tree

Running `git checkout -b <tmp> <ref>` or `git merge --no-commit` directly in the main working tree risks:

- Colliding with uncommitted changes already present (the dry-run's changed files may overlap with real in-progress edits)
- Leaving the repo in a half-merged/half-checked-out state if the test is interrupted
- Requiring careful cleanup (`git merge --abort`, checkout back) that itself competes with concurrent work in the same tree

An isolated worktree sidesteps all of this — it has its own working tree and index, entirely separate from the main one.

## Procedure

### 1. Create a detached worktree from the bare mirror

Use the bare mirror (`ghq`-style bare clone), not the main working tree, as the source:

```bash
BARE=/path/to/ghq/github.com/<org>/<repo>.git   # or any bare/mirror remote of the repo
SCRATCH=/tmp/conflict-check                      # any scratch location, session-specific

git -C "$BARE" worktree add --detach "$SCRATCH" origin/<base-ref>
```

`--detach` avoids the "branch already checked out elsewhere" error when the branch under test is also checked out in another active worktree.

### 2. Run the test

**Cherry-pick applicability**:

```bash
cd "$SCRATCH"
git cherry-pick --no-commit <sha>
git status --short          # staged M/A with no U (unmerged) = clean
git diff --stat              # confirm expected file set
```

**Merge cleanliness** (e.g. would branch A merge cleanly into branch B):

```bash
cd "$SCRATCH"
git merge origin/<other-branch> --no-commit --no-ff
git diff --name-only --diff-filter=U | wc -l   # 0 = clean, N>0 = N conflicting files
```

### 3. Clean up

```bash
cd "$SCRATCH"
git merge --abort 2>/dev/null || git reset --hard   # discard the dry-run state
cd "$BARE"
git worktree remove --force "$SCRATCH"
```

If a safety hook blocks `git merge --abort` (treating it as "discarding in-progress conflict resolution"), it is safe to leave the disposable scratch worktree as-is rather than force through the guard — it does not affect the main working tree or any shared branch.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | `git checkout -b <tmp>` in the main working tree to test a merge/cherry-pick | `git worktree add --detach <bare> <ref>` — isolated, no risk to uncommitted work |
| 2 | Trust `git merge-tree <base> <a> <b>` (legacy 2-tree form) with the wrong base argument (e.g. passing one of the branches itself as base) | Compute the actual merge-base first (`git merge-base <a> <b>`) and pass that, or just do a real `git merge --no-commit` in an isolated worktree — it's authoritative where `merge-tree` misuse is not |
| 3 | Interpret a platform's `mergeable: false` / `mergeable_state: "dirty"` API field as possibly stale without checking | Reproduce locally via this dry-run procedure before concluding the platform's mergeability computation is wrong |
| 4 | Leave the scratch worktree registered after the test | Remove it (`git worktree remove --force`) unless a safety hook blocks the abort step — in that case leaving it is harmless (see Step 3) |

## Related

- [worktree.md](./worktree.md) — general worktree inventory/reuse/create workflow (for actual work, not dry-run testing)
