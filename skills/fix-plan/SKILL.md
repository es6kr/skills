---
name: fix-plan
description: |
  fix_plan.md / checklist.md schema and lifecycle management. Topics — format ([ ]/[x]/[BLOCKED] markers, Progress/Completed sections), priority (P0-P3 GitHub-aligned BLOCKED suffix + external/selfable reason classification), add (Action/Why/How authoring), move ([x] → Completed summary, subtree partial completion), sync (gh pr/issue state polling → auto-check), issue-drafts (write → publish → archive → delete lifecycle). Use when: "fix_plan", "checklist", "BLOCKED priority", "triage blocked", "fix-plan sync", "issue draft cleanup".
metadata:
  author: es6kr
  version: "0.1.0"
depends-on:
  - github-flow
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Bash(gh:*)
  - Bash(mv:*)
  - Bash(mkdir:*)
---

# Fix Plan

Schema and lifecycle management for `fix_plan.md` (Ralph convention) and `checklist.md` (non-Ralph workspaces). Vendor-agnostic — extracted from Ralph integration to be reusable across environments.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| format | Schema: `[ ]` / `[x]` / `[BLOCKED]` markers, Progress/Completed sections, item state changes, section-consistency check | [format.md](./format.md) |
| priority | `[BLOCKED:P0-P3:reason]` GitHub-aligned priority suffix + `external` / `selfable` reason classification + triage workflow | [priority.md](./priority.md) |
| add | New item authoring schema (Action / Why / How), length budget, deliverable separation (research / plan / checklist split) | [add.md](./add.md) |
| move | `[x]` → Completed summary rules, subtree-move partial completion under unfinished parent, optional abstract RAG dispatch | [move.md](./move.md) |
| sync | GitHub PR/Issue state polling (`gh pr view` / `gh issue view`) → auto-check `[ ]` → `[x]` on MERGED PR or CLOSED issue; PR CLOSED-without-merge → `[BLOCKED:P2:external]` | [sync.md](./sync.md) |
| issue-drafts | Issue Drafts lifecycle: write → publish → archive (`.bak/`) → delete from fix_plan | [issue-drafts.md](./issue-drafts.md) |

## Topic Dependencies

```text
fix-plan (schema + lifecycle)
  ├─→ format (entry — section structure + markers)
  ├─→ priority (new convention — BLOCKED P0-P3 + reason)
  ├─→ add (authoring)
  ├─→ move (completion → Completed)
  │     └─→ optional --rag=<skill>:<topic> dispatch for semantic indexing (caller-supplied)
  ├─→ sync (GitHub state polling) — depends on github-flow gh CLI conventions
  └─→ issue-drafts (lifecycle of draft files)
```

- All topics are independently invocable
- `move` topic optionally dispatches to a RAG receiver if the caller supplies `--rag=<skill>:<topic>` — generic skill stays vendor-agnostic; receiver implementation lives in the caller (e.g., ralph wrapper)
- `sync` topic uses `gh` CLI per `github-flow` skill's conventions

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `task-tracker` | `fix_plan.md` | Tracker filename. Use `checklist.md` for non-Ralph workspaces |
| `rag-receiver` | (unset) | Optional `<skill>:<topic>` dispatch for `move` topic semantic indexing — set via the `--rag=<skill>:<topic>` CLI flag on the `move` topic (see [move.md](./move.md)). No env var or config file is consumed by this skill; the caller routes |

## Quick Reference

### Schema (format)

```markdown
# Fix Plan

## Progress

- [ ] {Action}
  - **Why**: {motivation}
  - **How to apply**: {procedure}
- [BLOCKED:P0:external] {Action} (awaiting X)
- [x] {Completed item — pending move}

## Completed

- 2026-06-07 12:00 — {one-line summary} (commit {sha}, PR #{N})
```

See [format.md](./format.md) for full schema.

### BLOCKED priority + reason (priority — NEW convention)

```markdown
- [BLOCKED:P0:external] PR #45 user merge decision
- [BLOCKED:P1:selfable] consolidate Step 2.4 PR create (branch + body ready)
- [BLOCKED:P2:external] CodeRabbit re-review awaiting
```

- **P0**–**P3**: GitHub priority label-aligned (P0 highest)
- **external**: true external dependency
- **selfable**: progressable now (P-rank for immediate action)

See [priority.md](./priority.md) for full convention.

### Add new item

```markdown
- [ ] {one-sentence Action}
  - **Why**: {motivation 1-2 sentences}
  - **How to apply**: {procedure / tools / commands}
```

See [add.md](./add.md) for length budget + deliverable separation.

### Move to Completed

After `[x]` checked, summarize to one line + move to Completed section. See [move.md](./move.md).

### Sync GitHub state

```bash
gh pr view <N> --json state,mergedAt   # PR
gh issue view <N> --json state,closedAt # Issue
```

MERGED PR or CLOSED issue → auto `[x]`. PR CLOSED-without-merge → `[BLOCKED:P2:external]`. See [sync.md](./sync.md).

### Issue Drafts lifecycle

`issue-drafts/<slug>.md` → `gh issue create` → archive to `.bak/` → delete from fix_plan. See [issue-drafts.md](./issue-drafts.md).

## See Also

- `github-flow` (depends-on) — `gh` CLI conventions for sync + register
- Ralph integration is a separate workstream maintained outside this published skill. A Ralph wrapper, when present, owns Ralph-specific concerns: the `## REPEAT` persistent-item section, autonomous-loop `[BLOCKED]` skip semantics, and the caller-side `--rag=<skill>:<topic>` dispatch (this skill exposes only the abstract flag contract). See the Ralph project's documentation for wrapper details
