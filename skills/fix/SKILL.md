---
metadata:
  author: es6kr
  version: "0.2.0" # x-release-please-version
name: fix
description: >-
  User behavior correction skill. Triggered by "fix:" prefix feedback (e.g., "fix: why didn't you commit?").
  Analyzes the mistake, improves the relevant prompt (skill/rule/agent/memory/hook) to prevent recurrence,
  then fixes the current issue. TodoWrite required for all steps.
  Use when "fix:", "fix this", "correct", "why not", "why missing", "behavior fix" is mentioned.
---

# Fix: Behavior Correction Skill

Activated when user gives feedback with "fix:" prefix. Finds the root cause of the mistake, improves the relevant prompt (skill/rule/agent/memory/CLAUDE.md/hook), and fixes the current issue.

## Trigger

- Messages with `fix:` prefix
- Behavior correction feedback: "fix this", "correct", "why not", "why missing"

## Options

- `--plan`: In Step 2, instead of modifying prompts directly, **emit only the modification plan** for user review before execution. Use for complex changes or changes spanning multiple files.

## Procedure

### Step 0. TodoWrite (MANDATORY — first action, no exceptions)

**Before any analysis or text output**, register TODO items.

**⚠️ CRITICAL — Do not delete prior fix tasks on chained /fix (HARD STOP)**:

When a new /fix arrives while a prior /fix's tasks are still pending/in_progress:
- **Do not delete** prior fix tasks — incomplete work (especially Resume) is lost
- **Insert 4 new fix tasks via TaskCreate**
- Include the prior fix's incomplete work in the new fix's Resume (fix-2)

**⚠️ CRITICAL — Preserve existing tasks when TaskCreate is unavailable (HARD STOP)**:

In sessions where TaskCreate is disconnected/unavailable, only TodoWrite is usable. **TodoWrite takes an array and overwrites the entire todo list on every call** — registering only 4 fix-* items will **wipe all existing todos**.

**Self-check immediately before calling**:
1. How many existing tasks (N) are registered in TodoWrite? (Confirm from prior call result or context)
2. Did you **include all N existing tasks in this call's array**?
3. Did you **append** the 4 fix-0/1/2/3 items after the existing N?

**Correct pattern** (pseudo-code; `...existing_8_tasks` is a placeholder for the actual array of existing tasks read from the prior TodoWrite/TaskList output — substitute the real entries verbatim):

```text
# If 8 existing tasks exist, call with a 12-item array adding fix-* 4
TodoWrite([
  ...existing_8_tasks,    # ← replace with the actual 8 existing task objects, not a literal spread
  { content: "🔍 fix: {summary} — root cause analysis", status: "in_progress" },
  { content: "🔧 Root cause fix", status: "pending" },
  { content: "🔄 Resume original work: {one-line summary of original work}", status: "pending" },
  { content: "📋 Completion report + cleanup", status: "pending" },
])
```

**Forbidden pattern** (data loss):
```text
# Ignoring existing tasks and registering only 4 fix-* → all existing tasks vanish
TodoWrite([
  { content: "🔍 fix: ...", status: "in_progress" },
  { content: "🔧 Root cause fix", status: "pending" },
  { content: "🔄 Resume original work: ...", status: "pending" },
  { content: "📋 Completion report + cleanup", status: "pending" },
])  # ❌ Existing task data is lost
```

**Default form (when no existing tasks)**:

```text
TodoWrite([
  { id: "fix-0", content: "🔍 fix: {user feedback summary} — root cause analysis", status: "in_progress" },
  { id: "fix-1", content: "🔧 Root cause fix", status: "pending" },
  { id: "fix-2", content: "🔄 Resume original work: {one-line summary of original work}", status: "pending" },
  { id: "fix-3", content: "📋 Completion report + cleanup", status: "pending" },
])
```

- **Antigravity (Gemini) Users**: Create or update the `task.md` artifact representing the TODO list above. This fulfills the TodoWrite requirement.

- In `fix-2`'s `{original work}`, list **the initial request plus everything in progress including the immediately preceding action**
  - Example: "Deploy workflow: image swap done, verification 3/5 in progress, PR body update pending"
  - Listing only the most recent action narrows the scope — go all the way back to the initial request and enumerate the full task list
- fix-2 = "Complete the original work with the revised approach" — the goal is **the deliverable the user originally requested**, not skill/rule changes themselves
- Step 0 is **the first tool call** after /fix activation. Text output before TodoWrite = violation.

