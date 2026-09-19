# Review Topic (`review.md`)

## 1. User Review Gate (HARD STOP)

The User Review Gate is the mandatory boundary between Stage 1 (Planning & Research) and Stage 2 (Execution & Implementation).

An agent MUST NOT start writing production source code, mutating infrastructure, or advancing implementation without explicit user approval of the plan.

---

## 2. Review Protocol & Checkpoints

1. **Present Plan Summary**: Provide an executive summary of changes, affected files, and key trade-offs in visible response text.
2. **Interactive Selection**: Invoke `AskUserQuestion` / `ask_question` presenting explicit options:
   - Option 1: Proceed to implementation (Recommended)
   - Option 2: Revise design or trade-offs
3. **Wait for Approval**: Do not call implementation tools until user approval is received.

---

## 3. Worktree Isolation Setup

Upon receiving approval to execute:
- Check if an isolated worktree is required (`using-git-worktrees` skill).
- Avoid working directly on dirty base branches (`main`, `develop`, `local/ghq`).
- Create an isolated worktree:
  ```bash
  git worktree add -b feat/<task-name> .worktrees/<task-name> <base-branch>
  ```
