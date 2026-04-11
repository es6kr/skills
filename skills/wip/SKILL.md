---
name: wip
description: Track in-session work progress with TodoWrite/TaskCreate. Auto-register steps for 3+ step tasks, update status per step, handle completion/abort. "wip", "track progress", "register tasks", "task register", "step tracking" triggers.
---

# WIP (Work In Progress)

Track current session work as a checklist.

## When to Use

- Starting a multi-step task (3+ steps)
- User gives a large task instruction
- Need to show progress to the user

## Tool Selection

| Tool | When | Features |
|------|------|----------|
| **TaskCreate** | Multiple independent tasks, dependency management needed | ID-based, status tracking, blockedBy |
| **TodoWrite** | Sequential step list | Simple, ordered progression |

### Decision Tree

```
New work arrives
  ├─ Multiple independent tasks → TaskCreate
  │   (e.g., "modify 3 files in parallel")
  └─ Sequential steps → TodoWrite
      (e.g., "5-step deploy procedure")
```

## TodoWrite Pattern

### Register

```
Before starting:
TodoWrite([
  { content: "Step 1 description", status: "in_progress" },
  { content: "Step 2 description", status: "pending" },
  { content: "Step 3 description", status: "pending" }
])
```

### Progress

```
After step 1 completes:
TodoWrite([
  { content: "Step 1 description", status: "completed" },
  { content: "Step 2 description", status: "in_progress" },
  { content: "Step 3 description", status: "pending" }
])
```

### Rules

- **One in_progress at a time** — don't run multiple steps simultaneously
- **Update immediately on completion** — mark completed as soon as done
- **No skipping** — proceed in order, don't start next step before completing current

## TaskCreate Pattern

### Register

```
TaskCreate({ subject: "Modify file A", status: "pending" })
TaskCreate({ subject: "Modify file B", status: "pending" })
TaskCreate({ subject: "Run tests", status: "pending", addBlockedBy: ["1", "2"] })
```

### Progress

```
TaskUpdate({ taskId: "1", status: "in_progress" })
// do work
TaskUpdate({ taskId: "1", status: "completed" })
```

## Skip Conditions

WIP tracking is unnecessary for:
- Single command execution (kubectl get, ls, etc.)
- Tasks with 2 or fewer steps
- Read-only queries
- User explicitly says "keep it simple"
