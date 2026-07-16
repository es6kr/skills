---
name: todowrite
metadata:
  author: es6kr
  version: "0.1.0"
depends-on:
  - wip
description: Route TODO checklists to the right storage + TaskList conversational discipline. session - in-session tracking via /wip, file - persistent TODO (fix_plan.md, TODO.md), issue - team-shared via GitHub Issues, conversation-id - subject-prefix references in user-visible output (no internal TaskList IDs), completion-report - TaskUpdate completion message format + file-change disclosure, fix-plan-sync - two-way sync between task medium and checklist medium, priority-prefix - encode task priority + execution order via subject prefix when TaskUpdate has no priority field, media-separation - 3-layer model: tracking (files) vs recording (RAG) vs knowledge (Wiki) [media-separation.md]. "TODO management", "checklist", "todowrite", "fix_plan cleanup", "register as issue", "task ID", "completion report", "task transfer", "task priority", "prefix ordering", "3-layer separation", "RAG vs wiki", "work record media" triggers.
---

# TodoWrite

Route TODO checklists to the appropriate storage based on context, and enforce conversational/reporting discipline around TaskList items.

## Routing Decision

```
New TODO arrives
  ├─ Only needed this session → /wip (TaskCreate/TodoWrite)
  ├─ Persists beyond session → file (fix_plan.md, TODO.md)
  └─ Team-shared → issue (GitHub Issues)
```

## Topics

| Topic | Storage | Lifetime | Tool / Guide |
|-------|---------|----------|--------------|
| session | TaskCreate/TodoWrite | Session | → `/wip` skill |
| file | fix_plan.md, TODO.md | While file exists | Write/Edit |
| issue | GitHub Issues | Permanent | `gh issue create` |
| conversation-id | — | Always-on | [conversation-id.md](./conversation-id.md) — subject-prefix references in user-visible output |
| completion-report | — | Always-on | [completion-report.md](./completion-report.md) — TaskUpdate completion format + file-change disclosure |
| fix-plan-sync | — | Always-on | [fix-plan-sync.md](./fix-plan-sync.md) — two-way sync between task medium and checklist medium |
| priority-prefix | — | Always-on | [priority-prefix.md](./priority-prefix.md) — priority/order via subject prefix (`P{n}`, PR-anchored, `fix-*` > P0) |
| media-separation | — | On-demand | [media-separation.md](./media-separation.md) — 3-layer model: tracking files vs RAG vs LLM Wiki |

## Skip exceptions

**TodoWrite can be skipped when**:
- Running a single command (e.g., `kubectl get`, `ls`)
- A task with 2 or fewer trivial steps
- Information lookup only

**`AskUserQuestion` can be skipped when**:
- The user gave a clear directive
- The action is safe and reversible
- The general best practice is unambiguous

## Session → /wip

Current session task tracking is handled by the `wip` skill:

```
/wip    # Track session work with TodoWrite/TaskCreate
```

## File-based TODO

### fix_plan.md (Ralph projects)

```markdown
## Pending

- [ ] Item 1 — description
- [ ] Item 2 — description

## Completed

- [x] Done item — (completed: 2026-04-03, commit abc1234)
```

**Rules:**
- Move to `Completed` section on completion + timestamp
- Mark blocked items with `[BLOCKED]` tag
- Mark skipped items with `[SKIPPED]` tag

### TODO.md (General projects)

```markdown
# TODO

## High Priority
- [ ] Urgent item

## Normal
- [ ] Regular item

## Done
- [x] Completed item (2026-04-03)
```

## Issue-based TODO

Team-shared TODOs go to GitHub Issues:

```bash
# Create issue (user approval required)
gh issue create --title "Item" --body "Description"

# List issues
gh issue list --label "todo"
```

**Note:** `gh issue create` only runs when user explicitly says "create an issue".

## Routing Examples

| Situation | Route | Reason |
|-----------|-------|--------|
| "Run this 5-step deploy" | `/wip` (session) | Session tracking is sufficient |
| "Fix this bug later" | file (fix_plan.md) | Persists beyond session |
| "Assign this to Jinju" | issue (GitHub) | Team sharing needed |
| "Note this from the review" | file (fix_plan.md) | Outside current PR scope |
