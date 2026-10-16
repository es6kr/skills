# Prune Worktrees & Branches

Safely detect and remove merged worktrees and remote-tracking expired (`gone`) local branches.

## When to use

- After merging a Pull Request into `main` or `develop`
- Periodic cleanup of accumulated feature or fix worktrees
- Called as Step 1 of the `tidy` topic pipeline (`[tidy.md](./tidy.md)`)

## Pruning Procedure

### 1. Batch Prune Merged Worktrees (Dry-Run First)

Use the dedicated Python helper script to scan all auxiliary worktrees in the repository:

```bash
python skills/git-repo/scripts/prune_merged_worktrees.py --repo <repo_path>
```

The script performs real-time verification:
- Checks GitHub PR status via `gh pr list --head <branch>` (detects squash merges which Git hash equality misses)
- Falls back to `git merge-base --is-ancestor` when offline or `gh` is unavailable
- Validates the working directory is clean (`git status --porcelain` is empty)
- Enforces the **Operation-State Gate**: skips any worktree with `CHERRY_PICK_HEAD`, `MERGE_HEAD`, `REBASE_HEAD`, or unmerged conflict status codes

### 2. Physical Execution with Branch Deletion

Once verified, execute the physical removal and delete corresponding local branches:

```bash
python skills/git-repo/scripts/prune_merged_worktrees.py --repo <repo_path> --execute --delete-branch
```

### 3. Clean Expired Remote-Tracking (`gone`) Branches

Fetch with prune and prune local branches whose remote tracking branch has been deleted:

```bash
git fetch -p
git branch -vv | grep 'gone]'
```

Delete confirmed gone branches:

```bash
git branch -d <branch_name>   # safe delete
git branch -D <branch_name>   # force delete if merged via squash/rebase
```

## Safety Invariants (HARD STOP)

1. **Operation-State Gate**: Never prune or delete a worktree in the middle of a rebase, merge, cherry-pick, or bisect.
2. **Dirty Tree Preservation**: Worktrees with uncommitted modifications or untracked candidate files must be preserved ([PRESERVED]) or resolved via `commit-tidy` and `diff-merge` before pruning.
