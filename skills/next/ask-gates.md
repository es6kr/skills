# Ask Gates — recording-skip / TaskList primary-source / current-work confirmation

## Step 0.3: Recording/management topic ask-skip gate (HARD STOP)

**If the just-completed work is a "simple recording/management topic", skip the next-action ask entirely.** Stop hook auto-triggers next skill on every task completion, but recording-topic completion is not a user-decision branch point.

### Default = ask. Skip = exception (closed list — HARD STOP)

**The skip-target table below is a CLOSED list.** Any just-completed work that does not exactly match a row in the table = **ask is required** (proceed to Step 0.4+). Do not extrapolate skip justification to "similar" cases such as plan/research authoring, user-awaiting-reply states, or "prior turn already asked" rationales.

| # | Don't (skip extrapolation — forbidden) | Do (closed-list discipline) |
|---|------|------|
| 1 | "Plan/research/analysis authoring just completed → similar to recording → skip" | Plan/research/analysis is **not** recording (it creates new decision axes: proceed / refine / hold). Ask required |
| 2 | "User is awaiting reply on a prior chat-text question → skip the next-action ask" | Awaiting-reply on one axis ≠ no decision on the next-action axis. trade-off ask and next-action ask are **separate axes** — both required |
| 3 | "Re-asking would revert the user's prior Other selection → skip" | Prior ask = topic-decision axis (e.g., PR tag). Next-action ask = progress-decision axis (proceed / refine / hold). Different axes, no revert |
| 4 | "Stop hook re-triggered next, but I already asked once this turn → skip" | The just-completed work is the trigger condition, not "have I asked in this turn". If the work changed (new artifact, new state), ask again |
| 5 | "TaskList has just one item and it depends on user → no decision axis → skip" | Even single-item TaskList has progress / refine / hold axes for the just-produced artifact. Ask the artifact-level decision |
| 6 | "User said 'stop working this session' → skip ALL asks including the wrap-up/cleanup ask" | "Stop working" forbids proposing *new task work*, not asking about the wrap-up mechanism itself. Treat it as an explicit wrap-up-intent signal (Context-usage gate condition 1 in suggestion-patterns.md) — if context-usage also reads at/above the session model's threshold (condition 2 — Fable/Mythos 55%, Opus 50%, others 45%), the cleanup ask is *more* warranted, not skipped. Present the ask; do not silently auto-run cleanup either — the user still decides |
| 7 | "The invocation string contains `fix-plan` → matches the skip row" (skill-name surface match) | Match by the run's **actual step composition**, not the skill name: any run that executed priority / triage / model-triage — including every role-scoped `--deep` / `--impl` / role-mapped no-arg run — is NOT a skip target. Only pure add / move / check bookkeeping skips |

### Skip-target topic list

| Topic / skill | Identification signal | Skip ask? |
|---------------|----------------------|-----------|
| `/ralph fix-plan` **add / move / check only** | User message: `fix-plan`, `fix_plan`, "record in checklist" | ✅ Skip |
| `/ralph fix-plan` **priority / triage / sync** | User message: `fix-plan priority`, "triage", "prioritize blocked" | ❌ **NOT skip** — triage surfaces immediate-action candidates (top-N selfable). Route the start decision to `Skill("wip")`, not skip and not `next` single-select (see Step 0.4 "Surfacing/triage → wip delegation") |
| `/fix-plan` **role-scoped default run** (`--deep` / `--impl` / `--role=*`, or a no-arg run resolved via a workspace role mapping) | Run report shows sync + priority executed (deep adds model-triage) | ❌ **NOT skip** — role runs include triage by definition. After the report, surface **role-fitting continuable candidates** in the same turn: `deep` → design/audit-fit work, `impl` → `selfable` implementation candidates, `pm` → bookkeeping remainder. Multi-item → route via `Skill("wip")`; single next-step → `next` ask |
| `/archive`, `/safe-delete` | User message: `archive`, `delete`, `move to .bak` | ✅ Skip |
| `/todo`, `/todowrite` add/move | User message: `todo add`, `task register` | ✅ Skip |
| `/wip` start/register | User message: `wip`, "track progress" | ⚠️ Conditional (multi-step task → ask allowed) |
| Intermediate modification with remaining tasks | `task.md` / `TaskList` has active `pending` or `in_progress` items | ✅ **Skip ask** — proceed directly to next remaining task in same turn |
| Code modification / implementation | Edit/Write performed (all tasks completed) | ❌ Ask required (verification/commit/push branch) |
| Commit / push | git commit/push performed | ❌ Ask required (next-step branch) |
| Skill/rule modification | Skill/rule file Edit | ❌ Ask required (test/commit branch) |

### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | Stop hook triggered next → unconditionally compose AskUserQuestion options | First check skip-target topic list. Skip = report only |
| 2 | "fix-plan completed, should I proceed with code-workflow next?" autonomous proposal | fix-plan = recording topic. Wait for explicit user follow-up instruction |
| 3 | "archive completed, should I delete the rest too?" autonomous proposal | archive = single-action. Report and end |
| 4 | "User can pick Other or end-session option, so it's safe to ask" rationalization | Ask itself implies a user decision is needed. No decision needed = no ask |

### Self-check (every time before composing options)

