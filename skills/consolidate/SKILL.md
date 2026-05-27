---
name: consolidate
depends-on: [superpowers, git-repo]
metadata:
  author: es6kr
  version: "0.1.1" # x-release-please-version
description: >-
  Consolidate and respond to external feedback on PRs/issues. Topics —
  pr (workflow entrypoint + skip conditions),
  collect (gather AI reviews + superpowers load),
  internal (Internal Code Review fallback + UI capture),
  classify (dual-label Type|Severity + diff scope check),
  decide (user decision: findings + Formal Review),
  post (Summary + Formal Review + status + deferred),
  next (post-summary next-action ask).
  Use when: "review consolidate", "PR review", "AI review", "CodeRabbit review", "Copilot review",
  "review check", "review summary", "merge ready", "internal review", "code-reviewer",
  "inline review", "line-level comment", "PR line review".
allowed-tools: [Agent, AskUserQuestion, Bash, Edit, Glob, Grep, Read, Write]
---

# Consolidate

Consolidate and respond to external feedback on PRs and issues.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| classify | Step 4 Analyze and Classify (dual-label Type \| Severity, PR scope cross-check) | [classify.md](./classify.md) |
| collect | Step 3 Collect AI Reviews + Step 3.6 superpowers framework load | [collect.md](./collect.md) |
| decide | Step 5 User Decision (Axis A/B) + Step 6 Fix or Reject | [decide.md](./decide.md) |
| internal | Step 3.5 Internal Code Review Fallback + Step 4.5 UI capture verification | [internal.md](./internal.md) |
| next | Step 8 Post-Summary Next-Action Ask | [next.md](./next.md) |
| post | Step 7 Post Summary + Formal Review (unified vs separate) + Step 7.5 Status + Step 7.6 Deferred registration | [post.md](./post.md) |
| pr | Workflow entrypoint — PR identify, skip conditions, Copilot sequential, worktree checkout, Rules | [pr.md](./pr.md) |

## Topic Dependencies

```
pr (entry: identify → skip → worktree checkout)
  └─→ git-repo/worktree (Step 2.7: check out PR branch into a worktree — all review runs against real files)
collect → internal (code-reviewer dispatch operates in the Step 2.7 worktree)
```

- Step 2.7 worktree checkout runs on every review (after skip conditions) so the code-reviewer reads real files, CONFLICTING is detected locally, and inline line numbers match HEAD.

## Quick Reference

### PR Review Workflow

Review CodeRabbit/Copilot feedback on a PR, decide what to act on, and post an AI Review Summary comment.

Entry: [`pr.md`](./pr.md) (Workflow index + Step 1, 2, 2.5, 2.6, 2.7 + Rules)

Step execution order:
1. **`pr.md`** Step 1 (Identify PR) + Step 2 (Skip Conditions) + Step 2.5 (Copilot sequential, multi-PR only) + Step 2.6 (re-review trigger policy — first vs re-review) + Step 2.7 (checkout PR branch into a worktree — MANDATORY, all reviews)
2. **`collect.md`** Step 3 (Collect AI Reviews) + Step 3.6 (superpowers framework)
3. **`internal.md`** Step 3.5 (Internal Review Fallback, walkthrough only / on failure) + Step 4.5 (UI capture verification)
4. **`classify.md`** Step 4 (Analyze and Classify)
5. **`decide.md`** Step 5 (Formal Review Decision — Axis B only) + Step 6 (Fix or Reject — only on explicit user instruction)
6. **`post.md`** Step 7 (Post Summary + Formal Review) + Step 7.5 (Status line) + Step 7.6 (Deferred registration)
7. **`next.md`** Step 8 (Post-Summary Next-Action Ask)
