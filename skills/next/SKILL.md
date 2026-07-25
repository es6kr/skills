---
metadata:
  author: es6kr
  version: "0.1.1"
name: next
depends-on:
  - fix
  - hook
description: |
  Suggest next actions after completing any task. Auto-invocation via Stop hook (`resources/next-trigger.sh`) using JSON `decision:"block"` (registered in the settings.json Stop array). Fires when assistant response contains completion keywords (locale patterns in `data/*.regex`).
  stall-detect - detect stalled follow-up steps and invoke /fix [stall-detect.md], ask-gates - recording-skip / decision-deferral forced-ask / TaskList primary-source / current-work confirmation gates [ask-gates.md], suggestion-patterns - per-context "After X" next-action option templates [suggestion-patterns.md].
  Use when "next action", "what next", "stall", "stuck", "not progressing", "follow-up missing" is mentioned.
triggers:
  - event: Stop
    action: script
    script: resources/next-trigger.sh
---

# Next Action Suggester

## Topic Dispatch

**When this skill is invoked with a topic specifier (e.g., `/next suggestion-patterns` or `Skill("next", "suggestion-patterns")`), load and follow only the matching topic file. Do not echo the Topics table or summarize other topics in the response.** The Topics table below is an index — for a normal invocation, follow the Instructions and Read each topic when you reach the step that references it.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| stall-detect | Detect stalled follow-up steps and invoke /fix | [stall-detect.md](./stall-detect.md) |
| ask-gates | Step 0.3/0.4/0.5/0.7 ask gates: recording-skip, decision-deferral forced-ask, TaskList primary-source, current-work confirmation | [ask-gates.md](./ask-gates.md) |
| suggestion-patterns | Per-context "After X" next-action option templates | [suggestion-patterns.md](./suggestion-patterns.md) |

After task completion, use `AskUserQuestion` to suggest next steps and get user selection.

## When to use

Use `next` skill in the following scenarios:
- **Explicit invocation**: When the user explicitly calls `/next` or requests next actions ("what next", "next action").
  - **User Analysis Request Priority (HARD STOP)**: When `/next` is invoked alongside a specific request to analyze an issue or cause (e.g. `/next/fix analyze why next wasn't called`), perform the 5-Why analysis and present the investigation report **FIRST thing** before presenting any `AskUserQuestion` options.
- **Automatic trigger (in supported environments)**: In environments with Stop-hook support (`resources/next-trigger.sh`), auto-triggers on completion keywords.
- **Manual auto-invocation prohibition (HARD STOP)**: In environments without active Stop hooks (or after completing recording/fix tasks), do NOT manually append `next` options unless explicitly requested by the user or required by `ask-gates.md`. Specifically after `/fix` execution, do NOT automatically invoke `next` unless `/next` was explicitly requested in the user prompt.

After task completion, use `AskUserQuestion` to suggest next steps and get user selection.

## Instructions

### Step 0-0: Audit first (text), register only real work (HARD STOP — first action upon entering `/next`)

**Do NOT register the `next` skill's own internal procedure steps (audit / context-check / gates / option-composition) as tasks.** They are one-turn skill mechanics; registering them in the user-facing task list pollutes it with meta-tasks that create-and-complete within a single turn — which directly contradicts TaskCreate's own guidance ("skip for trivial / 1-turn work"). Task registration happens later, at **Step 3**, and only for the **actual follow-up work the user selects** (2+ selected → TaskCreate each; 1 selected → execute directly).

**What Step 0-0 still requires — a visible-text audit, NOT a task**: on an explicit `/next` call, before composing options, print the audit in visible text — why the auto-trigger missed (if it did) and a short session-state check. Emitting it as prose satisfies the requirement; do NOT substitute a `[x]`-marked task for the visible analysis, and do NOT skip it.

**Environment note**: In Antigravity (Gemini), the `task.md` artifact doubles as the progress-display medium, so a lightweight `task.md` checklist there is acceptable. In Claude Code, `TaskList`/`TaskCreate` is a user-work medium — keep internal procedure steps out of it (narrate them in text) and reserve `TaskCreate` for Step 3's selected work.

### Step 0-1: Antigravity Session Check & Context Usage Gate (MANDATORY in Antigravity)

Antigravity offers limited backend hooks, so environment detection and session context size evaluation must be performed **first thing** on entering the `next` skill — before composing anything.

