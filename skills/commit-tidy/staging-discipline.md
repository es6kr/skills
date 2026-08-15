# Staging Discipline

Pre-commit staging audit + sensitive-directory commit gate. Replaces the bare `git status` check with a full `git diff --cached --name-only` dump + 1:1 intent comparison.

## When to use

- Before every `git commit` invocation
- When the staged area accumulates across multiple operations
- When working on a branch that may have stale staged files from a prior turn or tool
- When editing inside sensitive directories (`rules/`, `agents/`, `docs/`, or any user-defined "never auto-commit" path)

## Core rule: explicit `git add` only (HARD STOP)

**Forbid `git add .` and `git add -A` outside of initial-import scenarios.** Every commit's staging set must come from explicit per-file or per-directory `git add` invocations the assistant chose.

| # | Don't | Do |
|---|-------|-----|
| 1 | `git add .` or `git add -A` to stage everything | `git add <file1> <file2>` or `git add apps/dt/` — explicit paths |
| 2 | Run `git commit` without running `git status` first | After `git add`, run `git status` and confirm nothing unintended (SVG, configs, etc.) got staged |
| 3 | Batch `add` over many modified files at once | Use `git add -p` (patch mode) to review and stage hunks one at a time |
| 4 | Trust `git status` alone (staged + unstaged are mixed and hard to disambiguate by sight) | **Right before every `git commit`, run `git diff --cached --name-only` to dump the full staged list** → match 1:1 against intent → commit only if all match |
| 5 | Ignore the possibility that something (user or tool) staged files in a prior turn | Read every line of `git diff --cached --name-only` and verify each was staged by an `add` you explicitly issued this session. Any out-of-scope entry → `git restore --staged <file>` before commit |

The one exception: a new project's very first import commit, or a user-requested "stage everything" instruction.

## Sensitive-directory commit gate (HARD STOP)

**Files under `rules/`, `agents/`, `docs/` (or any user-marked sensitive directory) commit ONLY when the user explicitly named them in an `add` instruction in this session.** A prior-turn modified-but-unstaged state must not be carried along by a different commit.

| # | Don't | Do |
|---|-------|-----|
| 1 | Out-of-scope modified files are staged; commit them anyway | Before commit, run `git diff --cached --name-only` → any out-of-scope staged entry → `git restore --staged <file>` or split into a separate commit |
| 2 | `rules/*.md` auto-committed without user instruction | Edits to `rules/` require **both** an explicit user `add` instruction **and** an explicit commit-message instruction. Do not let them ride along on another commit |
| 3 | `agents/*.md`, `docs/` auto-committed | Same rule — only on explicit user instruction |
| 4 | "I'll notice if the intended file isn't in the commit, then fix it" thinking | **Pre-commit visual check of the full staged list is the only first-line defense.** Post-commit correction requires `git reset` / `git rebase` |
| 5 | A plan's "Files to modify" table lists a sensitive-dir file (`rules/`, `.claude/rules/`), so batch-`git add` it as "intended" | **Plan membership does not waive the gate.** Sensitive-dir files in a plan batch still require the explicit user `add` instruction — and an untracked sensitive file being newly tracked (create-mode) is the highest-risk case: check its language and audience (workspace-local Korean rules never belong in a PUBLIC repo commit) |

### Self-check (every time before `git commit`)

1. Run `git diff --cached --name-only` and dump the output
2. Match each line 1:1 against your intent (your own `git add` history this session)
3. Any line not matching intent → halt commit → `git restore --staged <file>` → re-verify
4. Any line under `rules/`, `agents/`, `docs/` → confirm the user explicitly instructed adding that file in this session

## Procedure (every commit)

1. `git status` to enumerate dirty state (staged + unstaged + untracked)
2. Explicit `git add <paths>` for each intended file (no `.` / `-A`)
3. `git diff --cached --name-only` to dump the full staged list
4. Visual 1:1 match: every dumped line must trace to an `add` you ran this session
5. Out-of-scope entry? → `git restore --staged <file>` → return to step 3
6. Sensitive-directory entry? → verify the user explicitly named it → otherwise restore-stage
7. `git commit` only when steps 4-6 pass cleanly

## Failure pattern