### 1. Root Cause Analysis (5-Why depth)

**No trivial exception (HARD STOP)**: Even when the symptom is fixable with a 1-line change, 5-Why analysis is mandatory. code-workflow has a trivial skip, but fix's purpose is **finding the structural cause on every invocation to prevent recurrence**. Even for "simple typos / encoding issues", Why 1~3 must be written.

**Recurrence pre-check (first step of Step 1)**:
1. `Grep` failed-attempts.md + rules files for prior records of the same pattern
2. If a prior record exists → **classify as "Nth recurrence"** → include in Why analysis "why prior fixes were ineffective"
3. If the rule already exists but wasn't followed → **do not stop at "existing rule not followed"; strengthen the rule** — rewrite rule text to be more specific/explicit, or design an enforcement mechanism (hook, PreToolUse guard). "Existing rule wasn't followed" is not a conclusion; the goal is **to analyze why it wasn't followed and make it followable**

**Confirm existing rule coverage (CRITICAL — do not duplicate rules in fix.md)**:

The following rules apply automatically before entering the fix procedure (rules/ is always_on). Re-adding them to fix.md creates location errors and duplication:

- `ask-user-question.md` "Forbid arbitrary action on unclear instructions" — when user instructions/statements admit multiple interpretations, AskUserQuestion is required
- `common.md` "Cross-verify state from multiple sources" — do not conclude from a single statement/output; verify at least 2 sources
- `common.md` "Don't guess existing code's purpose/behavior — read it" — verify against primary sources (code, API, files)
- `common.md` "Glob/Grep before claiming absence/necessity" — claims of "doesn't exist / is needed" must follow code verification

**If Why analysis identifies the above rules as root cause, the rules themselves do not need to be modified** — go deeper with Why 4-5 to ask "why was that rule ignored in the fix flow?". If the answer is "fix procedure forces a reactive flow" or "existing rules aren't applied automatically", do not trap the rule inside the fix skill — record it as a recurrence in failed-attempts.md (next candidate for hook automation).

Don't stop at the direct cause. Dig at least **3 levels deep**:

```
Why 1: What went wrong? (symptom — the immediate mistake)
Why 2: Why did I make that decision? (judgment — missing knowledge/rule)
Why 3: Why was that knowledge/rule missing? (structural — skill/rule gap)
```

- Fixing only Why 1 = patching a symptom. It recurs in a different form.
- Why 2-3 reveal **structural causes** (platform ignorance, DRY violation, etc.) — these go into rules/skills.
- Search for the responsible **skill/rule/hook** files (Grep/Glob)

**Completion gate — do NOT proceed to Step 1.5 until ALL of these are true:**
1. Each issue has **Why 1, Why 2, Why 3, Why 4, Why 5** written out explicitly — stopping at Why 3 fails the gate. Why 4 = "why it wasn't followed (procedural/structural defect)", Why 5 = "where that defect originates (skill flow, missing automation, etc.)"
2. Why 5 identifies a **specific target** (skill, rule, hook, agent prompt, project config, etc.) to fix
3. No AskUserQuestion or implementation actions during Step 1 — analysis only

### 1.5. Action plan per Why (MANDATORY — required before entering Step 2)

**Iterate over all Whys and explicitly enumerate the action for each.** All entries in this list must be executed in Step 2 before Step 3 can proceed.

```text
| Why | Target file | Action |
|-----|-------------|--------|
| Why 1 | (current issue — resolved in Step 3) | Step 3 Resume |
| Why 2 | git.md | Add rule: "Forbid alternative command selection on failure" |
| Why 3 | failed-attempts.md | Record 2nd recurrence |
| Why 4 | fix/SKILL.md | Strengthen Checkpoint |
| Why 5 | fix/SKILL.md | Add Step 1.5 (this change) |
```

**Action types**:
- Edit/Write → execute in Step 2
- failed-attempts.md recording → execute in Step 2 (mandatory on recurrence)
- hook design/creation → execute in Step 2 (when escalation applies)
- Step 3 Resume → execute in Step 3

**Step 2 Checkpoint verifies that every row in this table is completed.**

### 2. Prompt Improvement (Prevent Recurrence) — never skip

**Step 2 execution gate (HARD STOP)**:
If Step 1 produced even one Why, Step 2 is **mandatory**. "Trivial, so no rule changes" is forbidden. You must perform at least one Edit/Write on the target file(s) identified by Why analysis before Step 3 can proceed. Zero Edit/Write = Step 2 not executed = procedure violation.

