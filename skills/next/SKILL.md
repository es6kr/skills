---
metadata:
  author: es6kr
  version: "0.1.1" # x-release-please-version
name: next
depends-on: [fix]
description: >-
  Suggest next actions after completing any task. **Auto-invocation currently broken**: Stop hook (`resources/next-trigger.sh`) outputs stdout marker but Claude Code Stop hook spec routes stdout to debug log only (LLM not notified) — see hook/SKILL.md "Output channel spec per event". Use this skill via explicit `/next` invocation or by manually calling Skill("next") after task completion until hook is migrated to JSON `decision:"block"` or stderr+exit2.
  stall-detect - detect stalled follow-up steps after task completion and invoke /fix [stall-detect.md].
  Use when "next action", "what next", "stall", "stuck", "not progressing", "follow-up missing" is mentioned.
---

# Next Action Suggester

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| stall-detect | Detect stalled follow-up steps and invoke /fix | [stall-detect.md](./stall-detect.md) |

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

### Step 0: Stall Detection (mandatory)

Before suggesting next actions, run the [stall-detect](./stall-detect.md) topic.

If stall detected → topic invokes `/fix`. If no stall → proceed to Step 0.5.

### Step 0.5: TaskList primary-source check (MANDATORY — every time before composing ask options)

**Immediately before calling `AskUserQuestion`, call `TaskList` to directly verify current pending/in_progress tasks.** Do not compose options from context summary / memory / inference of recent work.

#### Why it's mandatory

- Right after `/compact`, summary memory can be stale — frequent mismatch with the real task list
- When task names/contents appear in option descriptions, the user **trusts they exist** → fabricating virtual tasks in options breaks that trust
- One TaskList call = primary source for option accuracy

#### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | Compose options by quoting "Task #N registered" from summary memory | Call `TaskList` → use pending/in_progress entries directly as option candidates |
| 2 | Assume "the task I just registered is still there" | Task IDs/contents can change after /compact. Read TaskList every time |
| 3 | Option-ify only some pending tasks (e.g., "only the 1 immediately actionable") | Include all pending tasks as option candidates. If trigger conditions differ, state them in description |
| 4 | Write virtual tasks ("FA-update immediate progress") in option descriptions | Quote real task subject + ID (note: `#NN` is replaced by subject keywords per workflow.md HARD STOP) |

#### Self-check (every time before calling AskUserQuestion)

1. Does this ask relate to task progress direction? → If yes, TaskList Read is mandatory
2. Do the tasks mentioned in option descriptions **actually exist in TaskList**? — 1:1 mapping with TaskList output
3. If there are N pending tasks but only M < N appear in options → state the filtering reason in description or use the wrap-up pattern

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

### Step 3: Register and execute selected action(s)

**If 2 or more actions are selected, register each via TaskCreate and execute sequentially.** If only 1 is selected, execute it directly.

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

### After PR fix commit push (after pushing a fix commit to an existing PR)

**Precondition**: A fix commit has just been pushed to an existing PR. CI has been re-triggered.

**Self-check before calling**: Verify AI Review Summary posting status via `gh pr view <N> --json comments`.

**When AI Review Summary is not posted** (multiSelect: false):
```typescript
options: [
  { label: "Wait for CI → consolidate (Recommended)", description: "After CI passes, run /consolidate pr-review <N>. Test Plan verification comes after consolidate" },
  { label: "Wait for CI only", description: "Decide next action after CI result" },
]
```

**When AI Review Summary is posted** (multiSelect: false):
```typescript
options: [
  { label: "Wait for CI → Test Plan verification (Recommended)", description: "After CI passes, verify unchecked Test Plan items" },
  { label: "Wait for CI only", description: "Decide next action after CI result" },
]
```

| # | Don't | Do |
|---|-------|-----|
| 1 | CI passes → jump directly to Test Plan verification (skipping consolidate) | CI passes → check AI Review Summary → if missing, run consolidate first → then Test Plan |
| 2 | "User asked for Test Plan check, so verify only" | Even if user-requested, if consolidate is not posted, guide consolidate first |

### After PR creation (BEFORE consolidate — branch on CodeRabbit walkthrough posting state)

**Precondition**: Passed `github-flow/pr.md` Step 9. Branch on whether CodeRabbit walkthrough has arrived.

**Self-check before calling**: Verify walkthrough state via `gh pr view <N> -R <repo> --json comments`. Do not stop at reporting — **always** branch into one of the option sets below.

**When walkthrough is posted** (multiSelect: false):
```typescript
options: [
  { label: "Call consolidate pr-review immediately (Recommended)", description: "/consolidate pr-review <N> — post Internal Review + AI Review Summary" },
  { label: "Internal Review first", description: "Self-review via superpowers:code-reviewer → then consolidate" },
  { label: "Hold", description: "Push additional commits and wait for re-review" },
]
```

**When rate limited / pending** (multiSelect: false):
```typescript
options: [
  { label: "Register task and move on (Recommended)", description: "TaskCreate \"Run /consolidate pr-review <N> after CodeRabbit review arrives\" — call when notified" },
  { label: "Manual trigger and wait", description: "Force trigger with @coderabbitai review comment and wait for walkthrough arrival" },
  { label: "Skip consolidate (skip-review)", description: "Apply coderabbit:ignore label → proceed with Internal Review only" },
]
```