See the user-local `~/.claude/skills/cleanup/data/failed-attempts.md` HOT entry "staged files leaked into a different commit" (this file is external to the repo — not checked into version control). The standard scenario: the assistant runs `git add <intended-file>`, but a prior-turn modification is already staged, and the commit ends up with the wrong fileset. The pre-commit `git diff --cached --name-only` dump catches this every time.

## Related topics

- `interactive-amend` — when the wrong fileset is already committed and needs amend recovery
- `soft-reset-amend` — when multiple wrong commits need a soft-reset re-stage cycle
- `security-scan` — pre-commit secret scan for PUBLIC repos (runs AFTER staging-discipline gate passes)
- `message-discipline` — commit-message conventions once the staged set is verified

---

## Branch state check before starting a new commit (HARD STOP)

**Before committing a new change (or presenting commit options via AskUserQuestion), always check whether the current branch has uncommitted changes from other tasks.** If other-task changes are mixed on a shared branch (main/master/develop), the commit may conflict with the other task's intent, or the push may cause conflict/rollback. When detected, **split into a worktree or create a new branch first**.

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Right after Edit, present commit-method AskUserQuestion (PR branch / push to master / hold) immediately | **Before** presenting commit options, run `git status` — if other-task changes are detected, include a worktree-split option |
| 2 | Current branch is main/master/develop yet ignore unstaged/staged other changes and run `git add <new-file>` | Use `git status` to check other changes → if they belong to another task, `/git-repo` worktree-split → commit inside the new worktree |
| 3 | Assume "only my staged changes matter, other changes are unrelated" | The same push may carry other unpushed commits, and working-directory changes from another task may unintentionally affect the next task |
| 4 | Omit "worktree split" from the AskUserQuestion commit options list | If the branch is main/master/develop and ≥1 change exists, the "worktree split" option is mandatory in the list |
| 5 | Push the new commit while leaving the other task's unstaged changes in place | Check the other task's intent (report to user) → split via worktree or as a separate task |
| 6 | **Place "create new worktree" as option #1 / Recommended in the worktree-split option list** (when reusable candidates exist) | **If 1+ inactive worktree candidates exist, place "rename and reuse" as option #1 / Recommended**. New creation goes to option #2 or lower. See `/git-repo` "Recommended placement rule" table |

### Self-check (every time before presenting commit options)

1. `git -C <repo> status --short` to list changed files
2. `git -C <repo> branch --show-current` to identify current branch
3. Current branch is main/master/develop AND changes ≥ 2 (mine + other) → **worktree split is mandatory**
4. Only my single change AND branch is PR/feature → commit directly is OK
5. If there are unpushed commits, check `git log @{u}..HEAD --oneline` — if they include another task's commits, plan a separate push strategy

### Worktree-split decision tree

```text
git status (change list)
  ├─ Only my single change, branch = PR/feature → commit directly
  ├─ Mine + other-task, branch = main/master/develop → /git-repo worktree split mandatory
  ├─ Only mine, branch = main/master/develop → present both "create PR branch" and "split into worktree + create PR branch"
  └─ Another task in progress on a PR branch → leave it alone. Return to main and create a new worktree
```

### Failure case

See `~/.claude/skills/cleanup/data/failed-attempts.md` HOT entry for "worktree split option missing in commit-method ask" (Makefile environment targets case, AskUserQuestion presented commit options without a worktree-split option and without pre-commit `git status` check).

---

## Full-range squash-candidate scan (HARD STOP — triggered by any squash finding)

**The moment a squash candidate is found anywhere in the unpushed history, that finding is a signal to scan the ENTIRE unpushed range for the same pattern — not just the range the user happened to mention.** A user pointing at one specific commit range (by hash or description) defines the *minimum* scope, never the *maximum*. Stopping analysis at the user-named range misses adjacent streaks of the identical pattern.

### Procedure

1. Once ANY squashable streak is identified (2+ consecutive commits touching the same single file, or an equivalent repetition pattern), run a full-range scan before reporting or proposing anything:
   ```bash
   git log --name-only --oneline @{u}..HEAD   # or origin/<branch>..HEAD if no upstream is set
   ```
