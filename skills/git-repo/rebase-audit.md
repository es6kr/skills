# Rebase Audit

Audit an **active interactive rebase**'s currently-staged files for accidental reverts, without touching the rebase itself.

## When to use

- An interactive rebase (`git rebase -i`) is paused at a conflict, or about to `--continue`, and the staged content should be reviewed before it lands as a commit
- A rebase replays many commits across many files — manually diffing each staged file against its prior state is repetitive and easy to under-cover
- The goal is specifically to catch **accidental reverts**: a conflict resolution that silently drops a fix/finding a past commit deliberately introduced, because the "wrong side" of the conflict was kept

This topic is read-only with respect to the rebase: it never runs `git rebase --continue/--skip/--abort`, never edits staged content, and never touches `REBASE_HEAD`/`rebase-merge`/`rebase-apply`. It only reports candidates for the user to review.

## Procedure

### 1. Confirm an active rebase (HARD STOP — do not proceed otherwise)

```bash
gitdir=$(git -C <repo> rev-parse --absolute-git-dir)
ls "$gitdir"/rebase-merge "$gitdir"/rebase-apply 2>/dev/null
```

If neither exists, there is no active rebase — this topic does not apply (see `worktree` topic's "Operation-state gate" for the same detection pattern used elsewhere in this skill).

### 2. List staged files

```bash
git -C <repo> diff --cached --name-only
```

Every file the current rebase step has staged is a candidate for audit.

### 3. Per-file HEAD-vs-index diff

For each staged file:

```bash
git -C <repo> diff --cached -- <file>
```

`HEAD` during a paused rebase is the last successfully-replayed commit, so this diff shows exactly what the current step's resolution is about to commit for that file — the same view a manual `diff <(git show HEAD:<file>) <file>` produces.

### 4. Revert-pattern heuristic

Within each file's diff, flag a hunk as a **revert candidate** when it **removes** content that:

- Matches wording from a past commit message touching the same file (`git log --oneline -- <file>`) — e.g. the commit added a line documenting a fix/finding, and this hunk deletes that exact line or a close paraphrase
- Removes a Don't/Do table row, a HARD STOP marker, or a self-check bullet that a prior commit introduced (these are the highest-cost accidental-revert targets — silent behavioral regressions)
- Re-introduces a pattern a past commit explicitly removed (check the commit message for "remove"/"fix"/"correct" framing, then look for the pre-fix text reappearing)

This is a heuristic, not a guarantee — false positives (legitimate re-edits that happen to remove similar text) and false negatives (reverts with no textual trace in commit messages) are both possible. Its job is to narrow 13 files down to a short review list, not to replace human judgment.

```bash
# For each staged file, cross-reference removed lines (diff `-` lines) against
# recent commit subjects/bodies touching that file:
git -C <repo> log --oneline -20 -- <file>
git -C <repo> diff --cached -- <file> | grep '^-[^-]'
```

### 5. Present candidates via AskUserQuestion (multiSelect)

Report every flagged hunk as one option (file + line range + a one-line excerpt of what would be lost), and let the user pick which ones to actually restore. Do not auto-restore — a flagged hunk may be an intentional re-edit, not a revert.

```text
AskUserQuestion {
  question: "N staged files show hunks that may be accidental reverts. Which should be restored?",
  multiSelect: true,
  options: [
    { label: "<file>:<line-range>", description: "Removes: \"<excerpt>\" (introduced in <past-commit-sha> \"<subject>\")" },
    ...
  ]
}
```

### 6. Restore selected candidates

For each user-selected candidate, re-apply the removed content to the **index** (staged, not the rebase machinery itself) via a targeted Edit on the working-tree file followed by `git -C <repo> add <file>` — the same isolate-hunk-style targeted restoration, scoped to just that hunk. Do not touch hunks the user did not select.

### 7. Leave the rebase decision to the user

After restoration, report the updated `git diff --cached` state and stop. Whether to `git rebase --continue` is the user's call — this topic never runs it.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Run this audit without first confirming an active rebase (Step 1) | Gate on `rebase-merge`/`rebase-apply` presence — outside a rebase, this topic doesn't apply |
| 2 | Auto-restore every flagged hunk | Present all candidates via `AskUserQuestion` multiSelect — restoration is a per-hunk user decision |
| 3 | Run `git rebase --continue/--skip/--abort` as part of this topic | This topic is audit-only. Rebase control flow stays with the user |
| 4 | Treat a flagged hunk as confirmed-revert | It's a heuristic candidate — cite the past commit it may have reverted so the user can judge intent |
| 5 | Diff against a fixed commit SHA captured once at topic start | Re-run `git diff --cached -- <file>` fresh each time — the rebase may advance (new `--continue`) between audit passes |

## Self-check (before presenting candidates)

1. Did Step 1 confirm an active rebase? If not, stop — this topic doesn't apply.
2. Does every flagged hunk cite the specific past commit(s) whose content it may be reverting?
3. Are all candidates gathered into a single `AskUserQuestion` multiSelect call, rather than one ask per file?
4. Did any restoration touch content outside the user's selected hunks?

## Post-mortem: clobbered branch pointers after a botched rebase

A different failure shape than the live-rebase case above: an interactive rebase finishes badly (e.g. lands on a junk placeholder commit) and, as a side effect, a batch of unrelated local branches end up pointing at that same wrong tip — their reflog shows a single `branch: Created from main`-style entry with no prior history, meaning the ref was recreated rather than moved. This shows up hours or days later as many branches sharing one identical short SHA that clearly isn't any of their real work.

This is a **branch-pointer repair**, not a rebase-in-progress audit — no `rebase-merge`/`rebase-apply` state exists by the time it's noticed, and nothing here touches rebase machinery. It shares this topic's spirit (reconstruct correct state without trusting the corrupted ref) enough to live alongside it rather than as a new topic.

### Detection

```bash
# Find every local branch pinned to the same (bogus) short SHA
git branch --format='%(objectname:short) %(refname:short)' | sort | uniq -c -w8 | awk '$1>1'

# Confirm it's a recreate, not a real position: a single reflog entry with no prior SHA
git reflog show <branch> --date=iso   # one line, "branch: Created from <ref>" = recreated
```

### Recovery — reconcile each branch to its own GitHub PR head

Each affected branch's real content almost always still exists in its own git history via the PR that was opened from it — the local ref is wrong, not the work. Reconcile branch-by-branch:

1. **Map branch → PR head SHA** by exact `headRefName` match:
   ```bash
   gh pr list -R <owner>/<repo> --state all --limit 400 --json number,state,headRefName,headRefOid
   ```
   A handful of branches may have no name match (renamed before opening the PR, or never had one) — leave those unresolved rather than guessing from a fuzzy name match.

2. **Verify the candidate SHA before trusting it** — name match alone is not proof. Diff the PR head's own changed files (relative to its merge-base with the primary branch) against the affected worktree's on-disk content:
   ```bash
   mb=$(git merge-base <pr-head-sha> origin/main)
   git diff --name-only "$mb" <pr-head-sha>                       # files the PR itself touched
   git -C <worktree> diff <pr-head-sha> -- <one of those files>   # should be empty or mode-only
   ```
   Expect zero real hunks (ignore pure `old mode`/`new mode` lines — Windows checkouts routinely lose the exec bit) or a residual diff that reads as legitimate uncommitted follow-up work, not a wholesale content mismatch. A "deleted file" diff where the file is physically present and byte-identical on disk is a false alarm too — it means the path is `??` untracked because the corrupted branch's tree (main) predates that file, not a real mismatch (`git status --porcelain -- <file>` shows `??`; content is confirmed with `git show <sha>:<file>` vs the file on disk).

3. **Repair with `git reset --mixed <pr-head-sha>`** run inside that branch's own worktree — never `--hard`. The working-tree files are already correct (they were never touched, only the ref and index were), so `--mixed` re-points `HEAD` and rebuilds the index to match, leaving any genuine uncommitted follow-up work exactly where it was as ordinary unstaged changes. This is local-only and reversible via reflog; per this workspace's git rules, `git reset` of any kind is a `AskUserQuestion` HARD STOP — surface the full branch→PR→SHA mapping table before running it, and separately flag `main` itself if it is also among the affected refs.

4. **`main` (or any shared/primary branch) is a special case, not part of the bulk repair.** A primary branch has no "PR of its own" to restore from in the same sense — its correct target is `origin/main` (or whatever upstream tracks it), not any single feature PR's head, even if a PR happens to have `headRefName: main` (that PR's head can itself be stale relative to the current remote tip). Diagnose separately:
   ```bash
   git rev-list --count origin/main..<local-main-sha>   # commits only in the corrupted local tip
   git rev-list --count <local-main-sha>..origin/main   # commits missing from the corrupted local tip
   ```
   A nonzero count in both directions confirms divergence from a bad rebase rather than a legitimate ahead-of-remote state, and the fix is `git reset --mixed origin/main` — proposed to the user as its own decision, not bundled into the feature-branch batch.

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Trust a branch→PR name match without diffing content | Verify via merge-base diff of the PR's own changed files (Step 2) before resetting anything |
| 2 | Treat a `deleted file mode` diff against an untracked-but-present file as a real mismatch | Check `git status --porcelain` first — `??` + byte-identical content is a false alarm, not evidence of the wrong SHA |
| 3 | Bundle `main`/primary-branch repair into the same batch as feature branches | Diagnose `main` separately against `origin/main` — it has no single PR head to restore from |
| 4 | Run `git reset --hard` to "just fix it faster" | `--mixed` only — working-tree files were never corrupted, only the ref/index; `--hard` would discard real uncommitted follow-up work |
| 5 | Reset branches the batch script couldn't confidently map | Leave unmapped branches (no PR, or ambiguous fuzzy match) unresolved and report them, rather than guessing |