| # | Don't | Do |
|---|-------|-----|
| 1 | Write Why as inline text and skip Step 2 | Edit/Write every target file identified by Why |
| 2 | Assume "current issue is resolved, so Step 2 is unnecessary" | Resolving current issue = Step 3, recurrence prevention = Step 2. Both are mandatory |
| 3 | Shorten Step 2 in later fixes within a chain | Every /fix call is the same quality. No shortening by call count |

"Prompt" = any persistent text that influences Claude's behavior. Priority (check in order — **stop at the first match**):

| Priority | Target | Condition | Example |
|----------|--------|-----------|---------|
| **1st** | **Skill** (`~/.claude/skills/`, `.claude/skills/`) | Skill procedure incomplete or wrong | Fix procedure step missing |
| 2nd | **Rule** (`~/.agent/rules/`, `.claude/rules/`) | Behavior rule missing or insufficient | Add to failed-attempts.md |
| 3rd | **Sub-agent** (`.claude/agents/*.md`) | Agent prompt missing constraint | Add rule to agent description |
| 4th | **Memory** (`memory/*.md`) | Context/reference info missing | Add project/reference memory |
| 5th | **CLAUDE.md / AGENTS.md** | Project-level instruction gap | Add section |
| 6th | **Hook** (`settings.json` hooks) | Automation needed for repeated mistakes | Add PostToolUse hook |

**Use Do & Don't table format (MANDATORY for 2+ recurrences)**:
When adding or strengthening rules, use the **Do & Don't table** instead of prose. Placing forbidden patterns (Don't) next to correct alternatives (Do) raises scan speed and compliance. For rules that have recurred 2+ times, switching to a table is required.

```markdown
| # | Don't | Do |
|---|-------|-----|
| 1 | {violation pattern} | {correct pattern} |
```

When fixing:
- **Skill is 1st priority** — if the problem is a skill's incomplete procedure, fix the skill. Don't skip to failed-attempts.md
- **If Why 3's conclusion is "missing procedure/rule"**: first look for an existing skill that owns that procedure. If a skill owns it, fix the skill → then the rule file
  - Example: "no move rule exists" → adding a move rule to the archive skill is the 1st priority; rule-management.md is 2nd
- **If the fix skill's own procedural defect is the cause**: fix/SKILL.md is also a target — do not grant itself an exception
- Rule location must be confirmed via **AskUserQuestion**
- failed-attempts.md recording is **only for cases not covered by higher-priority targets** — no duplicate recording if root cause is already reflected in a skill or prompt

