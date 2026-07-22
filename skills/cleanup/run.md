# Run (sequential execution)

Sequentially performs the 5-step cleanup process before session end.

## Core Philosophy: Not Cleanup, but Learning + State Preservation

cleanup is not a simple cleanup tool — it is a **self-improving loop + session-end state preservation** mechanism.

**The two essential functions of cleanup**:
1. **Self-improving loop** — every session is an opportunity to make the system better
   - **What mistakes were made?** → prevent with rules (improve: retrospect)
   - **Did automation work correctly?** → check hooks/skills (improve: automation-review)
   - **What was repeated?** → promote to an automation candidate (improve: pattern-detect → `/skill-kit route`)
   - **What was newly learned?** → accumulate as knowledge (persist: memory, documentation)
2. **Session-end state preservation (for compact/rewind readiness)** — cleanup is invoked at session end. It's not starting new work, it's **preserving the current progress state so the next session can resume**
   - Next-session work candidates → registered as wip multi-select tasks (Step 5)
   - Session chunk → RAG store (3-C.1)
   - Distilled facts → dual-write to memory (3-C.2)
   - Active artifacts → RAG store check (3-C.3)
   - fix_plan update (Step 4)

### cleanup ≠ next Responsibility Separation (HARD STOP)

| Skill | Essence | Invocation timing |
|------|------|----------|
| **next** | Natural follow-up recommendation after completing work (single-select, 1 item, immediate execution) | While work is in progress |
| **wip** | Task registration/tracking/compact restoration (multi-select N-item registration) | While work is in progress + cleanup Step 5 |
| **cleanup** | Session-end state preservation (delegates to wip — resume in the next session) | On session-end signal |

If cleanup calls next, it becomes "select 1 → execute immediately → session continues" → weakens the session-end signal + loses the remaining work candidates. **cleanup → wip multi-select task registration** is the correct approach.

**Skip decision principle**: only steps with an explicit skip condition can be skipped. Steps without a skip condition are **always executed**.

**Forbidden patterns**:
- Self-judging "not applicable" / "this session doesn't need it" to skip a learning step — the skill should judge this, not me
- Only listing text without actually calling the skill (`claudify improve`, `claudify persist`) — "listing candidates" is not execution
- Example: writing only text like "A deploy pattern is repeating → agentify candidate" and stopping there ❌ → call the `claudify improve` skill to actually detect and propose ✅

## Execution Order

1. **Commit session changes** → check for uncommitted changes and commit
2. **Self-Improve** → mistake analysis + hook/skill review + pattern detection (planned as `/claudify improve`)
3. **Knowledge Persist** → documentation recommendation + infra check + memory storage (planned as `/claudify persist`)
4. **Weekly Report** → record work (company projects only)
5. **Register next-session work as wip** → delegate to `Skill("wip")` (multi-select task registration, state preservation for compact/rewind)

### Per-Step Invocation Obligation Self-Check Table (HARD STOP)

Each step clearly distinguishes between **automatic skill calls** and **user-decision asks**. Do not bypass a step with a text-only report.

| Step | Invocation obligation (automatic) | Ask (user decision) | Auto-invocation condition |
|------|------------------|------------------|---------------|
| Step 0 | Call `TaskList` | — | Clean up when TaskList has completed tasks |
| Step 0.5 (4.5 Resume import) | RAG receiver import dispatch (`--rag=<skill>:<topic>`) for each discovered file | — | RAG receiver readyz response + research-*/plan-* discovered |
| Step 1 | `Skill("commit-tidy")` or `/commit-tidy` | Decide split strategy (internal ask inside the skill) | When there is 1+ uncommitted change |
| Step 2 (Self-Improve) | **`Skill("claudify", "improve")` call mandatory** — retrospect + automation review + pattern detect | How to handle findings (internal Phase 2 ask inside the skill) | **Always** (regardless of whether the conversation had mistakes/patterns — the skill judges) |
| Step 3 (Knowledge Persist) | **`Skill("claudify", "persist")` call mandatory** + RAG receiver import dispatch 3-C.1 | Storage location (internal ask inside the skill) | **Always** + auto-import when the RAG receiver readyz responds |
| **3-C.1 session RAG import** | **Automatic execution — no ask** | — | Immediately import with the `--raw` flag when the RAG receiver readyz responds OK |
| **3-C.3 check for missed active-artifact RAG store** | **Automatic execution — no ask** | — | Glob → identify this-session mtime artifacts → RAG receiver scroll → immediately store missing files. Matches plan/research/analysis/report/postmortem-*.md patterns |
| Step 4 | Identify the checklist file | Decide the medium (user-specified / fix_plan / checklist.md / AskUserQuestion) | When this session has artifacts |
| Step 5 | **`Skill("wip")` call mandatory** (multi-select task registration) | Internal multi-select ask inside wip (N next-session work candidates) | **Always** — state preservation for next-session resume at cleanup end |

**Don't / Do**:

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Output Step 2 as text-only "reporting retrospect/automation/pattern detect" | Call `Skill("claudify", "improve")` — the skill handles the Phase 2 ask as well |
| 2 | Ask about the 3-C.1 session RAG import as "wrap-up ask option 1" | RAG receiver readyz OK response = execute automatically (no ask). `--raw` flag mandatory |
| 3 | Defer Step 3 Knowledge Persist to an ask | Call claudify persist. Storage location is decided inside the skill |
| 4 | Self-compress procedure with "consolidating cleanup because of the preceding fix accumulation" | Per-step invocation obligations cannot be compressed. Compressing the procedure = rule violation |
| 5 | End a step by treating "candidate text listing = execution" | Already stated above: "listing candidates is not execution" — an actual Skill call is mandatory |
| 6 | Miss recognizing mandatory steps (3-C.1 auto-import + RAG report row) because run.md's body is long and only the preview was viewed | The table above + the Step 5 completion-report template's mandatory rows are within the preview range — obligations can be satisfied without reading the entire body. If in doubt, confirm the mandatory steps with `grep "3-C.1\|RAG Store" run.md` |
| 7 | **Demote a defect discovered by Step 2 self-improve (especially one that caused a failure/error this session) into a Step 5 next-action option** (e.g., placing a merge-gating defect as option 1 competing with "End session") | **Important improve results must be confirmed and executed immediately in Phase 3, right after being surfaced.** Step 5 next is a separate step **after** improve handling is done — do not demote improve results into the next menu. Session-failure-causing defects require feedback-memory recording + **actual fix execution** to complete Step 2 |

