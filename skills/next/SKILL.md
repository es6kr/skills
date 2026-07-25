---
metadata:
  author: es6kr
  version: "0.1.1"
name: next
depends-on:
  - fix
  - hook-kit
description: |
  Suggest next actions after completing any task. Auto-invocation via Stop hook + UserPromptSubmit reactive backstop, owned by the `next-invocation-guard` plugin (local-only, ported from `resources/next-trigger.sh` + `resources/next-reactive-guard.sh`). Fires when assistant response contains completion keywords (locale patterns in `data/*.regex`).
  stall-detect - detect stalled follow-up steps and invoke /fix [stall-detect.md], ask-gates - recording-skip / decision-deferral forced-ask / TaskList primary-source / current-work confirmation gates [ask-gates.md], suggestion-patterns - per-context "After X" next-action option templates [suggestion-patterns.md].
  Use when "next action", "what next", "stall", "stuck", "not progressing", "follow-up missing" is mentioned.
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

## Dependency-gated behaviors (conditional on skill availability)

Two of this skill's behaviors are **mandatory only when their backing skill exists in the current environment**, and must be **skipped entirely when it does not**. Detect availability from the session's available-skills list (the environment's skill registry / available-skills reminder) — never assume a skill is present.

| Behavior | Backing skill | When AVAILABLE | When ABSENT |
|----------|---------------|----------------|-------------|
| Context-usage check + session-cleanup / wrap-up recommendation (context-usage gate, cleanup option, retrospective) | a session-cleanup skill | Apply the context-usage gate and offer the cleanup / wrap-up option per its threshold rules | **Skip** — do not measure context usage, do not offer any cleanup / wrap-up option |
| fix_plan.md / checklist.md change verification during candidate discovery | a fix_plan / checklist skill | **Mandatory** — read the workspace tracker for changed / pending items BEFORE composing options (elevated from optional source to required check) | Treat the tracker as an ordinary optional file; no mandatory read |

**Why**: a next-action ask must not reference or recommend a skill the environment lacks (dead recommendation); conversely, when a fix_plan / checklist skill IS present its tracker is the authoritative source of pending work, and skipping it silently drops real candidates.

| # | Don't | Do |
|---|-------|-----|
| 1 | Offer a cleanup / wrap-up / retrospective option (or run the context-usage gate) in an environment with no session-cleanup skill | Gate both on session-cleanup availability — absent ⇒ omit entirely |
| 2 | Treat fix_plan.md / checklist.md as merely one optional source when a fix_plan / checklist skill is available | Available ⇒ reading the tracker for changes is mandatory before composing options |
| 3 | Assume the backing skill exists because "it usually does" | Check the session's available-skills list each time before applying the gated behavior |

**Self-check (before composing any next-action ask)**:
1. Is a session-cleanup skill available? → No: skip the context-usage gate + omit cleanup / wrap-up options. Yes: apply them.
2. Is a fix_plan / checklist skill available? → Yes: reading the workspace tracker for changes is MANDATORY before composing options. No: skip.

## Instructions

### Step ordering in Antigravity (resolves the two "runs first" steps below — HARD STOP)

Step 0-0 and Step 0-1 below each describe themselves as running "first" — that is only a conflict in Antigravity, where both apply (in Claude Code, Step 0-1 doesn't apply at all, so Step 0-0 is simply first). **In Antigravity, run Step 0-1's environment detection + context-usage gate before Step 0-0's audit** — Step 0-0's own "Environment note" branches on whether the session is in Antigravity, so that fact must already be known before Step 0-0's text is composed. Step 0-0's "first action upon entering `/next`" phrasing means first among the *user-facing/task-registration* steps (i.e., before any `AskUserQuestion` or task work), not literally the first line of code executed — Step 0-1's lightweight environment probe precedes it.

### Step 0-0: Audit first (text), register only real work (HARD STOP)

**Do NOT register the `next` skill's own internal procedure steps (audit / context-check / gates / option-composition) as tasks.** They are one-turn skill mechanics; registering them in the user-facing task list pollutes it with meta-tasks that create-and-complete within a single turn — which directly contradicts TaskCreate's own guidance ("skip for trivial / 1-turn work"). Task registration happens later, at **Step 3**, and only for the **actual follow-up work the user selects** (2+ selected → TaskCreate each; 1 selected → execute directly).

**What Step 0-0 still requires — a visible-text audit, NOT a task**: on an explicit `/next` call, before composing options, print the audit in visible text — why the auto-trigger missed (if it did) and a short session-state check. Emitting it as prose satisfies the requirement; do NOT substitute a `[x]`-marked task for the visible analysis, and do NOT skip it.

**Exception — substantial discovery gets one lightweight tracking task (HARD STOP)**: the "no task registration" rule above assumes discovery resolves in a single quick call (e.g., one `TaskList` read). When candidate discovery itself grows beyond that — 3+ tool calls, or spanning 2+ distinct sources (`TaskList` + `fix_plan.md` + `gh pr`/`issue` search, etc.) — register **exactly one** lightweight tracking task for the whole discovery phase (e.g., "next: composing candidate options") before making the first discovery call, so the user retains visibility into in-flight work and can interrupt cleanly. Mark it completed the moment `AskUserQuestion` is composed. This does not reopen the meta-task-pollution problem: it is still one task for the entire phase, not one per source, and it is pruned immediately.

**Self-candidacy exclusion (HARD STOP)**: capture this tracking task's own ID at registration time. Since candidate discovery treats pending/in-progress `TaskList` entries as candidates, this task — while pending/in-progress during its own discovery phase — would otherwise appear as a user-selectable follow-up option. Exclude the captured ID from candidate enumeration explicitly, then mark it completed once `AskUserQuestion` is composed.

| # | Don't | Do |
|---|-------|-----|
| 1 | Run `TaskList` + a `fix_plan.md` read + multiple `gh` searches across several tool calls with zero task tracking, leaving the user unable to see what discovery is in flight | Register one lightweight tracking task before the first discovery call when 3+ tool calls or 2+ sources are anticipated; mark it completed once options are composed |
| 2 | Apply the "no task registration" rule uniformly regardless of how many tool calls discovery actually takes | Trivial discovery (single `TaskList` call) → no task, per the base rule above. Substantial discovery (3+ calls / 2+ sources) → one tracking task |

**Environment note**: In Antigravity (Gemini), the `task.md` artifact doubles as the progress-display medium, so a lightweight `task.md` checklist there is acceptable. In Claude Code, `TaskList`/`TaskCreate` is a user-work medium — keep internal procedure steps out of it (narrate them in text) and reserve `TaskCreate` for Step 3's selected work.

### Step 0-1: Antigravity Session Check & Context Usage Gate (MANDATORY in Antigravity — runs before Step 0-0 in that environment, see "Step ordering" above)

Antigravity offers limited backend hooks, so environment detection and session context size evaluation must be performed before Step 0-0's audit text is composed.

**Dependency precondition (HARD STOP)**: the context-usage measurement and cleanup recommendation in this step apply only when a session-cleanup skill is available in the environment (see "Dependency-gated behaviors"). If none is available, skip this gate entirely — do not measure context usage or set a cleanup option.

1. **Detect Environment**: Check if running in Antigravity / Gemini environment (`$env:ANTIGRAVITY_AGENT` or `transcript.jsonl` log path presence).
2. **Evaluate Context Usage (MANDATORY Physical Measurement HARD STOP)**: Check the size of `transcript.jsonl` in the conversation log directory via physical shell measurement (e.g. `powershell -Command "Get-Item <log-dir>\transcript.jsonl | Select-Object Length"`). In Antigravity (Gemini 1M capacity), compute context usage empirically: `tokens = 65,000 + ([math]::Round(transcript_bytes / 3.5))` and `pct = [math]::Round(($tokens / 1,000,000) * 100, 1)`. **Never invent, estimate, or hardcode example numbers from previous turns or memory.**
3. **Explicit Usage Display**: In the `AskUserQuestion` question text, **always explicitly state the physically measured context usage percentage and token count** (e.g. `[Context Usage: Physical Measured ~XX.X% (~YYK tokens based on ZZKB transcript.jsonl)]`). Never claim exact precision without physical file measurement.
4. **Antigravity Hook Manifest Verification (HARD STOP)**: In Antigravity environment, verify if `~/.agents/hooks.json` or active plugin hooks exist. If Antigravity hooks manifest is missing or inactive, audit the gap in prose before option generation.
5. **Threshold Gate**: If context usage >= 40% in Antigravity (or script emits CONTEXT_WARN), **set `(Recommended) Session cleanup and retrospective (/cleanup)` as the #1 option** to prevent context degradation.

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
| fix_plan.md / checklist.md | Project-tracked next items (Ralph or general workspace) — **mandatory read when a fix_plan / checklist skill is available** (see "Dependency-gated behaviors"); otherwise an ordinary optional source |
| Plane | Self-hosted project tracker, if this environment has one configured (check local infra docs for connection details) — check open issues/cycles when the project has one wired up |
| Session wrap-up | **Only when a session-cleanup skill is available** (see "Dependency-gated behaviors"). `/cleanup` — gated: explicit user wrap-up signal OR injected context-usage at/above the **per-model** threshold (Fable/Mythos 55%, Opus 50%, others 45% — see suggestion-patterns.md "Context-usage gate") |
| Other (free text) | Auto-provided by AskUserQuestion |

| # | Don't (forbidden) | Do (correct alternative) |
|---|-------------------|------------------------|
| 1 | Compose 2-3 options + end Step 2 | Enumerate sources above → fill 4 slots. Cap at 4 only if exhausted |
| 2 | "User can pick Other for anything else" rationale for fewer options | Other is for unexpected branches. Explicit options surface options the user might not think of |
| 3 | Skip Read of suggestion-patterns.md because "I know the patterns" | suggestion-patterns.md is updated with new "After X" templates regularly. Read every time |
| 4 | Treat just-completed work as the only source | Each candidate discovery source row is a separate enumeration. Cover all rows before stopping |

#### Premise verification for stale/prior-session candidates (HARD STOP)

**A candidate carried over from a pre-`/compact` summary or an old in-progress task is a *claim* ("X is still unresolved"), not a fact.** Composing it as an option restates that claim to the user as if current. Before presenting such a candidate, verify its premise is still true — check (a) fix_plan.md's `## Completed` section, (b) a RAG search if a store is registered, (c) Plane (see source row above), (d) when the fix_plan item's "How to apply" links a plan doc, that doc's own Progress Checklist — for evidence it was already resolved between sessions. This mirrors `/fix`'s own "Recurrence pre-check" (RAG + grep before concluding a pattern is still active) — the same discipline applied to `next`'s own candidate composition, not just to `/fix`.

| # | Don't (forbidden) | Do (correct alternative) |
|---|-------------------|------------------------|
| 1 | Carry an "still open" item straight from a pre-compact summary into an option label | Re-check its current state (fix_plan Completed / RAG / Plane) before phrasing it as actionable |
| 2 | Treat "it was in_progress when the summary was written" as proof it still is | in_progress in a stale summary is a snapshot, not current truth — verify, don't assume |
| 3 | Skip verification because the investigation "sounds involved" | The verification itself (grep fix_plan, one RAG query, one Plane check) is cheaper than dispatching the user into a re-investigation of an already-solved problem |
| 4 | Compose a decision ask from a fix_plan item's inline "Why"/summary text alone, when that item's "How to apply" points at a linked plan doc | Read the linked doc's own Progress Checklist / phase-completion state first — fix_plan's inline note can go stale relative to the doc's own tracked progress (e.g. a phase the fix_plan note calls undecided may already show complete in the plan doc) |

#### Self-check (every time before calling AskUserQuestion)

1. Did I Read `suggestion-patterns.md` this turn? → If no, Read first
2. Did I enumerate all 8 candidate discovery sources? → If skipped any, revisit before composing
3. Do I have 4 options or did I stop at 2-3? → If <4 and candidates remain, add until 4 or exhausted
4. Are options diverse (different action types: progress task / external follow-up / wrap-up / verify)? → If all 3 are the same family, broaden
5. Does the completed work carry ≥2 discrete findings the user must disposition? → Per-finding questions first (see suggestion-patterns.md "After analysis / review producing multiple findings"), never one option bundling all findings
6. Does any candidate originate from a pre-compact summary or an old in-progress task rather than this turn's own discovery? → If yes, run the premise-verification check above before including it
7. Does the candidate's fix_plan item reference a linked plan doc? → Read that doc's own Progress Checklist before composing the ask; do not rely solely on fix_plan's inline summary
8. Dependency gates (see "Dependency-gated behaviors"): is a session-cleanup skill available? (No → omit any cleanup / wrap-up option AND skip the context-usage gate). Is a fix_plan / checklist skill available? (Yes → reading the workspace tracker for changes is mandatory before composing)

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

**`TaskCreate`-unavailable fallback (HARD STOP — do not silently drop the selection)**: this is not a theoretical case here — options composed via [ask-gates.md](./ask-gates.md) Step 0.6 are, by that step's own trigger condition, sometimes composed in a turn where `TaskCreate`/`TaskList` is already known to be disconnected/unavailable. If `TaskCreate` fails or is unavailable when registering a 2+ selection, do NOT proceed as if registration succeeded and do NOT drop the unregistered items silently. Instead, register each unregistered selection as a `- [ ]` item in the active workspace's `fix_plan.md` (or `checklist.md`) `## Progress` section (or `## Hold` with `[BLOCKED] ... **trigger: Task tools reconnect**` if execution must also wait on the task tool, not just its tracking) — same fallback convention as `cleanup/run.md`'s "RAG store failure" TaskCreate-unavailable branch and `fix/SKILL.md`'s `claude-task` CLI fallback. State in the turn's report which items were written to `fix_plan.md` instead of `TaskCreate` and why.

**Background dispatch does not end the turn (HARD STOP)**: delegating a selected action to a background agent (`Agent` spawn — background or mailbox-returning) hands control straight back — it is NOT a turn-ending event. Scan the remaining selected/pending tasks and drive the next independent one **in the same turn**; "execute sequentially" governs result-consumption order, not idle waiting. Idle-waiting for the agent is acceptable only when nothing else is drivable. Idling past ~5 minutes also expires the prompt cache (5-min TTL), so the completion wake-up re-reads full context uncached. When a forced idle would exceed that cache window, never arm one long silent watcher — use short cycles (`timeout` ≤ 240 s, end → notify → re-arm); multiSelect-unselected ask items count as deferred fill candidates for the idle window, not declined work. Enforced by the idle-wait Stop hook (`block-idle-wait-without-short-cycle.sh`). Same rule as wip/resume.md Step 3 (background-dispatch rows).

**Decide foreground vs background BEFORE spawning, not after (HARD STOP)** — → claudify skill background-polling topic: a wakeup covers hang recovery, it does not license idling past the 5-minute prompt-cache TTL. Before every `Agent` spawn, check whether other selected/pending work this turn could run while the agent works.

| # | Don't (forbidden) | Do (correct alternative) |
|---|-------------------|------------------------|
| 1 | Background a single-item follow-up (e.g. "run Internal Review on this PR, then post the Summary") with nothing else queued, then idle-wait for its own notification | Spawn it in the foreground (`run_in_background: false`, or the Agent tool's default synchronous behavior) — a lone item is a foreground case |
| 2 | Background an agent because other selected/pending work exists this turn, then not actually drive that other work while it runs | Background it AND drive the other work in the same turn — backgrounding only pays off when something fills the wait |
| 3 | Assume the idle wait is "free" because usage-overage state isn't known yet | Always plan for the shorter 5-minute cache window, not the overage window |

#### Self-check (before every `Agent` spawn)

1. Is there other selected/pending work this turn could drive while the agent runs? → No → foreground it (`run_in_background: false`)
2. Yes → background it, and actually drive that other work in the same turn — do not idle-wait alone

(See failed-attempts.md "background-agent-without-parallel-work" for recurrence history.)

**Decide foreground vs background BEFORE spawning, not after (HARD STOP)**: idle-waiting on a lone background agent buys zero parallelism and only exposes the turn to prompt-cache-TTL-expiry cost (the 5-minute window — usage-overage state cannot be known in advance, so always plan for the shorter window) once nothing else fills the wait. Before every `Agent` spawn, check: is there other selected/pending work this turn could drive while the agent runs? If yes, background it and drive that other work. If no, spawn it in the foreground (`run_in_background: false`, or the Agent tool's default synchronous behavior) instead of backgrounding it and then idle-waiting alone for its own notification. A single-item follow-up (e.g. "run Internal Review on this PR, then post the Summary") with nothing else queued is a foreground case, not a background-and-wait case. (See failed-attempts.md "background-agent-without-parallel-work".)

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


