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
- **Reporting a step as "skipped" in prose without the step's own documented skip condition being met** — e.g. saying "no RAG receiver registered, skipped" when the step's own rule (see "RAG store failure = cleanup failure" below) requires a recovery attempt + FAILED status + retry-task registration, not a silent skip. A step-level "skip" in the completion report is only valid when the exact skip condition text from that step's own section is quoted alongside it.

**Task pre-registration (when Task tools are available)**: before executing Steps 1-5, register each as a `TaskCreate` entry (in_progress for the current step, pending for the rest) so a step cannot be silently dropped mid-run — this makes "did I skip a step" mechanically checkable via `TaskList` rather than dependent on the completion-report prose being accurate. If `TaskCreate`/`TaskList` are disconnected this session, state that explicitly in the report and fall back to the per-step Skip decision principle above (still no self-judged skipping) — tool unavailability is not a license to skip steps, only a license to skip the *tracking mechanism* for them. **Pre-registration creates tasks that Step 0's prune (below) structurally cannot catch** — Step 0 runs once, at entry, and can only see tasks that were already `completed` *before* this cleanup run started. The tasks created by this pre-registration mechanism only reach `completed` status *during* Steps 1-5, after Step 0 has already run — see Step 5.5 "Self-Task Cleanup" for the closing half of this lifecycle.

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
| **3-C.1 session RAG import** | **Automatic execution — no ask** | — | Immediately import when the RAG receiver readyz responds OK |
| **3-C.2 structured discovery chunk (mode B — HARD STOP)** | **Automatic execution — no ask** | — | If the session produced **reusable discoveries/decisions/deployments** (bug root-cause, infra gotcha, a config/URL/MTU/version that took effort to find, an architecture decision), store each as a keyword-searchable chunk via the **RAG receiver's structured-store dispatch (mode B)** — separate from 3-C.1. Session import (3-C.1 mode A) has **weak keyword retrieval**: it preserves turns but does NOT make a finding queryable (e.g. "DinD MTU hang", "dev-36 k3s runner"). Skip ONLY when the session had zero reusable discovery (pure Q&A / trivial edits) — and say so explicitly in the report row |
| **3-C.3 check for missed active-artifact RAG store** | **Automatic execution — no ask** | — | Glob → identify this-session mtime artifacts → RAG receiver scroll → immediately store missing files. Matches plan/research/analysis/report/postmortem-*.md patterns |
| **3-C.4 workspace fix_plan-history sync (mode C)** | **Automatic execution — no ask** | — | If this session added `## Completed` entries to `fix_plan.md` AND the current workspace exposes a fix_plan→RAG sync script (per `rag-store.md` "fix_plan.md Completed Item RAG Sync + Delete Obligation"), run it. Session import (3-C.1) and structured chunks (3-C.2) are conversation-shaped; this sync is deliverable-shaped (task/decision history) — neither of the other two modes substitutes for it |
| Step 4 | Identify the checklist file | Decide the medium (user-specified / fix_plan / checklist.md / AskUserQuestion) | When this session has artifacts |
| Step 5 | **`Skill("wip")` call mandatory** (multi-select task registration) | Internal multi-select ask inside wip (N next-session work candidates) | **Always** — state preservation for next-session resume at cleanup end |
| **Step 5 report (HARD STOP — re-read before writing)** | **Before composing the completion report, scroll back to "Step 5 Completion Report Table Mandatory Rows" and copy its row list literally.** That section sits *above* the Step 1-5 procedure bodies, so executing the steps in order never passes through it again — the report then gets assembled from memory, which is exactly how mandatory rows (Session identity, the 3-A LLM Wiki scope-check row, the separate 3-C.1 / 3-C.2 / 3-C.4 rows) are silently dropped | — | **Always** — applies to the cleanup wrap-up table AND any separate session-end report |
| Step 5.5 | `TaskUpdate(status: "deleted")` for every completed task created this run | — | **Always** — this run's pre-registered Step 0-4.5+5 tracking tasks (plus any other task created and completed during this run) reach `completed` only after Step 0 already ran, so nothing else prunes them |

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
9. **Verify the Step 2-B mandatory output format was actually produced (HARD STOP — a Skill call alone does not satisfy this)**: a `Skill("claudify", "improve")` trace existing in the transcript proves the call happened, but NOT that its internal B sub-step (Hook Review + Skill Check, see `improve.md`) produced its documented output. Check the response text for the literal `**Hook summary**: N registered / M OK / ...` line and a named enumeration of skills invoked this session. If either is missing — replaced by an unenumerated conclusion like "0 ignored" or "all skills worked correctly" with no per-hook/per-skill breakdown — the B sub-step was skipped even though the Skill call happened. Re-run it and produce the format before reporting Step 2 as done. A "nothing changed since the last cleanup pass" judgment does not exempt this check — re-confirm the counts explicitly, even if they repeat the prior pass's numbers.

### Step 5 Completion Report Table Mandatory Rows (HARD STOP — applies to both cleanup wrap-up and session-end reporting)

The cleanup wrap-up completion-report table **and** the resulting **session-end final report** written after wip task registration (e.g., "## ✅ Session Ended", "End session report", carryover summary) must **always** include the following rows. Applying the rule only to the cleanup wrap-up table but burying it in a 1-line prose entry within a separate session-end report is a visibility gap — the same rule violation.