1. What was the just-completed work? -- Identify by user message + action history
2. Does it **exactly match a row** in the skip-target topic list above? -- The list is CLOSED. "Similar" / "in spirit" matches don't count. If no exact match → ask required (proceed to Step 0.4+)
3. Did the user explicitly express follow-up intent alongside the recording-topic invocation (e.g., "record then proceed with X")? -- If no, end with report only
4. Does the just-completed work include code change / commit / push / external publish / plan-or-research authoring? -- If yes, ask is required (decision branch exists)
5. Am I about to skip on grounds of "user awaiting reply" / "prior turn already asked" / "re-ask reverts prior selection"? -- All three are extrapolation traps (see Don't/Do #2–4 above). Ask required
6. Even if skip is confirmed (step 1–5 all pass) — **did I run the context-usage gate (step 4 of "How to skip")? (HARD STOP)**: if live context-usage ≥ model threshold OR user signaled wrap-up intent, the cleanup/retrospective ask is **required** even for a confirmed skip target. Skip ≠ context-gate exemption.

### Antigravity Environment Context Usage Reporting Gate & Cleanup Selection Execution (HARD STOP)

When running in Antigravity (Gemini), backend hooks are limited. You MUST:
1. **Explicitly state current context usage % & token estimate** in the `AskUserQuestion` question text header (e.g. `[Context Usage: XX% (~YYK tokens)]`). In Antigravity (Gemini), token count MUST be physically computed from transcript JSONL bytes (`tokens = transcript_file_bytes / 3.5`), NOT arbitrarily guessed or fabricated. Context usage % MUST be calculated based on the **1M token capacity (1,000,000 tokens)**: `pct = (tokens / 1,000,000) * 100`. (e.g., ~140KB transcript = ~40,000 tokens = ~4%).
2. **Mandatory `/cleanup` Recommendation Gate**: If context usage >= 40% (>=400K tokens in Antigravity or transcript log size indicates high usage), set `(Recommended) Session cleanup and retrospective (/cleanup)` as option #1 in `AskUserQuestion`. **HARD STOP**: If context usage is strictly less than 40% (<400K tokens), attaching the `(Recommended)` tag to `/cleanup` is STRICTLY FORBIDDEN; tag the primary domain/technical follow-up action as `(Recommended)` instead.
3. **Mandatory Session Cleanup Execution (HARD STOP)**: When the user selects any option whose label denotes session cleanup (`/cleanup`, or its session-language equivalent), the agent MUST NOT conclude the turn with a plain text wrap-up message alone. The agent MUST immediately register cleanup tasks in `task.md` / `TaskList` and execute the `cleanup` skill protocol (via `Skill("cleanup")` or environment-appropriate autoloader such as `view_file` with `IsSkillFile: true` under Antigravity).

| # | Don't | Do |
|---|---|---|
| 1 | Omit context usage % or token count in `AskUserQuestion` question text when running in Antigravity | Include `[Context Usage: XX% (~YYK tokens)]` in the question text |
| 2 | Recommend forward work options without `/cleanup` when context usage >= 40% | Set `(Recommended) Session cleanup and retrospective (/cleanup)` as option #1 when usage >= 40% |
| 3 | Attach `(Recommended)` tag to `/cleanup` when context usage is below 40% | Attach `(Recommended)` to `/cleanup` ONLY when usage >= 40%; when < 40%, attach `(Recommended)` to the primary technical follow-up task |
| 4 | Conclude with text greeting when user selects a session-cleanup option (`/cleanup` or its session-language equivalent) | Immediately register cleanup tasks and execute `cleanup` skill protocol (`Skill("cleanup")` or `view_file IsSkillFile:true`) |

### How to skip (procedure)

1. Determine skip target via Step 0.3 self-check
2. **Run Step 0.4 first — skip never bypasses it (HARD STOP)**: even a confirmed skip-target must pass through Step 0.4's decision-deferral scan. If the report defers a decision as prose (e.g. "start decision is yours" / "the start decision awaits your instruction"), Step 0.4 **overrides** the skip and forces the ask. Only after Step 0.4 finds no deferred decision does the skip stand.
3. If skip-target **and** Step 0.4 clean, do not proceed to Step 0.5/0.7 (TaskList check, user-work confirmation)
4. **Run context-usage gate (HARD STOP — skip does NOT exempt this check)**: even when the skip is confirmed (recording topic + Step 0.4 clean), check the live context-usage signal from `suggestion-patterns.md` "Context-usage gate". If the live reading is at/above the model's threshold (Fable/Mythos 55%, Opus 50%, others 45%) **or** the user has already signaled wrap-up intent — the cleanup/retrospective ask becomes **required** per the positive-trigger rule. A skip-target completion that crosses the gate forces a single-question AskUserQuestion offering the cleanup/retrospective option (not the full next-action ask — just the cleanup decision). Without this check, skip silently discards the cleanup option on high-context sessions. **Post-compact floor (HARD STOP)**: when this turn sits immediately after a compact/summarization boundary — an explicit compact command, an `isCompactSummary` transcript entry, or a session that opened with a "continued from a previous conversation that ran out of context" summary — treat usage as **under 20% until you have re-measured it**, and do not cite any figure carried over from before that boundary. The measurement lags a compact by at least one assistant turn, so the number available to you at that moment still describes the pre-compact session and **overstates** the real one. Re-measure via the script named in `suggestion-patterns.md` "Live-check fallback" before letting this gate fire; if you cannot measure, the gate is NOT met.
5. Report completion as plain text only (no AskUserQuestion call) — **only when step 4's context-usage gate is also clear**
6. If Stop hook re-triggers next skill, re-evaluate the same skip judgment

### Case history

A recording-only instruction (record a checklist item) completed → the Stop hook triggered next → an AskUserQuestion proposed a "start a code-workflow (Recommended)" option → the user picked it → a full research + plan was authored against the user's intent of recording only. Recording topics are not decision branch points. (See failed-attempts.md "recording-topic ask-skip".)

Inverse-extrapolation: skipping the next-action ask because a prior chat-text question is awaiting reply is forbidden — the awaiting-reply axis is separate from the next-action axis, and plan/research authoring is not a recording-only topic. (See failed-attempts.md "next-skill ask skip extrapolation".)

If skip-target (exact match in closed list) → no ask. Otherwise → proceed to Step 0.4.

## Step 0.4: Decision-deferral forced-ask gate (HARD STOP)

**Before ending a completion report, scan your own just-emitted text for a decision left as prose.** If the report defers a decision to the user instead of asking it, that deferral is itself a decision axis — you **must** compose an `AskUserQuestion` for it, not end on the text. This is the mirror image of Step 0.3: 0.3 *skips* the ask for recording topics; 0.4 *forces* the ask when a real decision was left unasked.

**Applies regardless of whether `next` was formally invoked this turn.** This self-check is a standing rule for any turn-ending text — a `/fix` wrap-up, a tool-result summary, an aside tacked onto an unrelated report — not something gated behind an explicit `Skill("next")` call. A classic instance: appending "let me know if you want /cleanup" as a courtesy note at the end of an otherwise-unrelated report. That is exactly the text-deferral pattern this gate exists to catch — compose a standalone `AskUserQuestion` for it (folded into an existing ask if one is already being composed this turn, or on its own if not), rather than reasoning "no ask is happening this turn, so text is fine."

### Trigger phrases — a decision left as text

A report that ends with any of these is a forbidden text-question. Convert it to an ask:

| Pattern (any language) | Example |
|------------------------|---------|
| "let me know / tell me and I'll …" | "tell me and I'll do it", "let me know and I'll handle it" |
| "whether to X is …" left unanswered | "whether to commit/PR is up to you", "the decision is yours" |
| "your call / up to you / you decide" | "your call", "your decision", "up to you" |
| "next step is X (if you want)" | "the next step is X if you want", "let me know to proceed" |
| **Locale deferral phrases** (start/proceed/decision + awaiting/deferred, in the session language) | see `data/*.regex` deferral block — e.g. "the start decision awaits your instruction", "proceeding awaits your call" and their locale equivalents |

### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | End the report with "let me know and I'll handle it" (decision as prose) | Compose an `AskUserQuestion` whose options are the decision's real branches (e.g. commit-now / feature-branch+PR / hold) + Other |
| 2 | Treat a deferred decision as "out of scope — the user will instruct later" | A deferred decision is in `next`'s scope: it is a decision axis, so ask it now |
| 3 | Rely on the Stop hook firing to remember the ask | The Stop hook is belt-and-suspenders. This self-check is the first line — run it before ending the report |

### Self-check (every time before ending a completion report)

1. Does my report contain a decision phrased as prose (any trigger phrase above)?
2. If yes → an `AskUserQuestion` is **required** for that decision. Do not end on the text.
3. Is the decision a real branch (≥2 executable options)? Compose those as options + Other.
4. This gate **overrides** Step 0.3 skip: even right after a recording/management topic, a deferred decision forces the ask.

### Surfacing/triage → `wip` delegation (HARD STOP — route target, not just "ask")

When the deferred decision is **"which of N surfaced candidates to start"** (the output of a triage / surfacing topic — `fix-plan priority`, a candidate list, a "top-N actionable" report), the forced ask is **not** a `next` single-select "what next?". Route it to `Skill("wip")` — the surfaced candidates are multi-item work needing task registration + per-item direction (proceed / split / hold), which is wip's resume procedure. This generalizes the cleanup→wip rule ([[feedback_cleanup_wip_not_next]]) to every surfacing topic.

| # | Don't | Do |
|---|-------|-----|
| 1 | Triage surfaced top-3 candidates → end with "start decision is yours" (prose) | Call `Skill("wip")` → its resume procedure asks per-candidate direction |
| 2 | Triage → `next` single-select "pick one to start (Recommended)" | Surfaced candidates = multi-item. `next` single-select strips the split/hold/multi axes. Use `wip` |
| 3 | Triage = recording topic → Step 0.3 skip → no ask at all | Triage surfaces actionable candidates = decision branch. Step 0.4 override forces the ask; route = `wip` |

**Self-check (before ending any triage / surfacing / candidate-list report)**:
1. Did the just-completed work surface ≥1 actionable candidate for the user to potentially start?
2. If yes → the start decision is a real axis. Do not defer as prose (Step 0.4) and do not skip (Step 0.3).
3. Is it multi-item / needs per-item direction? → `Skill("wip")`. Single reversible next-step only? → `next` ask.

Otherwise → proceed to Step 0.5.

## Step 0.5: TaskList primary-source check (MANDATORY — every time before composing ask options)

**Immediately before calling `AskUserQuestion`, call `TaskList` to directly verify current pending/in_progress tasks.** Do not compose options from context summary / memory / inference of recent work.

### Why it's mandatory

- Right after `/compact`, summary memory can be stale — frequent mismatch with the real task list
- When task names/contents appear in option descriptions, the user **trusts they exist** → fabricating virtual tasks in options breaks that trust
- One TaskList call = primary source for option accuracy

### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | Compose options by quoting "Task #N registered" from summary memory | Call `TaskList` → use pending/in_progress entries directly as option candidates |
| 2 | Assume "the task I just registered is still there" | Task IDs/contents can change after /compact. Read TaskList every time |
| 3 | Option-ify only some pending tasks (e.g., "only the 1 immediately actionable") | Include all pending tasks as option candidates. If trigger conditions differ, state them in description |
| 4 | Write virtual tasks ("FA-update immediate progress") in option descriptions | Quote real task subject + ID (note: TaskList-internal `#NN` IDs are referenced by subject keyword, not exposed in user-visible output) |

### Self-check (every time before calling AskUserQuestion)

1. Does this ask relate to task progress direction? → If yes, TaskList Read is mandatory
2. Do the tasks mentioned in option descriptions **actually exist in TaskList**? — 1:1 mapping with TaskList output
3. If there are N pending tasks but only M < N appear in options → state the filtering reason in description or use the wrap-up pattern
4. **Does any option/question text reference a PR or issue?** → If yes, the full clickable URL (`https://github.com/<owner>/<repo>/pull|issues/<N>`) must appear in that same ask — a bare `#N` is forbidden even when accompanied by a repo name. This is `suggestion-patterns.md`'s own "Cross-cutting rule — PR/issue references in options require the full URL" restated here because Step 0.5's TaskList check is exactly the point in the flow where a task's subject (which may itself be a bare `#N`) gets copied into an option — do not carry that bare reference forward without resolving its URL first. Recurred twice (2026-07-17 fix, 2026-08-18/19 recurrence) precisely because `suggestion-patterns.md` was not Read before composing the ask on the second occurrence — treat `SKILL.md`'s "Read suggestion-patterns.md BEFORE composing options" HARD STOP as non-optional, not as background context you can skip once you've read it before in the session

## Step 0.6: Workspace fix_plan.md active integration protocol (MANDATORY — when TaskList is empty, done, or unavailable)

**Trigger scope (HARD STOP)**: this step applies whenever `TaskList` yields no actionable pending items — whether because it is genuinely empty, all items are done, **or the TaskList/TaskCreate tool is disconnected/unavailable this turn**. "Unavailable" is not a different case from "empty" — both mean the session-local task medium cannot surface backlog, so the persistent checklist medium (`fix_plan.md`) becomes the primary source. Do not read the word "empty" literally and treat a disconnected tool as exempt.

1. **Locate Workspace Root(s)**: Determine the active workspace root(s) containing `.git`, `.ralph/`, **or Ralph-marker files** (`PROMPT.md` + `AGENT.md` alongside `progress.json` / `status.json` / `.circuit_breaker_state`) — a Ralph-loop-owned workspace is not always a git repo and does not always name its state directory `.ralph/`. **Do not derive this from current cwd alone** — a session can move across multiple workspaces (e.g., start in a project directory debugging an issue, then pivot to a skills/rules repo). Enumerate every workspace root visited during the session (via Bash cwd changes, Read/Edit/Grep paths, or `cd`/`git -C` targets seen in the transcript), not just the one matching the cwd at the moment `next` fires.
2. **Find fix_plan.md**: For each workspace root from step 1, read its project backlog checklist at any of `<workspace-root>/.ralph/fix_plan.md`, `<workspace-root>/fix_plan.md`, or `<workspace-root>/.agents/fix_plan.md` if present. The third pattern is a **workspace-LOCAL** `.agents/` state directory (some Ralph workspaces name their loop directory `.agents/` instead of `.ralph/`) — this is a different thing from the global `~/.agents` skills/rules repo; do not skip it because `.agents` "already means the global skills repo" in this session. A workspace without any of the three is skipped, not treated as proof no other workspace has one.
3. **Extract Pending Backlog**: Extract pending checklist items (`- [ ]`) from the `## Priority Work` (or equivalent priority) section.
4. **Context & Relevance Filtering**: Filter these tasks to identify those related to the current session (e.g., matching files edited, directories touched, or keywords from the conversation history). **Relevance-filter fallback (HARD STOP)**: if this filter yields zero session-related items but the unfiltered, priority-sorted backlog (step 5) has entries, do NOT conclude "no candidates" — fall back to surfacing the top priority-sorted items regardless of session relevance. `fix_plan.md` is the workspace's standing backlog, not merely a continuation thread for the current session's topic; a real P0/P1 item is worth surfacing even when it has nothing to do with what the session just did.
5. **Sort by Priority**: Sort the remaining candidates by priority level: `P0` -> `P1` -> `P2` -> `[REPEAT]`.
6. **Compose Options**: Surface the top 2-3 prioritized and related tasks as options in `AskUserQuestion`. Place them above generic options like "End session", using concise labels with their priority level indicated in the description (e.g. `[P0]`). **When surfaced via the step 4 relevance-filter fallback** (session-unrelated but top-priority), the option description MUST also carry an explicit "(workspace backlog, unrelated to this session)" qualifier — the user needs to know these are not a continuation of what was just discussed.
7. **Write-back when the user selects (HARD STOP)**: this step is entered when `TaskList`/`TaskCreate` is empty, done, **or unavailable** — so `SKILL.md` Step 3's default "register each via `TaskCreate`" cannot be assumed to succeed for a selection made here. If `TaskCreate` is still unavailable at selection time, follow `SKILL.md` Step 3's `TaskCreate`-unavailable fallback (write the selection back into `fix_plan.md`/`checklist.md` instead of silently treating "options were shown" as "the selection is tracked").

### Don't / Do table

| # | Don't | Do |
|---|---|---|
| 1 | Suggest "End session" immediately when session tasks are complete without checking the project's persistent backlog | Read the active workspace's `fix_plan.md` first, find prioritized tasks, and offer them |
| 2 | Pull tasks from a parent or different workspace's `fix_plan.md` | Detect the current workspace root(s) first, then read the local `.ralph/fix_plan.md` for each one actually visited this session |
| 3 | Present tasks out of priority order (e.g. suggesting P2/REPEAT before P0/P1) | Sort strictly by priority level (`P0` -> `P1` -> `P2` -> `[REPEAT]`) and surface the highest first |
| 4 | Present all `fix_plan.md` tasks blindly | Filter for tasks that are relevant to the files or topics touched in the current session first |
| 5 | Treat "TaskList tool disconnected/unavailable" as outside this step's scope because the trigger says "empty" | Unavailable = equivalent to empty for this step's purpose. The fix_plan.md check is the fallback specifically when the session-local task medium cannot be read at all |
| 6 | Derive "the workspace" solely from the cwd at the moment `next` fires, especially when that cwd (e.g. a skills/rules repo) has no `fix_plan.md` | Check every workspace root the session actually touched. A session that started in a project directory and later moved to a different repo still has backlog in the first one |
| 7 | Grep the tracker's `##` header list once, then re-read only the section you most recently edited before reporting "no candidates" | Read **every** top-level `##` section from that header list before concluding — recency (just-edited section) is not grounds to skip siblings. This is exactly how a populated `## Priority Work` / `## REPEAT` section gets missed while a freshly-touched section (e.g. `## Fable Target Tasks`) gets re-read |
| 8 | Apply row 2's "don't pull from a parent workspace's fix_plan.md" when the **local** tracker's active-work section has itself been replaced with a redirect note pointing to that parent (e.g. "this repo's items live in `<parent-path>` — see there") | An explicit redirect note is the local tracker delegating scope — follow it, and treat the parent tracker's own top-level `##` sections as in-scope for this session. Row 2 bans *assuming* a parent's backlog is relevant; it does not ban following a redirect the local tracker itself declares |
| 9 | Skip checking `<workspace-root>/.agents/fix_plan.md` because the session already used `~/.agents` heavily this turn (skills/rules repo) and the name "`.agents`" reads as "that global repo" | The two are unrelated: `~/.agents` (absolute, home-rooted, git-tracked skills/rules repo) vs `<workspace-root>/.agents/` (relative to a *different* project's root, untracked Ralph state dir). A workspace-relative `.agents/` is always a candidate under step 2, regardless of how much `~/.agents` was touched this session |
| 10 | Step 4's session-relevance filter returns zero matches → conclude "no candidates" and fall through to Step 0.65's free-text ask, discarding the priority-sorted backlog entirely | Zero relevance matches ≠ zero candidates. Apply the step 4 fallback: surface the top priority-sorted items from the unfiltered backlog, labeled "(workspace backlog, unrelated to this session)" |

### Self-check (before declaring "no work" / "session complete")

1. Is TaskList empty, done, or **did the TaskList/TaskCreate call itself fail or return unavailable**? → Either case triggers this step
2. Did the session's cwd change at any point (project debugging → skills/rules repo, or similar)? → If yes, check `fix_plan.md` in **each** workspace root visited, not just the final cwd
3. Does the final-cwd workspace lack a `fix_plan.md`? → That is not evidence no other visited workspace has one — check them all before concluding no backlog exists
4. If you grepped the tracker's `##` header list, did you actually Read every top-level section on that list — or only the one you most recently wrote to? → Read all of them before reporting a candidate count
5. Does the local tracker's active-work section contain a redirect note pointing to a parent/org-level tracker? → Follow it and scan that parent's own top-level `##` sections (not just the subsection the note names)
6. Did you check for a **workspace-LOCAL** `<workspace-root>/.agents/fix_plan.md`, not just `.ralph/fix_plan.md` or bare `fix_plan.md`? → Some Ralph workspaces (non-git, no `.ralph/`) use `.agents/` as their loop state directory — a plain `ls <root>/fix_plan.md <root>/.ralph/fix_plan.md` misses it

## Step 0.65: Repeated no-candidate invocation → forced direct ask (HARD STOP)

**When `next` fires again in the same session and Step 0.5/0.6 again surface zero candidates (TaskList empty AND fix_plan.md's unfiltered priority-sorted backlog is also empty — not merely "no session-relevant item", see Step 0.6 item 4's relevance-filter fallback) — the same "no-candidate" outcome as a prior `next` firing this session — do not silently end the turn or repeat a generic "nothing to do" report.** Force an `AskUserQuestion` that asks the user directly what to work on next, using free text (no guessed/speculative options), even though there is no discovered candidate to offer.

This is narrower than the general "avoid guess options" guidance below — it specifically targets **repeated zero-candidate firings**, where staying silent turn after turn reads as the assistant giving up on discovery duty.

| # | Don't | Do |
|---|-------|-----|
| 1 | Second (or later) zero-candidate `next` firing this session → end with "no work found" text again | Compose an `AskUserQuestion`: "What would you like to work on next?" with a free-text-first option (no guessed candidates) + "End session" |
| 2 | Treat "no candidates found" as license to skip the ask entirely | Absence of a discovered candidate is not absence of a decision — the user still decides what's next |
| 3 | User answers one specific ask (e.g. a re-auth/verification offer) with frustration/anger/a terse dismissal, and the assistant reads that as "stop asking anything for the rest of the session" → every later Stop-hook `next` re-trigger ends on generic standby/completion text instead of this step's forced ask | Scope the frustration to the **specific declined candidate only** — drop that one candidate, but the Step 0.65 forced direct ask (a fresh, different decision: "what next") still fires. Anger at a repeated/low-value ask is not consent to stop being asked entirely; it is a signal to stop repeating *that* ask |

### Self-check

1. Did `next` fire more than once this session with a zero-candidate outcome each time? → If yes, this step applies
2. Am I about to end the turn with a repeat "nothing to do" report? → Forbidden. Compose the direct-input ask instead
3. Did the user's most recent reply express frustration/anger toward a *specific* prior ask (not a general "stop working" instruction)? → That drops the declined candidate only — this step's forced direct ask is still owed, not exempted

## Step 0.66: Unchanged-candidate-set re-fire within the same chain (HARD STOP)

**Silent skip (status report, no `AskUserQuestion`) requires BOTH conditions below — "candidate set unchanged" ALONE is never sufficient.** The only case where skipping the ask is permitted is immediately after a `/cleanup` run in this same turn/chain — because `/cleanup` Step 5 (wip delegation) has already composed and resolved its own wrap-up ask, so a `next` re-fire right after it would be a redundant re-ask of a decision the user just made. Every other "candidate set looks unchanged" situation still requires an ask (at minimum the single-item confirmation form below) — an unchanged backlog does not, by itself, mean nothing needs asking.

**Preconditions (BOTH required for the silent-skip path)**:
1. **Cleanup precondition (HARD STOP — check this FIRST)**: was the immediately-preceding action in this turn/chain an actual `/cleanup` (or equivalent session-wrap-up skill) execution — not merely "no urgent items" or "the transcript looks quiet"? If the preceding action was anything else (an import, a push, a code edit, a prior `next` ask with no cleanup in between), this precondition FAILS and the silent-skip path is not available, regardless of the same-set test result.
2. **Same-set test**: compare the current candidate list (post Step 0.5/0.6 discovery) against the immediately-prior `next`-ask's candidate list in this chain. Identical if every item matches by subject/target (ignoring cosmetic wording) AND none has a new state (no new TaskList entry, no fix_plan change, no user reply that altered scope).

This is distinct from Step 0.65 (zero-candidate repeated firing) — here candidates DO exist, but they are the same ones already surfaced and either answered or explicitly deferred moments earlier in the same chain.

| # | Don't | Do |
|---|-------|-----|
| 1 | Skip the ask solely because the candidate/decision set looks unchanged | Check the cleanup precondition FIRST. Unchanged set + no preceding `/cleanup` = still ask (minimal form) |
| 2 | Compose a new full `AskUserQuestion` with the same options as the previous ask in this chain, just reworded | If both preconditions hold: end the turn with a short status report ("carried over: X, Y, Z — no new candidates this fire") and no ask |
| 3 | Keep re-asking until the user manually breaks out (rejects the tool call, issues an unrelated command) | Recognize the unchanged-set condition before the ask, not after the user has to reject it |
| 4 | Treat "the hook fired again" as proof a fresh ask is owed regardless of content | The hook firing is a *reminder to check*, not a mandate to always ask — check both preconditions first |
| 5 | Silently drop the carryover items on grounds of "already asked" | Still report their carryover status in plain text (per Step 0.3's skip-still-reports discipline) — silence is the ask-gates violation this table exists to prevent elsewhere |
| 6 | Treat an intervening non-cleanup action (RAG import, a push, a PR conversion) between the prior ask and this fire as "nothing changed, so cleanup precondition is close enough" | Only a literal `/cleanup` run satisfies the cleanup precondition. Any other intervening action means this step's silent-skip path does not apply — ask |
| 7 | Extend the cleanup-adjacent silent-skip across an entire "waiting on external/user action" polling period — treat the global "don't repeat the same ask while the user is actively polling/working" rule as overriding this step's own Exception clause for every subsequent re-fire | The cleanup-adjacent skip is a **single, one-time** use immediately after `/cleanup`. Every re-fire after that (including during a polling wait) falls back to the Exception below (minimal single-item confirmation) — the global polling-ask-avoidance rule governs *repeating a full multi-option ask*, not *whether any ask at all is owed on a Stop-hook re-fire* |

**Exception**: if the one item that is still genuinely open differs from the rest (e.g., 3 items already deferred, 1 item newly blocking), a minimal single-item confirmation for that one item is allowed — do not fold it back into a full 4-option re-ask of the whole set. This minimal-confirmation form is available even when the cleanup precondition fails (it is not a "full ask", so it isn't gated the same way) — use it instead of a silent status report whenever precondition 1 fails. **This is the required fallback for every next-trigger re-fire during a polling/waiting period** (row 7) — a bare status report with zero `AskUserQuestion` call is never correct here, no matter how many times the hook has already fired.

### Case history — repeated re-fires during a polling wait (2026-08-17)

A session waited on a user's manual `git push` (a bash-guard-blocked command) while `next-trigger.sh` fired 8+ times in a row. Each time the assistant called `Skill("next")` (satisfying the hook's literal check) but ended with plain status text ("still waiting", "same state") — zero `AskUserQuestion` calls across the entire wait. The assistant had correctly applied the cleanup-adjacent single-use skip once, then kept reusing that same reasoning for every subsequent fire, reasoning that the global "don't repeat the same ask while the user is polling" rule justified continuing to skip. It does not — see row 7. The mechanical root cause (why the hook kept re-firing at all) turned out to be a separate bug in `next-trigger.sh` itself: the hook's own injected `"Stop hook feedback: ..."` block text is stored in the transcript as a `type=="user"` entry with string content, indistinguishable from a genuine human prompt to the hook's own "last real user turn" anchor — so every re-fire reset the hook's turn-based suppression against itself. Fixed at the hook level (exclude that literal prefix from the anchor computation) plus a belt-and-suspenders 3-consecutive-fires-without-`AskUserQuestion` escalation counter, independent of this specific bug, for any other scenario producing the same symptom.

### Self-check

1. **Did a `/cleanup` (or equivalent session-wrap-up skill) actually execute as the immediately-preceding action in this turn/chain?** → If no, the silent-skip path is unavailable — go to item 4 below (compose at least a minimal ask), regardless of how the same-set test comes out.
2. Is this `next` firing within the same `stop_hook_active` continuation chain as an earlier `next`-ask this turn/chain? → If no, this step does not apply
3. Does the candidate/decision set match the immediately-prior ask's set exactly (same-set test above)? → Only relevant if item 1 passed. Both pass → skip the full ask; end with a status report
4. Item 1 failed (no preceding cleanup) OR the set is only partially unchanged → compose at least the single-item confirmation form (Exception above) — never a bare status report with zero `AskUserQuestion` call
5. Am I about to re-ask the same set a 2nd+ time in this chain hoping for a different answer? → Forbidden. Report and stop, or escalate to Step 0.65's direct free-text ask only if the set is now genuinely empty

### Case history

A session ran a RAG session-import skill (NOT `/cleanup`) mid-session, then `next` fired twice in the same chain. Both times the assistant applied this step's exemption on the "candidate set unchanged" test alone (2 carryover backlog items) and ended with a plain-text status report, no `AskUserQuestion` — even after the Stop hook re-fired the same "no next call" complaint twice. The precondition that was missing: the intervening action was an import, not a cleanup, so the silent-skip path was never actually available — at minimum a single-item confirmation ask was owed each time. The user corrected this directly, stating that skipping the ask is acceptable in exactly one case: right after a cleanup run.

## Step 0.7: User current-work confirmation ask (HARD STOP — required when user-action state is unclear)

**Before composing options, if any of the following conditions apply, ask the user "what are you currently working on / waiting for" FIRST. Do not bake assumptions into option descriptions.**

### Precedence gate — populated pending backlog ≠ unclear current work (HARD STOP, fires FIRST)

**A non-empty pending TaskList means work exists. Whenever Step 0.5's TaskList read returns ≥1 pending task, the "no work to do" / "nothing to resume" / "current activity unclear" framings are FORBIDDEN — the backlog IS the work.** This gate fires BEFORE the trigger conditions below: even when the Stop hook auto-invoked `next` after a resume/assigned task completed (or the resume turned out to be a no-op / already-done), a populated backlog is NOT an "unclear current activity" situation. Unclear-activity handling (the trigger table below) applies only when the backlog is empty or genuinely ambiguous (e.g., 2+ in_progress with no clear pending queue).

**Autonomous-loop re-fire is also covered (HARD STOP)**: a Stop-hook-driven re-feed of a generic continuation prompt (e.g. a ralph-style loop's repeated "proceed with task until X, then cleanup" text, or any similar autonomous-loop channel) is a resumed-work moment exactly like the ones this gate already governs — it is NOT a separate free-text instruction to interpret ad-hoc each time. On any such re-fire, check TaskList/`fix_plan.md` for actionable pending items and start the top one BEFORE doing anything else — before re-checking context-usage thresholds, before running cleanup, before any side-investigation the re-fed text superficially suggests. A re-fed loop prompt saying "proceed with task" is an instruction to work the backlog, not license to decide anew each iteration what "task" means from scratch. (Case history: a multi-iteration autonomous-loop session never advanced any of its registered pending TaskList items — every iteration was absorbed into cleanup/fix/ask cycles because the re-fed prompt was treated as free text instead of routed through this gate.)

| Signal | Wrong response (forbidden) | Correct response |
|--------|---------------------------|------------------|
| Assigned/resume task done + pending TaskList ≥1 | "Nothing to resume — tell me what to work on" (frames backlog as empty) | Backlog is the work → `Skill("wip", "resume")` for per-item direction, OR autonomously proceed with the top actionable item (report the choice) |
| Stop hook auto-invoked next + pending TaskList ≥1 | Apply the "ask what you're working on (unclear)" path | Multi-item backlog = wip resume territory (per-item proceed/split/hold), not a "what are you working on" confusion ask |
| Long gap / stale resume + pending TaskList ≥1 | "A week passed, current work is hard to determine" | Time gap does not empty the backlog. Reconcile pending tasks against reality (active worktrees, fix_plan), then engage — never declare emptiness |

| # | Don't | Do |
|---|-------|-----|
| 1 | Equate "the single assigned/resume task is complete" with "no work exists" | Read TaskList (Step 0.5). Pending ≥1 → work exists. Never emit "no work"/"nothing to resume" |
| 2 | Use the "unclear current activity → what are you working on" path when a concrete pending backlog is visible | Visible backlog = activity is NOT unclear. Route to wip resume (per-item direction) or autonomous-proceed |
| 3 | Frame a stale-resume (long gap, assigned task done) as "current work hard to determine" | Reconcile the pending backlog against reality, then engage. Don't declare emptiness |
| 4 | Treat a re-fed autonomous-loop prompt ("proceed with task until X") as free text to interpret ad-hoc each iteration (context-threshold checks, cleanup, side-investigations) while a pending backlog sits untouched | Route the re-fire through this gate immediately: read TaskList/fix_plan, start the top actionable item, THEN consider threshold/cleanup |

**Self-check (before applying any Step 0.7 trigger)**:
1. Did Step 0.5's TaskList read return ≥1 pending task? → If yes, the "no work"/"unclear activity" framings are forbidden. Route to wip resume or autonomous-proceed
2. Am I about to say "nothing to resume" / "no work" / "current activity unclear" while a pending backlog exists? → Stop. The backlog is the work
3. Is this a multi-item backlog needing per-item direction? → `Skill("wip", "resume")`, not a `next` "what next?" single-select

(Same failure class as the Ralph "`[RALPH_TODO]`-only, ignore plain `- [ ]` checklist backlog → 'no actionable work' false exit" recurrence in failed-attempts.md — a narrow "actionable work" definition producing a false "no work" conclusion despite a real backlog.)

### Trigger conditions

| Signal | Example | Required action |
|--------|---------|-----------------|
| 2+ in_progress tasks in TaskList | {server-A} migration + {app-import} + ansible inspection all in_progress | Ask the user which is actually being worked on |
| User's prior message ambiguous about scope | "finishing ssh fix and design change" (which server? which design change?) | Ask the user to pinpoint scope |
| Task description includes "user direct work" / "user execution wait" | {server-A} sudo wait, manual server work | Ask the user "is the work done? in progress? not started?" |
| Stop hook auto-invoked next (not single task completion) | Multi-task session, partial completion | Ask the user "which work was completed? what to do next?" |

### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | Write "{task X} user-action wait" in option description as assumption | Ask user first: "Currently working on {X}, {Y}, or {Z}?" → compose options based on the answer |
| 2 | Interpret a prior user message ("in progress", "finishing") as a specific task | If ambiguous, ask: "What does 'in progress' refer to — {task A} or {task B}?" |
| 3 | Compose options assuming "user is waiting on task #N because TaskList says it's in_progress" | TaskList in_progress = registered state, not current real-time activity. Ask the user |
| 4 | Skip the ask with the justification "Other is available so the user can adjust" | "Other" doesn't compensate for assumption errors. Ask explicitly when the activity is unclear |

### Self-check (every time before composing options)

1. Has the user explicitly told us in the last 1-2 messages what they are currently working on? → If yes, use that; if no, ask
2. Are there 2+ in_progress tasks in TaskList? → If yes, the user might be working on any of them. Ask
3. Did the user just hand off work that requires "manual sudo / external API / browser action"? → Ask if it's done
4. Did the user say something ambiguous about scope ("in progress", "finishing", "applying the design change")? → Ask for pinpoint

### Distinguish "in progress" vs "waiting on" (HARD STOP)

**in progress** ≠ **waiting on**. Both must be asked separately when the situation is unclear.

| Concept | Meaning | How to ask |
|---------|---------|------------|
| in progress | Work the user is actively performing (running a sudo command, working in the IDE, etc.) | "What are you working on right now?" |
| **waiting on** | Something the user is awaiting an external response/result for (CI result, teammate response, build finish, etc.) | **"What result are you waiting on?"** — must be asked as a separate question |

**Do not combine the two in a single option.** Example: "{server-A} sudo in progress" is in-progress, while "{server-B} 502 recovery waiting" is waiting-on. Mixing them in one option set makes the answer ambiguous.

### Avoid guess options — prefer free-text via Other (HARD STOP)

**Listing 3–4 speculative options forces the user to pick something unrelated to their actual state.** AskUserQuestion's "Other" is a free-text channel — use it.

| # | Don't | Do |
|---|-------|-----|
| 1 | All 4 options are Claude-guessed task names (possibly unrelated to the user's state) | 2–3 options with clear branching (e.g., "Claude continues autonomously" / "I'm working on something") + Other |
| 2 | Hard-code a concrete task guess like "{server-A} in progress" as an option | Use "I'm doing external work (please write what in Other)" |
| 3 | Fill option description with assumed information before receiving the user's answer | If user state is unconfirmed, minimize options and capture via free text |

### Example — user vs assistant

**Bad (assumption-driven options)**:
```
Q: "{server-A} user-action wait. Next action?"
options: [
  "Start {server-B} inspection (Recommended)",
  "Confirm {service} SSH key path",
  "End session"
]
```

**Bad (guess options pretending to ask state)**:
```
Q: "Multiple in_progress tasks. What are you currently working on?"
options: [
  "{server-A} sudo migration in progress",  ← guess
  "{server-B}/{server-C} inspection in progress",  ← guess
  "Other server work (please specify)",
  "Nothing — Claude can pick up the next task"
]
```

**Good (separate ask for in-progress vs waiting-on + free text)**:
```
Q1: "What are you currently working on? (Other free text recommended)"
options: [
  { label: "Claude continues the next task autonomously", description: "User is doing something else — Claude proceeds on its own" },
  { label: "I'm working on something myself", description: "Write what in Other" },
]

Q2: "What result/response are you waiting on? (Other free text)"
options: [
  { label: "Nothing — Claude can proceed", description: "No external item to wait on" },
  { label: "Waiting on something", description: "Write what in Other (e.g., CI result, teammate response, server recovery, etc.)" },
]
```

After receiving both answers, compose the actual next-action options based on the answered current state + waiting items.

## Context-usage citation on every next-composed ask (HARD STOP — not scoped to cleanup options)

**Every `AskUserQuestion` this skill composes states the live context-usage percentage in the question text, regardless of whether a cleanup/wrap-up option is being offered.** The `context-usage-stale` guard class (17+ recurrences, hooks `context-usage-inject.sh` + `block-cleanup-option-below-context-gate.sh`) only covers citation accuracy **inside a cleanup option** — it cannot detect a plain next-action ask that omits the number entirely, because a hook sees only the tool-call payload and cannot tell "this ask was composed by `next`" from any other skill's ask. This gate exists precisely to cover that hook-blind spot at the skill-composition layer.

Get the number the same way the cleanup-gate section does: the latest injected `Context usage: ... (NN%)` line, or a live re-check via the injection script when the last reading predates this turn's tool-call chain (see suggestion-patterns.md "Live-check fallback").

| # | Don't | Do |
|---|-------|-----|
| 1 | Compose a next-action ask with zero cleanup candidates and omit the context percentage because "no cleanup option is being offered, so the citation rule doesn't apply" | Cite the live percentage in the question text regardless — it is baseline situational awareness for the user, independent of whether cleanup is being recommended |
| 2 | Assume `block-cleanup-option-below-context-gate.sh` will catch a missing percentage | That hook only fires when a cleanup/wrap-up option is present in the payload. A plain "what next" ask with no such option is invisible to it — this is a skill-level obligation, not a hook-enforced one |
| 3 | Assume the gate is NOT met because an earlier reading this turn/chain was below threshold (**stale-LOW**) — a long tool-call chain (audits, a full /fix flow) can grow usage tens of points past the old number | Re-measure immediately before deciding next-vs-cleanup and before composing the ask. A below-threshold reading taken more than a few tool calls ago never proves the gate is still unmet — staleness cuts both ways (stale-HIGH overstates after a compact; stale-LOW understates after a long chain) |
| 4 | Treat a percentage that was correct at ask-composition time as still valid once the user answers, and execute the selection without re-measuring | The gate has no validity duration. Automatic context compression can fire **while the ask is open** and leaves no `isCompactSummary` / `compact_boundary` marker, so the staleness is undetectable after the fact — re-measure before executing any selection the percentage justified. Full rule: suggestion-patterns.md "Round-trip invalidation" |

### Self-check (every time before calling `AskUserQuestion` from this skill)

1. Does the question text include the live percentage (`NN%` or `NN.N%`)? → If no, add it before calling
2. Is the reading fresh (post-compact, not from a stale earlier turn in a long tool-call chain)? → If stale, get a live reading first (suggestion-patterns.md "Live-check fallback") — stale in EITHER direction: an old high reading overstates post-compact, an old low reading understates after a long tool-call chain
3. Is the fresh reading at/above the session model's threshold (or did the injection script emit a `CLEANUP-GATE` directive)? → The cleanup/retrospective option becomes **REQUIRED as the Recommended #1 option** of the turn-final ask — next-action candidate discovery is secondary and may be skipped

---

## Post-task-completion follow-up is Skill("next") invocation duty — no plain-text questions (HARD STOP)

**When a task-batch (or work flow) completes and the turn is wrapping up, the way to ask about the next action is to call `Skill("next")` and then `AskUserQuestion`. Ending with a plain-text question like "anything else you'd like me to do?" / "let me know the next action" / "let me know the follow-up direction" is forbidden.** Discovering follow-up work is the assistant's responsibility, not the user's — the `next` skill actively surfaces candidates from fix_plan / open PRs·issues / dependent follow-ups / the just-completed work, and presents them as options.

Always-on promotion of memory `feedback_subskill_resume_orchestration` (3rd recurrence). The `next` skill's description specifies Stop-hook auto-invocation, but the safety net can break if the dispatcher isn't wired up or Korean-regex coverage is missing — so **an assistant's explicit `Skill("next")` call is the correct approach**.

### Don't / Do

| # | Don't (forbidden) | Do (correct alternative) |
|---|-------------|-----------------|
| 1 | End the completion report with a plain-text question like "anything else you'd like me to do?" / "anything else to handle?" and close the turn | Call `Skill("next")` in the same turn → surface candidates → present as `AskUserQuestion` options |
| 2 | Offload discovery to the user via text like "let me know the next action" / "let me know the follow-up direction" | Follow-up discovery = assistant's responsibility. The `next` skill surfaces candidates from primary sources (fix_plan/PR/issue) |
| 3 | Relying on "AskUserQuestion is too heavy, wrap up with text" / "the Stop hook will fire on its own" | The hook is a safety net (may not cover Korean). The assistant explicitly calls `Skill("next")` on the final turn |
| 4 | After a sub-skill (`/wip`, `/fix`, `/cleanup`, consolidate, etc.) returns, output only the report and end | Return to the outer flow — if a proceed-item remains, move to the next item; otherwise call `Skill("next")` |
| 5 | Classifying a wait/polling-handoff turn (registering `ScheduleWakeup` and returning control) as "work incomplete, so `next` doesn't apply" + interpreting the `ScheduleWakeup` result's "Nothing more to do this turn" wording as exempting the final report and `next` + **emitting the text first and placing the wakeup call as the turn's last call** (leaving the final message tool-call-only) | A wait handoff is also a user-facing close — `next` ask (if needed) → **call `ScheduleWakeup` → receive its result → the turn's final output must be the final-report text**. "Nothing more to do this turn" is not grounds to omit the text (enforcement: `next-trigger.sh` blind-spot guard — detects tool-call-only/`ScheduleWakeup` turn endings) |
| 6 | Ending with a **status/completion statement** rather than a plain-text "question" (e.g. "done", "completed", "passed", "remaining state: waiting on ~") → judging "not a question, so the `next` rule doesn't apply" + omitting `Skill("next")` | **The trigger is "task-batch completion", not "a question was written"**. Whether it's a question or a status statement, if the work flow is complete and the turn is wrapping up, call `Skill("next")` in the same turn. Even if the completion phrasing isn't covered by the hook's regex and the safety net doesn't fire, the assistant calls it proactively (same as row 3 — no reliance on the hook) |
| 7 | Treating a **mid-turn AskUserQuestion on another axis** (a push/deploy confirmation, a trade-off answer, an option selection) as having satisfied the completion-time `next` duty → wrapping up with a report only | A mid-turn ask is a **different decision axis**; the next-action ask fires at batch completion regardless. Critically, on a **continuation chain** (a turn that resumed from an earlier Stop-hook block), the Stop-hook safety net is **structurally silent** for every later stop in that chain (`stop_hook_active` loop prevention — no block, no log). Long chained turns with multiple ask round-trips are therefore exactly where the assistant's explicit `Skill("next")` call is the ONLY path — evidence: next-trigger.debug.log gap, next-invocation family 10th recurrence. **This chain-blindness is not specific to the `next`-invocation duty** — it applies equally to a Step 0.4 prose-decision left unresolved mid-chain (see "Chain-continuation carry-forward check" above) |

### Self-check (every time before wrapping up a turn on task completion)

1. Did a task-batch / work flow complete in this turn? → If yes, this rule applies
2. Am I about to close the response with a plain-text question ("follow-up/next/additional work" + "anything else?"/"let me know"/"?") **or a status/completion statement** ("done"/"completed"/"passed"/"remaining state: waiting on ~")? → Neither may close the turn by itself. If a task-batch completed, replace it with `Skill("next")` (the trigger is **task completion**, not the presence of a question)
3. Does this same turn include a `Skill("next")` tool call? → If no, add the call
4. Only genuine branch axes explicitly requiring the user (e.g. push/merge confirmation) may get a separate ask — and even those can be folded into `next`'s options
5. Is this turn being handed off via `ScheduleWakeup`? → Confirm that **after** calling wakeup and receiving its result, the **turn's final output is the final-report text** — a tool-call-only final message is a violation (placing the text only before the wakeup call is also a violation)


