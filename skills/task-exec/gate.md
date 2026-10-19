# Gate Topic (`gate.md`)

## 1. Plan Acceptance Prerequisite Gate (HARD STOP)

Execution must never start without an accepted plan:

1. **Verify Plan Exists & Is Decided**: Confirm that an architecture plan (`plan-*.md` or `implementation_plan.md`) was produced in Stage 1 and accepted by the user.
2. **Worktree Readiness**: Ensure the working directory is an isolated feature worktree or dedicated branch, not a dirty base branch (`main`, `develop`, `local/ghq`).
3. **Backlog Claiming**: Use the existing owner helper to claim the target task only when that tracker mutation is authorized; otherwise retain local in-progress evidence without claiming a canonical tracker change.

---

## 2. Blocking Mutating Actions Without Plan Approval

Executing state-mutating actions (e.g. `kubectl apply`, `terraform apply`, `docker rm`, `git push`, browser clicks) on tracker items without an approved plan and workflow-skill gate will trigger automated hook blocks (`block-live-action-without-workflow-skill.sh`).

## Resumed Task Admission

Recover the existing accepted scope identity: original goal, approved plan
reference/revision, owner/resource scope and authorized actions. Recovery is not
expiration of approval. Do not require a duplicate approval for an unchanged
accepted action; changed scope or missing authority returns to
[review](../task-plan/review.md).

Recheck current isolated-worktree readiness and admission/source freshness before
writing: actual checkout, clean index, live intended base pinned by SHA, and the
allowed path/commit range. Do not use an unverified local branch as the feature
base or treat an old readiness receipt as current. Preserve unrelated dirty
owner work and existing delivery guards. A missing prerequisite blocks dependent
work only; no recovery checkpoint authorizes push, merge, install, configuration,
live adapter calls, or duplicate dispatch outside the original decision.