| Step | Result |
|------|------|
| **Session identity (mandatory)** | **`Session ID: <full-36-UUID>` + Recommend running: `/rename <model>-<topic>-<sessid8>` (2-3 candidates; each = model family token + dominant-work topic + UUID's leading 8 hex; keep the `/rename ...` command in its own code span with no label or colon inside it, so a single copy-paste is directly runnable)** |
| 0. TaskList | (cleanup result) |
| 1. Commit | (commit result or skip reason) |
| 2. Self-Improve | `claudify improve` result |
| 3. Knowledge Persist | `claudify persist` result |
| **3-A LLM Wiki scope check (mandatory row whenever `<workspace>/llm-wiki/` exists)** | **"N candidates found — dispatched to raw knowledge ingest" OR "0 candidates — session content was tooling-local, not company-facing" OR "N/A — no `llm-wiki/` in this workspace". State the outcome even when it is zero (3-A Don't/Do row 3), and reach it only after reading `llm-wiki/index.md`'s actual category list rather than the abstract `AGENTS.md` scope alone (3-A Don't/Do row 5).** |
| **3-C.1 RAG Store (mandatory row)** | **State which medium actually fired ([rag-store.md](./rag-store.md) Medium Matrix (1)-(4)) — the wording differs by medium, do not reuse one fixed template for all: purpose-built importer (medium 2) → "N JSONL log step entries / turns recorded (session import, receiver: `<importer>`) — session UUID `<uuid>`. M artifacts imported."; generic MCP store used as 3-C.1 substitute (medium 1, no purpose-built importer found) → "1 ad-hoc summary chunk added (receiver: MCP store) — session UUID `<uuid>`. NOT a full session import (no purpose-built importer found)."; medium (4) local pending queue → "❌ FAILED — queued to local pending-import queue (`<queue-file>`), retry task registered."** |
| **3-C.2 Structured discovery chunk (mode B — mandatory row)** | **M discovery chunks added (receiver structured-store dispatch, mode B) — keys: `<key1>`, … OR "none — no reusable discovery this session". Session import (mode A) alone ≠ knowledge persisted; discoveries need mode B to be searchable.** |
| **3-C.4 fix_plan-history sync (mode C — mandatory row when `fix_plan.md` gained Completed entries this session)** | **P points synced (workspace `<name>` sync script) OR "none — no new Completed entries this session" OR "no sync script for this workspace".** |
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
| 6 | Omitting the active session UUID (`<uuid>`) or substituting a placeholder in the RAG store row or report header | Always extract conversation ID and explicitly format as `session UUID <full-36-UUID>` in row 3-C.1 and report header |
| 7 | Omit the physical numerical chunk count `N` (e.g. replacing `N chunks added` with vague prose omitting `N`) | Always include the concrete integer number of chunks `N` (e.g., `12 chunks added`) and imported artifacts count `M` in row 3-C.1 (e.g. `12 chunks added (receiver: RAG import dispatch) — session UUID <uuid>. 0 artifacts imported.`) |
| 8 | On a 2nd+ `/cleanup` invocation in the same session, reconstruct this table from memory of the prior pass's report shape | Re-read this section's literal row text before composing — a remembered shape silently drops compound sub-clauses (e.g., the Session identity row's `/rename` sub-clause) that a fresh read would catch. Enforced by `block-cleanup-missing-rename.sh` (Stop) for the Session identity row specifically |

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

**Explicit `--ralph` flag in an interactive session (no `RALPH_LOOP=1`) is a distinct case from a true autonomous loop (HARD STOP)**: a true `RALPH_LOOP=1` loop gets a self-healing safety net — a step skipped this iteration can be retried on the next. A user-typed `--ralph` flag in an interactive session has no such next iteration; a step skipped here is skipped for good unless someone notices. Do not apply the two identically — see the RAG-store carve-out below, which applies regardless of which path triggered Ralph Mode.

**Ask-bypass axis vs. passive-persistence axis (HARD STOP — do not conflate)**: Ralph Mode exists because Ralph cannot call `AskUserQuestion` — it restricts only the steps that would otherwise need a user decision (rule/skill/hook edits, agent spawns, automation creation). It does **not** extend to steps that already run with **no ask in normal mode** — the RAG session-chunk store (3-C.1), the structured discovery-chunk store (3-C.2), and the missed-active-artifact store (3-C.3) are all documented above as "Automatic execution — no ask" even outside Ralph Mode. Skipping them under Ralph Mode is a category error: a step that needs no confirmation cannot be made "more autonomous-unsafe" by removing the confirmation channel. These three sub-steps **still run automatically in Ralph Mode** — only their *reporting* medium changes (append the result to `.ralph/improvements.md` instead of a chat-visible report row, since Ralph has no chat to report to). See each sub-step's own "Ralph mode" note below for the corrected behavior.

**Ralph mode behavior rules**:

| User session | Ralph mode |
|------------|-----------|
| Confirm via AskUserQuestion | Record `[NEEDS_REVIEW]` to `.ralph/improvements.md` |
| Direct modification (rules, memory, hook) | **Forbidden** — record only |
| Skill/agent creation | **Forbidden** — record candidates only |
| Delegate via Agent tool | **Forbidden** — record only |
| RAG session-chunk / discovery-chunk / missed-artifact store (3-C.1/3-C.2/3-C.3) | **Still runs automatically** — these need no ask in normal mode either. Result logged to `.ralph/improvements.md` instead of a chat report row |

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
   - **Plane-index precondition (HARD STOP)**: before flipping the marker, check whether the matched line carries a Plane index reference (the `→ Plane (<issue URL>)` suffix `plane-backlog`'s Phase-3 migration produces, per `fix-plan/sync.md` "Secondary-tracker sync cadence"). If present, the fix_plan.md line is an **index**, not the source of truth — Plane is. Complete the Plane issue first (see "Plane-indexed item completion order" below); only then check `[x]` locally.
3. After the checklist update completes, `TaskUpdate(status: "deleted")`
4. Report the cleanup count: `**Task cleanup**: N completed → deleted (fix_plan reflected)`

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Skip the fix_plan update after deleting a task | Update fix_plan **first** → then delete |
| 2 | Skip the update by saying "no corresponding item in fix_plan" | Determine this by grepping the task subject keywords |
| 3 | Check `[x]` on a Plane-indexed fix_plan.md line before the Plane issue itself is completed | Run the "Plane-indexed item completion order" gate below **before** flipping the marker |

### Plane-indexed item completion order (HARD STOP — applies to Step 0 item 2 and Step 4 Step B "matches existing item" below)

When a workspace has adopted Plane as its canonical backlog (its local `fix_plan.md`/`checklist.md` demoted to an **index** — signalled by a `workspace_profile.py --json` non-empty `plane_host`, or a pinned note in the tracker itself stating Plane is the source of truth), a matched line carrying a `→ Plane (<issue URL>)` suffix must **not** be marked `[x]` locally until the indexed Plane issue itself reflects completion. The local marker is a pointer, not the record — completing the pointer while the record it points at is still open leaves the canonical backlog wrong.

**Procedure**:
1. Extract the Plane issue URL/ID from the matched line's `→ Plane (...)` suffix (real-world example: `[INFRA-6] ... → Plane (https://plane.dgs.ai.kr/.../issues/<id>) *(Phase 3 indexing ...)*`).
2. No script in this environment currently **pushes** completion state to Plane (`plane_sync.py` is pull-only — Plane state → fix_plan marker, per `fix-plan/sync.md`). So: either (a) the Plane issue was already completed independently (verify via `plane-backlog sync --dry-run` or a direct issue-state read) — if so, the pull already reconciled it, proceed to check `[x]` locally, or (b) it has not — in that case do **not** mark local `[x]` autonomously. Surface the Plane issue URL to the user (report line or, if other decisions are already being asked this turn, fold it into that `AskUserQuestion`) and hold the local marker at its current state until the user confirms the Plane issue is completed (manually, or via a future push-capable script).
3. Never silently complete the local index while the canonical Plane record remains open — that is the exact drift this gate prevents.

| # | Don't | Do |
|---|-------|-----|
| 1 | Mark `[x]` on a Plane-indexed line because the session's own work is done, without checking Plane's state | Verify Plane reflects completion first (pull-sync or direct read) — only then flip the local marker |
| 2 | Invent a PATCH-to-Plane call inline because none exists yet | No push script exists — surface the Plane URL to the user instead of fabricating a write path |
| 3 | Treat "no push script" as license to skip the check entirely and just mark local `[x]` | Absence of automation is not absence of the obligation — ask/report, don't silently complete the index |

**Self-check (before flipping any fix_plan.md marker to `[x]` — Step 0 or Step 4)**:
1. Does the matched line carry a `→ Plane (<url>)` suffix? → If no, proceed as normal.
2. If yes, does Plane's own state already show completion (via sync or direct check)? → If yes, flip the local marker. If no/unknown, hold the marker and surface the Plane URL instead.

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

## Step 2: Self-Improve (Mistake Analysis + Review + Pattern Detection)

Analyze session mistakes, review hooks/skills, and detect patterns.

**Automated Script Execution**:
- Run `python ~/.gemini/config/skills/cleanup/scripts/fa-analyze.py` to automatically analyze `failed-attempts.md` rules, status tags, and detect recurring error classes.

[claudify/improve.md](../claudify/improve.md) — planned conversion to a `Skill("claudify", "improve")` call.
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

### 3-A. Documentation recommendation (including LLM Wiki scope check — HARD STOP)

Suggest a location to document new information discovered during the conversation. **This is an explicit check, not a silent skip** — same discipline level as 3-C.1/3-C.2, just a different destination.

**Detection targets**: troubleshooting solutions, project/infra structure, failed attempts, external service usage, environment configuration

**Documentation location recommendations**:

| Information type | Recommended location |
|----------|----------|
| Project structure/configuration | The project's `CLAUDE.md` or `README.md` |
| Personal/dev-machine infra fact (VPN client quirk, local tool path, this-session-only debugging) | Domain skill topic (`/skill-kit route`) + RAG fact point (3-C.2) — **not** the LLM Wiki |
| Company/domain knowledge (a concept, process, or fact relevant to teammates outside the current chat — the kind of thing a new hire or another department would need explained) | The workspace's **LLM Wiki** (`<workspace>/llm-wiki/`), if one exists — see below |
| Failed attempts | `pages/FAILED_ATTEMPTS.md` |
| External service integration | The project's `docs/` |
| Personal workflow | `~/.claude/CLAUDE.md` (global) |
| Troubleshooting record | Today's Logseq journal |

- Exclude information that's already documented, or sensitive information (API keys, etc.)

**LLM Wiki scope check (trigger: does `<workspace>/llm-wiki/AGENTS.md` exist for the current workspace?)**:

1. If no `llm-wiki/` exists in the workspace, skip this sub-check (report "no LLM Wiki in this workspace").
2. If it exists, **read `<workspace>/llm-wiki/index.md`'s category list first** (the `## <Category> (\`pages/<domain>/\`)` headers) — this is the Wiki's actual, currently-in-use scope, not just its abstract `AGENTS.md` definition. A category like "Harness & Tools" can already cover exactly the kind of personal-tooling/harness-debugging knowledge that the abstract "company/domain knowledge for teammates" framing (below) would wrongly exclude on its own.
3. Only after checking the real category list, ask: does anything this session discovered fit an **existing category** (including a tooling/harness category if one exists), or the Wiki's abstract scope per `AGENTS.md` (curated domain knowledge — concepts, processes, meeting outcomes, terms someone outside this chat would need explained) — **as opposed to** genuinely session-local/one-off debug values that belong in RAG only?
4. Never write directly to `pages/*.md` — the Wiki's own HARD STOP requires raw knowledge ingestion first (`raw/<slug>.md` with a real `source_path`), then `pages/` updates derive from that raw source. Dispatch to the raw knowledge ingest skill (e.g. `raw-ingest` if available); do not hand-author `pages/` content inline from cleanup.
5. State the outcome explicitly in the Step 5 comprehensive report, even when the answer is "nothing this session belongs in the Wiki" — silence here is exactly the gap this section closes.

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat writing to a skill file (e.g., an infra fact added to a domain skill topic) as satisfying the LLM Wiki check too | They're different destinations for different audiences — skill files are Claude Code's own operational knowledge; the Wiki is curated for human teammates. Doing one doesn't exempt checking the other |
| 2 | Recommend the Wiki for every infra/troubleshooting fact discovered this session, regardless of audience | Personal dev-machine/session-local facts (a VPN client quirk on *this* machine, a local file path) stay in skill/RAG — pushing them into the company Wiki is scope creep the Wiki's own curation principle doesn't want |
| 3 | Silently omit the Wiki row from the Step 5 report when there's nothing to store | Always state the outcome — "N candidates found" or "0 candidates — session content was tooling-local, not company-facing" |
| 4 | Author `pages/*.md` directly from cleanup to save a step | Raw knowledge ingestion first (HARD STOP per the Wiki's own `AGENTS.md`) — cleanup dispatches to the ingest skill, it does not hand-write pages |
| 5 | Apply only the abstract "company/domain knowledge for teammates" definition from `AGENTS.md` and conclude "0 candidates" without reading `index.md`'s actual category list first | Read `index.md`'s categories before judging scope — a category already covering harness/tooling knowledge (e.g. "Harness & Tools") means session-local-sounding tooling facts can still be in-scope. The abstract definition alone under-scopes relative to the Wiki's real, curated content |

**Self-check (every cleanup run, before the Step 5 report)**:
1. Does `<workspace>/llm-wiki/AGENTS.md` exist? If no, report N/A and move on.
2. If yes, did you Read `index.md`'s category list before judging scope? If not, do that first — do not judge from the abstract `AGENTS.md` definition alone.
3. Does any session discovery meet an existing category's actual scope (not just the abstract "company knowledge" framing), or the Wiki's abstract scope for teammates?
4. If yes, dispatch to the raw knowledge ingest skill — never hand-author `pages/`.
4. State the explicit outcome (candidates found + dispatched, or none) in the Step 5 report — this row is mandatory whenever `llm-wiki/` exists in the workspace, matching the RAG row's mandatory-reporting discipline.

### 3-B. Infra documentation check

**Skip condition**: skip if there was no infra work

If infra-related work was performed, check whether the discovered information has been documented in CLAUDE.md.

### 3-C. Memory storage

Store project knowledge learned in this session to memory.

#### Pre-review: storage location classification

| Information type | Storage location | Example |
|----------|----------|------|
| Volatile session-only fact (changes every run, no reuse value beyond this session) | **Memory** (only if no domain skill owns the topic) | Current resource usage snapshot, a one-time debug value |
| Tool/credential/config reference tied to an existing domain (Vault path, API key location, server IP, install path) | **Skill** (`/skill-kit route` — add to or create a topic in the owning domain skill, e.g. `es6kr/vault.md`'s credential-location tables) | Where a PAT/token/config file lives, which CLI manages a service |
| Infra/IaC configuration knowledge | **Skill** (`/skill-kit route`) | Terraform structure, ArgoCD management procedure |
| Domain knowledge, procedure, guide | **Skill** (`/skill-kit route`) | Deployment procedure, troubleshooting guide |
| Behavioral rule, prohibition | **Rules** | Mistake-prevention rule (handled in Step 2 retrospect) |

**Judgment criterion**: usable procedurally → skill, addable to an existing skill topic → skill, tied to a credential/tool that a domain skill already documents → that skill (not memory), purely session-local with no domain skill owning it → memory.

**Why this table changed**: Claude Code's project memory (`~/.claude/projects/*/memory/*.md`) is a harness-specific, non-portable medium — it disappears in other environments (Antigravity, OpenClaw) and doesn't travel with the workspace's own rule/skill system. A credential-location or tool-reference fact is exactly the kind of thing a future session (in any environment) needs to rediscover — routing it to memory silently ties it to "this Claude Code project only." Prefer the domain skill that already owns the topic (see the existing credential-location tables in `es6kr/vault.md`, `es6kr/infra.md` as the established pattern) over creating a new memory file.

#### Storage tools (usable in parallel — different purposes)

| Tool | Condition | Purpose | Invocation |
|------|------|------|------|
| **RAG receiver import dispatch** | RAG receiver available (readyz responds) | **Whole-session semantic chunk** — searchable via the receiver's find tool for conversation flow in the next session | 3-C.1 procedure below |
| Serena MCP | `activate_project` responds | Structured key-value facts (memory_set/memory_get) | `list_memories` → `edit_memory` / `write_memory` |
| Claude Code auto memory | Only for facts genuinely valid in Claude Code alone (this harness's own settings/session state) — NOT a default fallback for domain/reference facts. See "Pre-review" table above; most facts route to a skill instead | Markdown file (`memory/MEMORY.md` + individual) | Edit/Write |

RAG and Serena are used in parallel where available. Claude Code auto memory is conditional, not a third parallel default — check the Pre-review table first; a skill destination usually applies instead.

#### 3-C.1 Session semantic chunk storage (RAG receiver dispatch)

**Call when the condition is met**:

##### Availability check — 2 stages (HARD STOP)

This step is mandatory before entering RAG store. **Do not conclude "unreachable" from a single signal**.

| Order | Signal | Meaning | Action |
|-----|------|------|------|
| 1 | RAG receiver MCP tool available (in the system reminder's "available tools" list or matched via `ToolSearch` — the receiver's store/find tool name) | MCP is already connected to the receiver — primary availability signal | Run [rag-store.md](./rag-store.md) "Purpose-fit priority for 3-C.1" detection procedure FIRST — a purpose-built session-importer script (medium 2) outranks this generic MCP tool for whole-session import, even though the MCP tool is available. Only call the MCP store tool directly for 3-C.1 if no purpose-built importer is found |
| 2 | The endpoint readyz probe explicitly documented by the receiver skill (use only the endpoint from the receiver's `<skill>:<topic>.md` doc) | Direct HTTP probe — secondary availability signal | MCP not connected, but the endpoint is alive. Enter via the script path |
| **FAILED** | (1) MCP unavailable AND (2) endpoint probe timeout/HTTP 5xx | Both must fail to be unreachable | **Entire cleanup status = FAILED. Do not declare "✅ Complete"** — apply the "RAG store failure = cleanup failure" procedure below |

##### After a successful import: advance the receiver's gap baseline (HARD STOP)

The session import performed here is the **same operation** that a receiver's mid-session gap hook triggers on its own. Such a hook typically decides whether to fire by comparing the transcript's current line count against a per-session checkpoint file that, by default, **only the hook itself writes**. If cleanup imports without advancing that checkpoint, the baseline stays stale — right after this cleanup the hook still measures against the old point, fires again, and demands a duplicate import of the very turns 3-C.1 just stored.

So on a successful 3-C.1 import, advance the receiver's baseline **in the same step**. The receiver skill documents the exact path and command (for the es6kr receiver, see its `qdrant-import` topic, "The checkpoint is a shared baseline"). Skip only when the receiver exposes no such checkpoint.

| # | Don't | Do |
|---|-------|-----|
| 1 | End 3-C.1 at "import succeeded" and leave the checkpoint untouched | Advance the receiver's baseline in the same step — the import is not finished until the state tracking it agrees |
| 2 | Treat the checkpoint as the hook's private state | It records "where a session import last happened", whichever entry point performed it |
| 3 | Let the hook fire right after cleanup and satisfy it with another import | That import is a no-op re-run over turns already stored; the fix is the stale baseline, not another import |

##### RAG store failure = cleanup failure (HARD STOP)

**3-C.1 RAG store is a mandatory cleanup step — on failure/unavailability, report the entire cleanup as FAILED.** RAG store is the core medium for "session-end state preservation" (this skill's philosophy #2), and if the session ends in a missed state, the opportunity to store the session chunk is effectively lost ("retry next session" is a weak trigger, so actual retries rarely happen).

**On failure, all of the following are mandatory**:

1. **Recovery-attempt decision is a mandatory ask, not an autonomous judgment (HARD STOP)** — when the failure occurs and connection info for the underlying service is knowable (an endpoint documented in the receiver topic, a local process/port, a VPN state, etc. — i.e., there is *something* to check or restart), do NOT autonomously decide either "attempt recovery" or "skip straight to fallback." Call `AskUserQuestion` immediately: state the failure (tool/endpoint + error text), and offer options such as "Attempt recovery now (check/restart the underlying service, re-probe)" / "Skip recovery — fall back to local pending queue now" / "Investigate more (I'll look at the connection details first)". Only proceed with whichever path the user selects. This applies even mid-cleanup — do not defer the ask to the end-of-cleanup Phase 2 batch, since the RAG store step blocks subsequent steps' correctness (retry-task registration content depends on the outcome).
   - **Exception**: if no connection info is knowable at all (no documented endpoint, no local process to check, receiver skill provides no diagnostic path) — there is nothing to ask about; skip directly to the FAILED procedure below without asking (asking "recover?" with no actionable path is a hollow ask).
2. On confirmed recovery failure (whether reached via the user selecting "skip" or via an attempted-and-failed recovery), mark the Step 5 completion-report table's "3-C.1 RAG Store" row as **`❌ FAILED`** (not worded as "Skipped"/"held")
3. Use **"⚠️ cleanup FAILED (RAG store failed)"** instead of "✅ cleanup complete" in the report title/header
4. **Medium (4) local pending-import queue file — the actual preservation mechanism (HARD STOP, do this BEFORE step 5)**: write `~/.claude/skills/cleanup/data/rag-pending/<session-uuid>.md` per [rag-store.md](./rag-store.md) "Medium (4)" spec (session UUID + date, artifact paths, distilled facts with metadata, one-line unreachable-reason). A `TaskCreate`/fix_plan retry note alone is a reminder, not preservation — per rag-store.md's own self-check, the queue file is the durable guarantee that survives even if no future session reads the retry task.
5. **Retry task registration obligation**: register a "Retry RAG store (session <UUID> + N artifacts)" pending task via `TaskCreate` — do not end with carryover text alone. This is supplementary to step 4's queue file, not a substitute for it.
   - **Fallback when `TaskCreate` itself is disconnected (HARD STOP)**: do not silently drop the retry obligation. Register it in the workspace's `fix_plan.md` `## Hold` section instead, using the same `[BLOCKED] ... **trigger: <condition>**` format as other hold items (trigger = "Task tools reconnect" or equivalent). This mirrors step4-wrapup.md's medium-separation principle (BLOCKED external-wait items go to fix_plan.md hold, not a task) extended to the case where the task-tracking tool itself is the unavailable dependency. Step 4's queue file write still applies regardless of `TaskCreate` availability — it is a plain file write, not gated on the task tool.
6. Report the failure cause (MCP disconnected / endpoint down / underlying network down / **TaskCreate disconnected**) + recovery path + queue file path in 1 line

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Declare "✅ Session cleanup complete" after skipping the RAG store | RAG failure = cleanup FAILED. State ⚠️ FAILED in the header |
| 2 | End with only "Skipped — retry candidate for next session" carryover text | Write the medium (4) local pending-import queue file (item 4 above) + register a `TaskCreate` retry task (pending) + report failure cause/recovery path |
| 3 | Judge "complete" because other cleanup steps finished | Even 1 mandatory step FAILED = the entire cleanup is FAILED. Show per-step status in the report table |
| 4 | Judge FAILED immediately after confirming RAG receiver unavailability with no recovery decision | Confirm the underlying connectivity state, then `AskUserQuestion` whether to attempt recovery (per item 1 / row 5) before judging FAILED — do not autonomously restart |
| 5 | Autonomously attempt recovery (or autonomously skip it) when connection info is knowable, then only report the outcome after the fact | `AskUserQuestion` first whenever there's an actionable recovery path — recovery may touch infra state (restarting a service, etc.) the user should decide on, not something to silently do or silently skip |
| 6 | Treat "I have a safe local pending-queue fallback" as satisfying the recovery-attempt obligation | The fallback (medium 4) is the *terminal* step after recovery is declined/fails — it does not substitute for asking whether to attempt recovery first |

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
5. If 1, 2, and 3 all fail, **is there any connection info to act on** (documented endpoint, known local process/port, VPN state)? → If yes, `AskUserQuestion` before doing anything else (recovery vs skip vs investigate) — do not decide autonomously. If no actionable info exists at all, apply the **cleanup FAILED procedure** directly (above)
6. **Before calling ANY store/import command, have you Read the receiver skill's topic file THIS TURN** (e.g. `es6kr/qdrant-import.md`)? — A generic MCP tool (e.g. `mcp__qdrant__qdrant-store`) succeeding is NOT proof the receiver's documented protocol (session-turn import script, WSL execution requirement, sanitize/compress preprocessing, idempotent chunk IDs) was followed. "The tool call worked" ≠ "the receiver's Mode A/B/C contract was satisfied" — Read the topic file first, then use its documented invocation (case history: failed-attempts.md "RAG store/search handled ad-hoc instead of the existing permanent script")

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
| 4 | Treat "I wrote a memory/skill file this session" as evidence that dual-write is already satisfied, and report 3-C.2 as "none — already covered by the memory files above" | A memory file write is (a) only. It is not evidence against doing (b) — it is evidence a fact was distilled, which is exactly 3-C.2's trigger. Writing (a) without (b) is the Don't-row-3 violation restated with different wording |

**Self-check (immediately before writing the Step 5 "3-C.2" report row)**: for **each** memory/skill file (a) written or edited in this session's Step 3-C, was a corresponding RAG receiver fact-point (b) also stored for that same fact? Enumerate them by filename — if any (a) has no matching (b), that is an open dual-write, not a completed one; store it now before reporting 3-C.2. "Already covered by memory files" is never a valid 3-C.2 skip justification — the only valid skip is "no reusable discovery this session" (no memory/skill files were written at all).

#### 3-C.3 Check for missed active plan/research/analysis RAG store (HARD STOP)

The `skill-usage.md` "Generic skill artifact RAG store obligation" rule says **immediately after writing** is the store trigger. However, without an enforcement medium (a hook, etc.), the write-time trigger is sometimes missed. cleanup serves as that fallback — check active artifacts generated in this session for anything missing from RAG + store them.

**Check targets (Hybrid Sweep — Option C)**:
- `**/.ralph/docs/generated/{plan,research,analysis,report,postmortem}-*.md`
- `**/.omc/plans/*.md`
- **Session-Brain Root Sweep (`<appDataDir>/brain/<conversation-id>/*.md`)**:
  - Direct non-recursive check of all `.md` files in the active session's brain root.
  - **Automation Helper Script**: `python .agents/skills/cleanup/scripts/hybrid_sweep_rag.py <session_brain_dir>`
  - If a `.metadata.json` sidecar exists (`<file>.md.metadata.json`), check `userFacing` value.
  - Fallback: If no `.metadata.json` or schema differs, exclude known internal control files (`task.md`, `ask.md`), and treat all other unrecognized `.md` files (e.g. `outputs_classification_report.md`, `llm_wiki_structure_report.md`) as active artifact candidates for RAG store.
- **Dual LLM Wiki Sync Helper**:
  - `python .agents/skills/cleanup/scripts/sync_dual_wiki.py` (Syncs public artifacts between the workspace's own internal LLM Wiki repos)


**Procedure**:

1. **Identify files via Glob/Hybrid Sweep with mtime ≥ session start time** — active artifacts written/edited in this session (including unrecognized session-brain `.md` files captured via Option C)
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
| 5 | Check an IDE session-brain directory for only one known file pattern (e.g. `walkthrough.md`) and treat the directory as covered | Every file pattern the directory can produce needs its own Glob row — a directory being "already on the list" does not mean every artifact type inside it is checked |

**Self-check (every time during cleanup Step 3)**:
1. Identify `**/{plan,research,analysis,report,postmortem}-*.md` files written/edited this session (Glob mtime filter)
2. Count of identified files = N. If N=0, skip
3. If N≥1, run the RAG receiver's scroll per file → check existing chunk count
4. Files with 0 chunks = storage obligation. Call immediately + report quantitatively
5. Omitting the report = this sub-step is incomplete

**Ralph mode**: still stores un-stored files (per the "Ask-bypass axis vs. passive-persistence axis" carve-out in the top-level "Ralph Mode" section — 3-C.3 needs no ask in normal mode either). Log the artifact list + store result to `.ralph/improvements.md` instead of a chat report row.

**Ralph mode**: 3-A/3-B (documentation-location recommendation, infra-doc edit check) perform detection+recording only (`.ralph/improvements.md`) — these would normally prompt the user for a location/edit decision. **3-C.1/3-C.2/3-C.3 (RAG session/discovery/artifact store) are exempt from this restriction and still run automatically** — they carry no ask in normal mode, so Ralph Mode's ask-bypass rationale does not apply to them (see top-level "Ask-bypass axis vs. passive-persistence axis"). Only direct modification of rules/skills/hooks/memory files stays recording-only.

#### 3-C.4 Workspace fix_plan-history sync (mode C — HARD STOP)

**3-C.1/3-C.2 alone do not satisfy a workspace's "all deliverables must be persisted" obligation** — session chunks and discovery chunks are conversation-shaped, not deliverable-shaped. When `fix_plan.md` gained new `## Completed` entries this session, the deliverable record itself (not just the conversation about it) must reach the RAG store. `rag-store.md`'s "fix_plan.md Completed Item RAG Sync + Delete Obligation" section owns the full sync/delete procedure — this sub-step's only job is to make sure that procedure actually gets invoked as part of cleanup, instead of remaining a rule that's easy to forget because nothing in this checklist named it.

**Procedure**:
1. Did this session add any `## Completed` entries to the current workspace's `fix_plan.md`? If no, skip (report "none — no new Completed entries this session")
2. Does the current workspace expose a fix_plan→RAG sync script (e.g. a `fix-plan-to-qdrant`-style topic under that workspace's own skill)? Search installed skills' Topics tables for a description matching "fix_plan Completed → RAG" / "workspace fix-plan history". If none exists, report "no sync script for this workspace" — this sub-step does not mandate building one
3. If both hold, run `rag-store.md`'s "fix_plan.md Completed Item RAG Sync + Delete Obligation" procedure (bulk-sync → delete synced `## Completed` body) and report the point count

**Don't / Do**:

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat 3-C.1 (session import) as covering fix_plan's Completed history because the conversation that produced it was imported | Session import preserves turn-by-turn dialogue; it does not make "what got completed, and when" independently queryable. Run the workspace sync script separately |
| 2 | Skip this sub-step silently because it's new and easy to forget | Report one of the three outcomes explicitly (synced P points / none this session / no script for this workspace) in the Step 5 table |

**Self-check (every time during cleanup Step 3, after 3-C.3)**:
1. Grep this session's `fix_plan.md` diff for new `## Completed` lines — count ≥1?
2. If yes, does a workspace-specific sync script exist? (Topics-table search, not a guess)
3. If both yes, run it and get the point count before reporting Step 5

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
| Matches an existing `- [ ]` or `[BLOCKED]` item | **Update that item to `- [x]`** + append 1 line of completion info (commit/file/verification). Do not add a new row. **If the line carries a `→ Plane (<url>)` index suffix, apply the "Plane-indexed item completion order" gate (Step 0 above) first** — do not flip to `[x]` until Plane itself reflects completion |
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
| 6 | Flip a Plane-indexed line (`→ Plane (<url>)` suffix) to `[x]` because this session's work on it is done | Apply the "Plane-indexed item completion order" gate (Step 0 above) — the Plane issue is the source of truth, the local line is its index |

#### Self-check (immediately before editing fix_plan every time)

1. Extract a 1-line summary of this session's work items
2. Run **Step A grep** for each item — dump the result
3. If there's a matching existing item, update that line via Edit (do not add a new row)
4. If no match, append 1 line at the end of the appropriate existing section (`## Completed` / `## Priority Work` / `## Hold`)
5. **If you're about to create a new `##`/`###` date header, stop immediately** → return to AskUserQuestion or self-check #3-4
6. **If you're about to flip a matched line to `[x]` and it carries a `→ Plane (<url>)` suffix, stop and run the "Plane-indexed item completion order" gate (Step 0 above) first** — do not flip until Plane itself reflects completion

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

### Session Identity Rule — UUID + name recommendation (HARD STOP — included at cleanup end)

A session has **two identity axes**, and the cleanup end-report must carry **both**:
1. **UUID** (machine identity — for grep / RAG / transcript matching), and
2. **A human-readable name recommendation** (findability — what the user sees in the session list and passes to `/rename`).

**UUID**: when citing a session identifier in a session jsonl, RAG chunk, session id, checklist work item, etc., **full 36-character UUID output is mandatory**. This applies equally to the cleanup end-report text. **Missing the UUID output entirely is also a violation** — not just truncation, complete omission is forbidden too.

**Name recommendation (mandatory in the end-report)**: the cleanup end-report must also propose **2-3 `/rename` candidates** synthesized from the session's main work. Emitting only the UUID and no name recommendation is a violation — the UUID is not human-findable in the session list. `/rename` is a built-in the agent cannot run itself, so present the candidates for the user to copy.

**Format — `<model>-<topic>-<sessid8>` (mandatory)**: each candidate fuses machine identity and human identity into one copy-pasteable name so the session list entry says *which model produced it* and *which transcript it maps to*:
- `<model>` — the family token of the current model ID (`claude-opus-4-8` → `opus`, `claude-sonnet-5` → `sonnet`, `claude-haiku-4-5` → `haiku`, `claude-fable-5` → `fable`). Read it from the SessionStart `Current model:` line.
- `<topic>` — the session's single dominant theme (a skill / PR / feature), kebab-case, short (a few tokens), in the session's own working language.
- `<sessid8>` — the session UUID's leading 8 hex characters (the first hyphen-delimited group), so the name greps straight back to the transcript / RAG chunk.

Example: `opus-vsix-release-a1b2c3d4` (the `<sessid8>` shown is illustrative — always substitute the real session's leading 8 hex). This is cleanup's own recommendation format: it deliberately extends the bare single-slug convention the standalone `/rename` skill uses, adding the model prefix + session-id suffix for end-of-session findability + greppability.

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Prefix-only notation like `session jsonl(a1b2c3d4)` | Full UUID like `session jsonl(a1b2c3d4-e5f6-7890-abcd-ef1234567890)` |
| 2 | Truncated notation like `session abc123...` | The exact, full 36-character UUID |
| 3 | Abbreviating "for readability" | UUID is an identifier for copy·grep·API matching. Truncation = the user cannot use it directly |
| 4 | Using a prefix UUID in the cleanup completion report | Full UUID in both the completion report + checklist item |
| 5 | **The comprehensive/end report omits the UUID entirely** (only mentions commits/files/RAG) | **The end report's first line or table must include an explicit "Session ID: <UUID>" row** |
| 6 | Propose a bare topic-slug name (no model prefix, no session-id suffix) in the cleanup end-report | Use the `<model>-<topic>-<sessid8>` format — e.g. `opus-vsix-release-a1b2c3d4` — so the name carries model + session-id for findability + grep |
| 7 | Glue a label and colon inside the same code span as the command (e.g. `` `Recommend: /rename <name>` ``) — copying that span pastes "Recommend: /rename <name>" as one broken string | Keep the command in its own clean span — `` `/rename <name>` `` — with the label as plain text outside it, so a single copy-paste of the span is directly runnable |

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
5. Does the report include a `/rename` **name recommendation** (2-3 candidates) in the `<model>-<topic>-<sessid8>` format (model family token + dominant-work topic + UUID leading 8 hex)? — a UUID-only report, or a bare topic-slug missing the model prefix / session-id suffix, is incomplete
6. Is the `/rename <name>` command isolated in its own code span, with no label text or colon inside that span? — a glued `` `Recommend: /rename <name>` `` span breaks copy-paste-to-run

For case history, see `~/.claude/skills/cleanup/data/failed-attempts.md` under "session UUID omitted from wrap-up report."

**Ralph mode**: record the list of completed work to `.ralph/improvements.md` in checklist form. No Agent delegation.

---

## Step 4.5: Comprehensive Result Report (HARD STOP — mandatory right before entering Step 5)

**Immediately before** calling the Step 5 next skill, report the entire session's artifacts as a **single comprehensive matrix**. The Step 4 inline report is just a per-step progress report, not a comprehensive report. It's a separate medium.

### Walkthrough file — persist the comprehensive report, not just chat text (HARD STOP)

Chat text alone is not a state-preservation medium — it scrolls away and is not resumable across a compact/session boundary the way a file is. Antigravity's `wip/antigravity.md` already mandates a persistent `walkthrough.md` artifact with incremental updates as work progresses (its own environment's "Mandatory Incremental Walkthrough Update" rule); Claude Code sessions never got the equivalent, so this comprehensive report existed only as ephemeral response text.

**Procedure**: in addition to emitting the comprehensive matrix as response text (unchanged), write (or, on a 2nd+ cleanup pass this session, incrementally update) the same content to a file named `walkthrough-<topic>-<sessid8>.md`, using the storage-location fallback logic from `vibe-coding/artifact-rules.md` "Artifact Storage Locations" (`{ws}/llm-wiki/generated/` → `{ws}/.ralph/docs/generated/` (or the workspace's equivalently-named Ralph-loop directory, e.g. `.agents/docs/generated/`) → `{ws}/.omc/plans/` → `{ws}/docs/generated/` fallback). `<topic>` and `<sessid8>` follow the same convention as the `/rename` recommendation (dominant-work topic, kebab-case; session UUID's leading 8 hex).

**Content**: the walkthrough file body is a narrative account of the session's work — not merely a copy of the comprehensive matrix table. Include what was attempted, what was found, what decisions were made and why, and what the matrix's rows summarize in table form. The matrix table itself may be embedded at the end of the file as a quick-reference appendix.

**Incremental update, not overwrite-then-forget**: if `/cleanup` fires more than once in the same session, append/update the existing walkthrough file (matching the file already written earlier in the session) rather than creating a second one — mirrors Antigravity's incremental-update requirement.

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat the chat-text comprehensive report as sufficient state preservation | Also write it to a `walkthrough-<topic>-<sessid8>.md` file — chat text is ephemeral, the file persists |
| 2 | Copy the matrix table verbatim as the entire file body | Write a narrative account (what/why/decisions), with the matrix as an appendix |
| 3 | Create a new walkthrough file on every `/cleanup` firing within the same session | Update the existing session walkthrough file incrementally |
| 4 | Guess a storage path | Follow `vibe-coding/artifact-rules.md`'s Artifact Storage Locations fallback logic |

**Mandatory report-medium items** (all included in a single response text):

| Row | Content |
|---|------|
| Session ID | `Session ID: <full-36-UUID>` (consistent with the Step 4 "Session Identity Rule") |
| Session name | Recommend running: `/rename <model>-<topic>-<sessid8>` — 2-3 candidates (model family token + dominant-work topic + UUID leading 8 hex), e.g. `/rename opus-vsix-release-a1b2c3d4` (findability + greppability in the session list; keep the `/rename ...` command in its own code span with no label/colon glued to it, so copy-paste runs directly) |
| Commits | This session's created commit SHA + repository + branch matrix |
| Files | List of files changed via Edit/Write this session (path + line changes) |
| FA Prune | Demoted sections + archive file path + HOT line count change |
| Rules added | Newly added/strengthened rules/skills/agents/hooks files + sections |
| Pattern detection | Discovered patterns + fix_plan registration result |
| BLOCKED | Items handled as BLOCKED in this session + next-session trigger conditions |
| **Walkthrough file (mandatory row)** | **Path of the `walkthrough-<topic>-<sessid8>.md` file written/updated per the "Walkthrough file" subsection above** |

### Don't / Do

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Enter the Step 5 next call using only the Step 4 inline report | Output the Step 4.5 comprehensive matrix report, then call Step 5 next |
| 2 | Interpret the "no direct recommendation text output" rule as "the comprehensive report is also forbidden" | Comprehensive report ≠ next-action recommendation. Only the Step 5 recommendation ask is forbidden; the Step 4.5 comprehensive report is mandatory |
| 3 | Reason that "accumulated per-step inline reports are sufficient" | Per-step reports = progress reports. Comprehensive matrix = whole-session summary. Separate media. The user must be able to review everything at once |
| 4 | Omit some items like Session ID, commits, files | All 8 rows above are mandatory. State "N/A" explicitly for any that don't apply |
| 5 | Compress the comprehensive report text into the next option description | The comprehensive report is a separate response text. next options are a separate medium for deciding the next action |
| 6 | Emit the comprehensive matrix as response text only, with no `walkthrough-<topic>-<sessid8>.md` file written | The walkthrough file is a mandatory row, not an optional enhancement — chat text alone does not persist across compact/session boundaries |

### Self-check (immediately before the Step 5 next call every time)

1. Does the response text contain the 36-character Session ID UUID at least once? **Cross-check the exact UUID against the most recent hook-injected `Current session ID:` line in this turn (or a marker-method result) — a UUID copied from a memory file's `originSessionId` frontmatter, an old chat reference, or "the one I've been using all session" is not a valid source. If a RAG import earlier in the session used a different UUID than what's injected right now, that import targeted the wrong session's JSONL — re-run it with the correct UUID before finalizing this row.**
2. Are all 8 rows of the matrix above included, INCLUDING a literal `3-C.1 RAG Store` row (bold/highlighted per the mandatory-rows table)? A comprehensive report that reports RAG results only in earlier prose and omits the dedicated row is incomplete — go back and add it. (also state N/A explicitly for any non-applicable row)
3. Does the commits row state this session's SHA + repository + branch?
4. Does the files row state all paths Edit/Write-targeted this session?
5. Are the Step 4.5 comprehensive report and the Step 5 next call clearly separated as separate responses or separate sections?
6. **Does the BLOCKED row contain a RAG store failure item?** If yes, entering Step 5 next is **forbidden** — try all of workflow.md's "session-end RAG persistence obligation" medium matrix (MCP / vendor script / direct REST API). Only after all three media fail is entering next allowed. **Simply "stating BLOCKED" ≠ "qualified to enter next" — attempting medium alternatives is a prior obligation**
7. **Has the `walkthrough-<topic>-<sessid8>.md` file actually been written/updated on disk (not just planned in text)?** Verify with a real file check before citing its path in the Walkthrough file row — a described-but-unwritten path is a violation of this same gate

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

## Notes

- If a step has no findings, skip that step (do not output an empty result)
- Weekly Report targets only actual code changes/work
- Documentation recommendations exclude already-documented information
- Sensitive information (API keys, passwords, etc.) is excluded from documentation/memory targets
