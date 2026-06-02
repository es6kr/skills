---
metadata:
  author: es6kr
  version: "0.1.1"
name: next
depends-on: [fix, hook]
description: >-
  Suggest next actions after completing any task. Auto-invocation via Stop hook (`resources/next-trigger.sh`) using JSON `decision:"block"` (registered in settings.json Stop array, 2026-05-28). Fires when assistant response contains completion keywords (locale patterns in `data/*.regex`).
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

If stall detected → topic invokes `/fix`. If no stall → proceed to Step 0.3.

### Step 0.3: Recording/management topic ask-skip gate (HARD STOP — 2026-05-30)

**If the just-completed work is a "simple recording/management topic", skip the next-action ask entirely.** Stop hook auto-triggers next skill on every task completion, but recording-topic completion is not a user-decision branch point.

#### Skip-target topic list

| Topic / skill | Identification signal | Skip ask? |
|---------------|----------------------|-----------|
| `/ralph fix-plan` (add/move/check) | User message: `fix-plan`, `fix_plan`, "record in checklist" | ✅ Skip |
| `/archive`, `/safe-delete` | User message: `archive`, `delete`, `move to .bak` | ✅ Skip |
| `/todo`, `/todowrite` add/move | User message: `todo add`, `task register` | ✅ Skip |
| `/wip` start/register | User message: `wip`, "track progress" | ⚠️ Conditional (multi-step task → ask allowed) |
| `/session rename`, `/session move` | Single-action session management | ✅ Skip |
| Code modification / implementation | Edit/Write performed | ❌ Ask required (verification/commit/push branch) |
| Commit / push | git commit/push performed | ❌ Ask required (next-step branch) |
| Skill/rule modification | Skill/rule file Edit | ❌ Ask required (test/commit branch) |

#### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | Stop hook triggered next → unconditionally compose AskUserQuestion options | First check skip-target topic list. Skip = report only |
| 2 | "fix-plan completed, should I proceed with code-workflow next?" autonomous proposal | fix-plan = recording topic. Wait for explicit user follow-up instruction |
| 3 | "archive completed, should I delete the rest too?" autonomous proposal | archive = single-action. Report and end |
| 4 | "User can pick Other or end-session option, so it's safe to ask" rationalization | Ask itself implies a user decision is needed. No decision needed = no ask |

#### Self-check (every time before composing options)

1. What was the just-completed work? -- Identify by user message + action history
2. Does it match the skip-target topic list above? -- If yes, skip ask immediately
3. Did the user explicitly express follow-up intent alongside the recording-topic invocation (e.g., "record then proceed with X")? -- If no, end with report only
4. Does the just-completed work include code change / commit / push / external publish? -- If yes, ask is required (decision branch exists)

#### How to skip (procedure)

1. Determine skip target via Step 0.3 self-check
2. If skip-target, do not proceed to Step 0.5/0.7 (TaskList check, user-work confirmation)
3. Report completion as plain text only (no AskUserQuestion call)
4. If Stop hook re-triggers next skill, re-evaluate the same skip judgment

#### Violation case (2026-05-30, 1st)

`/ralph fix-plan` completed ZAP rescan Medium 5 recording → Stop hook triggered next skill → composed AskUserQuestion with "/code-workflow entry (Recommended)" option → user picked it → code-workflow research + plan auto-authored against user's intent of recording only. User pointed out: "I said fix-plan, why proceed with ask? Recording in checklist was the instruction". This Step 0.3 was added to prevent recurrence.

If skip-target → no ask. Otherwise → proceed to Step 0.5.

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

### Step 0.7: User current-work confirmation ask (HARD STOP — required when user-action state is unclear)

**Before composing options, if any of the following conditions apply, ask the user "what are you currently working on / waiting for" FIRST. Do not bake assumptions into option descriptions.**

#### Trigger conditions

| Signal | Example | Required action |
|--------|---------|-----------------|
| 2+ in_progress tasks in TaskList | {server-A} migration + {app-import} + ansible inspection all in_progress | Ask the user which is actually being worked on |
| User's prior message ambiguous about scope | "finishing ssh fix and design change" (which server? which design change?) | Ask the user to pinpoint scope |
| Task description includes "user direct work" / "user execution wait" | {server-A} sudo wait, manual server work | Ask the user "is the work done? in progress? not started?" |
| Stop hook auto-invoked next (not single task completion) | Multi-task session, partial completion | Ask the user "which work was completed? what to do next?" |

#### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | Write "{task X} user-action wait" in option description as assumption | Ask user first: "Currently working on {X}, {Y}, or {Z}?" → compose options based on the answer |
| 2 | Interpret a prior user message ("in progress", "finishing") as a specific task | If ambiguous, ask: "What does 'in progress' refer to — {task A} or {task B}?" |
| 3 | Compose options assuming "user is waiting on task #N because TaskList says it's in_progress" | TaskList in_progress = registered state, not current real-time activity. Ask the user |
| 4 | Skip the ask with the justification "Other is available so the user can adjust" | "Other" doesn't compensate for assumption errors. Ask explicitly when the activity is unclear |

#### Self-check (every time before composing options)

1. Has the user explicitly told us in the last 1-2 messages what they are currently working on? → If yes, use that; if no, ask
2. Are there 2+ in_progress tasks in TaskList? → If yes, the user might be working on any of them. Ask
3. Did the user just hand off work that requires "manual sudo / external API / browser action"? → Ask if it's done
4. Did the user say something ambiguous about scope ("in progress", "finishing", "applying the design change")? → Ask for pinpoint

#### Distinguish "in progress" vs "waiting on" (HARD STOP)

**in progress** ≠ **waiting on**. Both must be asked separately when the situation is unclear.

| Concept | Meaning | How to ask |
|---------|---------|------------|
| in progress | Work the user is actively performing (running a sudo command, working in the IDE, etc.) | "What are you working on right now?" |
| **waiting on** | Something the user is awaiting an external response/result for (CI result, teammate response, build finish, etc.) | **"What result are you waiting on?"** — must be asked as a separate question |

**Do not combine the two in a single option.** Example: "{server-A} sudo in progress" is in-progress, while "{server-B} 502 recovery waiting" is waiting-on. Mixing them in one option set makes the answer ambiguous.

#### Avoid guess options — prefer free-text via Other (HARD STOP)

**Listing 3–4 speculative options forces the user to pick something unrelated to their actual state.** AskUserQuestion's "Other" is a free-text channel — use it.

