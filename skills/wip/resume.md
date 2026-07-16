# Resume — Task cleanup and remaining work

Environment-agnostic (Claude Code / Antigravity) **task cleanup + remaining-work** workflow.

- **Cleanup** = remove completed/stale items (no user confirmation required)
- **Remaining work** = per-item direction ask → execute selected items

## When to Use

- User invokes "task cleanup and remaining work", "task cleanup", "remaining work", "resume task", "task resume"
- Immediately after `/wip` (SKILL.md "/wip Entry Procedure" references this topic)
- Resuming after a compact (need to identify outstanding work)

## Environment Detection

| Environment | Data medium | Tool guide |
|-------------|-------------|------------|
| Claude Code | `TaskList` / `TaskCreate` / `TaskUpdate` API | [claude.md](./claude.md) |
| Antigravity (Gemini) | `<appDataDir>/brain/<conversation-id>/task.md` artifact + `ask.md` emulation | [antigravity.md](./antigravity.md) |

Environment detection:
1. `TaskList` tool callable → Claude Code
2. `task.md` artifact exists or `appDataDir` context present → Antigravity
3. If both, prefer Claude Code (TaskList is more reliable)

## Precondition — Resume mode selected by SKILL.md Step 0

**Do NOT enter this workflow blindly.** SKILL.md `/wip Entry Procedure -> Step 0` must have classified args as Resume mode (or Mixed mode second phase). Registration-mode invocations (new-work args + 0 tasks) skip this file entirely and go to `TaskCreate` directly.

If you find yourself in this file with 0 existing tasks and args that request new deliverables (write / create / add / draft verbs), dispatch back to SKILL.md Step 0 and re-classify — you are in the wrong workflow.

## Step 1. Cleanup (`completed` auto only — `pending` deletion always requires user confirmation, HARD STOP)

Remove stale items immediately. The goal is to take them out of the selectable list so the next step's context is not muddied.

**HARD STOP — pending deletion is a user-decision area**: `completed` items are auto-deleted. `pending` items require `AskUserQuestion` confirmation regardless of label. Autonomous "stale/unrelated" reclassification is forbidden.

### Deletion targets