1. **Detect Environment**: Check if running in Antigravity / Gemini environment.
2. **Evaluate Context Usage**: Check the size of `transcript_full.jsonl` in the conversation log directory. In Antigravity (Gemini), compute context usage empirically: `tokens = 30,000 (system prompt baseline) + (transcript_full_bytes / 4)` and `pct = (tokens / 1,000,000) * 100`. Never copy example placeholder numbers.
3. **Explicit Usage Display**: In the `AskUserQuestion` question text, **always explicitly state the estimated context usage percentage and token estimate** computed from `transcript_full.jsonl` with an explicit estimate disclaimer (e.g. `[Context Usage: Estimated ~XX.X% (~YYK tokens based on transcript size)]`). Never claim exact precision when using an estimated baseline.
4. **Threshold Gate**: If context usage >= 45% (or script emits CONTEXT_WARN), **set `(Recommended) Session cleanup and retrospective (/cleanup)` as the #1 option** to prevent context degradation.

### Step 0: Stall Detection (mandatory)

Before suggesting next actions, run the [stall-detect](./stall-detect.md) topic.

If stall detected → topic invokes `/fix`. If no stall → proceed to Step 0.3.

### Step 0.3–0.7: Ask gates (HARD STOP)

Before composing any next-action ask, pass four gates: **0.3** skip the ask entirely for recording/management topics (fix-plan, archive, todo, session rename); **0.4** if the completion report defers a decision to the user as prose ("let me know and I'll …", "whether to commit/PR is up to you"), that deferral is a decision axis — **force** an `AskUserQuestion` instead of ending on the text; **0.5** call `TaskList` as the primary source for option accuracy (never quote tasks from stale summary memory); **0.7** when the user's current activity is unclear (2+ in_progress tasks, ambiguous scope, handed-off manual work), ask "what are you working on / waiting on" first — separate "in progress" from "waiting on", and prefer free-text via Other over guess options.

**Read [ask-gates.md](./ask-gates.md) before composing options** — it holds the skip-target topic list, the TaskList primary-source Don't/Do, the current-work confirmation triggers, and the in-progress-vs-waiting-on examples. If Step 0.3 marks the work skip-target → report only, no ask; otherwise proceed to Step 1.


### Step 1: Identify completed task type

Identify the type of task just completed.

### Step 2: Use AskUserQuestion tool

**HARD STOP — Read [suggestion-patterns.md](./suggestion-patterns.md) BEFORE composing options.** suggestion-patterns.md holds per-context "After X" option templates that include diversity sources (pending tasks, open PRs, dependency follow-ups, session wrap-up, etc.). Skipping this Read = ad-hoc option list = high risk of missing candidate sources. Step 2 entry without suggestion-patterns.md Read = skill bypass (skill-usage.md "Multi-topic topic .md Read mandatory" violation).

#### Option diversity (HARD STOP)

**Fill all 4 option slots whenever possible.** AskUserQuestion supports max 4 options + auto "Other" = 5 candidates total. Composing only 2-3 options when 4+ candidates exist = under-recommendation. The user typically phrases this as "no more candidates?" or "any more suggestions?".

#### Candidate discovery sources (enumerate all before composing)

| Source | What to look for |
|--------|------------------|
| Visible TaskList | All pending/in_progress entries (call `TaskList` per Step 0.5) |
| Just-completed work | Direct follow-ups (commit / push / verify / test / publish) |
| Open PRs / issues | `gh pr list --search "involves:@me state:open"` / `gh issue list` (when relevant) |
| Recent commits awaiting CI | `gh run list --limit 5` for pending CI watch |
| fix_plan.md / checklist.md | Project-tracked next items (Ralph or general workspace) |
| Plane | Self-hosted project tracker, if this environment has one configured (check local infra docs for connection details) — check open issues/cycles when the project has one wired up |
| Session wrap-up | `/cleanup` — gated: explicit user wrap-up signal OR injected context-usage at/above the **per-model** threshold (Fable/Mythos 55%, Opus 50%, others 45% — see suggestion-patterns.md "Context-usage gate") |
| Other (free text) | Auto-provided by AskUserQuestion |

| # | Don't (forbidden) | Do (correct alternative) |
|---|-------------------|------------------------|
| 1 | Compose 2-3 options + end Step 2 | Enumerate sources above → fill 4 slots. Cap at 4 only if exhausted |
| 2 | "User can pick Other for anything else" rationale for fewer options | Other is for unexpected branches. Explicit options surface options the user might not think of |
| 3 | Skip Read of suggestion-patterns.md because "I know the patterns" | suggestion-patterns.md is updated with new "After X" templates regularly. Read every time |
| 4 | Treat just-completed work as the only source | Each candidate discovery source row is a separate enumeration. Cover all rows before stopping |

#### Premise verification for stale/prior-session candidates (HARD STOP)

