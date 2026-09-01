---
name: cleanup
depends-on:
  - claudify
  - fa
  - fix
  - hook-kit
  - skill-kit
description: |
  Run the self-improving loop before session end. config - enable/disable individual tasks [config.md], hook-review - review hook errors and suggest improvements [hook-review.md], rag-store - persist to RAG before session end + sync fix_plan completed items to RAG (medium matrix fallback) [rag-store.md], run - 5-step sequential execution (commit → self-improve → knowledge persist → checklist record → next-action recommendation) [run.md]. Mistake recording (retrospect) and FA pruning moved to the fa skill — invoke Skill("fa") / Skill("fa", "fa-prune"). Supports Ralph mode (records to improvements.md instead of AskUserQuestion).
  Use on "wrap up", "session cleanup", "end session", "cleanup", "record mistake", "save feedback", "improve", "retrospect", "hook error", "next action", "RAG store", "qdrant store", "fix_plan sync".
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

**Moved topics**: `retrospect` and `fa-prune` are owned by the [`fa` skill](../fa/SKILL.md) — invoke `Skill("fa")` / `Skill("fa", "fa-prune")`. The stubs [retrospect.md](./retrospect.md) / [fa-prune.md](./fa-prune.md) only redirect.

## Quick Reference

### Run everything

```
/cleanup              # run topic (default)
/cleanup run          # explicit run
```

### Change settings

```
/cleanup config                    # view current settings
/cleanup config disable serena     # disable serena memory
/cleanup config enable serena      # enable serena memory
```
