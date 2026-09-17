# Delivery Topic (`delivery.md`)

## 1. Unit Task Post-Execution & Commit Tidy (HARD STOP)

Upon verifying green implementation:
1. **Mandatory `commit-tidy` Invocation**: Group modifications into logical modification units. Stage and commit atomically using Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`).
2. **Backlog Status Update**: Mark task as completed (`[x]` in `task.md` or `Done` in Plane).
3. **Walkthrough / Knowledge Persistence**: Record key findings in `.agents/docs/generated/walkthrough-*.md` and index into RAG memory.

---

## 2. Pull Request Delivery

1. **Pre-Push Validation**: Confirm all local pre-push checks (`bats tests/`, `pytest tests/`, `lint-frontmatter.sh`) pass.
2. **Push Ref**: Push the feature branch to `origin`.
3. **Create Pull Request**: Open a PR with structured summary, test plan, and clear context:
   ```bash
   gh pr create --title "feat(<scope>): <description>" --body "..."
   ```