**A candidate carried over from a pre-`/compact` summary or an old in-progress task is a *claim* ("X is still unresolved"), not a fact.** Composing it as an option restates that claim to the user as if current. Before presenting such a candidate, verify its premise is still true — check (a) fix_plan.md's `## Completed` section, (b) a RAG search if a store is registered, (c) Plane (see source row above) — for evidence it was already resolved between sessions. This mirrors `/fix`'s own "Recurrence pre-check" (RAG + grep before concluding a pattern is still active) — the same discipline applied to `next`'s own candidate composition, not just to `/fix`.

| # | Don't (forbidden) | Do (correct alternative) |
|---|-------------------|------------------------|
| 1 | Carry an "still open" item straight from a pre-compact summary into an option label | Re-check its current state (fix_plan Completed / RAG / Plane) before phrasing it as actionable |
| 2 | Treat "it was in_progress when the summary was written" as proof it still is | in_progress in a stale summary is a snapshot, not current truth — verify, don't assume |
| 3 | Skip verification because the investigation "sounds involved" | The verification itself (grep fix_plan, one RAG query, one Plane check) is cheaper than dispatching the user into a re-investigation of an already-solved problem |

#### Self-check (every time before calling AskUserQuestion)

1. Did I Read `suggestion-patterns.md` this turn? → If no, Read first
2. Did I enumerate all 8 candidate discovery sources? → If skipped any, revisit before composing
3. Do I have 4 options or did I stop at 2-3? → If <4 and candidates remain, add until 4 or exhausted
4. Are options diverse (different action types: progress task / external follow-up / wrap-up / verify)? → If all 3 are the same family, broaden
5. Does the completed work carry ≥2 discrete findings the user must disposition? → Per-finding questions first (see suggestion-patterns.md "After analysis / review producing multiple findings"), never one option bundling all findings
6. Does any candidate originate from a pre-compact summary or an old in-progress task rather than this turn's own discovery? → If yes, run the premise-verification check above before including it

```typescript
AskUserQuestion({
  questions: [{
    question: "What would you like to do next?",
    header: "Next Action",
    multiSelect: true,
    options: [
      { label: "Option 1", description: "Description" },
      { label: "Option 2", description: "Description" },
      { label: "Option 3", description: "Description" },
      { label: "Option 4", description: "Description" }
    ]
  }]
})
```

### Step 3: Register and execute selected action(s)

**If 2 or more actions are selected, register each via TaskCreate and execute sequentially.** If only 1 is selected, execute it directly. This is the **only** point where `/next` registers tasks — the skill's internal procedure steps (Step 0-0 audit, gates, option composition) are never registered; only the user-selected follow-up work is.

**Background dispatch does not end the turn (HARD STOP)**: delegating a selected action to a background agent (`Agent` spawn — background or mailbox-returning) hands control straight back — it is NOT a turn-ending event. Scan the remaining selected/pending tasks and drive the next independent one **in the same turn**; "execute sequentially" governs result-consumption order, not idle waiting. Idle-waiting for the agent is acceptable only when nothing else is drivable. Idling past ~5 minutes also expires the prompt cache (5-min TTL), so the completion wake-up re-reads full context uncached. When a forced idle would exceed that cache window, never arm one long silent watcher — use short cycles (`timeout` ≤ 240 s, end → notify → re-arm); multiSelect-unselected ask items count as deferred fill candidates for the idle window, not declined work. Enforced by the idle-wait Stop hook (`block-idle-wait-without-short-cycle.sh`). Same rule as wip/resume.md Step 3 (background-dispatch rows).

## Suggestion Patterns

Per-context option templates for "After X" completions (code change, feature, bug fix, config, commit, push, PR fix-commit re-review, PR creation reviewer matrix, skill/agent creation, file creation, refactoring, complex workflow, exploration, session wrap-up, PR consolidate).

**Read [suggestion-patterns.md](./suggestion-patterns.md)** for the matching context's option set before calling `AskUserQuestion`. Several patterns carry their own HARD STOP gates (re-review policy, Copilot availability, session wrap-up priority) — follow the pattern's gate, not a generic option list.

## Rules

1. **Always 2-4 options** - AskUserQuestion limitation
2. **Be specific** - "Run npm test" instead of just "Test"
3. **Context-based** - Adjust based on project/situation
4. **Use multiSelect** - When multiple actions can be done together
5. **Register then execute** - When 2+ options are selected, TaskCreate then run sequentially. If only 1, execute directly
6. **State conditions when proposing merge** - When including PR merge in options, the description must show condition state in the form `CI:✅ Review:✅ TestPlan:x/y`. Actual merge runs only via the `/github-flow merge` skill — direct `gh pr merge` is forbidden


