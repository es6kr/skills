# Rename Worktree

Rename an existing git worktree — both the directory and all internal metadata references.

`git worktree move` exists on some platforms but is unreliable on Windows. This procedure uses direct metadata manipulation for cross-platform safety.

## When to Use

- Reuse an existing worktree for a different branch/purpose
- Fix a misleading worktree name after branch rename
- Reclaim a worktree created by vibe-kanban or Claude Code isolation

## Supported layouts

- **Standard layout** — `<repo>/.git/worktrees/<name>` is the metadata location
- **Bare-with-worktree** — `<repo>/.git` is a gitdir-file pointing into a separate bare repo (e.g., `~/.agents/.git` → `~/ghq/.../<repo>.git`). The script auto-detects this by reading the worktree's `.git` pointer and overriding `GIT_WT_BASE` with the actual metadata parent directory; no special flag is required.

## Procedure

**One script call completes the rename** — no manual steps.

```bash
bash ~/.claude/skills/git-repo/scripts/rename-worktree.sh <repo> <old-name> <new-name> [--branch <branch>] [--wt-base <dir>]
```

| Argument | Description | Example |
|----------|-------------|---------|
| `<repo>` | Main repository absolute path | `~/ghq/github.com/org/repo` |
| `<old-name>` | Current directory name under the worktree base | `claude` |
| `<new-name>` | New directory name | `chore-cleanup-pr17-leftovers` |
| `--branch` | (optional) Branch to switch to. Checkout if local, create otherwise | `chore/cleanup-pr17-leftovers` |
| `--wt-base` | (optional) Worktree base dir relative to `<repo>` (default `.claude/worktrees`). Set for repos that keep worktrees elsewhere (e.g. `.worktrees`) | `.worktrees` |

Only the **worktree directory** base is affected by `--wt-base`. The `.git/worktrees/<name>` metadata location is auto-resolved from the worktree's `.git` pointer (see "Supported layouts"), so no metadata flag is needed.

### Examples

```bash
# Rename worktree + switch branch
bash ~/.claude/skills/git-repo/scripts/rename-worktree.sh \
  ~/ghq/github.com/myorg/myrepo \
  claude \
  chore-cleanup-leftovers \
  --branch chore/cleanup-leftovers

# Rename worktree only (keep branch)
bash ~/.claude/skills/git-repo/scripts/rename-worktree.sh \
  ~/ghq/github.com/myorg/webapp \
  old-feature \
  new-feature

# Repo that keeps worktrees at <repo>/.worktrees/ (not .claude/worktrees/)
bash ~/.claude/skills/git-repo/scripts/rename-worktree.sh \
  ~/ghq/github.com/myorg/turborepo-web \
  old-feature \
  new-feature \
  --wt-base .worktrees
```

### Internal steps performed by the script

1. mv `.claude/worktrees/<old>` → `<new>` (directory)
2. mv `.git/worktrees/<old>` → `<new>` (metadata)
3. Update the worktree's `.git` file → point to the new metadata path
4. Update the metadata's `gitdir` → point to the new worktree path
5. `git worktree repair`
6. (optional) Branch switch
7. Verification output

### Manual procedure (when needed)

Use only when the script cannot run (permission issues, non-standard paths, etc.):

<details>
<summary>Manual procedure (expand)</summary>

1. `mv .claude/worktrees/<old> .claude/worktrees/<new>`
2. `mv .git/worktrees/<old> .git/worktrees/<new>`
3. `echo "gitdir: <repo>/.git/worktrees/<new>" > .claude/worktrees/<new>/.git`
4. `echo "<repo>/.claude/worktrees/<new>/.git" > .git/worktrees/<new>/gitdir`
5. `git worktree repair`
6. `cd .claude/worktrees/<new> && git checkout <branch>`
7. Verify with `git worktree list`

</details>

## Key Principles

- **Operation-state gate before any rename/reuse** — if the worktree's gitdir contains `CHERRY_PICK_HEAD`/`MERGE_HEAD`/`REBASE_HEAD`/`rebase-merge`/`rebase-apply`/`BISECT_LOG`, or `git status --porcelain` shows unmerged codes (`DU`/`UU`/`AA`…), an operation is mid-flight — **abort the rename and report to the user** (see `worktree.md` §2 Step 2.0)
- **Always check for uncommitted changes first** — renaming metadata with dirty state risks data loss
- **Update both directions**: metadata→worktree (`gitdir`) AND worktree→metadata (`.git` file)
- **Paths must be absolute** in `gitdir` and `.git` files
- **On Windows**: use forward slashes in `.git` file paths (git handles both, but forward is safer)

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `fatal: not a git repository` | `.git` file points to old metadata path OR uses Unix-style `/c/...` on Windows | Update `.git` file in worktree dir with Windows-style `C:/...` path |
| worktree not in `git worktree list` | metadata dir name mismatch | Check `.git/worktrees/` for old name remnants |
| `fatal: <path> is already registered` | old metadata not fully renamed | Remove old entry, re-register |
| worktree shows `prunable` after rename | metadata file paths are Unix-style on Windows | Rewrite `.git` and `.git/worktrees/<name>/gitdir` with `C:/...` paths, then `git worktree repair` |
| `ERROR: metadata directory not found at <repo>/.git/worktrees/<name>` in a bare-with-worktree layout | Older script revision hardcoded `<repo>/.git/worktrees` and did not resolve from the worktree `.git` pointer | Script now derives `GIT_WT_BASE` from `dirname(gitdir)` of the worktree's `.git` file — pull the latest skill version |
| Directory + metadata renamed successfully but branch is unchanged (`git branch --show-current` still shows `<old>`) | `--branch <target>` is already checked out in another worktree — the final `git checkout <branch>` step fails after the mv steps already succeeded, and the script does not roll back | Check out under a differently-named local branch instead: `git -C <renamed-worktree> checkout -b <local-name>-tmp origin/<target>`, do the work there, then push its content to the target ref: `git push origin <local-name>-tmp:<target>` (see failed-attempts.md "rename-worktree.sh partial failure") |

### Windows path compatibility (2026-05-21 fix)

Earlier versions of `scripts/rename-worktree.sh` wrote `/c/Users/...` style paths into git metadata files (`.git`, `.git/worktrees/<name>/gitdir`). Windows git fails to resolve those paths → `fatal: not a git repository: (NULL)`. The script now uses `cygpath -m` to convert to `C:/Users/...` style on Git Bash/MSYS while keeping Unix paths for `mv`/`cd` operations.

If you hit this on an existing worktree, manually fix both metadata files:
```bash
printf 'gitdir: C:/path/to/repo/.git/worktrees/<name>\n' > <worktree>/.git
printf 'C:/path/to/repo/.claude/worktrees/<name>/.git\n' > .git/worktrees/<name>/gitdir
git worktree repair
```
