# Task ↔ Checklist Two-Way Sync (HARD STOP)

When a task changes state (`completed` / `deleted`), the corresponding checklist entry (`fix_plan.md` or workspace `checklist.md`) **must** be updated in the same turn. The same is true in reverse: when an item moves to a checklist, the task medium must be cleaned up.

## Sync map

| Task change | Checklist sync action |
|-------------|----------------------|
| `completed` | Check the matching item `[x]` + record completion info |
| `deleted` (superseded) | Update the matching item with "superseded by …" or check `[x]` |
| `deleted` (cancelled) | Record the cancellation reason on the matching item |
| **Merge (N tasks → 1)** | **The checklist also merges N items into 1 with a sub-checklist** |
| **Split (1 task → N)** | The checklist splits the 1 item into N |
| **Transfer (task → checklist)** | **Mark the task `deleted`** + register the checklist entry. One medium only |
| **External-wait transition** | Task `deleted` + checklist `## Hold` or `[BLOCKED]` (see `fix.md` Step 4 medium-separation rule) |

**"Clean-up" ≠ "delete" (checklist only)**: cleaning up a checklist means status update (`[x]` check + reason note + Completed move), not item removal. **However, on the task side, the cleanup IS `deleted`** — when transferring, the task is deleted and the checklist gains a new row.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Change a task to deleted/completed without touching the checklist | Right after the task state change, find and update the matching checklist item |
| 2 | Wholesale-delete a checklist item | Check `[x]` + annotate "superseded/done" → move to Completed via `/ralph fix-plan` |
| 3 | "I cleaned the task — checklist later" deferral | Update both media in the same turn |
| 4 | Register on the checklist and keep the same task → duplicated medium | Right after registering on the checklist, mark the task `deleted`. One medium |
| 5 | Just update the task description ("paused pending 3 decisions") and skip medium unification | Description updates are not a substitute for medium cleanup. Checklist-registered = task deleted |
| 6 | "If I leave the task around, I won't forget" thinking | `fix_plan.md` is reloaded at the start of every session → nothing is forgotten. Duplicated media = sync burden |

## Transfer trigger keywords (HARD STOP — self-check mandatory)

When the user uses any of the following keywords, treat it as a **task ↔ fix_plan transfer intent** and fire the self-check:

| Keyword | Meaning | Required action |
|---------|---------|-----------------|
| "move to fix_plan" / "to the checklist" | task → fix_plan transfer | Register on the checklist + mark the corresponding task `deleted` |
| "transfer" / "move" / "relocate" | medium change | Update both media (close source + register destination) |
| "defer" / "hold" / "next session" | external-wait or hold transition | Task `deleted` + register on the checklist `## Hold` (`fix.md` Step 4 medium separation) |
| "remove from tasks" / "clean tasks" | close the task medium | Task `deleted` (no silent autonomous decision — only on the user's explicit instruction) |

### Self-check (right after the user issues a transfer instruction)

1. **Check whether TaskList contains the same item**: call `TaskList` → identify the transfer-target task
2. **If identified, mark `deleted`** (the user's instruction grants explicit deletion authority)
3. **Register on the checklist + delete the task in the same turn**: do not defer one side to a later turn
4. **In the transfer report, state both medium results**: `"fix_plan registered + task <subject> deleted"` format

### Transfer-target scope confirmation (HARD STOP)

**If the user says "move X to Y" and X is ambiguous, immediately `AskUserQuestion`. Self-interpretation is forbidden.**

A transfer instruction is a combination of source medium (X) and destination medium (Y). The destination is usually unambiguous ("under the rule file", "fix_plan", "Issue"), but X is often ambiguous:

| X expression | Possible scopes |
|--------------|-----------------|
| "the diff part" | (a) changes this session added (b) the whole `git diff` output (c) staged diff (d) unstaged diff |
| "this content" / "this" | the text just mentioned / the visible paragraph / the whole file |
| "what I changed" | this session's changes / all uncommitted changes / a specific file's changes |
| "what I added" | this session's additions / the latest additions / every added line |
| "the related part" | direct relations / dependency-included / the same section |

| # | Don't | Do |
|---|-------|-----|
| 1 | User's view = "the whole `git diff` output" but you self-interpret as "only this session's additions" | What the user sees = `git diff` output as-is. The cleanup rule ("only files modified this session") only applies inside cleanup — not to user-facing transfer instructions |
| 2 | Interpret "the diff part" narrowly as "the latest additions" | "diff part" is an ambiguous keyword. Prior-session uncommitted + this session's additions could both be in scope. Ask first |
| 3 | Apply the cleanup Step 1 "filter to files modified this session" rule to a user transfer instruction | Cleanup-internal rules = cleanup's own scope. User transfer = the user's viewpoint. Two separate rule domains |
| 4 | Run with one interpretation and wait for the user to say "that's not what I meant" | Ask before executing. The rollback cost vastly exceeds the ask cost |

### Self-check (right after receiving a user transfer instruction)

1. **Is the scope of X clear?** Does the user's wording narrow X to a single candidate?
2. **Did an ambiguous keyword appear** ("diff", "this", "what I changed", "the related part")? Yes → 2+ candidates → `AskUserQuestion` is mandatory
3. **If not clear, ask before executing**: present options "`{X candidate 1}`", "`{X candidate 2}`", "`{X candidate 3}`"
4. **Confirm what the user sees**: show `git diff` / `git status` output directly to the user and ask "which part?"

## Reference

See `~/.claude/skills/cleanup/data/failed-attempts.md` "task / checklist two-way sync" and "transfer-target scope" entries for recurrence history.