**Self-check (immediately before entering cleanup + immediately before each step)**:
1. Check the "invocation obligation" column for the current step
2. Is the invocation condition met? (e.g., RAG receiver readyz response)
3. If met, immediately call `Skill()` — no ask
4. Ask applies only to items in the "user decision" column
5. Attempting to end a step with a text-only report should trigger a forced self-check re-verification
6. **Self-check immediately before writing the wrap-up report table**: does the report table explicitly include a "RAG store (N chunks added — receiver)" row as required? If missing, add it immediately. This row ensures user visibility — preventing "missed without even knowing" omission
7. **Self-check immediately before writing Step 5 next options (HARD STOP)**: among the option candidates, is there **an unexecuted defect found by Step 2 self-improve** (especially one that caused a failure/error this session)? — if so, that is **not** a next option but something to execute immediately in Phase 3. Do not demote it into the next menu (competing with "End session"). Only enter Step 5 after the improve result has been executed
8. **Verify claudify call trace (HARD STOP — immediately before entering Step 2/3 every time)**: if there's no `Skill("claudify", "improve")` call trace in this response turn's tool-call history right before entering Step 2, call it immediately. If there's no `Skill("claudify", "persist")` call trace right before entering Step 3, call it immediately. **Filling in an inline retrospect report + a comprehensive-matrix table's "claudify improve results" row ≠ a Skill call.** A Skill call = quoting the tool response result. Filling the table with self-written text = a violation of Don't #1. On repeated occurrences, this is a candidate for hook escalation (`block-cleanup-without-claudify.sh` — blocks when the cleanup-completion response's transcript has no `Skill("claudify",` trace)

### Step 5 Completion Report Table Mandatory Rows (HARD STOP — applies to both cleanup wrap-up and session-end reporting)

The cleanup wrap-up completion-report table **and** the resulting **session-end final report** written after wip task registration (e.g., "## ✅ Session Ended", "End session report", carryover summary) must **always** include the following rows. Applying the rule only to the cleanup wrap-up table but burying it in a 1-line prose entry within a separate session-end report is a visibility gap — the same rule violation.

| Step | Result |
|------|------|
| 0. TaskList | (cleanup result) |
| 1. Commit | (commit result or skip reason) |
| 2. Self-Improve | `claudify improve` result |
| 3. Knowledge Persist | `claudify persist` result |
| **3-C.1 RAG Store (mandatory row)** | **N chunks added (receiver: RAG import dispatch) — session UUID `<uuid>`. N artifacts imported.** |
| 4. Weekly Report | (skip / write result) |
| 5. **wip task registration (mandatory row)** | **`Skill("wip")` call result — N tasks registered (next-session resume possible). Enumerate candidates** |

**The "3-C.1 RAG Store" row is the top visibility priority — bold/highlighting recommended.** Omission triggers "the user doesn't even know it's missing" → triggers this fix (recurrence accumulation).

**If the RAG row is FAILED, the entire cleanup = FAILED** — change the table header to "⚠️ cleanup FAILED (RAG store failed)". Do not declare "✅ Complete" (see the "RAG store failure = cleanup failure" HARD STOP in 3-C.1).

**Don't / Do**:

| # | Don't | Do |
|---|-------|-----|
| 1 | Include only a "3. Knowledge Persist" row in the Step 5 report table without stating the RAG store result | A separate "3-C.1 RAG Store" row is mandatory — chunks N + receiver + session UUID + artifact import result |
| 2 | Bury the RAG store result in prose inside the claudify persist result | Elevate it to a separate row — user-visible at a glance |
| 3 | RAG receiver readyz responds OK but the import call is skipped while the report table still shows a "RAG Store" row | The call itself is mandatory — the report row displays the result, it is not a bypass channel |
| 4 | The cleanup wrap-up table explicitly states the RAG row, but the subsequent separate session-end report (e.g., "## ✅ Session Ended") buries the RAG result in a 1-line prose list | The session-end report carries the same obligation — highlight visibility with a separate markdown table row / bold line / dedicated header section |
| 5 | Fill the "Self-Improve / Knowledge Persist" rows with a self-written inline retrospect text + FA Prune non-execution report + comprehensive-matrix text (0 claudify Skill call traces) | **Only quoting Skill call results is allowed.** Quote only the `Skill("claudify", "improve")` tool response result text + `Skill("claudify", "persist")` tool response result text into the rows. Filling the row with a self-written retrospect report = bypassing the call = a violation |

For accumulated violation cases, see failed-attempts.md HOT (occurrence classification + escalation specification). Escalation from the 3rd occurrence: hook automation — `~/.agents/skills/hook-kit/resources/block-cleanup-without-rag.sh` registered. Injects a reminder when the cleanup/session-end response text matches the marker + lacks a RAG-visual-highlight row + has RAG-receiver call traces.

## Prerequisites

- **Fully skip** if there is no conversation content or only simple questions
- If a `config.md` settings file exists, skip the tasks disabled in it

## Ralph Mode

Ralph cannot use AskUserQuestion, so every step performs **detection + recording to improvements.md only**.

**Detection method**: Ralph mode only when **all** of the following hold:
1. `.ralph/` directory exists AND
2. Environment variable `RALPH_LOOP=1` is set

**If `.ralph/` exists but it's an interactive user session, use normal mode** — AskUserQuestion is used normally. Do not judge based on `.ralph/` existence alone.

**Ralph mode behavior rules**:

| User session | Ralph mode |
|------------|-----------|
| Confirm via AskUserQuestion | Record `[NEEDS_REVIEW]` to `.ralph/improvements.md` |
| Direct modification (rules, memory, hook) | **Forbidden** — record only |
| Skill/agent creation | **Forbidden** — record candidates only |
| Delegate via Agent tool | **Forbidden** — record only |

**improvements.md recording format**:

```markdown
## [Step name] (date)

### [Item title]
- **Finding**: [what was found]
- **Suggestion**: [how to improve it]
- **Tag**: [NEEDS_REVIEW]
```

---

## Before Step 0: Guard to Complete Unfinished Work First (HARD STOP)

Before entering cleanup, if there is **work started but not completed in this session**, it must be completed before cleanup.