| # | Don't | Do |
|---|-------|-----|
| 1 | Stop at a "waiting for review" text report without presenting options | Check walkthrough state, then present options per the branches above |
| 2 | Offer merge options when walkthrough has arrived | consolidate first — consistent with block-merge-without-review.sh guard |
| 3 | Batch-handle multiple PRs as "all waiting for review" | Check walkthrough state per PR (arrival/rate-limit may differ) |

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

### After session wrap-up with pending tasks (HARD STOP — TaskList based)

**Precondition**: The session's core work is complete and the user signals "wrap-up / end session / cleanup", or only asset cleanup (file moves, doc updates) remains. At least one pending/in_progress task remains for carryover.

**Step 0.5 required — Read TaskList directly to identify pending entries**:

```bash
TaskList   # use pending/in_progress entries as the source
```

#### Option composition rules

| Pending count | multiSelect | Option layout |
|------------|-------------|----------|
| 0 | — | Wrap-up pattern unnecessary → **skip ask** (AskUserQuestion requires ≥2 options per Rule 1; a sole "End session" is not a valid call) |
| 1 | false | `[Run now, Defer to next session, Hold]` — quote task subject |
| 2~3 | false | `[Run-now option per task + End session (Recommended)]` — include all pending in options |
| 4+ | false (max 4) | Top 3 by priority + "End session" — note "carryover N items" in description for the rest |

**Option description format (subject keyword + trigger condition)**:

```typescript
{ label: "Run {task subject keyword} now", description: "{what to do} — {trigger: immediate / scheduled / external response}" }
```

#### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | Recommend only "1-2 immediately actionable" among pending | All pending as candidates. State trigger conditions in description |
| 2 | Quote task names from summary memory | Call TaskList and quote real subjects |
| 3 | Expose TaskList-internal `#NN` IDs in option descriptions | Per workflow.md "TaskList ID forbidden in conversation" — reference via subject keyword |
| 4 | Omit "End session" option → user cannot choose wrap-up | Always include "End session" as one of the options (paired with at least one Run-now option to satisfy Rule 1's ≥2 options) |
| 5 | Skip TaskList Read before wrap-up ask | TaskList every time per Step 0.5 |

#### Example (2 pending, right after asset cleanup)

```typescript
AskUserQuestion({
  questions: [{
    question: "Asset move complete. Next action for this session?",
    header: "Next Action",
    multiSelect: false,
    options: [
      { label: "End session (Recommended)", description: "Carry over 2 tasks (cleanup Phase 2 Ralph exit note, CB no_progress misclassification analysis) to next session" },
      { label: "Run cleanup-RalphExit task now", description: "Note Ralph exit point right before cleanup run.md Phase 2 — ready to start" },
      { label: "Run RalphCB-no_progress task now", description: "Analyze CB OPEN no_progress misclassification — ready to start (analysis task)" },
    ]
  }]
})
```

### After PR consolidate (after AI Review Summary is posted)

**Precondition**: Completed `consolidate/pr-review.md` through Step 7 (Internal Review + AI Review Summary posted).

**Merge option guard** (`block-merge-without-review.sh` pass-through conditions):
- Description must include "AI Review Summary posted (\<URL\>)" or "AI Review Summary ✅"
- Or replace with a non-merge option such as "consolidate pr-review first"

**When all 4 merge conditions are met** (multiSelect: false):
```typescript
options: [
  { label: "Squash merge (Recommended)", description: "AI Review Summary posted (<comment-URL>) | CI ✅ | Test Plan ✅ | Mergeable ✅" },
  { label: "Apply minor findings, then merge", description: "Apply N Minor findings → CI pass → merge" },
  { label: "Hold", description: "Decide after further review" },
]
```

**When Test Plan has unchecked items** (multiSelect: false):
```typescript
options: [
  { label: "Verify unchecked items (Recommended)", description: "Verify N items via web-ui-test / curl → mark [x] → merge" },
  { label: "Move to separate issue, then merge", description: "Register the unchecked items as a follow-up issue and remove from this PR's Test Plan" },
  { label: "Hold", description: "Decide after verification" },
]
```

**When CI fails (unrelated to PR)**:
```typescript
options: [
  { label: "Report CI failure cause + register separate issue", description: "Register an issue noting unrelatedness to PR changes + assess mergeability" },
  { label: "Self-approve + merge (if confirmed unrelated)", description: "AI Review Summary posted (<URL>) | E2E confirmed unrelated to PR | Squash merge" },
  { label: "Hold", description: "Wait for CI to pass" },
]
```

**Actual merge is executed only via the `/github-flow merge` skill** — register as a follow-up task after option selection.

## Rules

1. **Always 2-4 options** - AskUserQuestion limitation
2. **Be specific** - "Run npm test" instead of just "Test"
3. **Context-based** - Adjust based on project/situation
4. **Use multiSelect** - When multiple actions can be done together
5. **Register then execute** - When 2+ options are selected, TaskCreate then run sequentially. If only 1, execute directly
6. **State conditions when proposing merge** - When including PR merge in options, the description must show condition state in the form `CI:✅ Review:✅ TestPlan:x/y`. Actual merge runs only via the `/github-flow merge` skill — direct `gh pr merge` is forbidden

