# Fix Worktree

A tool to fix incorrect worktree configuration in ghq bare repositories.

## Problem Scenarios

The following issues can occur in ghq + git worktree structures:
- `bare = false` but `core.worktree` points to a wrong path
- Worktree exists but is not registered in the bare repo
- Remaining `core.worktree` config causes git commands to fail

## Usage

### Scan and fix all bare repos

```bash
scripts/git-fix-worktree.sh
```

### Fix a specific bare repo

```bash
scripts/git-fix-worktree.sh /path/to/repo.git
```

## Fix Behavior

1. **When worktree exists**: Register in bare repo's `worktrees/` directory
2. **Worktree's `.git` file**: Fix to point to subdirectory under `worktrees/`
3. **Index regeneration**: If missing, regenerate with `git read-tree HEAD` (preserves uncommitted changes)
4. **Config restoration**: Remove `core.worktree`, set `core.bare = true`

## Example Output

```
Scanning for broken bare repos in: /Users/es6kr/.ghq
Fixed: /Users/es6kr/.ghq/github.com/user/repo.git
  Registered worktree: /Users/es6kr/works/repo
  Updated .git -> /Users/es6kr/.ghq/github.com/user/repo.git/worktrees/repo
  Rebuilt index
Done.
```

## Related Commands

```bash
# Check worktree status
git worktree list

# Check bare repo configuration
git config -f /path/to/repo.git/config --list

# Check worktree's .git file
cat /path/to/worktree/.git
```

## Notes

- Local changes (uncommitted changes) are safely preserved
- Index regeneration is based on HEAD, so staged/unstaged files remain intact
- The script only modifies metadata and does not delete actual files
