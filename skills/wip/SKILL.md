---
name: wip
description: >-
  Track in-session work progress. Register steps for 3+ step tasks, update status per step, handle completion/abort.
  antigravity - task.md artifact-based checklist [antigravity.md],
  claude - TodoWrite/TaskCreate API [claude.md].
  "wip", "track progress", "register tasks", "task register", "step tracking" triggers.
metadata:
  author: es6kr
  version: "0.1.1"
---

# WIP (Work In Progress)

Track current session work as a checklist.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| antigravity | task.md artifact-based checklist for Antigravity sessions | [antigravity.md](./antigravity.md) |
| claude | TodoWrite/TaskCreate API for Claude Code sessions | [claude.md](./claude.md) |

## When to Use

- Starting a multi-step task (3+ steps)
- User gives a large task instruction
- Need to show progress to the user

## Quick Reference

### Antigravity

Use `task.md` artifact with standard markdown checkboxes (`- [ ]`, `- [/]`, `- [x]`).
Do NOT wrap checkboxes in backticks.

See [detailed guide](./antigravity.md).

### Claude

Use `TodoWrite` for sequential steps, `TaskCreate` for parallel tasks with dependencies.

See [detailed guide](./claude.md).

## Skip Conditions

WIP tracking is unnecessary for:
- Single command execution (kubectl get, ls, etc.)
- Tasks with 2 or fewer steps
- Read-only queries
- User explicitly says "keep it simple"

## Rules (Sequential Flow)

- **One in_progress at a time** — applies to ordered/sequential tracking (TodoWrite/checklist mode)
- **Update immediately on completion** — mark completed as soon as done
- **No skipping** — proceed in order, don't start next step before completing current
