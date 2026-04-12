# Claude Code WIP Tracking

Track in-session work progress using Claude Code's built-in TodoWrite/TaskCreate tools.

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
