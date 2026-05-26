# Move Worktree

Move unregistered worktree directories to `.claude/worktrees/` and register them as proper git worktrees, or reclaim merged PR worktrees for a different branch.

## When to Use

- A worktree was created in `.worktrees/` (wrong location) and needs to move to `.claude/worktrees/`
- An orphaned directory in `.claude/worktrees/` has no `.git` file (not a registered worktree)
- Reclaiming a merged PR's worktree directory for a new branch

## Procedure

### Scenario A: Register a new worktree from an existing directory

When `.claude/worktrees/<name>` exists but is not a git worktree (no `.git` file, not in `git worktree list`):

```bash
cd /path/to/main-repo

# 1. Check current worktrees
git worktree list

# 2. Verify the directory is NOT registered
#    (it should NOT appear in worktree list)

# 3. Create a proper worktree at the target path
#    This will fail if the directory already exists — remove or rename it first
mv .claude/worktrees/<old-name> .claude/worktrees/<old-name>.tmp
git worktree add .claude/worktrees/<new-name> <branch-name>
# Clean up the old directory
rm -rf .claude/worktrees/<old-name>.tmp  # AskUserQuestion required (safe-delete)
```

### Scenario B: Move from `.worktrees/` to `.claude/worktrees/`

When a worktree was created in the wrong location:

```bash
cd /path/to/main-repo

# 1. If it's a registered worktree, use git worktree move
git worktree move .worktrees/<name> .claude/worktrees/<name>

# 2. If it's just a directory (not registered), treat as Scenario A
mv .worktrees/<name> .claude/worktrees/<name>
git worktree add .claude/worktrees/<name> <branch>
```

### Scenario C: Reclaim a merged PR worktree for a new branch

When a worktree was used for a now-merged PR and you want to reuse it:

1. **If the worktree is still registered** (`git worktree list` shows it):
   - Use [rename-worktree](./rename-worktree.md) procedure to rename + switch branch

2. **If the worktree is orphaned** (not in `git worktree list`):
   - Remove the old directory
   - Create a fresh worktree: `git worktree add .claude/worktrees/<new-name> <new-branch>`

3. **If the old branch is already merged and deleted**:
   ```bash
   # Prune stale worktree entries
   git worktree prune
   # Create new worktree
   git worktree add .claude/worktrees/<new-name> <new-branch>
   ```

### Post-move verification

```bash
git worktree list                    # confirm registration
cd .claude/worktrees/<name>
git branch --show-current            # confirm correct branch
git status --short                   # confirm clean state
```

## Key Principles

- **`.claude/worktrees/` is the only valid location** — `.worktrees/` is prohibited per CLAUDE.md
- **Always verify with `git worktree list`** before and after operations
- **Use `git worktree prune`** to clean up stale entries from deleted directories
- **For registered worktrees needing rename**: delegate to [rename-worktree](./rename-worktree.md)
- **AskUserQuestion required** before deleting any worktree directory (`safe-delete` rule)
