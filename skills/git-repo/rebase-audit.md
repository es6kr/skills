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
