---
name: consolidate
metadata:
  author: es6kr
  version: "0.1.1"
description: >-
  Consolidate and respond to external feedback on PRs/issues.
  pr - Workflow entrypoint (PR identify + skip conditions + Copilot sequential) [pr.md].
  collect - Step 3 collect AI reviews + superpowers framework load [collect.md].
  internal - Step 3.5 Internal Code Review fallback (CodeRabbit Free walkthrough only / Copilot failure) + Step 4.5 UI capture verification [internal.md].
  classify - Step 4 analyze/classify with dual-label (Type | Severity) + PR diff scope cross-check [classify.md].
  decide - Step 5 user decision (Axis A findings + Axis B Formal Review) + Step 6 fix or pushback [decide.md].
  post - Step 7 post Summary + Formal Review (Mergeable unified POST) + Step 7.5 in-chat status + Step 7.6 deferred registration [post.md].
  next - Step 8 post-summary next-action ask (next/wip routing) [next.md].
  "review consolidate", "PR review", "AI review", "CodeRabbit review", "Copilot review",
  "review check", "review summary", "merge ready", "internal review", "code-reviewer",
  "inline review", "line-level comment", "file:line annotation", "PR line review" triggers.
allowed-tools: [Agent, AskUserQuestion, Bash, Edit, Glob, Grep, Read, Write]
depends-on: [superpowers]
---

# Consolidate

Consolidate and respond to external feedback on PRs and issues.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| pr | Workflow entrypoint — PR identify, skip conditions, Copilot sequential, Rules | [pr.md](./pr.md) |
| collect | Step 3 Collect AI Reviews + Step 3.6 superpowers framework load | [collect.md](./collect.md) |
| internal | Step 3.5 Internal Code Review Fallback + Step 4.5 UI capture verification | [internal.md](./internal.md) |
| classify | Step 4 Analyze and Classify (dual-label Type \| Severity, PR scope cross-check) | [classify.md](./classify.md) |
| decide | Step 5 User Decision (Axis A/B) + Step 6 Fix or Reject | [decide.md](./decide.md) |
| post | Step 7 Post Summary + Formal Review (unified vs separate) + Step 7.5 Status + Step 7.6 Deferred registration | [post.md](./post.md) |
| next | Step 8 Post-Summary Next-Action Ask | [next.md](./next.md) |

## Quick Reference

### PR Review Workflow

Review CodeRabbit/Copilot feedback on a PR, decide what to act on, and post an AI Review Summary comment.

Entry: [`pr.md`](./pr.md) (Workflow index + Step 1, 2, 2.5 + Rules)

Step execution order:
1. **`pr.md`** Step 1 (Identify PR) + Step 2 (Skip Conditions) + Step 2.5 (Copilot sequential, multi-PR only)
2. **`collect.md`** Step 3 (Collect AI Reviews) + Step 3.6 (superpowers framework)
3. **`internal.md`** Step 3.5 (Internal Review Fallback, walkthrough only / on failure) + Step 4.5 (UI capture verification)
4. **`classify.md`** Step 4 (Analyze and Classify)
5. **`decide.md`** Step 5 (User Decision — Axis A/B) + Step 6 (Fix or Reject)
6. **`post.md`** Step 7 (Post Summary + Formal Review) + Step 7.5 (Status line) + Step 7.6 (Deferred registration)
7. **`next.md`** Step 8 (Post-Summary Next-Action Ask)
