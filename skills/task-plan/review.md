# Review Topic (`review.md`)

## 1. User Review Gate (HARD STOP)

The User Review Gate is the mandatory boundary between Stage 1 (Planning & Research) and Stage 2 (Execution & Implementation).

An agent MUST NOT start writing production source code, mutating infrastructure, or advancing implementation without explicit user approval of the plan.

---

## 2. Review Protocol & Checkpoints

1. **Present Plan Summary**: Provide an executive summary of changes, affected files, and key trade-offs in visible response text.
2. **Interactive Selection**: Only for initial approval or a missing changed-scope decision, invoke the active harness's native question capability presenting explicit options:
   - Option 1: Proceed to implementation (Recommended)
   - Option 2: Revise design or trade-offs
3. **Wait for First or Changed-Scope Approval**: Do not call implementation tools until approval for that scope is received. Check existing attributable approval before presenting another selection.

---

## 3. Worktree Isolation Setup

Upon receiving approval to execute:
- Check if an isolated worktree is required (`using-git-worktrees` skill).
- Avoid working directly on dirty base branches (`main`, `develop`, `local/ghq`).
- Create an isolated worktree:
  ```bash
  git worktree add -b <type>/<task-name> .worktrees/<task-name> <verified-live-base-sha>
  ```

## Continuing Authorization After a Detour

Recover the accepted plan reference/revision, original goal, authorized actions,
resource/owner scope, and unfinished action from the existing decision receipt.
Approval remains applicable to that accepted scope after correction or recovery;
passing the detour does not expire it. Do not ask a generic proceed question after
recovery. Resume the approved action after required correction checks pass.

Planning-only authorization does not authorize implementation. A new action,
resource, or scope outside the accepted decision must return to review. Ask only
for the missing decision and keep the dependent action pending; continue other
independent actions already authorized. Do not turn design answers, failed
questions, or a recovery record into implementation permission. Respect explicit
record-only or cancellation limits from the user.