**Escalation on recurrence** (same pattern 2+ times):
- If a rule addition can't prevent the 1st recurrence, escalate to a stronger mechanism:
  - **1st time**: add a rule (Do & Don't table + HARD STOP)
  - **2nd time**: **consider creating a hook** — design a PreToolUse/PostToolUse pattern. Refine the rule, but design the hook in parallel
  - **3rd time**: **hook creation required (HARD STOP)** — rules alone are confirmed insufficient. Implement the hook + **fully remove that section from failed-attempts.md** (move to `~/.agents/.bak/` — no annotations or ~~strikethrough~~; the goal is context savings)
  - **Recurrence after hook**: if the hook didn't block it → strengthen the hook pattern + record in `failed-hooks.md` (a separate file, not failed-attempts.md)

**`--plan` mode**:
- Emit only the list of target files + a preview of changes per file
- Do not perform Edit/Write (but **plan artifact .md saving is performed**)
- **Stop here after Step 2** — do not proceed to Step 3 or 4
- After reporting the plan, wait for user response. On "apply" approval, perform Edit/Write and proceed to Step 3

**Plan artifact .md saving (MANDATORY in `--plan` mode)** — applies `vibe-coding.md` "Artifact path rules":

| Environment detection | Save path | Filename |
|---------------------|-----------|----------|
| `{workspace}/.ralph/docs/generated/` exists | `.ralph/docs/generated/plan-fix-{slug}.md` | slug = key keyword (e.g., `consolidate-next-action`) |
| `{workspace}/.omc/plans/` exists (no Ralph) | `.omc/plans/plan-fix-{slug}.md` | same |
| Neither exists | Confirm path via AskUserQuestion | — |

**Chat output format** (after saving artifact):
```text
Plan saved: <absolute path>

Key summary:
- N target files
- Key changes ...

See the file above for details. Reply "apply" or with feedback.
```

Do not re-dump the entire plan body into chat — chat shows only path + 3-5 line summary.

| # | Don't | Do |
|---|-------|-----|
| 1 | Output --plan results only in chat and stop | Save .md to `.ralph/docs/generated/` or `.omc/plans/` and report the path |
| 2 | Save the artifact but also dump the full plan body in chat | Chat = path + 3-5 line summary only |
| 3 | Decide "it's just a draft, no need to save" | --plan = artifact. Always save |

**Checkpoint (MANDATORY before proceeding to Step 3; in `--plan` mode, only after approval):**
**Verify that the targets identified at every Why level (1~5) were actually modified before completing Step 2:**
1. **Iterate over Why 1~5** and enumerate the target file paths each level identified (skills, rules, agents, etc.)
2. For each file, confirm that Edit/Write was performed in this Step 2
3. If any target was not modified, **do not advance to Step 3 — finish the modifications first**
4. **Do not pass on "existing rule not followed" alone without modifications** — if a rule existed but wasn't followed, strengthen its text to be more specific/explicit, or add examples / forbidden patterns. "Just naming the rule path" and moving on permits the same mistake to recur
5. **Do not check only Why 3 while omitting Why 1-2 targets** — if Why 2 says "X causes misunderstanding", X must be modified
6. **Verify escalation artifacts**: if this fix is the Nth recurrence, confirm the artifact for that count was actually produced in Step 2. 2nd time = hook design doc, **3rd time = hook script file + settings.json registration**. Missing artifact = Step 2 incomplete

### 3. Resume Original Work (fix-2)

**This is the most important step.** The user's original request must be completed — not just the fix itself.

**3-0. Infer user intent (MANDATORY — execute before any mechanical task listing)**:
From the user's /fix message (skill args) and session context, infer **"what outcome does the user want"**:
1. **Re-read /fix args**: identify which words the user emphasized and what they said "must be done"
2. **Cross-reference session context**: what is the current state of that work? Code modified but not verified? Not deployed? Not committed?
3. **Pin down the concrete meaning of "resolve / complete / proceed"**: the same word means different things in different contexts. "Resolve" = code fix? Through verification? Through deployment? — infer from session state
4. **State the inferred result as one sentence**: "What the user wants: {concrete action}". This sentence is the basis for all subsequent task listing
5. **Specify verification medium (HARD STOP — prevent scope reduction)**: copy the medium the user saw (URL, API endpoint, screen path, command output) verbatim. In fix Step 3 verification, **reproduce via that medium directly**. No detoured verification.

| User message | Verification medium (use verbatim in Resume) |
|--------------|----------------------------------------------|
| "/api/system-log?limit=30: HttpError" | `curl <APP_URL>/api/system-log?limit=30` (with cookie) — verify response status/body |
| "500 on the login screen" | Playwright on sign-in screen → submit → verify response |
| "Error when clicking X button on page Y" | Playwright on page Y → click X button → verify result |
| "File upload failure" | Reproduce with the same file + same form data via multipart POST |

Example: `/fix start with Critical` + session shows code modified but not verified → "What the user wants: Playwright verification that the modified code actually works" + verification medium: the screen path the user reported (e.g., `/dashboard/sso-callback`)

6. **Recognize user dismissal signals (HARD STOP — do not re-raise secondary facts)**: items the user has explicitly dismissed must **not be re-raised** in fix Step 1 verification / Step 3 reporting. Focus on the core work only.

**Dismissal trigger keywords**:

| User expression | Interpretation |
|-----------------|----------------|
| "Just force push over there" | That remote/branch state is out of verification scope |
| "Forget about that" / "That's done" | Item handled or irrelevant — do not raise |
| "Don't worry about it" / "Skip" | That fact is irrelevant to the core work |
| "Already did it" / "Handled" | User handled it directly — no re-verification/re-reporting |
| "Why do you keep bringing up X" / "Again with X" | Annoyance at secondary mention of X in the prior response — return to core immediately |

| # | Don't | Do |
|---|-------|-----|
| 1 | Re-report dismissed items under the pretext of "fact verification" | Verification is limited to the core work medium. Even if dismissed items appear in git fetch/grep, exclude them from report text |
| 2 | Statements that "prove the user's guess wrong" | Do not fabricate something the user never said and refute it. Quote only what the user said |
| 3 | After dismissal, re-mention the same fact "for accuracy" once more | One dismissal = permanent silence. Same in all follow-up responses |
| 4 | Continue mentioning X despite annoyance signals ("damn", "why X again", "wtf") | Annoyance signal = ↑ ask priority + immediate return to core. Zero mention of dismissed items from the next response |

**Self-check (every time before writing a response)**:
1. Did the user dismiss any item in the prior N messages?
2. If so, does that item appear in this response's text?
3. If it appears, is it directly tied to the core work? — remove if not essential to the core work

**3-0.5. Re-call rejected AskUserQuestion (HARD STOP)**:

If the turn immediately before fix had **AskUserQuestion rejected + /fix triggered** as the flow, then after fix Resume removes the reject cause, **re-calling ask with improved options** is part of Step 3's deliverable. Do not autonomously decide "end without re-call".

#### Reject cause classification

| Reject reason | Can fix resolve it? | Resume handling |
|---------------|---------------------|-----------------|
| ask **secondary issue** (visual noise, stale context, inaccurate option description) | ✅ Yes | Remove cause in fix Step 2/3 → **re-call ask with improved options** |
| ask **intent rejection** (user denies the very intent to proceed) | ❌ No | No re-call. End with fix completion report |
| ask **option mismatch** (the options themselves are wrong) | ✅ Yes | Restructure options → re-call ask |
| ask **timing mismatch** (preconditions unmet) | ✅ Yes | Satisfy preconditions → re-call ask |

#### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | AskUserQuestion rejected → fix done → autonomously decide "end without re-call" | If fix resolved the reject cause, **re-call with improved options**. Reject ≠ permanent end |
| 2 | Default-interpret the reject reason as "user rejects the very intent" | Determine the reject reason from the user's immediate message (/fix args, annoyance signals). Distinguish intent rejection vs secondary issue |
| 3 | "We already asked once; let the user decide on their own" | A secondary issue that fix resolved leaves the user able to decide via ask. ask = decision trigger |
| 4 | Re-call by copy-pasting the rejected options verbatim | Reflect the reject cause in description (e.g., note "Summary cleaned up" → attestation the user can verify) |
| 5 | Avoid ask out of "re-call = nagging" thinking | Reporting reject-cause resolution + re-calling ask is not nagging. It restores user decision authority |

#### Self-check (every time before entering fix Step 3)

1. Was there an **AskUserQuestion call in the turn right before this fix trigger**? → If no, skip this procedure
2. Was that AskUserQuestion **rejected**? (`The user doesn't want to proceed with this tool use`) → If no, skip
3. Determine reject reason from immediate user /fix args + annoyance signals → classify as intent rejection vs secondary issue
4. If it was a secondary issue and fix resolved it → include an **ask re-call** in fix Step 3 (part of the deliverable)
5. In the re-call's option descriptions, **state the fact fix resolved** as attestation (e.g., "Summary cleanup complete (only 1 active)")

#### Violation case (2026-05-17)

PR #146 Step 8 next-action ask posted → user rejected + `/fix why does the summary keep growing` called → fix cleaned up to 1 Summary (from 3) → fix completion report autonomously decided "end without re-call". User pointed out: "When the immediate ask is rejected, fix should ask again with the improved direction". This Step 3-0.5 was added to resolve it.

**3-1. Resume existing in_progress tasks (HARD STOP)**:
If TaskList had in_progress/pending entries before entering fix, fix Step 3 must **continue executing those tasks** before fix can end. "Already in TaskList, so no need to separate" is not resume — **actual execution** is resume.

| # | Don't | Do |
|---|-------|-----|
| 1 | End fix saying "existing tasks are in TaskList, so no separation needed" | Continue executing existing in_progress tasks in fix Step 3 |
| 2 | Resume only fix-2's subject scope and ignore existing tasks | fix-2 + existing in_progress tasks are **all** resume targets |
| 3 | Shorten resume with "login success = verification complete" | Login is a prerequisite. Run each verification item (countdown, permissions, etc.) individually |
| 4 | After completing 1 Resume item → switch to AskUserQuestion "what's next?" | **Complete all Resume items sequentially**. Completing 1 is not a switch point — start the next item immediately |
| 5 | Sub-task completed → "this task is done, let's take a breath" | After sub-task completes, immediately move to the next item of the Resume task. AskUserQuestion only **after all Resume items complete** |

1. Re-read `fix-2` subject — it contains the full list from the initial request to the immediately preceding action
2. **Classify done/not-done**: confirm the current state of each task (done, in progress, not yet started)
3. **Identify missing tasks**: list the correct procedure step by step, compare with what actually ran, and find **skipped intermediate steps**. Example: in "create issue → branch → implement → PR", if issue creation was skipped, that is the missing task
4. Register the not-done + missing tasks and execute sequentially
5. Produce each task's **original deliverable** (e.g., classification table, plan document, deployment result, checklist update)
6. Verify after completing all tasks

**Step 3 constraints**:
- **Destructive commands require AskUserQuestion even during fix** — `git checkout -- .`, `git reset --hard`, `rm -rf`, etc. must not be executed without approval even under the pretext of "restoring original work"
- **Do not reinterpret user instructions** — if fix feedback is ambiguous, confirm via AskUserQuestion. Do not flip interpretations like reading "don't lose the changes" as "delete the changes"

**Anti-patterns**:
- "Script creation complete. Run it later" — fix's goal is **completing the original work**, not improving tooling. Tooling is the means.
- **Only reporting "X is now possible" and stopping** — register the not-done task via TaskCreate and **execute it immediately**. A status report is a precondition for execution, not the result.
- **Do not assume "original work already ended, so Resume is unnecessary"** — original work = the **deliverable** the user wanted, not "the act of invoking a skill/command". Even if an upper workflow (N steps) was invoked, if one intermediate step was missed, that step's deliverable does not yet exist = original work incomplete. After fix, the missed step must **be run now**.
- **Do not assume "session ended, so re-running is impossible"** — most skills are stateless. Only the missed step needs to be run standalone. There's no need to redo the entire upper workflow.

**Forbid verification scope reduction (HARD STOP — 2nd recurrence prevention)**:

Do not use a different medium than what the user reported as a detour. Reproduce via the "verification medium" specified in fix Step 3-0.

| # | Don't | Do |
|---|-------|-----|
| 1 | User reports "/api/X error" → substitute verification with login success / other APIs working | Directly call the user-seen `/api/X` via curl/Playwright → verify response status/body |
| 2 | User reports "permission error on screen Y" → after DB ALTER, only confirm admin login | Enter the user-seen screen via admin session → reproduce the same interaction → confirm whether the permission error recurs |
| 3 | One step (login) passes → assume subsequent steps (permission check / page entry / API call) are OK | Run each subsequent step **individually** for every step in the user-reported medium |
| 4 | Assume "logs are clean → normal" | Logs clean + **the user-medium reproduction response** both required |

**Self-check (every time before reporting verification complete)**:
1. Did you copy the user's fix-args medium (URL/API/screen) accurately?
2. Did you call/reproduce directly via that medium?
3. Did you compare the response with the user-reported error to confirm "normal" vs same/similar?
4. Did you avoid detoured verification (different URL, different screen, logs only)?

**Violation case (2026-05-09)**: In fix #93, while diagnosing "/api/system-log?limit=30 error", only admin login + integrated dashboard load were checked and reported as "ALTER verification complete". In reality, calling the system-log API itself reproduced the permission error → user re-pointed it out, starting fix #102.

**Step 3 mandatory self-questions (MANDATORY before marking fix-2 complete)**:
1. Did Why analysis identify a "skipped intermediate step"? → If yes, that step is fix-2's **immediate execution target**
2. Can that step **run standalone now (stateless)?** → If yes, run it unconditionally. "Original work is done, skip" is a violation
3. If the missed step is a skill/tool invocation → execute in this fix Step 3 → complete through result handling

### 4. Completion Report + Cleanup

**⚠️ Chained /fix Resume integrated execution gate (HARD STOP)**:

If /fix has been invoked 2+ times in this session, **before** marking fix-* tasks deleted in Step 4, collect **all 🔄 Resume tasks** in TaskList and verify outstanding work.

| # | Don't | Do |
|---|-------|-----|
| 1 | completed→deleted only the current fix's fix-2 | Collect **every** task in TaskList containing the `🔄 Resume` keyword |
| 2 | Ignore and delete a prior fix's Resume that is in_progress | **Split prior Resume's outstanding work into separate tasks** before deleting |
| 3 | Mark each fix complete independently | **Integrate and clean up** outstanding work from all Resumes before bulk-deleting |

**Procedure**:
1. Call `TaskList` → collect every task containing `🔄 Resume` or `Resume`
2. Extract outstanding work from each Resume task's description
3. **Register outstanding work as new tasks** (without the fix-* prefix)
4. Only after new tasks are registered, **bulk-delete all fix-* tasks**

```text
Fix complete:
- Root cause: {what was missing}
- Improvement: {which file was modified and how}
- Current fix: {result of fixing the current issue}
```

**Outstanding-work separation guard (HARD STOP — required before deleting fix-* tasks)**:

If fix-2 (Resume Original Work) contains outstanding work, **separate by medium per status** before deleting fix-* tasks:

#### Medium separation principle (HARD STOP)

| Status | Example | Medium (TaskList vs checklist) |
|--------|---------|--------------------------------|
| Hold (user decision) | "Track B is next session", "Playwright on hold" | **TaskList**: when actionable |
| Partial completion | Track A done, Track B not run | **TaskList**: separate task for Track B |
| Awaiting follow-up verification | Awaiting CI pass, awaiting merge review | **TaskList**: can trigger verification |
| **Awaiting external response (BLOCKED)** | Awaiting owner reply, external API lock, awaiting permission grant | **Register in fix_plan.md hold section (no task)** |
| **Cannot proceed autonomously** | Items that cannot move one step without user decision/external action | **fix_plan.md hold section** |

**Why is BLOCKED forbidden as a task?**
- TaskList = "tracking actionable work" medium. Only register items that can be auto-triggered
- BLOCKED = no external trigger means no progress → tracking it as a task adds no value beyond "still BLOCKED" reports each session
- fix_plan.md hold section = "carry over to next session + trigger when external response arrives" information preservation
- Registering an item in both media only adds sync burden

#### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | Register external-wait items in both a separate task and fix_plan | Register only in fix_plan.md hold section. No task creation |
| 2 | Create a task with subject "[BLOCKED] awaiting reply on xxx" | Use fix_plan.md `## Hold` section in the form `- [ ] [BLOCKED] xxx (... awaiting reply, trigger: ...)` |
| 3 | "Register as task so the user doesn't forget" thinking | fix_plan.md is reloaded at each session start, so it won't be forgotten. The checklist is sufficient |
| 4 | Keep both checklist and task entries to "strengthen safety" | Duplicate media = mismatch risk. Unify to a single medium |

#### Self-check procedure (before deleting fix-3)

1. Re-read fix-2 subject + body → extract the full list of original work
2. Classify each item's status:
   - (a) Done — task completed
   - (b) Actionable hold / partial completion / verification needed — register as a separate task in **TaskList**
   - (c) **BLOCKED (external response/permission)** — register in **fix_plan.md hold section (no task)**
3. fix-* tasks may only be deleted after (b) and (c) are reflected in their media
4. If a wrong BLOCKED task is found → immediately delete + transfer to fix_plan.md

**Violation patterns**:
- fix-2 "resume original work" scope had Track A + B; completed only Track A and marked fix-2 completed → deleted
- Misclassifying a user-held item as "done"
- Losing outstanding-work information for the sake of TODO list cleanliness

**Correct flow** (PR #299 example):
- Before marking fix-2 complete: register Track B (Playwright/ZAP) as a separate task → fix-2 completed → fix-* deleted

**After reporting + outstanding-work separation verified, delete all `fix-*` TODO items created in Step 0** — fix TODOs are temporary session-level tracking only; outstanding work is preserved in separate tasks while only `fix-*` are cleaned up.

## Anti-patterns

- Repeating "already fixed" without actually fixing the root cause
- Patching only the current issue without improving prompts (skill/rule/agent/memory/CLAUDE.md/hook)
- Text response without TodoWrite after /fix activation
- Recording in failed-attempts.md when the root cause is a skill defect (skill fix is 1st priority)
- **Stopping at Why 1** — fixing the symptom without asking Why 2-3 (structural cause)
- **Not cleaning up TODO/Task after completion** — must delete all fix TODOs when done
- **"User is right, so skip"** — even when the user's point is correct, Steps 0~4 must all execute. fix's value is not resolving the current issue but preventing recurrence. "You're right, executing right away" abandons Why analysis + rule modifications
- **"Fixing right now" / "I know the cause, skip"** — Step 1 Why analysis cannot be skipped, whether recurrence or trivial. Recurrence = evidence that prior fix's Why was insufficient, so go **deeper**. "Fix right now" is not a procedure that exists in the fix skill
