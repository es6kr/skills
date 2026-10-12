# Delivery Topic (`delivery.md`)

## 1. Unit Task Post-Execution & Commit Tidy (HARD STOP)

Upon verifying green implementation:
1. **Mandatory `commit-tidy` Invocation**: Group modifications into logical modification units. Stage and commit atomically using Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`).
2. **Feature-Range Acceptance**: For created/relocated feature branches, run
   the common [feature-base gate](../git-repo/feature-base.md) in `deliver` mode
   with the task's pinned base SHA, approved final commit count and explicit
   allowed paths. Require exit zero and retain the JSON receipt before marking
   the task locally complete. Clean state alone or merge-base equality is not
   enough. Runtime adapter activation, if in scope, requires separate native
   allow/block receipts; source/tests do not establish it.
3. **Backlog Status Update**: Mark task as completed (`[x]` in `task.md` or `Done` in Plane).
4. **Walkthrough / Knowledge Persistence**: Record key findings in `.agents/docs/generated/walkthrough-*.md` and index into RAG memory.

---

## 2. Pull Request Delivery

1. **Pre-Push Validation**: Confirm all local pre-push checks (`bats tests/`, `pytest tests/`, `lint-frontmatter.sh`) pass.
2. **Authorization and Fresh Acceptance**: Re-run the same `deliver` gate
   immediately before publication. Push/PR/merge require their own existing
   task authority; local completion alone never grants it.
3. **Push Ref**: Push the feature branch to `origin`.
4. **Create Pull Request**: Open a draft PR per Draft-to-PR gate with structured summary, test plan, and clear context (or use `github-flow/pr`):
   ```bash
   gh pr create --draft --title "feat(<scope>): <description>" --body "..."
   ```
