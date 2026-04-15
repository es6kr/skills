# Fix Worktree

A tool to fix incorrect worktree configuration in ghq bare repositories.

## Diagnosis (Problem Scenarios)

The following issues can occur in ghq + git worktree structures:
- `bare = false` but `core.worktree` points to a wrong path
- Worktree directory exists but is not registered in the bare repo
- Incorrect `core.worktree` config causes git commands to fail

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

## Register Existing Directory as Worktree

Register a directory that already contains files but is not listed as a git worktree, using metadata manipulation only.

### Pre-check (mandatory)

```bash
# Verify it's not already registered
cd /path/to/main-repo && git worktree list
```

If the directory is already listed, skip registration.

### Procedure

1. **Create branch** (based on existing commit):

```bash
cd /path/to/main-repo
git branch worktree-<name> <commit-sha>
```

2. **Create gitdir metadata** (`<main-repo>/.git/worktrees/<name>/`):

```bash
mkdir -p .git/worktrees/<name>
echo 'ref: refs/heads/worktree-<name>' > .git/worktrees/<name>/HEAD
echo '../..' > .git/worktrees/<name>/commondir
echo '<absolute-path-to-worktree-dir>/.git' > .git/worktrees/<name>/gitdir
```

3. **Create `.git` file in the worktree directory**:

```bash
echo 'gitdir: <absolute-path-to-main-repo>/.git/worktrees/<name>' > /path/to/worktree-dir/.git
```

4. **Rebuild index** (resolves deleted file status):

```bash
cd /path/to/worktree-dir && git reset HEAD -- .
```

5. **Verify**:

```bash
cd /path/to/main-repo && git worktree list   # confirm registration
cd /path/to/worktree-dir && git status        # confirm clean state
```

### Key Principles

- **Never move files (mv)** — only create metadata, leave existing files untouched
- **Never use `git worktree add`** — it fails on directories that already contain files
- **Always check registration first** — `git worktree list` to prevent duplicates

## Register Existing Directory as Worktree

Register a directory that already contains files but is not listed as a git worktree, using metadata manipulation only.

### Pre-check (mandatory)

```bash
# Verify it's not already registered
cd /path/to/main-repo && git worktree list
```

If the directory is already listed, skip registration.

### Procedure

1. **Create branch** (based on existing commit):

```bash
cd /path/to/main-repo
git branch worktree-<name> <commit-sha>
```

2. **Create gitdir metadata** (`<main-repo>/.git/worktrees/<name>/`):

```bash
mkdir -p .git/worktrees/<name>
echo 'ref: refs/heads/worktree-<name>' > .git/worktrees/<name>/HEAD
echo '../..' > .git/worktrees/<name>/commondir
echo '<absolute-path-to-worktree-dir>/.git' > .git/worktrees/<name>/gitdir
```

3. **Create `.git` file in the worktree directory**:

```bash
echo 'gitdir: <absolute-path-to-main-repo>/.git/worktrees/<name>' > /path/to/worktree-dir/.git
```

4. **Rebuild index** (resolves deleted file status):

```bash
cd /path/to/worktree-dir && git reset HEAD -- .
```

5. **Verify**:

```bash
cd /path/to/main-repo && git worktree list   # confirm registration
cd /path/to/worktree-dir && git status        # confirm clean state
```

### Key Principles

- **Never move files (mv)** — only create metadata, leave existing files untouched
- **Never use `git worktree add`** — it fails on directories that already contain files
- **Always check registration first** — `git worktree list` to prevent duplicates

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
