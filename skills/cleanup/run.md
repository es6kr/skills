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

**Task pre-registration (when Task tools are available)**: before executing Steps 1-5, register each as a `TaskCreate` entry (in_progress for the current step, pending for the rest) so a step cannot be silently dropped mid-run — this makes "did I skip a step" mechanically checkable via `TaskList` rather than dependent on the completion-report prose being accurate. If `TaskCreate`/`TaskList` are disconnected this session, state that explicitly in the report, then fall back to the **`claude-task` CLI** (`todowrite` skill's `claude-task` topic — `claude-task --env agent add/list/update`, persisting to `~/.agents/tasks/default/`) as the step-tracking medium, mirroring the fix skill's Step 0 fallback — before that, actually attempt one direct `TaskCreate` call (a ToolSearch no-match alone cannot distinguish "disconnected" from "disabled in this context"; only the call's error text can, and the "disabled" case should be reported to the user). Only if the CLI is also unusable, fall back to the per-step Skip decision principle above (still no self-judged skipping) — tool unavailability is not a license to skip steps, only a license to degrade the *tracking mechanism* for them. Untracked step state is exactly what produces duplicated or dropped report media later in the pass (see the "Same-pass duplication rule"). **Pre-registration creates tasks that Step 0's prune (below) structurally cannot catch** — Step 0 runs once, at entry, and can only see tasks that were already `completed` *before* this cleanup run started. The tasks created by this pre-registration mechanism only reach `completed` status *during* Steps 1-5, after Step 0 has already run — see Step 5.5 "Self-Task Cleanup" for the closing half of this lifecycle.

## Execution Order

1. **Commit session changes** → check for uncommitted changes and commit
2. **Self-Improve** → mistake analysis + hook/skill review + pattern detection (planned as `/claudify improve`)
3. **Knowledge Persist** → documentation recommendation + infra check + memory storage (planned as `/claudify persist`)
4. **Checklist & Backlog Sync** → update completed tasks and sync external trackers via `Skill("backlog")` and helper scripts (`update_item.py`, `plane_sync.py`)
4.5. **Weekly Report** → record work (company projects only)
5. **Register next-session work as wip** → delegate to `Skill("wip")` (multi-select task registration, state preservation for compact/rewind)

### Per-Step Invocation Obligation Self-Check Table (HARD STOP)

Each step clearly distinguishes between **automatic skill calls** and **user-decision asks**. Do not bypass a step with a text-only report.

| Step | Invocation obligation (automatic) | Ask (user decision) | Auto-invocation condition |
|------|------------------|------------------|---------------|
| Step 0 | Call `TaskList` | — | Clean up when TaskList has completed tasks |
| Step 0.1 (Context & Session Profile) | **Automatic execution — no ask**: run `context-usage-now.sh` or `python skills/session/scripts/profile-session.py --current --compact-summary` | — | **Always** — measures token percentage and evaluates Auto-compact risk (`[LOW]` ~ `[CRITICAL]`) |
| Step 0.5 (4.5 Resume import) | RAG receiver import dispatch (receiver resolved from the workspace config) for each discovered file | — | RAG receiver readyz response + research-*/plan-* discovered |
| Step 1 | `Skill("commit-tidy")` or `/commit-tidy` | Decide split strategy (internal ask inside the skill) | When there is 1+ uncommitted change |
| Step 2 (Self-Improve) | **`Skill("claudify", "improve")` call mandatory** — retrospect + automation review + pattern detect | How to handle findings (internal Phase 2 ask inside the skill) — with `--auto`, proceed with the documented safe default instead of asking (see "Auto Mode vs. Ralph Mode") | **Always** (regardless of whether the conversation had mistakes/patterns — the skill judges) |
| Step 3 (Knowledge Persist) | **`Skill("claudify", "persist")` call mandatory** + RAG receiver import dispatch 3-C.1 | Storage location (internal ask inside the skill) — with `--auto`, use the default medium for that content type instead of asking (see "Auto Mode vs. Ralph Mode") | **Always** + auto-import when the RAG receiver readyz responds |
| **3-C.1 session RAG import** | **Automatic execution — no ask** | — | Immediately import when the RAG receiver readyz responds OK |
| **3-C.2 structured discovery chunk (mode B — HARD STOP)** | **Automatic execution — no ask** | — | If the session produced **reusable discoveries/decisions/deployments** (bug root-cause, infra gotcha, a config/URL/MTU/version that took effort to find, an architecture decision), store each as a keyword-searchable chunk via the **RAG receiver's structured-store dispatch (mode B)** — separate from 3-C.1. Session import (3-C.1 mode A) has **weak keyword retrieval**: it preserves turns but does NOT make a finding queryable (e.g. "DinD MTU hang", "dev-36 k3s runner"). Skip ONLY when the session had zero reusable discovery (pure Q&A / trivial edits) — and say so explicitly in the report row |
| **3-C.3 check for missed active-artifact RAG store** | **Automatic execution — no ask** | — | Glob → identify this-session mtime artifacts → RAG receiver scroll → immediately store missing files. Matches plan/research/analysis/report/postmortem-*.md patterns |
| **3-C.4 workspace fix_plan-history sync (mode C)** | **Automatic execution — no ask** | — | If this session added `## Completed` entries to `fix_plan.md` AND the current workspace exposes a fix_plan→RAG sync script (per `rag-store.md` "fix_plan.md Completed Item RAG Sync + Delete Obligation"), run it. Session import (3-C.1) and structured chunks (3-C.2) are conversation-shaped; this sync is deliverable-shaped (task/decision history) — neither of the other two modes substitutes for it |
| **Step 4 (Checklist & Backlog)** | **`Skill("backlog")` or script helper (`update_item.py` / `plane_sync.py`) mandatory** — update completed items and sync external trackers without direct text editing | Decide target tracker (fix_plan / checklist / Plane) if ambiguous | When this session completed tasks or produced backlog items |
| Step 4.5 (Weekly Report) | Check company project scope and record weekly report | Weekly Report content/skip approval | Company project work |
| Step 5 | **`Skill("wip")` call mandatory** (multi-select task registration) | Internal multi-select ask inside wip (N next-session work candidates) — with `--auto`, proceed with the documented safe default instead of asking; the `Skill("wip")` call itself still happens (see "Auto Mode vs. Ralph Mode") | **Always** — state preservation for next-session resume at cleanup end |
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

**Same-pass duplication rule (HARD STOP — mandatory rows repeat, the full matrix does not)**: "must always include the mandatory rows" does NOT mean "re-emit the entire step-by-step table again". When the Step 4.5 comprehensive matrix (or an equivalent full wrap-up table) has already been emitted earlier in the **same** cleanup pass, the subsequent session-end report is composed of exactly three parts:

1. **Always-repeat rows (repeat verbatim — these are visibility anchors, never dedup them away)**: the Session identity row (full UUID + the `/rename` recommendations) and the RAG store rows **with their concrete chunk counts** (3-C.1 session-import N, 3-C.2 discovery-chunk N with keys). These repeat by design so the final visible message carries them even if the earlier table scrolled away.
2. **Delta rows**: only the steps that completed *after* the earlier table was emitted (typically Step 5 wip-registration result and Step 5.5 self-task prune).
3. **A one-line reference** to the earlier table for every other row ("full step matrix: see the Step 4.5 report above") — do not re-emit those rows.

Emitting two near-identical full tables minutes apart buries the delta the user actually needs (what changed since the first table) and doubles the scroll cost. The failure this rule targets is symmetric to the omission failures above: the mandatory-row obligations were all written against *omission*, and over-compliance ("repeat everything to be safe") is the opposite defect.

| # | Don't | Do |
|---|-------|-----|
| 1 | Re-emit the full Step 0-5 table as the session-end report because "mandatory rows apply to both" | Mandatory rows ≠ the whole table. Session-end report = always-repeat rows (Session identity + RAG counts) + post-table delta + one-line reference |
| 2 | Dedup so aggressively that the session-end report drops the rename recommendation or the RAG chunk counts | Those rows are the always-repeat set — they must appear again verbatim, counts included |
| 3 | Emit the Step 4.5 matrix, run Step 5 wip, then rebuild the "final report" from scratch as if no table existed yet | Track that the matrix was already emitted this pass (task entry or explicit note) and compose only the delta + always-repeat rows |

| Step | Result |
|------|------|
| **Session identity (mandatory)** | **`Session ID: <full-36-UUID>` + Recommend running: `/rename <model>-<topic>-<sessid8>` (2-3 candidates; each = model family token + dominant-work topic + UUID's leading 8 hex; keep the `/rename ...` command in its own code span with no label or colon inside it, so a single copy-paste is directly runnable)** |
| **Session Profile & Auto-Compact Risk (mandatory row)** | **`[Profile: <steps> steps, <tools> tools | Risk: <LEVEL>]` (automatically evaluated via `context-usage-now.sh` or `python skills/session/scripts/profile-session.py --current --compact-summary`). If Risk is HIGH or CRITICAL, state the top 2-3 most frequent tool call names.** |
| **Walkthrough & artifacts (mandatory row)** | **A markdown link to this session's walkthrough file + a one-line summary of what it covers, followed by a list of every artifact created or modified this session (PR/commit, docs, tracker, recurrence-log entries, RAG writes).** Author `walkthrough-<topic>-<sessid8>.md` at the path resolved by the "Walkthrough file" subsection below (`$WSCFG_ARTIFACTS_PATH`, then the `.agents/` → `.ralph/` → `docs/` fallbacks) **before** composing this row — the row links the file, it does not stand in for it. Write `none — no deliverable this session` only when the session genuinely produced nothing, and say why. |
| 0. TaskList | (cleanup result) |
| 1. Commit | (commit result or skip reason) |
| 2. Self-Improve | `claudify improve` result |
| 3. Knowledge Persist | `claudify persist` result |
| **3-A LLM Wiki scope check (mandatory row whenever `<workspace>/llm-wiki/` exists)** | **"N candidates found — dispatched to raw knowledge ingest" OR "0 candidates — session content was tooling-local, not company-facing" OR "N/A — no `llm-wiki/` in this workspace". State the outcome even when it is zero (3-A Don't/Do row 3), and reach it only after reading `llm-wiki/index.md`'s actual category list rather than the abstract `AGENTS.md` scope alone (3-A Don't/Do row 5).** |
| **3-C.1 RAG Store (mandatory row)** | **State which medium actually fired ([rag-store.md](./rag-store.md) Medium Matrix (1)-(4)) — the wording differs by medium, do not reuse one fixed template for all: purpose-built importer (medium 2) → "N JSONL log step entries / turns recorded (session import, receiver: `<importer>`) — session UUID `<uuid>`. M artifacts imported."; generic MCP store used as 3-C.1 substitute (medium 1, no purpose-built importer found) → "1 ad-hoc summary chunk added (receiver: MCP store) — session UUID `<uuid>`. NOT a full session import (no purpose-built importer found)."; medium (4) local pending queue → "❌ FAILED — queued to local pending-import queue (`<queue-file>`), retry task registered."** |
| **3-C.2 Structured discovery chunk (mode B — mandatory row)** | **M discovery chunks added (receiver structured-store dispatch, mode B) — keys: `<key1>`, … OR "none — no reusable discovery this session". Session import (mode A) alone ≠ knowledge persisted; discoveries need mode B to be searchable.** |
| **3-C.4 fix_plan-history sync (mode C — mandatory row when `fix_plan.md` gained Completed entries this session)** | **P points synced (workspace `<name>` sync script) OR "none — no new Completed entries this session" OR "no sync script for this workspace".** |
| **4. Checklist & Backlog (mandatory row)** | **`Skill("backlog")` or script helper (`update_item.py` / `plane_sync.py`) result — updated items & external sync status** |
| 4.5. Weekly Report | (skip / write result) |
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
| 9 | Treat "every row in this table is filled" as proof the report is complete, while a report item mandated by a separate always-on rule has no row here | **This table is meant to be self-sufficient** — assembling the report from it alone must satisfy every session-end reporting mandate. If you find a mandate elsewhere (an always-on rule, a workspace convention) with no row here, add the row instead of carrying the cross-reference in your head. An always-on rule living only in an uncommitted working-tree file can disappear between sessions; a row in this tracked table is the durable medium |

**Self-sufficiency of this table (HARD STOP)**: the row list above is the complete set of session-end reporting obligations — the three session-level items (walkthrough + artifacts, session rename candidates, RAG chunk counts) each have their own row. Compose the report *from this table*, not from another checklist spot-checked against it. Conversely, when a session-end obligation turns up that this table does not cover, the fix is to add a row here — not to remember it separately.

For accumulated violation cases, see failed-attempts.md HOT (occurrence classification + escalation specification). Escalation from the 3rd occurrence: hook automation — `~/.agents/skills/cleanup/resources/block-cleanup-without-rag.sh` registered. Injects a reminder when the cleanup/session-end response text matches the marker + lacks a RAG-visual-highlight row + has RAG-receiver call traces.

## Prerequisites

- **Fully skip** if there is no conversation content or only simple questions
- If a `config.md` settings file exists, skip the tasks disabled in it

## Context-threshold gate on an auto-trigger entry (HARD STOP)

When cleanup is entered via a **Stop-hook "cleanup trigger"** (the completion-keyword auto-trigger — `trigger-Stop.js` / next-trigger, NOT an explicit user `/cleanup`), measure **live context** against the model's cleanup threshold (Fable/Mythos 55%, Opus 50%, others 45%) before running the full 5-step sequence:

- **live context ≥ threshold** → run the full cleanup (session-end preservation is warranted).
- **live context < threshold** → do NOT run the full ceremony. Address only the specific concern the trigger / co-firing hook raised (e.g. a `check-session-rag` find/store imbalance → one RAG find, or a single session-import only if a real gap exists), then stop. A low-context auto-trigger is a nudge, not a mandate — full session-end preservation (claudify improve + wip + full report) at low context with ample budget is premature.

This generalizes the identical gate already documented for the `check-session-import-gap.js` trigger (`qdrant-import-modes.md` "context-threshold gate") to the general Stop cleanup-trigger. The trigger fires on completion keywords and knows nothing about context — do not read it as an unconditional order to run full cleanup.

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat a Stop "cleanup trigger" as a mandate → run the full 5-step cleanup regardless of context | Measure live context first; < model threshold → light-touch (address the specific hook concern only), ≥ threshold → full run |
| 2 | Read the `block-cleanup-option-below-context-gate.sh` hook's `Live context usage: N%` line as only an ask-gating datum | It is also the **entry signal** for this gate — `N% < threshold` means full cleanup is premature |

**Self-check (on any completion-keyword auto-entry to cleanup)**: (1) explicit user `/cleanup`, or an auto-trigger? (2) if auto-trigger, is live context ≥ the model threshold? (3) if < threshold → light-touch only (address the specific hook concern); do NOT run claudify improve / wip / full report. This gate does not apply when the user typed `/cleanup` explicitly — an explicit request runs the full sequence regardless of context.

## Auto Mode vs. Ralph Mode (HARD STOP — do not conflate)

Two distinct modes suppress `AskUserQuestion`, for different reasons, with different restrictions. Picking the wrong one either annoys an attended user with recording-only theater, or lets an unattended loop take actions only a human should approve.

| | **Auto Mode** (`--auto`) | **Ralph Mode** (true autonomous loop) |
|---|---|---|
| When it applies | `--auto` typed explicitly, **or** `--ralph` typed in an interactive session where `RALPH_LOOP=1` is NOT set (see remap rule below) | `.ralph/` directory exists **AND** `RALPH_LOOP=1` is set |
| Who is present | A human is in the session and can see the result immediately — just doesn't want to be interrupted with asks | No human attending this iteration |
| AskUserQuestion | Suppressed — proceed with the documented safe default for that step instead of asking | Suppressed — record `[NEEDS_REVIEW]` to `.ralph/improvements.md` instead of acting |
| Direct modification (rules, memory, hook, commit) | **Allowed** — this is a real session, the human will see the diff | **Forbidden** — record only |
| Skill/agent creation, Agent-tool delegation | **Allowed** | **Forbidden** — record candidates only |
| Report medium | Normal chat-visible report, same as an interactive run | `.ralph/improvements.md`, since Ralph has no chat to report to |
| Retry safety net | **None** — no next loop iteration will pick up a skipped step. Skipping here is permanent until someone notices | A skipped step this iteration can be retried next iteration |

**`--ralph`-in-interactive-session remap (HARD STOP)**: when `--ralph` is typed but `RALPH_LOOP=1` is not set, the session is attended — a human just asked cleanup not to interrupt them, not to restrict itself to record-only autonomous-loop behavior. Treat this exactly as **Auto Mode**, not Ralph Mode: suppress asks, but still directly commit/edit/call skills as a normal attended run would, and report to chat as normal. Do not apply Ralph's record-only restrictions here — those exist for the *no-human-present* case, which this is not. `--ralph` remains available for its literal, fully-restricted meaning whenever `.ralph/` + `RALPH_LOOP=1` both hold.

**If `.ralph/` exists but it's an interactive user session with neither flag given, use normal mode** — AskUserQuestion is used normally. Do not judge based on `.ralph/` existence alone.

**No retry safety net in Auto Mode (HARD STOP)**: unlike a true `RALPH_LOOP=1` loop, Auto Mode (including the `--ralph`-remapped case) has no next iteration — a step skipped now is skipped for good unless someone notices. Do not silently skip a step just because asking is suppressed; use the step's documented default instead. See the RAG-store carve-out below, which applies regardless of which mode triggered ask-suppression.

**Ask-bypass axis vs. passive-persistence axis (HARD STOP — do not conflate)**: Ralph Mode exists because Ralph cannot call `AskUserQuestion` — it restricts only the steps that would otherwise need a user decision (rule/skill/hook edits, agent spawns, automation creation). It does **not** extend to steps that already run with **no ask in normal mode** — the RAG session-chunk store (3-C.1), the structured discovery-chunk store (3-C.2), and the missed-active-artifact store (3-C.3) are all documented above as "Automatic execution — no ask" even outside Ralph Mode. Skipping them under Ralph Mode is a category error: a step that needs no confirmation cannot be made "more autonomous-unsafe" by removing the confirmation channel. These three sub-steps **still run automatically in Ralph Mode** — only their *reporting* medium changes (append the result to `.ralph/improvements.md` instead of a chat-visible report row, since Ralph has no chat to report to). See each sub-step's own "Ralph mode" note below for the corrected behavior.

**Ralph mode behavior rules (strict `.ralph/` + `RALPH_LOOP=1` case only — Auto Mode does none of this restriction, see the comparison table above)**:

| Normal session | Ralph mode |
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

**Scope (HARD STOP — do not let this guard become a side-quest)**: "unfinished work" here means work whose *decision* was already made by the user (an arrived background-agent result, a pending consolidate/code-workflow step, an already-approved action interrupted mid-execution). It does **not** license chasing that work through an unbounded chain of follow-on actions cleanup itself has no stake in. In particular: **`git push` / PR creation are never part of this guard's scope, and never part of cleanup's own Step 1** (Step 1 is "Commit Session Changes" — commit only; push is a separate, already-governed axis — see `~/.agents/rules/git.md`'s rule against pushing directly to a shared branch, and the general principle that push is always its own decision, gated separately from commit). If completing the unfinished work would require a push, commit locally as far as this guard's scope goes and stop there — push is its own decision, asked (or, in Auto/Ralph Mode, deferred) on its own terms, not folded into this guard's "finish it" resolution.
   - **If executing the already-approved unfinished work hits a NEW blocker cleanup did not create and has no scope to fix** (e.g., a pre-existing, unrelated repo-wide gate failure) — do not treat resolving that blocker as part of this guard either. Report it and move on to cleanup Step 0; in Auto/Ralph Mode, this ask-suppression applies here too, not just inside Steps 1-5 (see "Auto Mode vs. Ralph Mode" above — the mode's ask-suppression is not scoped to "only Step 1 onward").

**Procedure**:
1. Check the state of the prior work — whether background agent results have arrived, whether a consolidate/code-workflow intermediate step is pending, etc.
2. If there is unfinished work, AskUserQuestion (normal mode) — or apply the mode-appropriate default per "Auto Mode vs. Ralph Mode" above (Auto Mode: complete it directly without asking; Ralph Mode: record `[NEEDS_REVIEW]`, do not complete it):
   - "Finish then cleanup (Recommended)" — complete the unfinished work, then proceed to cleanup
   - "Cleanup first" — carry the unfinished work over to the next session
3. If the user selects "finish" (or Auto Mode's default applies), complete that work first — within the scope above — then re-enter cleanup

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Autonomously carry over unfinished work (e.g., an unposted consolidate review comment) to "the next session" | Confirm "finish vs carry over" via AskUserQuestion (or the mode default) |
| 2 | Ignore an arrived background agent result and proceed with cleanup | An arrived result means the work can be resumed. Complete it first |
| 3 | Reason that "cleanup was invoked, so cleanup is top priority" | cleanup is "session tidy-up," not "abandoning unfinished work" |
| 4 | Fold `git push`/PR creation into "finishing" a commit-shaped piece of unfinished work | Commit is in scope; push is not. Stop at commit, handle push as its own separate decision |
| 5 | Call `AskUserQuestion` about a new blocker hit while chasing this guard's unfinished work, while running in Auto/Ralph Mode | This guard is bound by the same mode as the rest of cleanup — suppress the ask per the active mode's default, same as any Step 1-5 ask would be |

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
1. Extract the Plane issue URL/ID from the matched line's `→ Plane (...)` suffix (real-world example: `[INFRA-6] ... → Plane (https://plane.example.com/.../issues/<id>) *(Phase 3 indexing ...)*`).
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

Commit files directly modified in this session that are still uncommitted. **This step is commit only — `git push` and PR creation are out of scope here and everywhere else in cleanup** (per `~/.agents/rules/git.md`: push is always its own decision, gated separately from commit). Do not chain a push onto a Step 1 commit result, in any mode.

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
5. **Before offering a "push this branch" option after a commit, does the current branch name match an accumulation-only pattern** (`local`, `local-only`, `wip`, `scratch`, `staging-local`, etc. — repo-agnostic, not limited to any one project's documented branch)? If yes, do not offer a push option for it — offer "cherry-pick to a feature branch, then push that branch" instead. If unsure, check `git ls-remote origin | grep <branch>` first: zero history there is itself evidence of accumulation-only intent. (Case history: a commit landed on a branch literally named `local-only`, with zero prior push history on origin, and a push option was still offered for it.)

**Ralph mode**: record the list of uncommitted files to `.ralph/improvements.md`. Do not directly execute commits.

---

## Step 2: Self-Improve (mistake analysis + review + pattern detection)

Full procedure: **[run-self-improve.md](./run-self-improve.md)**. Read it before executing Step 2 — the HARD STOPs and the automated-script list live there, not here.

## Step 3: Knowledge Persist (documentation + infra check + memory)

Full procedure: **[run-knowledge-persist.md](./run-knowledge-persist.md)**. Read it before executing Step 3 — the RAG store modes (3-C.1 session import / 3-C.2 structured discovery / 3-C.3 artifact import / 3-C.4 fix_plan-history sync), the walkthrough obligations and the memory dual-sync rules live there.

## Step 4 / 4.5: Checklist & Backlog Sync, Comprehensive Result Report

Full procedure: **[run-checklist-sync.md](./run-checklist-sync.md)**. Read it before executing Step 4 — the backlog sync procedure and the Step 4.5 mandatory report matrix (including the same-pass duplication rule) live there.

## Step 5 / 5.5: wip Handoff and Self-Task Cleanup

Full procedure: **[run-wip-handoff.md](./run-wip-handoff.md)**. Read it before executing Step 5 — the wip delegation contract and the Step 5.5 status-based prune HARD STOP live there.

## Notes

- If a step has no findings, skip that step (do not output an empty result)
- Weekly Report targets only actual code changes/work
- Documentation recommendations exclude already-documented information
- Sensitive information (API keys, passwords, etc.) is excluded from documentation/memory targets
