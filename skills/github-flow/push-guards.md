# Push Guards

Pre-push safety gates: branch-change ask, push-rejection ask, hook-failure handling, main/master push restriction, force-push CI status check, shared-branch direct-push restriction.

## When to use

- Before every `git push` invocation
- After receiving a "push rejected" or "non-fast-forward" error
- Before `git checkout` / `git switch` to a different branch
- Before `--force` / `--force-with-lease` push
- When the pre-commit hook or pre-push hook fails

## Branch change requires user instruction (AskUserQuestion required)

**Forbid `git checkout` / `git switch` invocations that the user did not explicitly instruct.** The principle is to complete work on the current branch.

### Syncthing-aware working-directory drift

In a Syncthing-synced repo, HEAD and the working directory can diverge. When `git status` shows unexpected changes, report to the user via AskUserQuestion before resolving.

## Pre-commit / pre-push confirmation (AskUserQuestion required)

User confirmation is required before:
- `git push`

**Commit-location (branch) verification**: if the user specified a worktree / branch, commit only at that location. Even if the changes live on master, move to the user-specified location first.

| # | Don't | Do |
|---|-------|-----|
| 1 | "Changes are on master, so commit on master" — autonomous decision | Per user's instruction, acquire the worktree → commit in the worktree |
| 2 | User requested a worktree, but you decide "worktree unnecessary" | The user's instruction is final. If you think it's unnecessary, AskUserQuestion |

**Absolutely forbidden**: autonomous creation of an empty commit (`git commit --allow-empty`) intended to trigger a workflow / deployment.

## When a user-specified command fails — pick the alternative via AskUserQuestion

**When a Git command the user explicitly named fails, stop and AskUserQuestion.** Forbid autonomous selection of "a different command that produces the same effect", especially escalation to a forbidden command like `git reset --hard`.

| # | Don't | Do |
|---|-------|-----|
| 1 | `git branch -f` failed → substitute with `git reset --hard` | Report the failure reason + AskUserQuestion for an alternative |
| 2 | Justify a forbidden command as "needed to fulfill the user's intent" | Forbidden commands run ONLY when the user **directly** names them |

## Push rejection handling (AskUserQuestion required)

**When `git push` is rejected, stop and AskUserQuestion.** Forbid autonomous `git pull`, `git rebase`, `git merge`. Show the remote's additional commits and let the user decide.

## Hook failure handling (--no-verify is forbidden)

**`--no-verify` is allowed ONLY when the user explicitly instructs it.** Do not bypass it even under environmental constraints. On failure, analyze the root cause → fix, OR report via AskUserQuestion.

## main/master push restriction (AskUserQuestion required)

**Before pushing to main/master, AskUserQuestion is required.** `--force` / `--force-with-lease` are absolutely forbidden against main/master.

## Force-push CI status check (HARD STOP)

**Before `git push --force` / `--force-with-lease`, check the current branch's in-progress / latest CI status.** Force-push cancels any in-progress run on the GitHub side and overwrites origin with the failed change.

### Procedure

1. **Query the current branch's latest run state**: `gh run list --branch $(git branch --show-current) --limit 5 --json status,conclusion,name`
2. **Process by state**:
   - `in_progress` / `queued` present → **force-push forbidden**. Wait for completion via watch, verify result
   - All `completed` + `conclusion=success` → force-push allowed
   - `conclusion=failure` present → force-push forbidden. Investigate the failure → fix → after passing → force-push
3. **Local squash / rebase + force-push flow**:
   - Squash complete (local) → check CI status → wait if in_progress, push if success, fix if failure
   - Even with prior user approval (e.g., "option B squash chosen"), **force-push itself happens only after CI result verification**

### Scope of application

- Feature-branch force-push: same rule applies (main/master force-push is forbidden outright by the higher rule)
- The user's explicit "force-push now" allows skipping the CI check — but the in-progress-run-cancellation risk must be reported

## Shared-branch (develop, etc.) direct-push restriction

**Direct push to shared branches like develop, master, main is forbidden.** Push must go through a feature branch + PR.

- **Direct-push allowed conditions**: user explicitly names the branch / deployment pipeline instruction / urgent hotfix
- **"Just push" instruction + current branch = develop**: AskUserQuestion → "direct push vs PR"

## Pre-push hook registration verification (HARD STOP)

When a repo ships a versioned hooks directory (`.githooks/`, usually wired via `make install-hooks` → `git config core.hooksPath .githooks`), the pre-push hook fires **only if `core.hooksPath` actually resolves to it**. A repo can carry `.githooks/pre-push` while `core.hooksPath` still points at the default `.git/hooks` (which is empty) — so **no local gate runs and bad content reaches CI uncaught** (e.g., untranslated Korean in an English skill caught only by the CI Korean-text job). File presence is not registration. Verify registration before the first push.

### Procedure (before the first push to a repo with a tracked hooks dir)

1. Detect a tracked hooks dir: `test -d .githooks && echo present`
2. Resolve the active hooks path: `git config --get core.hooksPath` (empty output = default `.git/hooks`)
3. If `.githooks/` is present but `core.hooksPath` is unset or not `.githooks` → the hook is **not registered**. Register it: `git config core.hooksPath .githooks` (or `make install-hooks` when the Makefile provides it)
4. Confirm the hook exists and is executable: `ls -l "$(git rev-parse --show-toplevel)/$(git config --get core.hooksPath)/pre-push"`
5. Only then push — the local gate now mirrors CI

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Assume the pre-push hook ran because `.githooks/pre-push` exists in the repo | Verify `core.hooksPath` resolves to the tracked hooks dir — file presence ≠ registration |
| 2 | Push, then discover CI caught what a local gate should have | Verify hook registration before pushing; register if missing |
| 3 | Treat a partial pre-push hook as sufficient | The pre-push hook must mirror the CI gates (lint / tests / language check). A hook that runs only a subset silently lets the unmirrored gate fail in CI alone |

