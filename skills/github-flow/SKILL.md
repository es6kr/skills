---
name: github-flow
metadata:
  author: es6kr
  version: "0.1.0"
depends-on: [code-workflow, web-ui-test]
description: |
  GitHub issue and PR workflow automation. Topics — dependencies (blocked-by/sub-issues via GraphQL), expand (expand-vs-split mid-work), merge (CI+review check before merge), plan-to-issue (MD to issue body), pr (PR with test plan), register (duplicate check + strategy), review (post structured comments), sanitize (HARD STOP personal data scan for PUBLIC repos). Converts session findings + plan files into issues with proper body/comment separation. Use when: "plan to issue", "issue register", "issue comment", "create PR", "PR body", "code review", "merge PR", "PR squash", "sanitize", "personal data", "PII", "redact", "expand PR", "expand issue", "blocked by", "blocking", "issue dependencies", "addBlockedBy", "upstream issue", "feature request", "bug report", "review apply", "deferred", "duplicate check", "sub-issue", "addSubIssue", "register issue", "post-fix issue".
---

# GitHub Flow

Convert plans, research, and implementation results into GitHub issues and PRs.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| dependencies | Manage native Issue Relationships (blocked-by/blocking) via addBlockedBy/removeBlockedBy GraphQL mutations | [dependencies.md](./dependencies.md) |
| expand | Decide expand-vs-split when new findings emerge mid-work and update title/body | [expand.md](./expand.md) |
| merge | CI success and AI review check then merge with commit cleanup, including pre-merge blockedBy verification | [merge.md](./merge.md) |
| plan-to-issue | Convert plan/research MD to GitHub issue body or comments | [plan-to-issue.md](./plan-to-issue.md) |
| pr | Create PR with structured body, test plan, and optional visual attachments | [pr.md](./pr.md) |
| register | Evaluate duplicates and decide registration strategy (new issue vs comment vs sub-issue) | [register.md](./register.md) |
| review | Review PR code and post structured review comments | [review.md](./review.md) |
| review-apply | Apply deferred [REVIEW_FEEDBACK] items from fix_plan to code, update PR Summary | [review-apply.md](./review-apply.md) |
| sanitize | HARD STOP scan for personal data before posting to PUBLIC repos | [sanitize.md](./sanitize.md) |
| upstream-issue | Register feature requests/bug reports on external open-source repos with duplicate check + draft + sanitize | [upstream-issue.md](./upstream-issue.md) |

## Topic Dependencies

```text
github-flow (issue/PR workflow)
  ├─→ plan-to-issue (issue body content)
  ├─→ register (evaluate duplicates and decide strategy)
  ├─→ pr (PR body content + visual attachments)
  ├─→ review (post structured review comments)
  ├─→ expand (mid-work scope expansion)
  ├─→ dependencies (Issue Relationships: blocked-by/blocking)
  │     └─→ used by merge step 5 (pre-merge blockedBy check)
  ├─→ merge (CI/Review/Test Plan/blockedBy verification → squash+merge)
  ├─→ review-apply (deferred [REVIEW_FEEDBACK] → code fix → Summary update)
  │     └─→ receives from: consolidate Step 7 (deferred registration)
  ├─→ sanitize (HARD STOP scan before posting to PUBLIC repos)
  └─→ upstream-issue (external repo feature request/bug report with duplicate check + draft + sanitize)
```

- **dependencies → merge**: dependencies adds blockedBy relationships. merge.md step 5 queries the same field to gate merge until predecessors are CLOSED
- **plan-to-issue → dependencies**: when a plan has frontmatter `chain:` declaring a sequential issue order, dependencies applies it to GitHub
- All topics → sanitize: any text published to PUBLIC repos (issue body, PR body, comments, review text) must pass sanitize HARD STOP first

## Applicability

This skill applies automatically when `git remote get-url origin` contains `github.com`. For non-GitHub remotes (GitLab, Bitbucket, etc.), this skill does not apply.

## Core Rules

### 1. Verification Plan Required

Every issue body and PR body must include a verification/test plan section. This is shared with code-workflow's plan step.

### 2. No Internal Paths in Issues/PRs

`.ralph/docs/`, `.ralph/fix_plan.md`, `.omc/` and other internal working paths must **never** appear in GitHub issue body, comments, or PR body. These are local-only artifacts.

**Instead of**: "See `.ralph/docs/generated/plan-180.md`"
**Write**: The actual content inline, or "See the implementation plan comment below"

### 3. Body vs Comment Selection

| Content Type | Target | Reason |
|-------------|--------|--------|
| Implementation plan (confirmed) | Issue body update | Stable reference for the issue |
| Checklist (impl/verify) | Issue body update | Trackable via GitHub checkbox |
| Discussion items / open questions | Issue comment | Threaded, time-stamped, doesn't clutter body |
| Progress updates | Issue comment | Chronological record |
| Review feedback summary | Issue comment | Preserves review history |
