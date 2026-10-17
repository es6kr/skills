# Step 4-C & Step 4.5: wip Handoff and Self-Task Cleanup

Steps 4-C and 4.5 of the `run` pipeline. Entry point: [run.md](./run.md).

## Step 4-C: Register Next-Session Work as wip → Delegate to `Skill("backlog", "record", mode="next-session")`

**After completing the Step 4-B comprehensive report, delegate via a `Skill("backlog", "record", mode="next-session")` call.** Since cleanup is invoked at session end, **rather than executing 1 next action immediately, register N candidates as wip tasks so that after compact/rewind the next session can resume**.

The backlog record topic handles registering N tasks via multi-select AskUserQuestion + TaskCreate by delegating internally to `Skill("wip")`. On the next session's start, `/wip` or "task cleanup + remaining work" trigger enables automatic resume.

Full procedure and rules: **[record.md](../backlog/record.md)**.
- cleanup → wip vs cleanup → next Difference (HARD STOP)
- wip Delegation Call Pattern
- No Re-recommending Existing TaskList Items + Routing Ralph-autonomous Items to /fix-plan (HARD STOP)
- Don't / Do table
- Self-check (immediately before the Step 4-C wip call every time)
- Skip condition
- Ralph mode

---

## Step 4.5: Self-Task Cleanup (status-based prune — MANDATORY, HARD STOP)

**After the Step 4-C wip call completes, prune this cleanup run's own tracking tasks before declaring cleanup done.** Step 0 (top of this file) only prunes tasks that were already `completed` *before* this cleanup run started — by construction it cannot see the Step 0-4 tracking tasks that line 40's "Task pre-registration" mechanism creates, since those only reach `completed` status *during* this very run, after Step 0 already executed. Without this step, cleanup's own step-tracking tasks accumulate as `completed`-but-undeleted noise in every session that uses Task tools.

This mirrors `fix/step4-wrapup.md` Measure 3 (status-based, not prefix-based prune) — the same gap, in the sibling skill that also pre-registers its own step-tracking tasks.

### Prune target matrix

| Task kind | Status | Cleanup target? |
|-----------|--------|-----------------|
| **This cleanup run's own Step 0-4 tracking tasks** (from line 40 pre-registration) | completed | ✅ mark deleted |
| **This cleanup run's own tracking tasks** | in_progress / pending | ❌ should not happen once cleanup finishes — investigate before pruning |
| **Other tasks created and completed during this cleanup run** (e.g. a fix-* chain nested inside cleanup) | completed | ✅ mark deleted |
| **Tasks that predate this cleanup run** | any status | out of scope — already handled by Step 0, or intentionally left pending/BLOCKED |

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Assume Step 0's prune already covers this because "TaskList cleanup" already ran once this session | Step 0 runs at entry, before this run's own tracking tasks exist. Re-check `TaskList` at the very end, after Step 4-C |
| 2 | Leave completed Step 0-4 tracking tasks in TaskList "for history" | History lives in the Step 4-B comprehensive report + fix_plan.md + git log. TaskList completed-but-undeleted entries are stale noise |
| 3 | Prune only tasks literally prefixed with a cleanup-step label and miss other same-run completions | Criterion is status (completed) + creation time (this cleanup run), not a naming prefix |
| 4 | Delete pending/in_progress tasks along with completed ones | Only `completed` tasks are pruned. `pending`/`in_progress` remaining work stays |

### Self-check (every time, immediately before declaring cleanup complete)

1. Call `TaskList` one more time — this is a **second** call, after Step 4-C, not a re-read of Step 0's earlier result
2. Identify this cleanup run's own pre-registered tracking tasks (Step 0/1/2/3/4) by their creation point in this run
3. Any of them still `completed`? → `TaskUpdate(status: "deleted")` for each
4. Any other task created and completed during this run (not part of the pre-registered set)? → same prune
5. State the prune count in the completion report: `**Self-task cleanup**: N tracking tasks deleted`

