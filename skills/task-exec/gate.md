# Gate Topic (`gate.md`)

## 1. Plan Acceptance Prerequisite Gate (HARD STOP)

Execution must never start without an accepted plan:

1. **Verify Plan Exists & Is Decided**: Confirm that an architecture plan (`plan-*.md` or `implementation_plan.md`) was produced in Stage 1 and accepted by the user.
2. **Worktree Readiness**: Ensure the working directory is an isolated feature worktree or dedicated branch, not a dirty base branch (`main`, `develop`, `local/ghq`).
3. **Backlog Claiming**: Mark the target task as in-progress (`- [ ] 🔄 <task_name>` in `task.md` or `In Progress` in Plane backlog SSOT).

---

## 2. Blocking Mutating Actions Without Plan Approval

Executing state-mutating actions (e.g. `kubectl apply`, `terraform apply`, `docker rm`, `git push`, browser clicks) on tracker items without an approved plan and workflow-skill gate will trigger automated hook blocks (`block-live-action-without-workflow-skill.sh`).