| Status | Sub-category | Deletion action |
|--------|--------------|-----------------|
| `completed` | — | **Auto-delete** (no confirmation) — completed tasks have no tracking value in the next session (their summary is already reflected in persistent files such as fix_plan.md) |
| `in_progress` (residue from a prior session) | — | **Auto-delete** — `in_progress` from before the compact is meaningless due to broken context |
| `pending` "actionable now" | Immediately actionable, autonomously executable | Keep (target of Step 2 direction ask) |
| `pending` "waiting on external" | Any label indicating a review/blocked/host-delegated/PR-merge-pending/user-decision-pending state (locale-agnostic — e.g. English `[REVIEW_PENDING]` / `[BLOCKED]`, or the equivalent in the workspace's local language) | **Not a deletion target** — keep. Consider migrating to checklist medium |
| `pending` "obsolete/unrelated" | Clearly unrelated or long-abandoned (e.g., not mentioned in 3+ sessions, related feature removed) | **Delete ONLY after user confirmation** — present candidate list via `AskUserQuestion` and delete only on explicit approval |

### Do NOT delete (HARD STOP — no autonomous classification)

- **`pending` items — delete forbidden without explicit user target, regardless of status/label**
  - The word "unrelated" is not a vocabulary the assistant may autonomously classify by. When classification is needed, present the candidate list via `AskUserQuestion` and delete only on explicit approval
  - Any label indicating a review/blocked/host-delegated state explicitly signals "waiting on external" → not a deletion target (locale-agnostic — recognize the equivalent label in the workspace's local language, not only English)
- The user has explicitly asked to "keep completed tasks"
- Tasks that belong to **an in-flight fix procedure** such as the `fix-*` series

### Don't / Do — pending deletion judgment

| # | Don't | Do |
|---|-------|-----|
| 1 | Receive a "delete stale tasks" instruction and autonomously classify pending tasks as stale before deleting | Pending always requires user confirmation. Present the candidate list via `AskUserQuestion` with explicit deletion approval per item |
| 2 | Reclassify labels that indicate a review-pending or blocked state as "unrelated" | These labels are explicit "waiting on external" states → never stale. Auto-exclude from deletion targets |
| 3 | Justify pending deletion via the "cleanup is no user confirmation required" clause | That clause applies only to `completed` + `in_progress` residue. Pending is a separate flow |
| 4 | Delete 4+ items in bulk without per-item judgment rationale | Verify each task's status / label / most-recently-mentioned session before deletion → report to user and get approval |

### Self-check (every time before executing a task-deletion command)

1. Do the deletion candidates include any `pending` status? — If yes, `AskUserQuestion` is immediately mandatory
2. Do any `pending` candidates carry a label indicating review/blocked/host-delegated state (in any language)? — If yes, exclude from deletion targets and report "this item is waiting on external, so keeping it" to the user
3. Is the user's instruction ambiguous vocabulary such as "delete stale"? — Present the candidate list and request explicit approval. "What counts as stale" is a user decision
4. Have per-item judgment rationale been reported to the user? — Blanket "all 4 are stale" is forbidden

### Per-environment commands

| Environment | Cleanup command |
|-------------|-----------------|
| Claude Code | `TaskList` → identify deletion targets → call `TaskUpdate(taskId, status: "deleted")` for each |
| Antigravity | Read `task.md` → identify lines to delete → remove those lines via `replace_file_content` |

## Step 2. Per-item direction ask

After Step 1, ask the direction for each remaining incomplete item (`pending` + `in_progress`).

### Direction options

| Label | Meaning |
|-------|---------|
| **Proceed** | Start execution as currently defined |
| **Split** | Split the larger task into smaller sub-tasks |
| **Merge** | Combine with another task into a single one |
| **Hold** | Defer until another task completes (precedence dependency) — stays in the task list |
| **Defer to checklist** | Move the task out of the task list into the checklist file (`fix_plan.md` hold section / `checklist.md`) — for external-wait / long-idle items that need cross-session persistence, not session tracking. Execution: see "Reverse direction — task → checklist demotion" below |
| **Delete** | No longer needed |

### Don't / Do — environment-agnostic

| # | Don't | Do |
|---|-------|-----|
| 1 | Ask only "which one first?" (priority alone) | Decide **per-item** direction (proceed / split / merge / hold / delete) first |
| 2 | Compress 5 items into a single ask | One independent question per item (Claude's `questions` array maxes at 4 — report the rest as "deferred") |
| 3 | Bundle tasks under one ask via `multiSelect` | Each question independently decides the direction of its task |
| 4 | Mark the first item `in_progress` without the direction ask | Step 3 may only be entered after Step 2 is complete |
| 5 | Offer only "Hold (keep as task)" for external-wait items (user manual action / merge instruction / reply pending) | Include **Defer to checklist** in the option set — external-wait items belong in the checklist medium per "Medium separation principle" below. Hold keeps them polluting the task list across sessions |

### Per-environment ask method

| Environment | Ask method |
|-------------|-----------|
| Claude Code | `AskUserQuestion` — one question per task in the `questions` array, max 4 (details: [claude.md](./claude.md) → "AskUserQuestion — per-item direction ask") |
| Antigravity | `ask.md` emulation (`ArtifactType: "other"`, `RequestFeedback: true`) — per-item options + Pros/Cons (details: [antigravity.md](./antigravity.md) → "Workflow → 1. Interactive Task Selection") |

### Auto-proceed exception (Claude Code)

If a task subject contains only simple **lookup/check keywords**, execute it immediately without asking and reflect the result (see [claude.md](./claude.md) → "Auto-proceed — verification/lookup tasks need no ask").

| Example keyword | Auto-run command |
|-----------------|------------------|
| "CI result", "PR state", "deploy check" | `gh pr checks` / `gh pr view` / `curl` |

The check result is reflected in **both** the task subject update **and** the matching `[x]` in the checklist file.

## Step 3. Decide start priority and execute

Among the items decided as "Proceed" in Step 2, decide the start priority → mark the first item `in_progress` → perform the work.

### Per-environment execution

| Environment | Execution |
|-------------|-----------|
| Claude Code | `TaskUpdate(taskId, status: "in_progress")` → work → `TaskUpdate(status: "completed")` |
| Antigravity | Change the matching line in `task.md` to `- [/]` → work → change to `- [x]` |

### Loop continuation (HARD STOP — do not stop with a report mid-batch)

Step 3 is a **loop**, not a single action. After each "Proceed" item completes — **including when it finished via a sub-skill call** (`github-flow`, `fix`, `consolidate`, etc.) — control returns to the /wip loop. Drive the **next** Proceed item **in the same turn**. Do not end the turn with a status report while Proceed items remain. When the batch is exhausted, invoke `Skill("next")` to surface the remaining/follow-up work — do not end with a bare report. Delegating an item to a **background agent** (`run_in_background`) also returns control immediately — the dispatch itself is not a reason to stop.

| # | Don't | Do |
|---|-------|-----|
| 1 | A sub-skill (github-flow/fix/…) returns → write a report → end the turn while other Proceed items are pending | Sub-skill return = control is back in the /wip loop. Mark that item done → start the next Proceed item in the same turn |
| 2 | Treat "the item I just drove via a sub-skill" as the whole batch | Batch = all items marked Proceed in Step 2. One done ≠ batch done |
| 3 | All Proceed items done → stop with a report | Batch exhausted → invoke `Skill("next")` for next-action options |
| 4 | Dispatch a background agent for one item → end the turn "waiting for the agent" while other pending/follow-up items are drivable | Background dispatch returns control to the loop at once — drive the next drivable item in the same turn (the agent's completion re-invokes the session by itself). Idling past ~5 minutes also expires the prompt cache (5-min TTL), so the completion wake-up re-reads full context uncached |

**Self-check (every time a sub-skill returns OR an item is marked completed inside Step 3):**
1. Are there Proceed items not yet driven? → Yes: start the next one in this turn (no report-and-stop)
2. Batch exhausted? → invoke `Skill("next")` (not a bare report)
3. A blocked item (waiting on a predecessor) is skipped, but skipping it does not satisfy the batch
4. A background agent is running → are other pending/follow-up items drivable now? Drive them in this turn; an idle wait is acceptable only when nothing else is drivable

### When there are 5 or more items

The ask-medium ceiling (Claude `questions` max 4, Antigravity `ask.md` visibility) means only the top 4 by priority are asked. The rest are reported in the "deferred / external wait" category only (re-ask on the next `/wip`).

## Task decomposition — synchronization with checklist files (MANDATORY)

`[ ]` open items in `fix_plan.md` / `checklist.md` are **pulled into tasks for execution tracking**.

### Core distinction

| Checklist item | Task handling |
|----------------|---------------|
| `[ ]` open (autonomously actionable) | **Register as an execution task** |
| `[ ] [BLOCKED]` (waiting on external response / permission) | **Do NOT create a task**. Leave it in the checklist; promote it to a task when the trigger arrives |
| `[x]` completed | **Bundle into a single cleanup task** (Completed move) — not one per item |

### Medium separation principle (HARD STOP)

| # | Don't | Do |
|---|-------|-----|
| 1 | Register a `[BLOCKED]` item as a task | Keep it in the checklist's hold section; do not register a task |
| 2 | Double-register BLOCKED items under the rationale "having it in the task list helps me not forget" | The checklist is reloaded every session, so it won't be forgotten. Duplicating the medium increases sync overhead |
| 3 | Use `[BLOCKED]` as a task subject prefix | Use the checklist's `## Hold` section: `- [ ] [BLOCKED] <subject> (trigger: ...)` |
| 4 | Report "BLOCKED still BLOCKED" on every `/wip` for external-wait tasks | If it is not in the task list, it is not a reporting target. When the response arrives, promote it from the checklist to a task |

### Reverse direction — task → checklist demotion (Defer to checklist execution)

The sync above defines promotion (checklist `[ ]` → task). The reverse — demotion — executes the Step 2 "Defer to checklist" decision:

1. Append the item to the checklist file (`fix_plan.md` hold section / `checklist.md`): `- [ ] [BLOCKED] <subject> (trigger: <re-activation condition>)` — the trigger is mandatory, otherwise the item can never be promoted back
2. Remove the task: `TaskUpdate(taskId, status: "deleted")` (Claude) / delete the line from `task.md` (Antigravity)
3. Never leave the item in both media — duplicate medium = sync burden (same principle as Don't `#2` above)
4. Report the demotion with the checklist path so the user knows where it went

### Ordering principle

Execution tasks (work to do now) come **first (top)**, hold tasks last. Because environment-specific additions append to the end:

1. Temporarily remove existing hold tasks
2. Extract all `[ ]` open items from the checklist → register them as execution tasks (top of the list)
3. Register a single `[x]` Completed-move task (if needed)
4. Re-register the hold tasks (bottom of the list)

## Violation history

- 2026-05-03 (wip 2nd recurrence): With 5 remaining items, only "which one first?" was asked → Step 2 was skipped. Reinforced via the "/wip Entry Procedure" added to SKILL.md.
- 2026-05-12 (D 2nd recurrence): Only the `[x]` items were turned into a cleanup task while the `[ ]` open work was not promoted to tasks → "Don't just leave it sitting in fix_plan — pull it into the task list" feedback received.
- 2026-05-20 (origin of this topic): The natural-language trigger "task cleanup and remaining work" was scattered across cleanup Phase 0 and wip Step A, lacking a single entry point. The resume topic was introduced to unify them.

## Quick Reference

```text
/wip or "task cleanup and remaining work" invocation
  ↓
Step 1: Cleanup (immediate, no ask)
  ├─ Claude: TaskList → TaskUpdate(status:"deleted") × N
  └─ Antigravity: task.md → replace_file_content
  ↓
Step 2: Per-item direction ask
  ├─ Claude: AskUserQuestion (questions array, 1 question per task, max 4)
  └─ Antigravity: ask.md (RequestFeedback: true)
  ↓
Step 3: Start priority + execute
  ├─ Claude: TaskUpdate(in_progress) → work → TaskUpdate(completed)
  └─ Antigravity: - [/] → work → - [x]
```