**Procedure**:
1. Check the state of the prior work — whether background agent results have arrived, whether a consolidate/code-workflow intermediate step is pending, etc.
2. If there is unfinished work, AskUserQuestion:
   - "Finish then cleanup (Recommended)" — complete the unfinished work, then proceed to cleanup
   - "Cleanup first" — carry the unfinished work over to the next session
3. If the user selects "finish," complete that work first, then re-enter cleanup

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Autonomously carry over unfinished work (e.g., an unposted consolidate review comment) to "the next session" | Confirm "finish vs carry over" via AskUserQuestion |
| 2 | Ignore an arrived background agent result and proceed with cleanup | An arrived result means the work can be resumed. Complete it first |
| 3 | Reason that "cleanup was invoked, so cleanup is top priority" | cleanup is "session tidy-up," not "abandoning unfinished work" |

**Skip condition**: skip if there is no unfinished work

---

## Step 0: Clean Up Completed Tasks + Sync Checklist

Clean up `completed`-status tasks from TaskList and reflect their completion in the checklist (fix_plan.md).

**Procedure**:
1. Call `TaskList`
2. For each `completed` task, **find the corresponding item in fix_plan.md and check `[x]`** + record completion info (apply the workflow.md "bidirectional task ↔ checklist sync" rule)
3. After the checklist update completes, `TaskUpdate(status: "deleted")`
4. Report the cleanup count: `**Task cleanup**: N completed → deleted (fix_plan reflected)`

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Skip the fix_plan update after deleting a task | Update fix_plan **first** → then delete |
| 2 | Skip the update by saying "no corresponding item in fix_plan" | Determine this by grepping the task subject keywords |

**Skip condition**: skip if TaskList has no completed tasks

---

## Step 1: Commit Session Changes

Commit files directly modified in this session that are still uncommitted.

**Procedure**:
1. Check uncommitted changes with `git status`
2. Filter to **only files modified in this session** (exclude changes that predate the session start)
3. **Branch policy self-check (HARD STOP — scoped to the `~/.agents` repo)**: if the current repository is `~/.agents` and there is an untracked (`??`) or modified (`M`) item under `skills/<slug>/`, apply the `.claude/rules/branch-policy.md` "self-check (immediately before commit/push/PR)" + "separating work accumulation from PR-creation timing" self-checks:
   - Confirm published status via the skill-registry lookup (e.g., `jq -r --arg slug "<slug>" '.skills[] | select(.slug == $slug or .local == $slug) | .slug' <skill-registry-index>`)
   - Check the current branch (`git branch --show-current`)
   - Only enter PR creation when explicitly instructed by the user. **Work-accumulation default = commit only to the `local` branch**
   - Do not mark "create PR" as Recommended in an ask option (unless explicitly instructed by the user) — this self-check's trigger includes the moment of composing the option description too (`~/.agents/rules/ask-user-question.md` "explicit PR-creation instruction obligation" → "self-check trigger expansion")
