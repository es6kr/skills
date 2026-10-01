# Step 5 / 5.5: wip Handoff and Self-Task Cleanup

Steps 5 and 5.5 of the `run` pipeline. Entry point: [run.md](./run.md).

## Step 5: Register Next-Session Work as wip → Delegate to `Skill("wip")` (multi-select task)

**After completing the Step 4.5 comprehensive report, delegate via a `Skill("wip")` call.** Since cleanup is invoked at session end, **rather than executing 1 next action immediately, register N candidates as wip tasks so that after compact/rewind the next session can resume**.

The wip skill handles registering N tasks via multi-select AskUserQuestion + TaskCreate. On the next session's start, `/wip` or "task cleanup + remaining work" trigger enables automatic resume.

### cleanup → wip vs cleanup → next Difference (HARD STOP)

| Aspect | next (follow-up recommendation during work) | **wip (state preservation at cleanup end)** |
|------|-------------------------|--------------------------------|
| Selection model | single-select, execute 1 immediately | **multi-select, register N tasks** |
| Session signal | Session continues (more work to do) | **Session ends (resume in next session)** |
| Appropriate call timing | Natural follow-up right after finishing work | **State preservation right before cleanup ends** |
| Unselected item handling | Lost (only 1 selected) | **Selected = registered, unselected = explicitly excluded** |

If cleanup calls next, it becomes "select 1 → execute immediately → session continues" → weakens the session-end signal. cleanup's essence ("state preservation for compact/rewind readiness") and next's essence ("natural follow-up after work") have different responsibilities.

### wip Delegation Call Pattern

```text
Skill("wip") with args:
  "cleanup Step 5 end point — register N task candidates for next-session resume via multi-select.

   This session's (UUID `<uuid>`) artifacts:
   - <key deliverables>

   Next-session work candidates (multi-select):
   1. <task 1> — <description>
   2. <task 2> — <description>
   ...
   "
```

The wip skill performs multi-select AskUserQuestion → registers the N selected via TaskCreate → preserves state so the next session can resume via `/wip`.

