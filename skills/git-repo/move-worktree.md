# Move Worktree

Move unregistered worktree directories to `.worktrees/` and register them as proper git worktrees, or reclaim merged PR worktrees for a different branch.

## When to Use

- A worktree was created in `.claude/worktrees/` (legacy location) and needs to move to `.worktrees/`
- An orphaned directory in `.worktrees/` has no `.git` file (not a registered worktree)
- Reclaiming a merged PR's worktree directory for a new branch

## Procedure

### Scenario A: Register a new worktree from an existing directory

When `.worktrees/<name>` exists but is not a git worktree (no `.git` file, not in `git worktree list`):

```bash
cd /path/to/main-repo

# 1. Check current worktrees
git worktree list

# 2. Verify the directory is NOT registered
#    (it should NOT appear in worktree list)

# 3. Create a proper worktree at the target path
#    This will fail if the directory already exists — remove or rename it first
mv .worktrees/<old-name> .worktrees/<old-name>.tmp
git worktree add .worktrees/<new-name> <branch-name>
# Clean up the old directory
rm -rf .worktrees/<old-name>.tmp  # AskUserQuestion required (safe-delete)
```

### Scenario B: Move from `.claude/worktrees/` (or any non-default location) to the configured worktree path

When a worktree exists outside the path defined by the active environment context (default: `.worktrees/`):

```bash
cd /path/to/main-repo

# 1. If it's a registered worktree, prefer `git worktree move`.
#    NOTE: `git worktree move` is known to be unreliable on Windows
#    (see rename-worktree.md). On Windows, delegate to the rename-worktree
#    script/procedure instead of running `git worktree move` directly.
git worktree move .claude/worktrees/<name> .worktrees/<name>

# 2. If it's just a directory (not registered), do NOT pre-mv and then
#    `git worktree add` to the same path — `git worktree add` rejects an
#    existing directory. Instead either:
#    (a) Stage at a sibling path, then `git worktree add` to the final path
#        and remove the staged directory (AskUserQuestion via safe-delete):
mv .claude/worktrees/<name> .worktrees/<name>.staged
git worktree add .worktrees/<name> <branch>
# rm -rf .worktrees/<name>.staged   # safe-delete approval required

#    OR (b) Treat as orphaned and follow Scenario A (rename the source first,
#    then `git worktree add` to the clean target path).
```

### Scenario C: Reclaim a merged PR worktree for a new branch

When a worktree was used for a now-merged PR and you want to reuse it:

1. **If the worktree is still registered** (`git worktree list` shows it):
   - **Check the parent directory first.** If it is NOT already `<repo>/.worktrees/` (e.g. it sits at a legacy `.claude/worktrees/`, a sibling `<repo>-wt/`, a bare `~/.worktrees/`, or was created by an external tool at an arbitrary path), apply **Scenario B above to relocate it first** — `rename-worktree.sh` alone will not fix the location, it only renames/re-branches in place under whatever base it's already at. Run `scripts/check-worktree-canonical.sh <repo> <name>` to make this check mechanically (exit 0 canonical / 1 non-canonical + prints the relocation command / 2 not registered).
   - Once the path is confirmed (or corrected to) `<repo>/.worktrees/`, use [rename-worktree](./rename-worktree.md) procedure to rename + switch branch

2. **If the worktree is orphaned** (not in `git worktree list`):
   - Remove the old directory
   - Create a fresh worktree: `git worktree add .worktrees/<new-name> <new-branch>`

3. **If the old branch is already merged and deleted**:
   ```bash
   # Prune stale worktree entries
   git worktree prune
### Scenario D: Promote a worktree to a standalone git repository (`--no-checkout` + `mv`)

When a worktree has accumulated local commits/changes and needs to be extracted into a separate, independent repository under `~/ghq/...`:

1. **Clone `.git` metadata only (no checkout)**:
   ```bash
   git clone --no-checkout --branch <branch> --single-branch /path/to/main-repo /path/to/new-repo
   ```

2. **Move working tree items directly to target repository** (preserves uncommitted modifications without copying overhead):
   ```bash
   # Move all files and directories except the .git pointer file (includes dotfiles)
   find .worktrees/<name> -mindepth 1 -maxdepth 1 ! -name .git -exec mv {} /path/to/new-repo/ \;
   ```

3. **Rebuild/synchronize index safely in the new repository**:
   ```bash
   git -C /path/to/new-repo reset HEAD -- .
   ```

4. **Prune the old worktree from the main repository**:
   ```bash
   rm .worktrees/<name>/.git
   rmdir .worktrees/<name>
   git -C /path/to/main-repo worktree prune
   ```

5. **Launch GUI on the new standalone repository**:
   ```bash
   sourcegit /path/to/new-repo
   ```

### Post-move verification

```bash
git worktree list                    # confirm registration
cd .worktrees/<name>
git branch --show-current            # confirm correct branch
git status --short                   # confirm clean state
```

## Key Principles

- **Use the worktree path defined by the active environment context** — this skill's default is `.worktrees/`
- **Always verify with `git worktree list`** before and after operations
- **Use `git worktree prune`** to clean up stale entries from deleted directories
- **For registered worktrees needing rename**: delegate to [rename-worktree](./rename-worktree.md)
- **AskUserQuestion required** before deleting any worktree directory (`safe-delete` rule)

