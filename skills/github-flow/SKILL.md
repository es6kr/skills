---
name: github-flow
metadata:
  author: es6kr
  version: "0.1.0"
depends-on: [code-workflow, web-ui-test]
description: |
  GitHub issue and PR workflow automation. plan-to-issue - convert plan/research MD to GitHub issue body/comments [plan-to-issue.md], pr - create PR with structured body and test plan [pr.md], review - review PR code and post structured comments [review.md].
  Converts session findings and plan files into GitHub issues with proper body/comment separation.
  Rules: verification plan required, .ralph/docs/ paths must not appear in issue/PR body.
  Use when: "plan to issue", "issue register", "issue comment", "create PR", "PR body", "code review".
---

# GitHub Flow

Convert plans, research, and implementation results into GitHub issues and PRs.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| plan-to-issue | Convert plan/research MD to GitHub issue body or comments | [plan-to-issue.md](./plan-to-issue.md) |
| pr | Create PR with structured body, test plan, and optional visual attachments | [pr.md](./pr.md) |
| review | Review PR code and post structured review comments | [review.md](./review.md) |

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
