# Backward Compatibility Topic (`compat-codeworkflow.md`)

## 1. Overview & Compatibility Contract

To ensure that existing workspace rules, IDE hooks, and automated scripts continue working without disruption, `/code-workflow` is transparently mapped to `/task-flow`:

- **`/code-workflow`** ➔ Routes to `/task-flow` (Universal Task Lifecycle Engine).
- **`/code-workflow steps`** ➔ Maps to `/task-plan` (Pre-search, Research, and Plan authoring).
- **`/code-workflow implement`** ➔ Maps to `/task-exec` (TDD Red-Green-Refactor implementation).
- **`/code-workflow pr`** ➔ Maps to `/task-exec delivery` (Finishing branch and PR publication).

---

## 2. Invariants & Safety
- All review checkpoints, worktree isolation gates, and TDD discipline rules from `code-workflow` are fully enforced within `task-flow`.
- Hook definitions targeting `code-workflow` will continue to function.