**⚠️ Absolutely forbidden** (HARD STOP):
- Calling `Skill("next")` (single-select, execute 1 immediately — violates cleanup's essence)
- Outputting text like "You can proceed in the next session" and stopping there — calling wip is mandatory
- **Skipping the Step 4.5 comprehensive report and calling wip directly** — violates the Step 4.5 obligation
- Only enumerating next-work candidates as chat text (not registered as wip tasks) — impossible to resume in the next session

### No Re-recommending Existing TaskList Items + Routing Ralph-autonomous Items to /fix-plan (HARD STOP)

**A task already registered in TaskList is itself a rewind-preservation medium — do not re-recommend/re-register it via wip.** In cleanup Step 0, completed tasks are auto-cleaned (deleted) and incomplete tasks remain as-is, visible as-is in the next session. Step 5 wip's re-registration target is **only candidates newly discovered this session that aren't yet in TaskList**. Re-listing existing items as wip options causes duplicate registration + noise.

Among remaining incomplete tasks, ones that the **Ralph autonomous loop can execute autonomously** (not gated on a user decision/external state) are routed to `Skill("fix-plan")` for fix_plan.md so Ralph can pick them up. User-gated ones (waiting for merge approval / external PR state / user branch, etc.) stay in TaskList.

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Re-list/re-recommend an existing TaskList item (#N pending) as a wip AskUserQuestion option | Existing items are already preserved — exclude from re-recommendation. wip targets are **only new candidates not in TaskList** |
| 2 | Re-register a completed task as "to do next too" | Completed tasks are deleted in Step 0. Only incomplete ones remain |
| 3 | Leave a Ralph-autonomously-executable remaining task only in TaskList and abandon it | Route via `Skill("fix-plan")` to fix_plan.md → Ralph autonomous pickup |
| 4 | Route a user-gated task (waiting for merge/approval/external state) to fix_plan | User-gated tasks stay in TaskList — Ralph cannot proceed autonomously |

**Self-check (immediately before the Step 5 wip call every time)**:
1. Confirm currently registered tasks via `TaskList` — these are already rewind-preserved (not re-recommendation targets)
2. Are there new candidates discovered this session that are **not** in TaskList? → If yes, only those are wip targets
3. Is each remaining incomplete task Ralph-autonomous (not externally gated)? → If yes, route via `Skill("fix-plan")`; if No (user-gated), keep in TaskList
4. If new candidates = 0 and routing targets = 0, skip the wip call

**Skip condition**: skip the wip call if there are 0 new candidates not in TaskList and 0 fix_plan routing targets and 0 remaining BLOCKED items. However, cleanup itself is still reported as normally complete.

**Ralph mode**: record next-session work candidates to `.ralph/improvements.md` with the `[NEEDS_REVIEW]` tag.

---

## Step 5.5: Self-Task Cleanup (status-based prune — MANDATORY, HARD STOP)

**After the Step 5 wip call completes, prune this cleanup run's own tracking tasks before declaring cleanup done.** Step 0 (top of this file) only prunes tasks that were already `completed` *before* this cleanup run started — by construction it cannot see the Step 0-4.5+5 tracking tasks that line 40's "Task pre-registration" mechanism creates, since those only reach `completed` status *during* this very run, after Step 0 already executed. Without this step, cleanup's own step-tracking tasks accumulate as `completed`-but-undeleted noise in every session that uses Task tools.

This mirrors `fix/step4-wrapup.md` Measure 3 (status-based, not prefix-based prune) — the same gap, in the sibling skill that also pre-registers its own step-tracking tasks.

### Prune target matrix

| Task kind | Status | Cleanup target? |
|-----------|--------|-----------------|
| **This cleanup run's own Step 0-4.5+5 tracking tasks** (from line 40 pre-registration) | completed | ✅ mark deleted |
| **This cleanup run's own tracking tasks** | in_progress / pending | ❌ should not happen once cleanup finishes — investigate before pruning |
| **Other tasks created and completed during this cleanup run** (e.g. a fix-* chain nested inside cleanup) | completed | ✅ mark deleted |
| **Tasks that predate this cleanup run** | any status | out of scope — already handled by Step 0, or intentionally left pending/BLOCKED |

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Assume Step 0's prune already covers this because "TaskList cleanup" already ran once this session | Step 0 runs at entry, before this run's own tracking tasks exist. Re-check `TaskList` at the very end, after Step 5 |
| 2 | Leave completed Step 0-4.5+5 tracking tasks in TaskList "for history" | History lives in the Step 4.5 comprehensive report + fix_plan.md + git log. TaskList completed-but-undeleted entries are stale noise |
| 3 | Prune only tasks literally prefixed with a cleanup-step label and miss other same-run completions | Criterion is status (completed) + creation time (this cleanup run), not a naming prefix |
| 4 | Delete pending/in_progress tasks along with completed ones | Only `completed` tasks are pruned. `pending`/`in_progress` remaining work stays |

### Self-check (every time, immediately before declaring cleanup complete)

1. Call `TaskList` one more time — this is a **second** call, after Step 5, not a re-read of Step 0's earlier result
2. Identify this cleanup run's own pre-registered tracking tasks (Step 0/1/2/3/4/4.5+5) by their creation point in this run
3. Any of them still `completed`? → `TaskUpdate(status: "deleted")` for each
4. Any other task created and completed during this run (not part of the pre-registered set)? → same prune
5. State the prune count in the completion report: `**Self-task cleanup**: N tracking tasks deleted`

**Skip condition**: skip only if `TaskCreate`/`TaskList` were disconnected for the entire run (already stated per line 40's fallback) — do not skip because "the count looks small."

**Ralph-mode carve-out (HARD STOP — do not conflate "no autonomous decision-work" with "leave your own tracking task open")**: the Ralph-mode short-circuit below skips the *decision-making* parts of Steps 1-5 (commit strategy, retrospect judgment calls, RAG-store choices), not this run's own bookkeeping. Before emitting the "cleanup complete" text in Ralph mode too, call `TaskList` and `TaskUpdate(status: "completed")` on this run's own pre-registered tracking task(s) from line 40 — closing your own procedural bookkeeping is not a "direct modification" in the sense Ralph mode restricts (rules/memory/hooks, skill/agent creation, delegated execution). A declared-complete report with the run's own tracking task still `pending`/`in_progress` is a self-contradiction the reader can immediately catch, and is exactly the failure the `check-self-task-open-at-wrapup.js` Stop hook now flags (see failed-attempts.md `self-task-prune-gap-at-skill-wrapup`, 3rd occurrence).

---

---

**⚠️ In Ralph mode, end here — declare cleanup complete after recording to improvements.md AND after the Ralph-mode carve-out above**

In Ralph mode (`.ralph/` exists + `RALPH_LOOP=1`), Phase 2/3 cannot be entered since they depend on AskUserQuestion. Once the steps up to this point finish:
1. Confirm that all findings collected in Steps 0-5 have been recorded to `.ralph/improvements.md` with the `[NEEDS_REVIEW]` tag
2. Once recording is complete, declare **cleanup complete** and end. Do not enter Phase 2
3. If there are unrecorded items, record them, then end

---

# Phase 2: Batch Confirmation (AskUserQuestion `questions` array)

Once collection for all steps finishes, do a **single AskUserQuestion** (`questions` array) to batch-confirm only the steps that have findings.

**If there are 0 findings, skip Phase 2 and 3** → output "No findings. Cleanup complete."

### Composing the questions array

Create a **separate question** for each step that has findings and add it to the array (maximum 4).

**Key principles**:
- **Each step is an independent question** — do not combine Weekly Report and next-action recommendation into one
- **LLM Wiki Recommendation**: If Step 3-A LLM Wiki Scope Check identified findings/candidates, **must include an independent question or option under Persist** proposing raw knowledge ingest dispatch (e.g. `raw-ingest` skill if available) for the discovered candidates.
- **Options must contain concrete content** — no abstract labels. Put the actual work title+reason in the label/description
- **Skip option**: for a multi-question set, if an individual question has 3 or fewer options, adding `{ label: "Skip", description: "Skip this item" }` is allowed

### Step Grouping (when questions exceeds 4)

| Group | Included steps | header |
|------|----------|--------|
| Improve | Retrospect + Automation Review + Pattern Detect | "Improve" |
| Persist | Knowledge storage (documentation+infra+memory+LLM Wiki ingest) | "Persist" |
| Work | Weekly Report | "Work" |
| Next | Next-action recommendation | "Next" |

---

# Phase 3: Execute Selected Items

**Immediately execute** the items the user selected, in the original step order. Do not stop after just reporting.

> **⚠️ Forbidden**: outputting only a summary like "User selection result: ..." and ending.

**Execution procedure**: register selected items via TodoWrite → sequentially in_progress → execute → completed

| Step | Execution content |
|------|----------|
| Retrospect | Create a feedback memory file + add to the MEMORY.md index + record to failed-attempts.md |
| Automation Review | Fix the hook script or call `/skill-kit upgrade` |
| Pattern Detect | `/skill-kit route` → chaining (upgrade/writer) |
| Knowledge | Write/edit documentation + add missing items to CLAUDE.md + store to Serena/Claude Code memory + **dispatch raw knowledge ingest skill (if available) for LLM Wiki candidates** |
| Weekly | Call `/weekly-report generate` |
| Next | Register the selected recommendation via TodoWrite and execute immediately |

---
