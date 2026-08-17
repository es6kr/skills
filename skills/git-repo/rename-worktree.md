# Rename Worktree

Rename an existing git worktree — both the directory and all internal metadata references.

`git worktree move` exists on some platforms but is unreliable on Windows. This procedure uses direct metadata manipulation for cross-platform safety.

## When to Use

- Reuse an existing worktree for a different branch/purpose
- Fix a misleading worktree name after branch rename
- Reclaim a worktree created by vibe-kanban or Claude Code isolation

**Scope limitation (HARD STOP)**: this script assumes `<old-name>` already lives directly under `--wt-base` (default `.worktrees`) — it renames the leaf directory and re-branches in place, it does **not** relocate a worktree that lives entirely outside any `--wt-base` tree (a legacy `.claude/worktrees/`, a sibling `<repo>-wt/` next to `<repo>/`, a bare `~/.worktrees/`, or a path an external tool created on its own). Running this script against such a worktree perpetuates its wrong location — it will rename/re-branch it in place at the wrong path, not move it. Check the worktree's parent directory first (`git worktree list`); if it is not already `<repo>/.worktrees/`, apply [move-worktree](./move-worktree.md) Scenario B to relocate it before calling this script.

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
| `--base` | (optional) Base ref for a **newly created** branch. Ignored when `--branch` already exists locally or on origin | `origin/main` |
| `--wt-base` | (optional) Worktree base dir relative to `<repo>` (default `.worktrees`). Set for repos that keep worktrees elsewhere | `.worktrees` |


Only the **worktree directory** base is affected by `--wt-base`. The `.git/worktrees/<name>` metadata location is auto-resolved from the worktree's `.git` pointer (see "Supported layouts"), so no metadata flag is needed.

### Examples

**Pass `--base` whenever the new branch should not start where the old work ended (HARD STOP for the reuse path).** Without it a newly created branch starts at the worktree's **current HEAD** — and in this script's primary use case, reclaiming an inactive worktree, that HEAD is the stale tip of the work the worktree used to hold. The new branch then silently carries commits that are already merged (or abandoned), and a PR opened from it shows them as its own. The script cannot pick a default safely, because the integration branch is not always `main` — some repos accumulate onto a staging branch — so it warns and names the HEAD it fell back to instead of guessing.

```bash
# Reclaiming an inactive worktree: base the new branch on the integration branch,
# not on whatever the old branch ended at
bash <skill-dir>/scripts/rename-worktree.sh \
  ~/ghq/github.com/myorg/myrepo \
  fix-old-merged-pr \
  fix-new-work \
  --branch fix/new-work \
  --base origin/main \
  --wt-base .worktrees

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
| `ERROR: metadata directory not found at ../../.git/worktrees/<name>` (note the **relative** path in the message) | The worktree's `.git` file holds a relative gitdir (`gitdir: ../../.git/worktrees/<name>`) instead of an absolute one. Both forms are valid git, and which one a worktree gets depends on how it was created, but the script resolves the pointer without first making it absolute relative to the worktree directory. It aborts before renaming anything, so the worktree is left intact | Rewrite the pointer as absolute, then retry: `printf 'gitdir: %s/.git/worktrees/%s\n' "<repo>" "<name>" > <worktree>/.git && git -C <repo> worktree repair`. Confirm with `cat <worktree>/.git` — a working example in the same repo shows the expected absolute form |
| Directory + metadata renamed successfully but branch is unchanged (`git branch --show-current` still shows `<old>`) | `--branch <target>` is already checked out in another worktree — the final `git checkout <branch>` step fails after the mv steps already succeeded, and the script does not roll back | Check out under a differently-named local branch instead: `git -C <renamed-worktree> checkout -b <local-name>-tmp origin/<target>`, do the work there, then push its content to the target ref: `git push origin <local-name>-tmp:<target>` (see failed-attempts.md "rename-worktree.sh partial failure") |

### Windows path compatibility (2026-05-21 fix)

Earlier versions of `scripts/rename-worktree.sh` wrote `/c/Users/...` style paths into git metadata files (`.git`, `.git/worktrees/<name>/gitdir`). Windows git fails to resolve those paths → `fatal: not a git repository: (NULL)`. The script now uses `cygpath -m` to convert to `C:/Users/...` style on Git Bash/MSYS while keeping Unix paths for `mv`/`cd` operations.

If you hit this on an existing worktree, manually fix both metadata files:
```bash
printf 'gitdir: C:/path/to/repo/.git/worktrees/<name>\n' > <worktree>/.git
printf 'C:/path/to/repo/.claude/worktrees/<name>/.git\n' > .git/worktrees/<name>/gitdir
git worktree repair
```
