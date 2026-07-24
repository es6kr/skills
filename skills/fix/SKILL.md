---
metadata:
  author: es6kr
  version: "0.1.5"
name: fix
description: |
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

- `--plan`: In Step 2, instead of modifying prompts directly, **emit only the modification plan** for user review before execution. Use for complex changes or changes spanning multiple files. **Forced Ask (HARD STOP)**: After saving the plan artifact .md and presenting the summary, you MUST invoke `AskUserQuestion` instead of stopping at plain text, forcing an explicit user decision.
  - **Trade-off-axis questions FIRST, disposition LAST (HARD STOP — applies to ANY /fix flow that authors or promotes a plan artifact, not only `--plan`)**: a generic disposition-only ask (`Apply plan now` / `Refine plan` / `Hold`) is FORBIDDEN when the plan contains Trade-offs rows or unresolved human-review questions (open interpretation notes, "confirm on review" markers). Convert **each** trade-off axis / open review question into its own question object in the `questions` array (one axis per question, max 4 per call — chunk sequential calls when more, never drop the tail), then ask the disposition (`Apply plan now` / `Refine plan` / `Hold`) as the **last** question or a follow-up call. Recurrence source: a promote-completion ask that offered only approve/refine/hold caused the user to re-request the trade-off review manually.
- `--local`: Scope Step 2 rule modifications to the **workspace-local** or **project-local** rule directory only. Use when the rule applies to a specific workspace (e.g., `~/ghq/github.com/<org>/`) or a specific repo, not globally.
  - Resolution order (Step 2 picks the innermost matching location):
    1. **Project-local** — `<repo>/.claude/rules/` if cwd is inside a git repo
    2. **Workspace-local** — nearest `.claude/rules/` walking up from cwd (typically `<workspace-root>/.claude/rules/`)
    3. **Fallback** — if neither exists, ask the user whether to create one (do NOT silently fall through to global `~/.agents/rules/`)
  - **Do not** write to `~/.agents/rules/` when `--local` is set. Global-rule cost is context-inflation on every session; `--local` opts into scoped protection.
  - Rule-file location + strength still respect the `rule-management.md` location-plus-method dual-axis ask when the scope choice within the local set is ambiguous (project vs workspace).

## Topic Dispatch

**When this skill is invoked with a topic specifier (e.g., `/fix step3-resume` or `Skill("fix", "step3-resume")`), load and follow only the matching topic file. Do not echo the Topics table or summarize other topics in the response.** The Topics table below is an index — for a normal `/fix` invocation, execute the Procedure below and Read each step's topic file when you reach that step.

## Topics

The core procedure (Step 0 → 4) lives below. Heavy step detail is split into topic files — **Read the matching topic before executing that step**.

