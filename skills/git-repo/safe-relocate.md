# Safe Branch Relocation (`safe-relocate`)

Use this topic when relocating working commits from a stale, diverged, or dirty working branch onto a clean fresh branch created directly off the latest remote base (`origin/main`, `origin/next-fix`, `origin/next-feat`).

## Purpose

Avoids common pitfalls during manual branch relocation:
- Accidental accumulation of unmerged sibling commits
- Implicit branch divergence from stale local tracking branches
- Pushing unverified files or out-of-scope diffs to remote PRs

## Mandatory 5-Step Relocation Procedure

Follow these steps sequentially whenever relocating commits to a fresh branch:

### Step 1: Remote Fetch & Base Synchronization
Fetch the latest remote state before creating the target branch. Never create a fresh branch from a local stale base.
```bash
git fetch origin <base-branch>
```

### Step 2: Fresh Branch Creation
Create the target branch directly off `origin/<base-branch>` to guarantee a zero-divergence starting state.
```bash
git checkout -b <fresh-branch-name> origin/<base-branch>
```

### Step 3: Divergence Verification
Verify that the new branch starts strictly aligned with `origin/<base-branch>`.
```bash
git rev-parse HEAD
git rev-parse origin/<base-branch>
```
Both SHAs MUST match before proceeding.

### Step 4: Selective Cherry-Pick & Conflict Resolution
Cherry-pick only the intended commits from the source branch.
```bash
# Range cherry-pick (oldest_sha^..newest_sha) or single commit
git cherry-pick <commit-sha-start>^..<commit-sha-end>
```
If conflicts occur, resolve them explicitly, stage changes (`git add`), and run `git cherry-pick --continue`. Never use `git reset` or `git checkout -- .` to bypass conflicts.

### Step 5: Diff & Scope Audit (HARD STOP)
Inspect the final diff against the base branch to confirm that only target files are modified and no extra files/lines were dragged along.
```bash
git diff --stat origin/<base-branch>
```
Verify:
1. File list matches the intended scope exactly.
2. No unexpected configuration or formatting changes are present.
3. No secrets or untracked test artifacts were included.

---

## Don't / Do Table

| # | Don't | Do |
|---|-------|----|
| 1 | Branch off local `main` / `next-fix` without fetching | Always fetch `origin` and branch off `origin/<base-branch>` |
| 2 | Use `git merge <old-branch>` to relocate commits | Use `git cherry-pick` for targeted commit relocation |
| 3 | Push immediately after cherry-pick without scope check | Always run `git diff --stat origin/<base-branch>` to audit modified files before push |
