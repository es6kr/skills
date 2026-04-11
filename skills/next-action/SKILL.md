---
name: next-action
description: Suggest next actions after completing any task. Use automatically when a task is finished to recommend 2-3 logical follow-up actions the user might want to take.
---

# Next Action Suggester

After task completion, use `AskUserQuestion` to suggest next steps and get user selection.

## When to use

Automatically use after any task completion:
- Code writing/modification complete
- Configuration changes complete
- File creation complete
- Commit/push complete
- Skill/agent creation complete
- Bug fix complete

## Instructions

### Step 1: Identify completed task type

Identify the type of task just completed.

### Step 2: Use AskUserQuestion tool

Present next step options via `AskUserQuestion`:

```typescript
AskUserQuestion({
  questions: [{
    question: "What would you like to do next?",
    header: "Next Action",
    multiSelect: true
    options: [
      { label: "Option 1", description: "Description" },
      { label: "Option 2", description: "Description" }
    ]
  }]
})
```

### Step 3: Execute selected action

Immediately perform the action(s) user selected.

## Suggestion Patterns

### After code writing/modification

```typescript
options: [
  { label: "Run tests", description: "Verify changes with test suite" },
  { label: "Commit", description: "Git commit the changes" }
]
```

### After feature implementation

```typescript
multiSelect: true,
options: [
  { label: "Write tests", description: "Add tests for new feature" },
  { label: "Document", description: "Update README or JSDoc" },
  { label: "Commit", description: "Git commit the changes" }
]
```

### After bug fix

```typescript
multiSelect: true,
options: [
  { label: "Add regression test", description: "Prevent bug recurrence" },
  { label: "Commit", description: "Git commit the fix" },
  { label: "Close issue", description: "Close related issue" }
]
```

### After configuration change

```typescript
options: [
  { label: "Verify", description: "Source or restart to apply settings" },
  { label: "Backup", description: "Backup config file" }
]
```

### After commit

```typescript
options: [
  { label: "Push", description: "Git push to remote" },
  { label: "Create PR", description: "Create Pull Request" }
]
```

### After push

```typescript
options: [
  { label: "Create PR", description: "Create Pull Request" },
  { label: "Check CI", description: "Verify pipeline status" }
]
```

### After skill/agent creation

```typescript
options: [
  { label: "Test", description: "Verify activation with trigger keywords" },
  { label: "Review integration", description: "Check for duplicates" }
]
```

### After file creation

```typescript
options: [
  { label: "Review content", description: "Verify created file" },
  { label: "Git add", description: "Stage with git add" }
]
```

### After refactoring

```typescript
multiSelect: true,
options: [
  { label: "Run tests", description: "Verify existing tests pass" },
  { label: "Check performance", description: "Run benchmarks (if applicable)" },
  { label: "Commit", description: "Commit refactoring" }
]
```

### After complex workflow completion

```typescript
multiSelect: true,
options: [
  { label: "Agentify", description: "Convert this workflow to an agent/skill" },
  { label: "Serena memory", description: "Save key learnings to Serena memory" }
]
```

### After project exploration/research

```typescript
multiSelect: true,
options: [
  { label: "Serena memory", description: "Store findings in project memory" },
  { label: "Document", description: "Update project documentation" }
]
```

## Rules

1. **Always 2-4 options** - AskUserQuestion limitation
2. **Be specific** - "Run npm test" instead of just "Test"
3. **Context-based** - Adjust based on project/situation
4. **Use multiSelect** - When multiple actions can be done together
5. **Execute immediately** - Perform action(s) right after user selection