| Topic | Description | Guide |
|-------|-------------|-------|
| step2-improvement | Step 2 detail: 4-filter gate, escalation matrix, `--plan`, Checkpoint | [step2-improvement.md](./step2-improvement.md) |
| step3-resume | Step 3 detail: intent inference, reject re-call, verification guard | [step3-resume.md](./step3-resume.md) |
| step4-wrapup | Step 4 detail: report format, medium separation, status-based prune | [step4-wrapup.md](./step4-wrapup.md) |
| behavior-discipline | Destructive-command gate, multi-repo tracking, chained-fix deps, anger→TDD switch | [behavior-discipline.md](./behavior-discipline.md) |

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
  { content: "📋 Wrap-up: report + task pruning", status: "pending" },
])
```

**Forbidden pattern** (data loss):
```text
# Ignoring existing tasks and registering only 4 fix-* → all existing tasks vanish
TodoWrite([
  { content: "🔍 fix: ...", status: "in_progress" },
  { content: "🔧 Root cause fix", status: "pending" },
  { content: "🔄 Resume original work: ...", status: "pending" },
  { content: "📋 Wrap-up: report + task pruning", status: "pending" },
])  # ❌ Existing task data is lost
```

**Default form (when no existing tasks — MINIMUM 5+ GRANULAR STEPS HARD STOP)**:

Every `/fix` task registration MUST contain at least 5+ (typically 6~8) granular steps. Collapsing the workflow or Resume phase into 4 or fewer generic items is strictly forbidden (`HARD STOP`).

```text
TodoWrite([
  { id: "fix-0", content: "🔍 fix: {user feedback summary} — 5-Why root cause analysis", status: "in_progress" },
  { id: "fix-1", content: "🔧 Prompt improvement plan (Step 1.5 Action Plan table & AskUserQuestion approval)", status: "pending" },
  { id: "fix-2", content: "🔌 Plugin/Dependency installation (if required) & environment parity check", status: "pending" },
  { id: "fix-3", content: "🛠️ Skill/Tool invocation & official autoloader execution (view_file IsSkillFile)", status: "pending" },
  { id: "fix-4", content: "🧪 Empirical Fix Verification (verify fix actually works in current execution)", status: "pending" },
  { id: "fix-5", content: "🔄 Resume original work: {granular breakdown step 1}", status: "pending" },
  { id: "fix-6", content: "🔄 Resume original work: {granular breakdown step 2}", status: "pending" },
  { id: "fix-7", content: "📋 Wrap-up & AskUserQuestion next options", status: "pending" },
])
```

- **Antigravity (Gemini) Users**: Create or update the `task.md` artifact representing the TODO list above. This fulfills the TodoWrite requirement.
- **Claude Code with `TaskCreate`/`TodoWrite` unavailable (HARD STOP — mechanical gate, not advisory)**: `ToolSearch` returning no match is NEVER sufficient diagnosis on its own — it cannot distinguish "temporarily disconnected" from "disabled in this context". **This gate blocks Step 0 completion**: before falling back to the CLI medium below, you MUST actually execute a direct `TaskCreate` call (not merely `ToolSearch` it) at least once per session, and again at the start of any `/fix` call after a prior direct call returned a disconnect-class error (connectivity can change mid-session). A `ToolSearch`-only check does NOT satisfy this gate — the gate requires the call attempt itself, because only the call's error message distinguishes the two cases below.
  - Error mentions disconnect/MCP-unreachable → treat as recoverable — retry at the start of each subsequent `/fix` call in this session
  - Error is **"exists but is not enabled in this context"** → this is a context/settings gap, not connectivity. **Report this to the user in the same turn, in plain text, before or alongside the fix-continuation work** — do not silently normalize the workaround as if no explanation were owed. State it plainly: "`TaskCreate` exists but is disabled in this session's context — this may be fixable in Claude Code settings." Silently working around it for an entire session without ever surfacing this is itself a Step 0 violation.
  - Only after this diagnosis, if no task tool is usable this turn, use the `claude-task` CLI (`todowrite` skill's `claude-task` topic — `claude-task --env agent add/list/update`) to track fix-0/1/2/3, updating status at every step transition. This CLI persists to `~/.agents/tasks/default/`, a fixed directory that survives session/scratchpad-path changes — **do NOT use the session scratchpad directory** for this tracking; the scratchpad path changes across sessions/compacts and silently drops its contents (case history: failed-attempts.md "scratchpad ephemeral task loss"). Narrating steps in prose only, with no durable record, does not satisfy the "register tasks" requirement — `claude-task` is an interim substitute, not a replacement goal, for `TaskCreate`.
  - **Self-check (before relying on the `claude-task` fallback in any `/fix` call this session)**: (1) Have I made an actual `TaskCreate` call attempt this session (not just `ToolSearch`)? → If no, make one now. (2) Did that call's error say "not enabled in this context"? → If yes, have I told the user this in plain text yet this session? → If no, say so now, in this turn. (3) Am I about to write fix-tracking state to the scratchpad directory instead of `claude-task`? → Forbidden — scratchpad is session-scoped and ephemeral, not a durable-tracking medium.

- In Resume tasks (`fix-5+`), list **the initial request plus everything in progress including the immediately preceding action**.
  - **Multi-substep Resume Breakdown (MINIMUM 5+ STEPS HARD STOP)**: When resuming multi-stage or complex work, **break Resume down into explicit substeps (`fix-5`, `fix-6`, `fix-7`, etc.)** instead of flattening it into a single line. This ensures sequential execution proceeds through all remaining phases without dropping intermediate actions (such as plugin install, skill call, code edit, empirical verification, or post-plan decisions).
  - Example: `fix-2: Plugin install`, `fix-3: Skill invocation`, `fix-4: Empirical fix verification`, `fix-5: Code implementation`, `fix-6: Verification & Walkthrough`
- **Multi-question `questions` Array Rule (HARD STOP)**: When invoking `AskUserQuestion` to address multiple decision axes or questions, **NEVER lump them into a single question object with compound text**. Build an array of discrete question objects in `questions: [{question: Q1, options: [...]}, {question: Q2, options: [...]}]` (one question per decision axis, up to 4 questions per call).
- **[Measure 2] Dependency and Reference State Declaration (MANDATORY)**: When registering `fix-2`, you must explicitly declare the **preconditions (Depends on)** and the **base commit state (Reference commit)** required for the `Resume` task to run safely.
  - *Format Example*: `🔄 Resume original work: {summary} (Depends on: {preconditions}, Reference commit: {commit_sha})`
- fix-2 = "Complete the original work with the revised approach" — the goal is **the deliverable the user originally requested**, not skill/rule changes themselves
- Step 0 is **the first tool call** after /fix activation. Text output before TodoWrite = violation.

### 1. Root Cause Analysis (5-Why depth)

**Environment Detection (MANDATORY)**: Before modifying any rules or settings file, detect the current platform via runtime environment variables:
- **macOS**: Check `$__CFBundleIdentifier` — `com.google.antigravity` = Antigravity, `com.microsoft.VSCode` = VS Code, `com.todesktop.230313mzl4w4u92` = Cursor
- **Windows**: Check `$env:ANTIGRAVITY_AGENT` — `1` = Antigravity. Also `$env:ANTIGRAVITY_EDITOR_APP_ROOT` for confirmation.

Routing table by detected environment:
- **Antigravity (Gemini)**:
  - Permissions config: Guide user to edit `~/.gemini/config/config.json`. Do not edit it directly.
  - Behavioral rules: Edit `~/.gemini/GEMINI.md`. Never touch shared `~/.agents/rules/` or Claude Code settings.
- **Claude Code** (neither Antigravity env var is set):
  - Permissions config: Edit `~/.claude/settings.json`.
  - Behavioral rules: Edit `CLAUDE.md` or `.claude/rules/`.

Do NOT use file-existence checks to detect the environment — both `.gemini/` and `.claude/` coexist on the same machine.

**No trivial exception (HARD STOP)**: Even when the symptom is fixable with a 1-line change, 5-Why analysis and the entire step-by-step procedure are mandatory. Bypassing or skipping any steps (Step 0 to Step 4) when `/fix` is triggered is strictly forbidden. Even for "simple typos / encoding issues / minor file copies", the procedure must be executed step-by-step.

| # | Don't | Do |
|---|-------|-----|
| 1 | Skip `/fix` step-by-step procedure when the correction seems simple or obvious | Always execute Step 0 (TodoWrite/task.md) first, followed sequentially by Step 1 (5-Why), Step 1.5, Step 2, Step 3, and Step 4 |
| 2 | Directly modify files or execute commands on a `/fix` trigger before initializing the task checklist | Ensure `task.md` or `TodoWrite` is initialized as the very first tool call in the turn |

**Recurrence pre-check (first step of Step 1) — MANDATORY 2-stage**:

**Stage 0 — RAG semantic search (if RAG receiver available)**:
- If the current environment has a registered RAG search tool (an MCP store with a find-style tool), call it with the fix pattern's core keywords **before** the grep step
- Semantic search catches paraphrased recurrences that exact-match grep misses (one pattern surfaces under different wordings)
- If RAG returns one or more archived/historical hits with similar semantic, classify as "Nth recurrence" even if the exact phrasing does not grep-match
- Receiver tool name is vendor-agnostic — `mcp__<vendor>__*-find` style. Caller picks whichever RAG store is registered in the current environment

**Stage 1 — exact-match grep (always run)**:
1. `Grep -r ~/.claude/skills/cleanup/data/` for prior records of the same pattern — **recursive search covers both HOT (`failed-attempts.md`) and archive (`archive/*.md`)**. Also grep `~/.agents/rules/*.md`.
2. If found in **HOT only** → classify as "Nth recurrence" → include in Why analysis "why prior fixes were ineffective"
3. If found in **archive only** → **invoke `Skill("cleanup", "fa-prune")` Step 7 restoration procedure** (cut section from archive → paste into HOT with recurrence label). Without restoration, the escalation rule (1st=rule / 2nd=hook review / 3rd=hook required) is silently invalidated.
4. If found in **both** → already in HOT (no restoration needed); just add recurrence note
5. If the rule already exists but wasn't followed → **do not stop at "existing rule not followed"; strengthen the rule** — rewrite rule text to be more specific/explicit, or design an enforcement mechanism (hook, PreToolUse guard). "Existing rule wasn't followed" is not a conclusion; the goal is **to analyze why it wasn't followed and make it followable**

**Why RAG + grep both (not RAG alone)**:
- RAG: semantic — catches paraphrased recurrences, misses exact-token rules
- grep: exact — catches rule violations, misses semantic recurrences
- Both required for full coverage. RAG-only = misses "existing rule wasn't followed" detections. grep-only = misses "Nth recurrence with different phrasing" detections

**Confirm existing rule coverage (CRITICAL — do not duplicate rules in fix.md)**:

The following general principles apply before entering the fix procedure. If your environment already enforces them as always-on rules, do not duplicate them into fix's own body — that creates location errors and duplication:

- **Forbid arbitrary action on unclear instructions** — when user instructions/statements admit multiple interpretations, AskUserQuestion is required (do not act on a guess)
- **Cross-verify state from multiple sources** — do not conclude from a single statement/output; verify at least 2 sources
- **Don't guess existing code's purpose/behavior — read it** — verify against primary sources (code, API, files)
- **Glob/Grep before claiming absence/necessity** — claims of "doesn't exist / is needed" must follow code verification

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

**This table MUST be physically emitted in your visible output before any Step 2 Edit/Write.** Knowing the targets mentally from the Why analysis is NOT a substitute — the table is the forcing function that surfaces "one Why → multiple fix spots". Skipping the emission silently leads to partial corrections (you fix the one spot you remember and miss the others).

**Iterate over all Whys and explicitly enumerate the action for each.** All entries in this list must be executed in Step 2 before Step 3 can proceed.

```text
| Why | Target file : spot | Action |
|-----|--------------------|--------|
| Why 1 | (current issue — resolved in Step 3) | Step 3 Resume |
| Why 2 | <rule-file> : staging section | Add rule: "Forbid alternative command selection on failure" |
| Why 3 | epic-bundle.md : Step 2 group line | by-theme → by-source-PR |
| Why 3 | epic-bundle.md : body template | per-PR section header |
| Why 3 | epic-bundle.md : Don't/Do table | add row |
| Why 3 | epic-bundle.md : self-check | add item |
| Why 5 | fix/SKILL.md : Step 2 Checkpoint | Add gate item |
```

**Multi-spot enumeration rule (HARD STOP)**: a single Why often maps to **multiple spots inside one file** (procedure step + output template + Don't/Do table + self-check). Enumerate **one row per spot**, not one row per file. "Target file : spot" granularity is mandatory — a single `epic-bundle.md` row that hides 4 spots is what produces "fixed the output but missed the procedure" partial corrections.

**Action types**:
- Edit/Write → execute in Step 2
- failed-attempts.md recording → execute in Step 2 (mandatory on recurrence)
- hook design/creation → execute in Step 2 (when escalation applies)
- Step 3 Resume → execute in Step 3

**Gate into Step 2 (HARD STOP — symmetric with the Completion gate into Step 1.5)**: do NOT perform any Step 2 Edit/Write until the table above is emitted in your visible output. The Completion gate already blocks entry *into* 1.5; this gate blocks exit *from* 1.5 into Step 2. Without it, a Step 1 → Step 2 fast-path skips the table.

**Step 2 Checkpoint verifies that every row in this table is completed.**

### 2. Prompt Improvement (Prevent Recurrence) — never skip

If Step 1 produced even one Why, Step 2 is **mandatory**. Default medium = `feedback` memory (1st-2nd recurrence); rule-file Edit only when the **4-filter gate** passes (3rd+ recurrence); hook implementation at 4th+ recurrence with a deterministic pattern. Minimize always-on rule context.

**Language gate (HARD STOP — mechanical, run before every skill-file Edit/Write in this step, not just once per fix call)**: this rule has already recurred more than once (search failed-attempts.md for the "skill language mismatch" pattern) precisely because it lived only as prose in the "Confirm existing rule coverage" bullet list in Step 1 — easy to read and still skip under conversation-language momentum. Before each individual Edit/Write to a skill file (`SKILL.md`, topic `.md`, `resources/*`) in this step: (1) run `head -5 <target-file>` or `Grep "^description:"` on the skill's `SKILL.md` to get its language, (2) write the new content in that language — if the skill is English-described and the content you're about to add contains locale-specific illustration, abstract it (describe the concept, don't insert literal non-English vocabulary) rather than translate-then-insert. This check runs **per file**, not once — a fix touching 3 skill files needs 3 checks, since they can differ in language. `~/.claude/skills/hook-kit/resources/block-skill-language-mismatch.sh` (PreToolUse:Edit/Write) is a backstop, not a substitute for this check — do not rely on the hook catching it after the fact.

**Skill-First Improvement Discipline (HARD STOP)**: When the root cause originates from a skill procedure, topic output gap, or template defect, modifying the skill file itself (`skills/<name>/SKILL.md` or `topics/*.md`) is MANDATORY. Do NOT default to adding rules exclusively into global `GEMINI.md` or `CLAUDE.md`. Global rule files are reserved for universal behavioral constraints (3rd+ recurrence); skill procedure defects must be resolved directly within the target skill.

**Rule/Skill Fix Execution Rule (HARD STOP)**: When a `/fix` task updates a skill/rule file that specifies a mandatory tool or skill call (such as `receiving-code-review`), simply editing the file text is incomplete — executing the mandated skill protocol on the active target codebase or artifact is MANDATORY before declaring the task completed.

**Prompt Improvement Plan AskUserQuestion Gate (HARD STOP)**: Before applying file edits to any skill file (`skills/**/*.md`) or rule file (`rules/**/*.md`), **you MUST emit the Step 1.5 Action-plan table and call `AskUserQuestion` presenting the proposed prompt modifications for user confirmation**. Modifying prompt/skill/rule files without first presenting the modification plan via `AskUserQuestion` is strictly forbidden.

**Read [step2-improvement.md](./step2-improvement.md) before executing** — it holds the 4-filter gate, medium-priority table, escalation matrix, no-stage-skipping Don't/Do, `--plan` mode, and the Step 2 Checkpoint (verify every Why-level target from the Step 1.5 table was actually modified). Do not advance to Step 3 until the Checkpoint passes.

### 2.5 Plugin/Dependency Installation Step (MANDATORY HARD STOP)

If the updated or referenced skill/rule specifies a plugin or dependency (e.g. `superpowers` plugin `obra/superpowers`, `cc-plugin`, or external tools), **you MUST execute the plugin/dependency installation command** (`claude plugin add <plugin>` or equivalent) in this step before proceeding. Skipping plugin installation and proceeding to doc edits or resume is strictly forbidden (`HARD STOP`).

### 2.6 Skill/Tool Invocation Step (MANDATORY HARD STOP)

If the updated or referenced skill/rule mandates a skill or tool call (e.g. `receiving-code-review`, `code-review`, `AskUserQuestion`), **you MUST execute the tool call / autoloader invocation (`view_file` on SKILL.md with `IsSkillFile: true` or native tool execution)** in this step. Updating doc text without physically triggering the tool/skill invocation is strictly forbidden (`HARD STOP`).

### 2.7 Empirical Fix Verification Step (MANDATORY HARD STOP)

Before moving to Step 3 Resume, **you MUST run concrete, empirical verification** demonstrating that the fix implemented in Step 2 actually works in the active session and codebase (e.g., verifying task checklist step creation, running tests, or verifying command exit codes). Relying on text edits alone without empirical verification is strictly forbidden (`HARD STOP`).

### 2.8 Active Task Completion & Ask Priority Gate (HARD STOP)

Completing active tasks in `task.md` / `TaskList` is the #1 top priority over invoking the `next` skill or proposing next-step options.
- If an active task has open questions, trade-offs, or requires user confirmation/decision, presenting `AskUserQuestion` for that active task is MANDATORY as the very first action of the turn.
- Invoking `next` skill or offering next-action suggestions while tasks are pending/in_progress or open asks remain is strictly forbidden (`HARD STOP`).

### 3. Resume Original Work (fix-2)

**The most important step.** Complete the user's original request — not just the fix. Infer user intent and pin the verification medium verbatim; re-call any rejected AskUserQuestion once its reject cause is resolved; resume existing in_progress tasks; reproduce verification through the exact user-reported medium (no detour).

**When the resumed step is itself a skill/tool call** (e.g., an un-invoked `next` / consolidate / ask), it becomes its **own terminal task** and the actual call MUST run **this turn** before wrap-up — reporting "it should now be called" and stopping is the exact Antigravity drift the guard exists for. See step3-resume.md "Skill/tool-invocation resume is a first-class task".

**Read [step3-resume.md](./step3-resume.md) before executing** — it holds intent inference, missing-question identification, dismissal-signal handling, reject-cause classification + secondary-issue default, the verification-scope-reduction guard, the Step 3 mandatory self-questions (PR Test Plan sync, architectural-finding record), and the skill/tool-invocation resume rule (same-turn call, unchecked `task.md` box blocks wrap-up).

### 4. Wrap-up (Report + Task Pruning)

Report the fix (🔍 root cause / 🔧 improvement / 🔄 current fix / 📋 wrap-up), separate outstanding work by medium (actionable → TaskList, BLOCKED → fix_plan.md hold section), then status-prune **all** completed tasks created this session (fix-* + original work), preserving pending/in_progress.

**Read [step4-wrapup.md](./step4-wrapup.md) before executing** — it holds the chained-Resume integration gate, the report format + emoji mapping, the medium-separation principle, the status-based prune matrix, and the per-step self-checks.

## Anti-patterns

- Repeating "already fixed" without actually fixing the root cause
- Patching only the current issue without improving prompts (skill/rule/agent/memory/CLAUDE.md/hook)
- Text response without TodoWrite after /fix activation
- Recording in failed-attempts.md when the root cause is a skill defect (skill fix is 1st priority)
- **Stopping at Why 1** — fixing the symptom without asking Why 2-3 (structural cause)
- **Not cleaning up TODO/Task after completion** — must delete all fix TODOs when done
- **"User is right, so skip"** — even when the user's point is correct, Steps 0~4 must all execute. fix's value is not resolving the current issue but preventing recurrence. "You're right, executing right away" abandons Why analysis + rule modifications
- **"Fixing right now" / "I know the cause, skip"** — Step 1 Why analysis cannot be skipped, whether recurrence or trivial. Recurrence = evidence that prior fix's Why was insufficient, so go **deeper**. "Fix right now" is not a procedure that exists in the fix skill
- **Resume scope narrowing via auto-Reject classification** — When Resume produces an AskUserQuestion for option design, **all findings (Accept + Reject + Defer)** must appear as user-decidable options. Auto-Reject classification (`superpowers:receiving-code-review` "Push back when wrong" procedure) followed by excluding the Reject finding from options strips the user's override authority. The user typically phrases this as "fix them all together — why only X separately?". See consolidate/next.md "Reject finding option mandate" for the required option pattern (Accept-applied / Apply-ALL-override / Defer-all)
- **Option outcome must be pre-verified for path-based or cross-cutting tooling** — When AskUserQuestion options change a tool's behavior whose outcome depends on **path-based** or **commit-history** analysis (release-please, semantic-release, changesets, dependabot config, CI matrix rules, etc.), the option author must **dry-run / simulate / enumerate the outcome** before presenting options to the user. The user's authority is "decide between simulated outcomes," not "pick the option label and discover the real outcome only after merge." If options A and B both produce the same real-world outcome (e.g., still bumps every package because a cross-cutting `feat(...)` commit touches every package's path), state that fact in the option descriptions or merge the options. Failing this verification means the user invests effort in choosing an option that does not change the eventual result, then has to fix it after seeing the unchanged outcome. Specifically for release-please: enumerate `git log <proposed-base>..HEAD -- skills/<package>/` for every package before committing to a `last-release-sha` choice — if any cross-cutting `feat(...)` commit (e.g., monorepo-wide annotation, config bump touching every package) sits in that window, the chosen base will not block bumps.
- **Pre-verify extends to architecture recommendations and tool-behavior explanations** — the "verify against primary sources before asserting" principle (Step 1's cross-verify / read-don't-guess / Glob-Grep-before-claiming) is not limited to bug diagnosis. Do not present an architecture recommendation or an explanation of how a tool behaves before checking the primary source (docs, config, the tool's actual output). Presenting a recommendation and then repeatedly retracting it as verification catches up is the exact pattern this bans — verify first, recommend once.
- **Modifying files without environment detection**: Editing settings or rules files without detecting the active execution environment (e.g. editing Claude Code settings while under Antigravity, or editing shared `~/.agents/rules` workspace rules for out-of-scope/unrelated domains).