4. **Local skill commit routing (HARD STOP — no ask when a published-skill change is found)**: if the files modified in the session are a published skill (`skills/<slug>/`), follow the `.claude/rules/branch-policy.md` "Local skill commit routing" procedure as-is. Key points:
   - Change classification (minor/patch) → automatic routing to the matching category worktree (`feat/*`/`fix/*`)
   - **Transfer method = cherry-pick default. No ask for cp vs cherry-pick** (branch-policy.md Rule 4 + Don't/Do #6)
   - Even if the main working tree has other modified files mixed in, don't ask "where to commit?" — execute the selective-commit 6-step procedure (backup cp → HEAD reset → re-Edit → commit → restore backup → cherry-pick to worktree)
   - Do not bypass branch-policy routing just because cleanup has its own commit flow. branch-policy takes precedence over commit-tidy/cleanup
5. If there are targets, call the `/commit-tidy` skill — including the split/squash strategy
6. commit-tidy handles the commit organization + execution

**Skip conditions**:
- No changes
- Not a git repository
- The change is not a file modified in this session and is unrelated to the modification

### No Extending a Prior User Hold Decision (HARD STOP — a new ask is required for new changes at every cleanup)

Even if the user chose "don't commit now" / "hold" in a prior turn/cleanup, **this does not apply to new changes at this cleanup entry point**. The scope of a hold decision is limited to the changes existing at that point in time. Subsequent additional changes require a new ask.

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Autonomously extend the user's "don't commit now" decision from a prior turn to this cleanup Step 1 → skip the commit-tidy call | Recheck `git status -s` fresh at every cleanup Step 1 → if there is 1+ change, calling commit-tidy is mandatory. The user's decision is scoped to the changes at that time |
| 2 | Reasoning "held before, so keep holding" | "Hold" is the answer to that ask at that time. New changes at this cleanup point are a new decision area. **Calling commit-tidy → asking the user inside it is the correct approach** |
| 3 | Autonomously write "user decision: hold maintained" in the cleanup report Step 1 row | The Step 1 row is "commit-tidy call result" (N commits / N held — but hold is the result of this cleanup's ask) |
| 4 | After classifying files, thinking "this is a prior hold item, so asking again is burdensome" → skip | Classification is irrelevant, call commit-tidy. Hold vs commit is decided by the user every time. If asking is burdensome, compress the ask format (1-line), not skip it |
| 5 | If accumulated `~/.agents` changes mix a prior hold + new changes from this session, handle it as "batch hold applies" | All accumulated + this-session changes are targets for the commit-tidy call. Split-commit vs batch-commit decisions are the user's ask |

### Self-Check (immediately before entering cleanup Step 1 every time)

1. Does `git status -s` show 1+ current change? — If yes, calling commit-tidy is mandatory
2. Are you about to extend a prior user decision ("don't commit now" etc.) to this cleanup? → Violation. A new ask is required for new changes at this cleanup point
3. Are you about to write an autonomous-judgment word like "user decision: hold maintained" in the Step 1 row of the report? → Violation. Use factual wording: "commit-tidy call result: N commits / N ask-hold decisions"
4. Are you about to skip the commit-tidy call itself? → Skip is only allowed with 0 changes. If there is 1+ change, calling is mandatory

For case history, see `~/.claude/skills/cleanup/data/failed-attempts.md` under "extending a prior commit-hold decision to new changes."

**Ralph mode**: record the list of uncommitted files to `.ralph/improvements.md`. Do not directly execute commits.

---

## Step 2: Self-Improve (mistake analysis + automation check + pattern detection)

**Topic reference**: [claudify/improve.md](../claudify/improve.md) — planned conversion to a `Skill("claudify", "improve")` call.
Currently the procedure below runs directly within cleanup.

Analyze the session's episodic data (mistakes, hook/skill behavior, repeated patterns) to improve the system.

### 2-A. Retrospect (mistake analysis)

Analyze mistakes made during the session and record them to feedback memory + failed-attempts.md.

**Procedure**: see [retrospect.md](./retrospect.md) — in Step 6 (FA Prune), if the section count > 20, calling `Skill("cleanup", "fa-prune")` is **mandatory** (a text-only note is ❌).

**Skip condition**: skip if there were no mistakes/corrections in the conversation

### 2-B. Automation Review (hook + skill check)

#### Hook behavior review

1. Collect the list of hooks registered in settings.json
2. **Verify hook file existence**:
   - Extract the executable path from each hook's `command`
   - Check whether the file actually exists
   - **File missing → classify as a "phantom hook"**
3. Check each hook's session-behavior status:
   - Triggered + acted → "OK"
   - Triggered + **did not act** → "**Ignored**"
   - Triggered + errored → record the error content
   - Not triggered → "Not triggered"
   - File missing → "**Phantom**"
4. **Detect ignored hook output**: search for markers such as `<skill-trigger>`, `BUILD_COMPLETED`, `AUTO_AGENTIFY_CANDIDATE:`
5. If there were errors, see [hook-review.md](./hook-review.md)
6. **Summary report** (output immediately):

```
**Hook Behavior Summary**: 16 registered / 10 OK / 6 not triggered / 0 ignored / 0 errors
```

**Skip condition**: none — always run if even 1 hook is registered

#### Skill malfunction check

1. Collect the list of skills invoked via `Skill()` in the session
2. For each skill, check the Post-execution Self-heal checklist:
   - Did the trigger fire correctly?
   - Was the correct topic selected?
   - Was the procedure complete (no manual correction needed)?
   - Were there any missing pieces in the output?
3. Add any discovered malfunctions to **Phase 2 questions array**

##### Detecting non-auto-invoked / late-invoked domain skills (HARD STOP — the invoked-skills list alone is insufficient)

The above check only looks at **invoked skills**. However, a **domain skill that should have surfaced (or surfaced late) but didn't** is not on the invocation list, or is missed because it appeared late (a skill without registered `triggers:` doesn't even have a hook marker, making it invisible even in the hook behavior review). Cross-verify the session's work domain against domain-skill load timing.

**Procedure**:
1. Identify **domain work commands** in the session — `ssh <known-host>` / `docker`·`docker compose` / `curl <infra-endpoint>` / `terraform`·`semaphore`·`kubectl` / Portainer API, etc.
2. Map each domain to its **domain skill** (e.g., map infra hosts → an internal infra skill; k3s → `k3s`)
3. **Cross-verify load timing**: was that domain skill loaded (via Skill call or reading a topic) **before the first domain command**?
   - Loaded before the first command → OK
   - Loaded late after the command / loaded only because the user explicitly instructed it / never loaded at all + reverse-engineering was performed (reading ssh config directly, extracting env via `docker inspect`, searching port listeners) → classify as a **non-auto-invocation defect** and add to Phase 2 questions
4. **Recurrence classification**: if the same domain skill's non-auto-invocation is already recorded in failed-attempts.md, classify it as the Nth occurrence + escalate (rule → trigger registration → PreToolUse hook)

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Only self-heal-check the list of invoked skills and stop | Also detect "should have surfaced but didn't" domain skills via cross-referencing domain command vs load timing |
| 2 | Classify as "normal" just because the domain skill was invoked (even if late) | Late-invoke + preceding reverse-engineering = a defect. The criterion is whether it loaded before the first domain command |
| 3 | "No registered `triggers:` → no hook marker → not visible in the hook review, so it's missed" | A skill without a registered trigger has no marker = invisible. This step (based on work domain) separately detects it |

3. Add discovered malfunctions/non-auto-invocations to **Phase 2 questions array**

**Skip condition**: skip if there were no domain tasks (server SSH/docker/infra/deploy) at all and no invoked skills, or all invoked skills behaved normally

### 2-C. Pattern Detect (detect automation candidates)

> **TODO**: consolidate pattern-detection logic after absorbing auto-agentify.

**⚠️ Always run — do not skip**: do not judge candidate presence in advance.

1. Detect repeated patterns in the conversation context
2. Recommendation route by pattern type:

| Pattern type | Recommendation | Example |
|-----------|------|------|
| Repeated manual verification (same test repeated across multiple targets) | **Write test code** | An SSO callback test repeated across multiple deployment targets → write an E2E spec |
| Repeated workflow (same command sequence repeated) | **Create a skill/agent** (`/skill-kit route`) | A deploy pattern → deploy topic |
| Repeated rule application (same judgment manually made each time) | **Add a rule/hook** | Test Plan check before PR merge → hook |

3. On finding a candidate, **register it as an actual item in fix_plan.md** (HARD STOP):
   - Test code candidate → register `- [ ] Write test code: {target}` in fix_plan.md
   - Mappable to an existing rule/skill → propose upgrade in Phase 2
   - **New pattern that fits nowhere → call `/skill-kit route`** → auto-chaining (upgrade/writer)

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Write only in "next-action recommendation" text and stop | Register as a `- [ ]` item in fix_plan.md — convert into a trackable state |
| 2 | Conclude with "low frequency" | 3 repetitions is a sufficient frequency. Register with whichever of test code/skill/hook is appropriate |

4. Add the candidate to **Phase 2 questions array**

**Ralph mode**: 2-A~2-C all perform detection+recording only (`.ralph/improvements.md`). No direct modification.

---

## Step 3: Knowledge Persist (documentation + infra check + memory)

**Topic reference**: [claudify/persist.md](../claudify/persist.md) — planned conversion to a `Skill("claudify", "persist")` call.
Currently the procedure below runs directly within cleanup.

Store knowledge discovered in the session to the appropriate location.

### 3-A. Documentation recommendation

Suggest a location to document new information discovered during the conversation.

**Detection targets**: troubleshooting solutions, project/infra structure, failed attempts, external service usage, environment configuration

**Documentation location recommendations**:

| Information type | Recommended location |
|----------|----------|
| Project structure/configuration | The project's `CLAUDE.md` or `README.md` |
| Infra/server information | `pages/` or Logseq |
| Failed attempts | `pages/FAILED_ATTEMPTS.md` |
| External service integration | The project's `docs/` |
| Personal workflow | `~/.claude/CLAUDE.md` (global) |
| Troubleshooting record | Today's Logseq journal |

- Exclude information that's already documented, or sensitive information (API keys, etc.)

### 3-B. Infra documentation check

**Skip condition**: skip if there was no infra work

If infra-related work was performed, check whether the discovered information has been documented in CLAUDE.md.

### 3-C. Memory storage

Store project knowledge learned in this session to memory.

#### Pre-review: storage location classification

| Information type | Storage location | Example |
|----------|----------|------|
| One-off environment fact | **Memory** | Server IP, current resource usage, API key location |
| Infra/IaC configuration knowledge | **Skill** (`/skill-kit route`) | Terraform structure, ArgoCD management procedure |
| Domain knowledge, procedure, guide | **Skill** (`/skill-kit route`) | Deployment procedure, troubleshooting guide |
| Behavioral rule, prohibition | **Rules** | Mistake-prevention rule (handled in Step 2 retrospect) |

**Judgment criterion**: usable procedurally → skill, addable to an existing skill topic → skill, purely for reference → memory

#### Storage tools (usable in parallel — different purposes)

| Tool | Condition | Purpose | Invocation |
|------|------|------|------|
| **RAG receiver import dispatch** | RAG receiver available (readyz responds) | **Whole-session semantic chunk** — searchable via the receiver's find tool for conversation flow in the next session | 3-C.1 procedure below |
| Serena MCP | `activate_project` responds | Structured key-value facts (memory_set/memory_get) | `list_memories` → `edit_memory` / `write_memory` |
| Claude Code auto memory | Fallback when Serena is absent | Markdown file (`memory/MEMORY.md` + individual) | Edit/Write |

The three tools are used **in parallel** — not a priority order, since they serve different purposes rather than storing the same information. Store to every available medium.

#### 3-C.1 Session semantic chunk storage (RAG receiver dispatch)

**Call when the condition is met**:

##### Availability check — 2 stages (HARD STOP)

This step is mandatory before entering RAG store. **Do not conclude "unreachable" from a single signal**.

| Order | Signal | Meaning | Action |
|-----|------|------|------|
| 1 | RAG receiver MCP tool available (in the system reminder's "available tools" list or matched via `ToolSearch` — the receiver's store/find tool name) | MCP is already connected to the receiver — primary availability signal | Enter import immediately. Call `ToolSearch select:<receiver-tool>` to load the schema, then use the store/find tools |
| 2 | The endpoint readyz probe explicitly documented by the receiver skill (use only the endpoint from the receiver's `<skill>:<topic>.md` doc) | Direct HTTP probe — secondary availability signal | MCP not connected, but the endpoint is alive. Enter via the script path |
| **FAILED** | (1) MCP unavailable AND (2) endpoint probe timeout/HTTP 5xx | Both must fail to be unreachable | **Entire cleanup status = FAILED. Do not declare "✅ Complete"** — apply the "RAG store failure = cleanup failure" procedure below |

##### RAG store failure = cleanup failure (HARD STOP)

**3-C.1 RAG store is a mandatory cleanup step — on failure/unavailability, report the entire cleanup as FAILED.** RAG store is the core medium for "session-end state preservation" (this skill's philosophy #2), and if the session ends in a missed state, the opportunity to store the session chunk is effectively lost ("retry next session" is a weak trigger, so actual retries rarely happen).

**On failure, all of the following are mandatory**:

1. One recovery attempt before judgment — confirm the underlying connectivity/VPN process (if applicable to the environment) is alive + if dead, restart and re-probe
2. On confirmed recovery failure, mark the Step 5 completion-report table's "3-C.1 RAG Store" row as **`❌ FAILED`** (not worded as "Skipped"/"held")
3. Use **"⚠️ cleanup FAILED (RAG store failed)"** instead of "✅ cleanup complete" in the report title/header
4. **Retry task registration obligation**: register a "Retry RAG store (session <UUID> + N artifacts)" pending task via `TaskCreate` — do not end with carryover text alone
5. Report the failure cause (MCP disconnected / endpoint down / underlying network down) + recovery path in 1 line

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Declare "✅ Session cleanup complete" after skipping the RAG store | RAG failure = cleanup FAILED. State ⚠️ FAILED in the header |
| 2 | End with only "Skipped — retry candidate for next session" carryover text | Register a `TaskCreate` retry task (pending) + report failure cause/recovery path |
| 3 | Judge "complete" because other cleanup steps finished | Even 1 mandatory step FAILED = the entire cleanup is FAILED. Show per-step status in the report table |
| 4 | Judge FAILED immediately after confirming RAG receiver unavailability with no recovery attempt | Confirm the underlying connectivity is alive + attempt one restart before judging |

**Don't / Do**:

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Guess an endpoint on your own (default localhost port, etc.) | Use only the endpoint documented in the receiver skill topic (`<skill>/<topic>.md`). Do not check a guessed endpoint |
| 2 | Downgrade the MCP-available reminder to ambient context + judge based solely on endpoint probe | The system reminder's "MCP available" signal = primary availability evidence. Prioritize ToolSearch + tool calls |
| 3 | Decide to skip RAG store after 1 probe failure | Both stages above must be checked. Even if the probe fails, proceed with import if MCP is available (MCP abstracts the endpoint) |
| 4 | Narrowly interpret "readyz response" as an HTTP probe only | An MCP call round-trip success is also included in "readyz response" |
| 5 | Enter endpoint checking without reading the receiver topic body | Reading the receiver topic's endpoint section is mandatory → use only the documented address |

**Self-check (immediately before entering 3-C.1 every time)**:
1. Does the system reminder show the RAG receiver MCP tool as available? — If yes, signal 1 satisfied, enter immediately
2. Attempt to load the receiver store/find tool schema via ToolSearch — success satisfies signal 1
3. If both 1 and 2 are unmet, probe the endpoint documented in the receiver topic (query for the exact address in the receiver topic first)
4. If the response is OK, enter
5. If 1, 2, and 3 all fail, apply the **cleanup FAILED procedure** (above — one recovery attempt → FAILED report + retry task registration)

##### Invocation command (delegated to the receiver topic)

The receiver's endpoint, script, and sanitize policy are defined by the receiver topic (`<skill>:<topic>.md`). cleanup performs only abstract dispatch:

```bash
# For confirming signal 2 (skip if signal 1 is satisfied)
# The endpoint is delegated to the receiver topic's availability procedure
# (e.g., the URL documented in the receiver topic)

# Store the session chunk (idempotent — re-importing the same session embeds/upserts only new turns)
# --raw: current session = the user's own context + active JSONL, so opt out of the receiver's sanitize procedure
#   (see the receiver topic's "opt-out conditions" for importing the current session)
<rag-import-command-per-receiver-topic> \
  --session-id <current-session-uuid> \
  --raw
```

`<current-session-uuid>` is extracted from `/session id` or the "Current session ID" inject from the UserPromptSubmit hook. For automatic invocation, the user enters the RAG-import skill's trigger command → the hook injects both the session/message uuid.

If the RAG receiver is unavailable (probe timeout/HTTP 5xx), **apply the cleanup FAILED procedure** (see "RAG store failure = cleanup failure" above — do not proceed to skip). The session chunk complements the fix_plan/failed-attempts context — a separate medium from fact storage (Serena/auto memory).

**Reason for using `--raw`**:
- The current session's JSONL is still being written — in-place clean-profanity modification risks damaging the active file
- This is the user's own raw context (profanity/emotional expressions have value as semantic search signals)
- Not an externally shared medium (internal vector store on a private network)

For importing other sessions (past sessions, sessions planned for external sharing, etc.), omit this flag and follow the receiver topic's sanitize procedure.

#### Storage targets (focused on context preservation)

- **Decisions**: why this approach was chosen (compared to alternatives)
- **Deployment/infra state**: current version, deployment progress, pending work
- **Discovered patterns/rules**: code conventions, project-specific quirks
- **Work in progress**: work state that needs to continue in the next session

#### 3-C.2 Distilled reusable fact dual-write (structured precise recall)

3-C.1 (session turn chunk) is for **preserving conversation flow**. However, **reusable single facts** discovered this session (infra details · decisions · gotchas) are hard to recall precisely if buried in turns. Such facts should be **recorded in both media together**:

| Medium | Role | Method |
|------|------|------|
| (a) Domain skill / memory | **Source of truth** (permanent text, always-loaded or on-demand) | Add a section to a domain skill topic (use `/skill-kit route` to decide the location) or a project memory file |
| (b) RAG receiver separate structured point | **Semantic search** (distinct from session turns, with type/topic metadata) | The receiver's fact-storage script (below) |

**Dual-write criteria — record as a fact if any of the following applies**:
- An infra fact that took significant time to diagnose (paths, ports, mount points, etc.)
- Load-bearing knowledge that the next session/another person would hit the same wall on
- Not "why it turned out this way" (turn flow) but "what is the fact" (a standalone fact)

**(b) RAG receiver fact point storage** (delegated to the receiver topic's fact-storage procedure):

```bash
<rag-fact-command-per-receiver-topic> \
  --id-seed "fact:<topic-slug>" \
  --document "<self-contained fact text>" \
  --type infra-fact --project <repo/domain> --category <cat> --topic <slug>
```

- `--id-seed` is stable → re-recording the same fact updates it (no duplicates)
- See the receiver topic's "single fact structured storage" section
- **Record (a) the source-of-truth first, then (b) the RAG receiver point** — the source of truth is authoritative, the RAG receiver is a search index

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Only import the session (3-C.1) and leave distilled facts buried in turns | Record reusable facts to both (a) domain skill/memory + (b) RAG receiver fact point |
| 2 | Write an ad-hoc script on the spot to record a single fact in the RAG receiver | Reuse the receiver's fact-storage script |
| 3 | Only a RAG receiver point, no domain skill | Source of truth (skill/memory) first. The RAG receiver is a search aid, not the source of truth |

#### 3-C.3 Check for missed active plan/research/analysis RAG store (HARD STOP)

The `skill-usage.md` "Generic skill artifact RAG store obligation" rule says **immediately after writing** is the store trigger. However, without an enforcement medium (a hook, etc.), the write-time trigger is sometimes missed. cleanup serves as that fallback — check active artifacts generated in this session for anything missing from RAG + store them.

**Check targets (Glob patterns)**:
- `**/.ralph/docs/generated/{plan,research,analysis,report,postmortem}-*.md`
- `**/.omc/plans/*.md`

**Procedure**:

1. **Identify files via Glob with mtime ≥ session start time** — only artifacts Written/Edited in this session (artifacts written in other sessions are handled in that session's cleanup)
2. **Query the RAG receiver's scroll for each file**: search for chunks whose `filename` or `source_path` metadata matches that file path
3. **Branch**:
   - 1+ existing chunk → already stored. Skip
   - 0 existing chunks → not stored. Store immediately
4. **Storage medium**:
   - Full-body RAG chunk: the receiver's raw-import command with `--file <path>` or an equivalent medium (prefer the vendor receiver's store tool if available)
   - If a distilled fact is clearly extractable, also do the 3-C.2 dual-write procedure (optional)
5. **Report the store result quantitatively** — format `RAG store summary: N chunks added for {file}` (apply the skill-usage.md "RAG store report format" rule)

**Don't / Do**:

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Import only the 3-C.1 session chunk and assume it's sufficient since artifact-specific facts are included in it | Session chunks preserve turn flow. Artifact bodies are stored as separate fact points/chunks. Search precision differs |
| 2 | Handle only via `.bak/` archive-time REPEAT items (does not cover active artifacts) | Also check active artifacts in this sub-step. Archive time is a separate trigger |
| 3 | Report as text "unsure if there are artifacts at session end" | Glob + scroll are mandatory. Do not assume 0 — confirm with primary sources |
| 4 | Skip and end when the RAG receiver is unavailable | RAG receiver unavailability = this sub-step is BLOCKED. State it in the Step 4.5 BLOCKED row + set a trigger for the next session |

**Self-check (every time during cleanup Step 3)**:
1. Identify `**/{plan,research,analysis,report,postmortem}-*.md` files written/edited this session (Glob mtime filter)
2. Count of identified files = N. If N=0, skip
3. If N≥1, run the RAG receiver's scroll per file → check existing chunk count
4. Files with 0 chunks = storage obligation. Call immediately + report quantitatively
5. Omitting the report = this sub-step is incomplete

**Ralph mode**: only record the artifact list + un-stored files to `.ralph/improvements.md`. No direct store.

**Ralph mode**: 3-A~3-C all perform detection+recording only (`.ralph/improvements.md`). No direct modification/storage. Skip RAG storage too (unsuited to autonomous execution).

---

## Step 4: Checklist Record

Record the work performed in this conversation to the checklist. **Always use the checklist medium regardless of project type** — no company/non-company branching.

### Checklist file decision order

1. **If the user explicitly named a checklist file, use it** (e.g., `checklist.md`, `tasks.md`, `progress.md`, etc. — a file quoted in this session's messages)
2. **If `.ralph/fix_plan.md` exists in the workspace, use it** (default 1st priority — applies equally in Ralph environments and non-Ralph regular sessions. fix_plan.md is already structured with Priority Work · BLOCKED · Completed sections, making it a suitable medium for session-work records)
3. **If only an artifact folder is specified and no checklist file exists**, use `<artifact-path>/checklist.md` as the default file (create if it doesn't exist)
4. **If none of the above applies**:
   - Search the workspace root (`pwd`) in order: `.ralph/docs/generated/checklist.md`, `.omc/plans/checklist.md`, `checklist.md`
   - Use the file found
   - If none are found, confirm the location via AskUserQuestion (options: create a new `checklist.md` at the workspace root / a different path / skip)

#### Handling procedure when using a session-log file (`fix_plan.md` / `checklist.md`) (HARD STOP — matching existing items is priority 1)

cleanup's core purpose is **tidying (state refresh + pruning completed items)**, not "adding session-work records." Creating a new section is a fallback for matching failure, not the default.

**Session-log file structure (HARD STOP — common to all checklist media)**: whether it's `fix_plan.md` or `checklist.md`, the session log is a **flat structure** — `## Completed` (completed, per-item inline `(session <UUID>)`) + `## Priority Work`/`## Hold`/`## Carryover`. **Creating per-session date sections (`## Session Work (YYYY-MM-DD)` / `### Session Work (date)`) is forbidden** — adding a date section every session causes append-only unbounded growth of the file, and the same work gets scattered across multiple sections. Session identifiers are expressed **inline per item, not as a section**.

**Procedure (repeat for each work item)**:

1. **Step A — existing-item matching grep (required)**: for each work item in this session, grep the session-log file by keyword to check for an existing registration
   ```bash
   grep -nE "<work keyword 1>|<work keyword 2>" <session-log file>
   ```
   - Matching keyword examples: environment name (dev-36/integration server/production server) + domain (brand/SVG/SSO/logout, etc.) + identifier (PR#/issue#/commit SHA)
2. **Step B — branch on the matching result**:

| Matching result | Handling |
|----------|----------|
| Matches an existing `- [ ]` or `[BLOCKED]` item | **Update that item to `- [x]`** + append 1 line of completion info (commit/file/verification). Do not add a new row |
| Matches an existing `- [x]` item (already complete) | **Skip the update** (already complete) |
| No matching item + work is complete | Append `- [x] {summary} (session <UUID>)` at the end of the `## Completed` section |
| No matching item + remaining work | Append `- [ ]` to `## Priority Work` or the appropriate category |
| No matching item + waiting externally | Append `- [ ] [BLOCKED] {summary}` to the `## Hold` section |

3. **Step C — no creating new date-header sections (HARD STOP)**: creating **`##`/`###`-level per-session date-header sections** like `## Session Work (YYYY-MM-DD)` / `### Session Work (YYYY-MM-DD, session <UUID>)` requires **explicit user approval only**. Adding a date section every session causes the file to grow append-only unbounded and the same work to scatter across multiple sections, making tracking difficult. Applies equally to `fix_plan.md` and `checklist.md`

#### Don't / Do table

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Add a new `### Session Work (YYYY-MM-DD, session <UUID>)` header at session start and accumulate results underneath | Step A grep to find the existing item is priority 1 — updating `- [ ]` → `- [x]` takes priority. New items are appended 1 line at the end of the existing section |
| 2 | Reasoning "it reads better to group this session's work together" | Trails (session UUID, commit SHA) are expressed inline within the item. Grouping into sections is the cause of medium bloat |
| 3 | "The incomplete item and this session's work are phrased differently" → add new | Keyword grep matches if it's the same domain/environment/target. Ignore phrasing differences and update the item |
| 4 | Skip Step A grep and directly add a `### Session Work` section | Step A is mandatory immediately before recording each work item. Fewer than 1 grep call = procedure violation |
| 5 | Create a new section without getting user approval | Confirm in advance via AskUserQuestion: "N new-domain work items don't match any existing item, so creating a new section" |

#### Self-check (immediately before editing fix_plan every time)

1. Extract a 1-line summary of this session's work items
2. Run **Step A grep** for each item — dump the result
3. If there's a matching existing item, update that line via Edit (do not add a new row)
4. If no match, append 1 line at the end of the appropriate existing section (`## Completed` / `## Priority Work` / `## Hold`)
5. **If you're about to create a new `##`/`###` date header, stop immediately** → return to AskUserQuestion or self-check #3-4

#### Violation cases

For the full case body, see `~/.claude/skills/cleanup/data/failed-attempts.md` "cleanup accumulating duplicates by adding new fix_plan sections"

**⚠️ Prohibition on detailed Completed records (RAG integration)**:
- The session's detailed content, analysis flow, execution logs, etc. are **fully and permanently stored in RAG** in step 3-C.1.
- Therefore, in the checklist's (`fix_plan.md` etc.) `## Completed` section, to prevent file-size bloat and preserve readability, only include a **concise summary of at most 1-2 sentences (1 line recommended)** — do not list a detailed analysis history (audit log).


### Recording targets

- Code/document/rule changes (work that has an actual artifact)
- Infra work results (deployment, migration)
- Decisions + artifacts (e.g., "/fix 1st rule strengthening — pre-sanitize RAG import")
- **Excluded**: simple questions/answers, query-only work

### Don't / Do

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Skip Step 4 entirely for non-company projects | Always record to the checklist. No company/non-company branching |
| 2 | Call the weekly-report skill in Step 4 | Step 4 is checklist-only. weekly-report is invoked only via a separate explicit user instruction |
| 3 | Create the checklist file at an arbitrary location | Follow the decision order above. User explicit > artifact-folder default > search > AskUserQuestion |
| 4 | Ignore the `<artifact-path>/checklist.md` default and use a different name | Use `checklist.md` (fixed default name) unless the user gives separate instructions |

### Session UUID Citation Rule (HARD STOP — included at cleanup end)

When citing a session identifier in a session jsonl, RAG chunk, session id, checklist work item, etc., **full 36-character UUID output is mandatory**. This applies equally to the cleanup end-report text. **Missing the UUID output entirely is also a violation** — not just truncation, complete omission is forbidden too.

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Prefix-only notation like `session jsonl(de2cee91)` | Full UUID like `session jsonl(de2cee91-8ffa-46f4-a8b4-26571bb66bd2)` |
| 2 | Truncated notation like `session abc123...` | The exact, full 36-character UUID |
| 3 | Abbreviating "for readability" | UUID is an identifier for copy·grep·API matching. Truncation = the user cannot use it directly |
| 4 | Using a prefix UUID in the cleanup completion report | Full UUID in both the completion report + checklist item |
| 5 | **The comprehensive/end report omits the UUID entirely** (only mentions commits/files/RAG) | **The end report's first line or table must include an explicit "Session ID: <UUID>" row** |

**Applicable timing**: all text throughout this skill's steps — progress reports, AskUserQuestion descriptions, completion reports, checklist items.

**End-report per-medium UUID output obligation**:

| Medium | UUID output format | Location |
|------|---------------|------|
| Comprehensive table (commits/files/RAG) | Add a `Session ID` row → `<full-36-UUID>` | At the top of the table or a separate line |
| Text report | "Session ended (`<UUID>`)" or a separate line | First or last line of the report |
| RAG result report | `Session <UUID> import complete — N chunks` | Result line |
| Checklist work item | `- [x] {work} (session `<UUID>`)` | Per item |

**Self-check (immediately before writing the cleanup end-report text every time)**:
1. Does the session UUID appear at least once in the report body? — Verify with Grep
2. Is the UUID the full 36 characters? Prefix-only/truncated/absent are all forbidden
3. Does the location match the per-medium obligation table?
4. Ending the report without outputting the UUID = a rule violation

For case history, see `~/.claude/skills/cleanup/data/failed-attempts.md` under "session UUID omitted from wrap-up report."

**Ralph mode**: record the list of completed work to `.ralph/improvements.md` in checklist form. No Agent delegation.

---

## Step 4.5: Comprehensive Result Report (HARD STOP — mandatory right before entering Step 5)

**Immediately before** calling the Step 5 next skill, report the entire session's artifacts as a **single comprehensive matrix**. The Step 4 inline report is just a per-step progress report, not a comprehensive report. It's a separate medium.

**Mandatory report-medium items** (all included in a single response text):

| Row | Content |
|---|------|
| Session ID | `Session ID: <full-36-UUID>` (consistent with the Step 4 "Session UUID Citation Rule") |
| Commits | This session's created commit SHA + repository + branch matrix |
| Files | List of files changed via Edit/Write this session (path + line changes) |
| FA Prune | Demoted sections + archive file path + HOT line count change |
| Rules added | Newly added/strengthened rules/skills/agents/hooks files + sections |
| Pattern detection | Discovered patterns + fix_plan registration result |
| BLOCKED | Items handled as BLOCKED in this session + next-session trigger conditions |

### Don't / Do

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Enter the Step 5 next call using only the Step 4 inline report | Output the Step 4.5 comprehensive matrix report, then call Step 5 next |
| 2 | Interpret the "no direct recommendation text output" rule as "the comprehensive report is also forbidden" | Comprehensive report ≠ next-action recommendation. Only the Step 5 recommendation ask is forbidden; the Step 4.5 comprehensive report is mandatory |
| 3 | Reason that "accumulated per-step inline reports are sufficient" | Per-step reports = progress reports. Comprehensive matrix = whole-session summary. Separate media. The user must be able to review everything at once |
| 4 | Omit some items like Session ID, commits, files | All 7 rows above are mandatory. State "N/A" explicitly for any that don't apply |
| 5 | Compress the comprehensive report text into the next option description | The comprehensive report is a separate response text. next options are a separate medium for deciding the next action |

### Self-check (immediately before the Step 5 next call every time)

1. Does the response text contain the 36-character Session ID UUID at least once?
2. Are all 7 rows of the matrix above included? (also state N/A explicitly)
3. Does the commits row state this session's SHA + repository + branch?
4. Does the files row state all paths Edit/Write-targeted this session?
5. Are the Step 4.5 comprehensive report and the Step 5 next call clearly separated as separate responses or separate sections?
6. **Does the BLOCKED row contain a RAG store failure item?** If yes, entering Step 5 next is **forbidden** — try all of workflow.md's "session-end RAG persistence obligation" medium matrix (MCP / vendor script / direct REST API). Only after all three media fail is entering next allowed. **Simply "stating BLOCKED" ≠ "qualified to enter next" — attempting medium alternatives is a prior obligation**

**Skip condition**: same as the Step 4 skip condition (no conversation content or only simple questions)

---

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

---

**⚠️ In Ralph mode, end here — declare cleanup complete after recording to improvements.md**

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
- **Options must contain concrete content** — no abstract labels. Put the actual work title+reason in the label/description
- **Skip option**: for a multi-question set, if an individual question has 3 or fewer options, adding `{ label: "Skip", description: "Skip this item" }` is allowed

### Step Grouping (when questions exceeds 4)

| Group | Included steps | header |
|------|----------|--------|
| Improve | Retrospect + Automation Review + Pattern Detect | "Improve" |
| Persist | Knowledge storage (documentation+infra+memory) | "Persist" |
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
| Knowledge | Write/edit documentation + add missing items to CLAUDE.md + store to Serena/Claude Code memory |
| Weekly | Call `/weekly-report generate` |
| Next | Register the selected recommendation via TodoWrite and execute immediately |

---

## Notes

- If a step has no findings, skip that step (do not output an empty result)
- Weekly Report targets only actual code changes/work
- Documentation recommendations exclude already-documented information
- Sensitive information (API keys, passwords, etc.) is excluded from documentation/memory targets
