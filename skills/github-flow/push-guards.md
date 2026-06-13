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

## Failure pattern

See failed-attempts.md HOT entry "force-push CI in-progress run cancelled" — during commit-tidy "phase-by-phase squash" option, force-push fired before the CI watch result returned. Force-push cancelled the still-running CI run + the broken squash landed in origin's permanent history.

## Related topics

- `merge` — merge condition gates (CI / AI Review Summary / Test Plan / Formal Review). Force-push CI check pairs with merge-condition CI check
- `identity-auth` — gh auth scope refresh for `gh run list` to work on org repos