## Pre-push bump-matrix self-check (HARD STOP — release-automation pipelines)

**When the target repo runs a commit-history-driven release automation (release-please, semantic-release, changesets, etc.), the PR's full commit-type distribution decides the release-please bump — not just the commit you are pushing this turn.** Adding a `fix` commit to a PR that already contains a `feat` commit still produces a `minor` bump on squash-merge, even though your incremental push was a patch-level change. Verify the bump matrix BEFORE pushing so the user is not surprised by `minor`/`major` on merge.

### Procedure (run before any push that lands on an open PR)

1. Detect the release-automation receiver in the target repo — `ls .github/workflows/ | grep -iE 'release-please|semantic-release|changesets'`. No match → bump-matrix check not applicable, skip
2. Identify the PR's commit type distribution from the merge base:
   ```bash
   MERGE_BASE=$(git merge-base origin/<base-branch> HEAD)
   git log "$MERGE_BASE..HEAD" --pretty=format:"%h %s"
   git log "$MERGE_BASE..HEAD" --pretty=format:"%s" | grep -oE '^[a-z]+' | sort | uniq -c
   ```
3. Predict the squash-merge bump from the highest-precedence type present:
   - `feat` → **minor**
   - `fix`, `perf`, `refactor`, `chore`, `docs`, `style`, `test`, `ci` → **patch** (some scope configs treat refactor/chore as no-release)
   - `feat!` or any commit body containing `BREAKING CHANGE:` → **major**
4. Compare the predicted bump against the user's intent (or the PR title's Conventional Commit type). On mismatch (e.g., PR title implies patch but the body contains a feat) → **AskUserQuestion required** before pushing. Options: (a) push as-is and accept the higher bump, (b) split the offending commit into a separate PR, (c) hold the push
5. Path-scoped release tooling (release-please monorepo, changesets): if a `feat(...)` commit touches multiple packages, predict the bump per package using `git log "$MERGE_BASE..HEAD" -- <path>` per package. Cross-cutting `feat(...)` that touches every package's path will minor-bump every package — report this matrix to the user before pushing

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Push the incremental commit and assume "my commit is `fix`, so the PR is patch" | The PR's bump = the highest-precedence type across **all** commits between merge-base and HEAD. Inspect the full distribution before pushing |
| 2 | Trust the PR title's Conventional Commit type as the bump source of truth | release-please reads the commit messages, not the PR title (unless the repo is configured to use the PR title for squash). Verify the actual squash strategy in `.github/workflows/release-*.yml` |
| 3 | Skip the bump-matrix check when the receiver is "obviously a release-please repo" | The check costs one `git log` + one `grep`. Run it every time — assumptions about the repo's release config drift |
| 4 | On a `feat`-in-`patch`-PR mismatch, push autonomously thinking "user can revert the bump after merge" | release-please publish artifacts (npm, marketplace, ClawHub) are immutable. Pre-push AskUserQuestion is the last enforceable gate. Post-merge there is no clean revert |
| 5 | Report only "your commit is `fix`" to the user and skip the distribution dump | Report the full type distribution `feat ×N, fix ×M, refactor ×K` so the user sees the cascade source, not just their incremental change |

### Self-check (before every push that lands on an open PR)

1. Does the repo run a release-please / semantic-release / changesets workflow? — if no, this check is not applicable
2. Did you run `git log <merge-base>..HEAD --pretty=format:"%s" | grep -oE '^[a-z]+' | sort | uniq -c`?
3. Does the predicted bump match the user's stated intent (or the PR title's Conventional Commit type)?
4. On mismatch → AskUserQuestion BEFORE `git push`. Do not push first and report after
5. For path-scoped release tooling (monorepo), did you verify which packages each `feat(...)` commit touches?

## Self-check (before every push)

1. Push target = main / master / develop?
   - **Yes** → AskUserQuestion for direction (PR vs direct push)
   - **No** → proceed to step 2
2. `--force` / `--force-with-lease`?
   - **Yes** → run the "Force-push CI status check" procedure above
   - **No** → proceed to step 3
3. Did `git push` get rejected?
   - **Yes** → AskUserQuestion (do NOT autonomously pull/rebase/merge)
   - **No** → push complete
4. Did the pre-push hook fail?
   - **Yes** → fix the root cause OR AskUserQuestion. `--no-verify` is forbidden
5. Does the repo ship a tracked hooks dir (`.githooks/`)?
   - **Yes** → confirm `core.hooksPath` resolves to it (register via `git config core.hooksPath .githooks` if not) before pushing — a present-but-unregistered hook means no local gate ran
6. Does the repo run release-please / semantic-release / changesets?
   - **Yes** → run the "Pre-push bump-matrix self-check" procedure above before pushing
   - **No** → bump-matrix check not applicable

## Failure pattern

See failed-attempts.md HOT entry "force-push CI in-progress run cancelled" — during commit-tidy "phase-by-phase squash" option, force-push fired before the CI watch result returned. Force-push cancelled the still-running CI run + the broken squash landed in origin's permanent history.

## Related topics

- `merge` — merge condition gates (CI / AI Review Summary / Test Plan / Formal Review). Force-push CI check pairs with merge-condition CI check
- `identity-auth` — gh auth scope refresh for `gh run list` to work on org repos
