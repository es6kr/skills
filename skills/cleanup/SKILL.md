---
name: cleanup
depends-on:
  - claudify
  - skill-kit
description: |
  Run the self-improving loop before session end. config - enable/disable individual tasks [config.md], fa-prune - deduplicate failed-attempts rules [fa-prune.md], hook-review - review hook errors and suggest improvements [hook-review.md], rag-store - persist to RAG before session end + sync fix_plan completed items to RAG (medium matrix fallback) [rag-store.md], retrospect - analyze mistakes and record to feedback memory/failed-attempts [retrospect.md], run - 5-step sequential execution (commit → self-improve → knowledge persist → checklist record → next-action recommendation) [run.md]. Supports Ralph mode (records to improvements.md instead of AskUserQuestion).
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
| fa-prune | Deduplicate failed-attempts.md rules | [fa-prune.md](./fa-prune.md) |
| hook-review | Review hook errors and suggest improvements | [hook-review.md](./hook-review.md) |
| rag-store | Persist to RAG before session end + sync completed fix_plan items (medium matrix fallback) | [rag-store.md](./rag-store.md) |
| retrospect | Analyze mistakes and record to feedback memory/failed-attempts | [retrospect.md](./retrospect.md) |
| run | 5-step sequential execution (commit → self-improve → knowledge persist → checklist record → next-action recommendation) | [run.md](./run.md) |

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