**Skip condition**: skip only if `TaskCreate`/`TaskList` were disconnected for the entire run (already stated per line 40's fallback) — do not skip because "the count looks small."

**Ralph-mode carve-out (HARD STOP — do not conflate "no autonomous decision-work" with "leave your own tracking task open")**: the Ralph-mode short-circuit below skips the *decision-making* parts of Steps 1-4 (commit strategy, retrospect judgment calls, RAG-store choices), not this run's own bookkeeping. Before emitting the "cleanup complete" text in Ralph mode too, call `TaskList` and `TaskUpdate(status: "completed")` on this run's own pre-registered tracking task(s) from line 40 — closing your own procedural bookkeeping is not a "direct modification" in the sense Ralph mode restricts (rules/memory/hooks, skill/agent creation, delegated execution). A declared-complete report with the run's own tracking task still `pending`/`in_progress` is a self-contradiction the reader can immediately catch, and is exactly the failure the `check-self-task-open-at-wrapup.js` Stop hook now flags (see failed-attempts.md `self-task-prune-gap-at-skill-wrapup`, 3rd occurrence).

---

---

**⚠️ In Ralph mode, end here — declare cleanup complete after recording to improvements.md AND after the Ralph-mode carve-out above**

In Ralph mode (`.ralph/` exists + `RALPH_LOOP=1`), Phase 2/3 cannot be entered since they depend on AskUserQuestion. Once the steps up to this point finish:
1. Confirm that all findings collected in Steps 0-4.5 have been recorded to `.ralph/improvements.md` with the `[NEEDS_REVIEW]` tag
2. Once recording is complete, declare **cleanup complete** and end. Do not enter Phase 2
3. If there are unrecorded items, record them, then end

---

# Phase 2: Batch Confirmation (AskUserQuestion `questions` array)

Once collection for all steps finishes, do a **single AskUserQuestion** (`questions` array) to batch-confirm only the steps that have findings.

**If there are 0 findings, skip Phase 2 and 3** → output "No findings. Cleanup complete."

### Composing the questions array

Create a **separate question** for each step that has findings and add it to the array (maximum 4).

**Key principles**:
- **Each step is an independent question** — do not combine distinct steps into one
- **LLM Wiki Recommendation**: If Step 3-A LLM Wiki Scope Check identified findings/candidates, **must include an independent question or option under Persist** proposing raw knowledge ingest dispatch (e.g. `raw-ingest` skill if available) for the discovered candidates.
- **Options must contain concrete content** — no abstract labels. Put the actual work title+reason in the label/description
- **Skip option**: for a multi-question set, if an individual question has 3 or fewer options, adding `{ label: "Skip", description: "Skip this item" }` is allowed

### Step Grouping (when questions exceeds 4)

| Group | Included steps | header |
|------|----------|--------|
| Improve | Retrospect + Automation Review + Pattern Detect | "Improve" |
| Persist | Knowledge storage (documentation+infra+memory+LLM Wiki ingest) | "Persist" |
| Next | Next-action recommendation | "Next" |

---

# Phase 3: Execute Selected Items

Immediately execute the items the user selected, in the original step order. Do not stop after just reporting.

> **⚠️ Forbidden**: outputting only a summary like "User selection result: ..." and ending.

**Execution procedure**: register selected items via TodoWrite → sequentially in_progress → execute → completed

| Step | Execution content |
|------|----------|
| Retrospect | Create a feedback memory file + add to the MEMORY.md index + record to failed-attempts.md |
| Automation Review | Fix the hook script or call `/skill-kit upgrade` |
| Pattern Detect | `/skill-kit route` → chaining (upgrade/writer) |
| Knowledge | Write/edit documentation + add missing items to CLAUDE.md + store to Serena/Claude Code memory + **dispatch raw knowledge ingest skill (if available) for LLM Wiki candidates** |
| Next | Register the selected recommendation via TodoWrite and execute immediately |

---
