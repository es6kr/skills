# Capability Matrix

Before invoking an operation, the pipeline queries the driver's capability flags. If a
capability is absent on the resolved forge, the pipeline follows a **degrade path**
(emulation or skip) instead of failing. This keeps the pipeline forge-portable without
lowest-common-denominator behavior.

## Flags

| Capability | GitHub | GitLab | Gitea | Degrade path when unsupported |
|-----------|--------|--------|-------|-------------------------------|
| `pr_pr_dependency` (PR↔PR native link) | ✗ (body cross-link) | ✓ (MR native) | ✗ | Body cross-link text (the existing GitHub approach) |
| `sub_issue` (parent–child native) | ✓ GraphQL `addSubIssue` | partial (Epics / premium, not 1:1) | ✗ | Task-list emulation (`- [ ] #N` under the parent body) |
| `issue_dependency` (blocks) | ✓ GraphQL `addBlockedBy` | ✓ REST `type=blocks` | ✓ (different shape) | Body "depends on: #N" text when none |
| `visibility_domain` | 2 values (bool) | 3 values | 2 values (bool) | Map 3→2 (`internal` → PRIVATE) |
| `reviewer_copilot` | ✓ | ✗ | ✗ | GitHub-only branch skipped |
| `reviewer_coderabbit` | ✓ | ✓ (parameterized by author login) | conditional | Parameterize the author login to stay portable |

## Hardest surface: GitHub-only GraphQL

The research grounding flagged the **hardest portability surface as the GitHub-only GraphQL
operations** — native sub-issues and Copilot review. These surface as capability flags set
`false` on non-GitHub forges, so the pipeline takes the emulation path (task-list sub-issues,
skipped Copilot reviewer) and degrades gracefully rather than erroring.

## Query-before-operate contract

1. The pipeline asks the driver for the flag relevant to the operation it is about to run.
2. `true` → call the native driver method.
3. `false` → follow the degrade path in the table above.

This means a capability flag is not just documentation — it is a runtime branch. A driver
that reports `pr_pr_dependency = false` (GitHub) causes the dependency step to write a body
cross-link instead of a native link, preserving the existing GitHub behavior with no
special-casing in the pipeline itself.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Hardcode a native call (e.g., native sub-issue) assuming every forge supports it | Query `sub_issue` first; on `false` emit the task-list emulation |
| 2 | Treat GitLab `internal` visibility as a third public tier | Map `internal` → PRIVATE so PUBLIC sanitize gates do not fire on an internal repo |
| 3 | Skip an operation entirely because one forge lacks it | Prefer the emulation degrade path; skip only when no emulation exists (e.g., Copilot reviewer) |
| 4 | Assume a bot reviewer (CodeRabbit) works identically across forges | Parameterize the author login; some forges need it explicit to stay portable |