2. Group the output by file: for each file, list the commits that touch only that file in a contiguous run.
3. Report **every** contiguous single-file streak found (not just the one the user named) as a squash candidate — even ones the user never mentioned.
4. Only after the full-range scan is complete does an AskUserQuestion / squash-plan proposal count as ready.

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | User names a specific commit-hash range → analyze only that range and stop | Treat the named range as a *trigger*, not a *boundary* — scan the full unpushed range for the same pattern |
| 2 | Verify a claimed squash candidate with `git log --name-only <user-named-range>` only | Also run `git log --name-only @{u}..HEAD` (whole range) grouped by file, independent of what the user named |
| 3 | Present a squash plan for one range while other identical streaks sit elsewhere in the same unpushed history | Enumerate all streaks in the same response — the user decides which to include, not the assistant by omission |
| 4 | Treat "the user will tell me if there's more" as sufficient | The assistant's job is to surface the full picture; a partial squash plan the user must supplement by re-asking is the exact failure this rule prevents |

### Self-check (before presenting any squash plan)

1. Did I run `git log --name-only @{u}..HEAD` (or the equivalent full-unpushed-range command) — not just the range the user named?
2. Does the output show more than one contiguous single-file streak?
3. If yes, does my report/plan include ALL of them, not just the one initially pointed at?

See `~/.claude/skills/cleanup/data/failed-attempts.md` "squash-scan-scope-narrowed-to-user-mention" for case history.

---

## Shared hardlinked-checkout HEAD-diff sanity check (HARD STOP — concurrent-session drift)

**Before staging/committing a file that lives in a checkout shared across concurrent sessions (e.g. a hardlinked skills repo checkout under `~/.agents`), run `git diff HEAD --stat -- <file>` against HEAD and inspect the actual diff hunks (`git diff HEAD -- <file>`), not just the reported insertion/deletion counts.** A concurrent session's commit can advance HEAD past this session's Read-time baseline — the on-disk file may already carry someone else's change by the time this session stages it, and a plain `git add` bundles that unrelated change into the commit silently. Without an explicit `HEAD` ref, `git diff` compares the working tree to the **index**, not HEAD — if the index already carries staged content, the check under-reports or shows 0. Insertion/deletion counts alone are also insufficient: two unrelated edits can produce identical `--stat` totals, so a concurrent overwrite with the same line-delta can silently pass a count-only check.

### Procedure

1. Right before `git add <file>` (not right after Edit — right before staging), run `git diff HEAD --stat -- <file>` comparing the working tree to HEAD.
2. Inspect `git diff HEAD -- <file>` and verify that every hunk belongs to this session's edit — use the `--stat` totals only as a preliminary signal, not the acceptance criterion.
3. Every hunk matches the intended edit → proceed to stage.
4. Any hunk is unfamiliar or doesn't match the intended edit (extra hunks, unfamiliar lines, sections not touched this session) → **halt, do not stage**, even if the `--stat` totals look right. A concurrent session's commit already landed on this file.
5. Re-`Read` the file for its current on-disk state, reconcile the intended change against it (re-apply the edit on top of the new baseline if it still applies cleanly), then re-check `git diff HEAD -- <file>` before staging again.

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Stage a shared-checkout file immediately after Edit without a fresh `git diff HEAD --stat -- <file>` check | Run `git diff HEAD --stat -- <file>` right before `git add`, not right after Edit — HEAD can move in between |
| 2 | Assume the Read-time content is still current because no tool reported a conflict | Hardlinked/shared checkouts have no built-in conflict signal — the sanity check is the only defense |
| 3 | Treat matching insertion/deletion totals as proof the diff contains only this session's edit | Two different edits can have identical `--stat` totals — inspect `git diff HEAD -- <file>` hunks and reconcile before staging, don't rationalize a size match away |
| 4 | Limit this check to skill files specifically | Applies to any shared-checkout path where concurrent sessions commit independently (skills, rules, shared docs under a hardlinked repo) |

### Self-check (every time, right before `git add` on a shared-checkout file)

1. `git diff HEAD -- <file>` — does every hunk belong to this session's own edit? (`--stat` totals are a preliminary signal only, not the acceptance criterion)
2. Any unfamiliar hunk → halt, re-Read, reconcile, re-check before retrying `git add`
3. Only stage once every hunk matches this session's edit exactly

See `~/.claude/skills/cleanup/data/failed-attempts.md` "concurrent-session-overwrites-hardlinked-shared-config" for case history (related failure mode: a prior Edit lost, not just an unrelated edit bundled into a commit).
