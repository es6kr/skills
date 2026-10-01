---
name: cleanup
depends-on:
  - claudify
  - fa
  - fix
  - hook-kit
  - skill-kit
description: |
  Run the self-improving loop before session end. config - enable/disable individual tasks [config.md], hook-review - review hook errors and suggest improvements [hook-review.md], rag-store - persist to RAG before session end + sync fix_plan completed items to RAG (medium matrix fallback) [rag-store.md], run - 5-step sequential execution pipeline, entry point and Steps 0-1 [run.md]; its step bodies live in run-self-improve.md (Step 2), run-knowledge-persist.md (Step 3), run-checklist-sync.md (Steps 4/4.5) and run-wip-handoff.md (Steps 5/5.5). Mistake recording (retrospect) and FA pruning moved to the fa skill — invoke Skill("fa") / Skill("fa", "fa-prune"). Supports Ralph mode (records to improvements.md instead of AskUserQuestion).
  Use on "wrap up", "session cleanup", "end session", "cleanup", "record mistake", "save feedback", "improve", "retrospect", "hook error", "next action", "RAG store", "qdrant store", "fix_plan sync", "cleanup --auto", "cleanup --ralph", "auto mode", "ralph mode".
triggers:
  - event: Stop
    action: inject
    message: "Run /cleanup run. This is the pre-session-end cleanup task."
metadata:
  author: es6kr
  version: "0.1.0"
---

# Cleanup

Sequentially run cleanup tasks before session end.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| config | Enable/disable individual tasks | [config.md](./config.md) |
| hook-review | Review hook errors and suggest improvements | [hook-review.md](./hook-review.md) |
| rag-store | Persist to RAG before session end + sync completed fix_plan items (medium matrix fallback) | [rag-store.md](./rag-store.md) |
| run | 5-step sequential execution (commit → self-improve → knowledge persist → checklist record → next-action recommendation) + automated helper script execution (`fa-analyze.py`, `hybrid_sweep_rag.py`, `sync_dual_wiki.py`) | [run.md](./run.md) |
| run-self-improve | Step 2 body — mistake analysis, hook/skill review, pattern detection | [run-self-improve.md](./run-self-improve.md) |
| run-knowledge-persist | Step 3 body — walkthrough, infra check, RAG store modes (3-C.1~3-C.4), memory dual-sync | [run-knowledge-persist.md](./run-knowledge-persist.md) |
| run-checklist-sync | Step 4 / 4.5 body — checklist & backlog sync, comprehensive result report matrix | [run-checklist-sync.md](./run-checklist-sync.md) |
| run-wip-handoff | Step 5 / 5.5 body — wip delegation contract, status-based self-task prune | [run-wip-handoff.md](./run-wip-handoff.md) |

**Moved topics**: `retrospect` and `fa-prune` are owned by the [`fa` skill](../fa/SKILL.md) — invoke `Skill("fa")` / `Skill("fa", "fa-prune")`. The stubs [retrospect.md](./retrospect.md) / [fa-prune.md](./fa-prune.md) only redirect.

## Quick Reference

### Run everything

```
/cleanup              # run topic (default)
/cleanup run          # explicit run
```

### Suppress asks (attended session, no interruptions)

```
/cleanup --auto        # attended session, don't ask — use documented defaults, still commit/edit/call skills normally
/cleanup --ralph       # typed in an interactive session (no RALPH_LOOP=1): treated as --auto (see run.md's mode comparison table)
```

`--ralph`'s fully-restricted meaning (record-only, no direct modification, report to `.ralph/improvements.md`) applies only to a true autonomous loop — `.ralph/` directory present **and** `RALPH_LOOP=1` set. See [run.md](./run.md) "Auto Mode vs. Ralph Mode" for the full comparison.

### Change settings

```
/cleanup config                    # view current settings
/cleanup config disable serena     # disable serena memory
/cleanup config enable serena      # enable serena memory
```