| # | Don't | Do |
|---|-------|-----|
| 1 | All 4 options are Claude-guessed task names (possibly unrelated to the user's state) | 2–3 options with clear branching (e.g., "Claude continues autonomously" / "I'm working on something") + Other |
| 2 | Hard-code a concrete task guess like "{server-A} in progress" as an option | Use "I'm doing external work (please write what in Other)" |
| 3 | Fill option description with assumed information before receiving the user's answer | If user state is unconfirmed, minimize options and capture via free text |

#### Example — user vs assistant

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

#### Re-review policy (HARD STOP — first review vs re-review)

| Scenario | Autonomous bot trigger allowed? |
|----------|-------------------------------|
| **First review** (PR initial creation; no prior review from a given bot) | ✅ Allowed — PR creation itself is the user trigger |
| **Re-review** (new commit pushed; a prior review from the same bot exists or was requested) | ❌ Forbidden — AskUserQuestion required before re-requesting |

A "bot trigger" includes any of:

- `gh api repos/<o>/<r>/pulls/<N>/requested_reviewers -X POST` (re-request)
- `gh pr comment <N> --body "/review"` or `@coderabbitai review` (slash-command trigger)
- `gh pr edit <N> --add-reviewer copilot-pull-request-reviewer` (re-add)

These are external-medium actions (notify the reviewer bot's quota/queue + post user-visible artifacts on the PR). Initiating them autonomously on a fix-commit-push flow steps into user decision territory.

#### Pre-trigger self-check (HARD STOP — every time before issuing a re-review trigger)

1. Has the same bot already produced **≥1 review** on this PR (any commit)? — `gh pr view <N> --json reviews --jq '[.reviews[] | select(.author.login | test("<bot>"; "i"))] | length'`. If `>0`, this is a re-review case.
2. Is there a **review currently in progress** (no submitted artifact yet but the bot is known to be working)? — Check the `gh pr checks <N>` output for the bot's status line (e.g., `CodeRabbit\tpending\t0\t\tReview in progress`) and the latest issuecomment timestamp from that bot author within the last ~5 min. If in-progress, **do not trigger** — wait.
3. Re-review case ✚ no in-progress signal → **AskUserQuestion required** with explicit options (Re-trigger / Skip Copilot - use 1st review + apply-evidence / Hold).

#### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | CI passes → jump directly to Test Plan verification (skipping consolidate) | CI passes → check AI Review Summary → if missing, run consolidate first → then Test Plan |
| 2 | "User asked for Test Plan check, so verify only" | Even if user-requested, if consolidate is not posted, guide consolidate first |
| 3 | "User asked for 'wait for Copilot re-review', so auto-trigger the re-request to make it arrive" | "Wait for X" ≠ "trigger X". Polling is allowed; bot re-trigger is not — AskUserQuestion required |
| 4 | Re-request after one missed poll → another /review comment → another `requested_reviewers` POST (cascade) | Single AskUserQuestion at the first missing-arrival decision point. No autonomous cascade |
| 5 | Skip the in-progress check before re-requesting | Always run the in-progress check first (step 2 above). A still-running review must not be re-triggered |

**When AI Review Summary is not posted + this is a re-review case** (multiSelect: false):
```typescript
options: [
  { label: "Re-request <bot> review (Recommended if no in-progress signal)", description: "Issue the re-request only after user explicit OK. Includes /review comment or requested_reviewers POST" },
  { label: "Skip <bot> — proceed with prior review + apply-evidence", description: "Use the 1st <bot> review + Internal Review fallback as Summary basis. Faster but loses follow-up findings" },
  { label: "Hold", description: "Decide later (waiting on external/user signal)" },
]
```

**When AI Review Summary is not posted + first-review case** (multiSelect: false):
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

### After PR creation (BEFORE consolidate — branch on reviewer matrix)

**Precondition**: Passed `github-flow/pr.md` Step 9. Branch on the **reviewer matrix** (CodeRabbit walkthrough + Copilot review request/post state), not just walkthrough.

**Self-check before calling** (HARD STOP — reviewer matrix required, walkthrough alone insufficient):

Run **two** queries per PR, not one:

```bash
# 1. CodeRabbit walkthrough
gh pr view <N> -R <repo> --json comments --jq '.comments[] | select(.author.login == "coderabbitai") | {created_at, hasWalkthrough: (.body | contains("<!-- walkthrough_start -->"))}'

# 2. Copilot reviewer request + review post
gh pr view <N> -R <repo> --json reviewRequests,reviews --jq '{
  copilotRequested: ([.reviewRequests[] | select(.login == "copilot-pull-request-reviewer")] | length),
  copilotReviewed:  ([.reviews[]        | select(.author.login == "copilot-pull-request-reviewer")] | length)
}'
```

Then map to a branch:

| CodeRabbit walkthrough | Copilot requested | Copilot reviewed | Branch (option set) |
|------------------------|-------------------|------------------|---------------------|
| ✅ posted | ✅ requested | ✅ reviewed | **Both reviewers complete** — full consolidate |
| ✅ posted | ❌ not requested | ❌ none | **Copilot absent** — branch (a) register + wait, (b) skip Copilot, (c) hold |
| ✅ posted | ✅ requested | ❌ pending | **Copilot pending** — wait for Copilot completion, then consolidate |
| ❌ rate-limited / pending | — | — | **Walkthrough waiting** — same as original "rate limited" branch |

**Branch: Both reviewers complete** (multiSelect: false):
```typescript
options: [
  { label: "Call consolidate pr-review immediately (Recommended)", description: "/consolidate pr-review <N> — CodeRabbit walkthrough ✅ + Copilot review ✅ both present" },
  { label: "Internal Review first", description: "Self-review via superpowers:code-reviewer → then consolidate" },
  { label: "Hold", description: "Push additional commits and wait for re-review" },
]
```

**Branch: Copilot absent (walkthrough only)** (multiSelect: false):
```typescript
options: [
  { label: "Request Copilot review and wait (Recommended)", description: "gh pr edit <N> --add-reviewer copilot-pull-request-reviewer → wait for Copilot review → then /consolidate pr-review <N>. Aligned with consolidate/pr.md Step 2.5 sequential Copilot policy" },
  { label: "Skip Copilot — consolidate with CodeRabbit only", description: "/consolidate pr-review <N> — Internal Review fallback covers Copilot's domain. Faster but loses Copilot's inline suggestions" },
  { label: "Hold", description: "Decide later" },
]
```

**Branch: Copilot pending** (multiSelect: false):
```typescript
options: [
  { label: "Register task and wait for Copilot (Recommended)", description: "TaskCreate \"Run /consolidate pr-review <N> after Copilot review arrives\" — call when notified" },
  { label: "Skip Copilot — consolidate with CodeRabbit only", description: "/consolidate pr-review <N> now, ignore pending Copilot" },
  { label: "Hold", description: "Decide later" },
]
```

**Branch: Walkthrough rate limited / pending** (multiSelect: false):
```typescript
options: [
  { label: "Register task and move on (Recommended)", description: "TaskCreate \"Run /consolidate pr-review <N> after CodeRabbit review arrives\" — call when notified" },
  { label: "Manual trigger and wait", description: "Force trigger with @coderabbitai review comment and wait for walkthrough arrival" },
  { label: "Skip consolidate (skip-review)", description: "Apply coderabbit:ignore label → proceed with Internal Review only" },
]
```

| # | Don't | Do |
|---|-------|-----|
| 1 | Stop at a "waiting for review" text report without presenting options | Run reviewer matrix queries, then present options per the matching branch |
| 2 | Offer merge options when walkthrough has arrived | consolidate first — consistent with block-merge-without-review.sh guard |
| 3 | Batch-handle multiple PRs as "all waiting for review" | Check reviewer matrix per PR (CodeRabbit and Copilot states may differ per PR) |
| 4 | Branch on walkthrough alone, ignoring Copilot state | Both reviewers form the matrix. Walkthrough ✅ + Copilot ❌ requires its own option set (Copilot register/skip/hold) |
| 5 | Recommend "/consolidate" when Copilot is absent without making the Copilot decision explicit | Make Copilot status an explicit choice in the option description — user must decide register vs skip vs hold |

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

**Precondition**: The session's core work is complete and the user signals wrap-up intent (explicit wrap-up keyword such as "wrap up", "cleanup", "end session"), or only asset cleanup (file moves, doc updates) remains. At least one pending/in_progress task remains for carryover.

**Step 0.5 required — Read TaskList directly to identify pending entries**:

```bash
TaskList   # use pending/in_progress entries as the source
```

#### Recommended priority — actionable follow-up over "End session" (HARD STOP — recurrence-driven 2026-05-25)

**"End session" must never be the default Recommended option.** It carries no actionable value beyond what the user already implies by stopping responding; suggesting it autonomously is a `workflow.md` HARD STOP violation ("autonomous proposal of work-progression decisions such as branching / session termination / skipping is forbidden"). If the user wants to end the session, they will say so or simply stop — `next` does not need to nominate it.

Instead, the **Recommended** option is always **the most actionable follow-up** available. In priority order:

1. **A helper skill invocation that adds value at session boundary** (retrospective cleanup, knowledge persistence, weekly report, file cleanup, etc.) — referenced by **purpose, not by skill name**. Example: `"Run session-cleanup retrospective"` or `"Run session wrap-up tooling"` — the user's skill router picks the matching skill. **Never hardcode an external skill name in this skill's body** — published skill names are out-of-tree dependencies and may rename without notice.
2. **Run the highest-priority pending task immediately**
3. **Resume a BLOCKED pending task with newly available preconditions** (e.g., CI just passed, external response just arrived)

"End session" appears **only as a non-Recommended fallback option**, and only when the user has shown signals consistent with wrap-up intent (explicit wrap-up keyword or 2+ consecutive declines of other follow-ups). In that case, the label is plain `"End session"` — never `"End session (Recommended)"`.

#### Option composition rules

| Pending count | multiSelect | Option layout |
|------------|-------------|----------|
| 0 | — | Skip ask entirely (no actionable follow-up exists). Do not generate a single "End session" option |
| 1 | false | `[Recommended: run helper skill OR run pending task, Defer to next session, Hold]` — quote task subject |
| 2~3 | false | `[Recommended: run helper skill OR run highest-priority pending, Run-now options per remaining task, End session (last option, no Recommended marker)]` |
| 4+ | false (max 4) | Top 3 by priority (Recommended at top) + `End session` (last, no marker) — note "carryover N items" in the End-session description |

**Helper-skill recommendation phrasing (skill name hidden)**:

```
{ label: "Run session retrospective + cleanup (Recommended)", description: "Invoke the session-cleanup helper to record this session's lessons + tidy temporary tasks. Skill router picks the matching tool." }
```

#### Self-check (HARD STOP — before drafting the option array)

For every option you are about to include, answer:

1. **What concrete next-turn action does this option trigger?** If the answer is "the session ends without further action," that option is `End session` and **must not** be Recommended.
2. **Does my Recommended option add value the user could not get by simply not responding?** If no, choose a different option as Recommended.
3. **Have I checked `workflow.md` "autonomous proposal of work-progression decisions" rule?** If the user has not explicitly requested wrap-up, the entire wrap-up pattern may not apply — re-route to a regular next-action ask.
4. **Is my Recommended option referencing a helper by purpose (not skill name)?** Hardcoded skill names break when external skills rename.

#### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | Recommend only "1-2 immediately actionable" among pending | All pending as candidates. State trigger conditions in description |
| 2 | Quote task names from summary memory | Call TaskList and quote real subjects |
| 3 | Expose TaskList-internal `#NN` IDs in option descriptions | Per workflow.md "TaskList ID forbidden in conversation" — reference via subject keyword |
| 4 | Mark "End session" as `(Recommended)` or place it first | "End session" is a fallback option only — never the default. Place it last with a plain label |
| 5 | Generate a "wrap-up" ask when the user has not signaled wrap-up intent | Only enter this pattern when the user used a wrap-up keyword or 2+ consecutive declines occurred |
| 6 | Hardcode an external skill's name in the option label | Refer to the helper by **purpose** (e.g., "session retrospective tooling") so the user's skill router resolves it; out-of-tree skill renames don't break this skill |
| 7 | Recommend a helper skill invocation that produces no artifact (vague "wrap up") | The helper must produce a concrete artifact (retrospective entry, cleanup report, persistence record). Vague "wrap up" = same as "End session" |
| 8 | Skip TaskList Read before wrap-up ask | TaskList every time per Step 0.5 |
| 9 | Compose the wrap-up ask **inline** without invoking `/next` and skip rows 1–8 because "I know the rule" | The rule is enforced by the skill's Self-check gate. **Inline composition = skill bypass = same gate applies**. Either call `/next` formally OR self-execute every row in this table + the 4-step Self-check before posting. Pattern: writing "Delete X + end session (Recommended)" as option 1 inline ≡ violating row 4 |
| 10 | Generate two end-session-like options ("X + end session" + "End session, leave Y") | At most 1 plain `End session` option, last, no Recommended marker. Multiple end-variants = recurrence signal — re-check Self-check rows 1–2 |

#### Example (2 pending, right after asset cleanup)

```typescript
AskUserQuestion({
  questions: [{
    question: "Asset move complete. Next action for this session?",
    header: "Next Action",
    multiSelect: false,
    options: [
      { label: "Run session retrospective + cleanup (Recommended)", description: "Trigger the session-wrap-up helper — records what worked / what did not into the failed-attempts log and prunes completed session tasks. Skill router picks the matching tool." },
      { label: "Run cleanup-RalphExit task now", description: "Note Ralph exit point right before cleanup run.md Phase 2 — ready to start" },
      { label: "Run RalphCB-no_progress task now", description: "Analyze CB OPEN no_progress misclassification — ready to start (analysis task)" },
      { label: "End session", description: "Carry over 2 tasks (cleanup Phase 2 Ralph exit note, CB no_progress misclassification analysis) to next session. Fallback if none of the above fits." },
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

