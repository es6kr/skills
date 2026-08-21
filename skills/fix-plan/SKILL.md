---
name: fix-plan
description: |
  fix_plan.md / checklist.md schema and lifecycle management. Topics — format ([ ]/[x]/[BLOCKED] markers, Progress/Completed sections), priority (P0-P3 BLOCKED suffix + external/selfable classification), add (Action/Why/How authoring), draft (deferred plan stub → promote via code-workflow), move ([x] → Completed summary, subtree partial completion), sync (gh pr/issue state polling → auto-check), issue-drafts (write → publish → archive → delete), model-triage (fit + dedicated section), completion-criteria (DoD + marker rules).
  Default (no args): move (or archive-receiver) → format → sync → priority → flowchart-sync, scoped by role-profile (--role=pm|deep|impl).
  Use when: "fix_plan", "checklist", "BLOCKED priority", "triage blocked", "fix-plan sync", "issue draft cleanup", "fix-plan draft", "fix-plan default", "fix-plan archive", "model triage", "completion criteria", "role profile", "--role".
metadata:
  author: es6kr
  version: "0.1.0"
depends-on:
  - code-workflow
  - github-flow
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Bash(gh:*)
  - Bash(mv:*)
  - Bash(mkdir:*)
---

# Fix Plan

Schema and lifecycle management for `fix_plan.md` (Ralph convention) and `checklist.md` (non-Ralph workspaces). Vendor-agnostic — extracted from Ralph integration to be reusable across environments.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| add | New item authoring schema (Action / Why / How), length budget, deliverable separation (research / plan / checklist split) | [add.md](./add.md) |
| claim | Multi-session in-progress lease: `[CLAIMED:<sid>:<ts>]` suffix tag on `[ ]` / `[BLOCKED:*:selfable]` items, claim→refresh→release lifecycle, stale-TTL takeover — prevents two sessions duplicating the same item | [claim.md](./claim.md) |
| completion-criteria | Definition of done per item output type (`Why` = scope narrative vs `How to apply` = deliverable), marker transition rules, residual-scope split | [completion-criteria.md](./completion-criteria.md) |
| draft | Record a deferred plan **stub** (purpose + defer reason + resume trigger + expected deliverable) in `## Plan Drafts` when full planning is postponed; promote to `code-workflow` research→plan when the trigger fires. Invoked `/fix-plan draft` | [draft.md](./draft.md) |
| flowchart | Priority flowchart (Mermaid `graph TD` dependency graph) authoring, clean syntax rules (no inline `%%`), plan document node mapping (`llm-wiki/outputs/`, `.ralph/plan-drafts/`) without `file://` URLs, and the `pm`-role default-pipeline sync procedure (drift check against priority-triage output) | [flowchart.md](./flowchart.md) |
| format | Schema: `[ ]` / `[x]` / `[BLOCKED]` markers, Progress/Completed sections, item state changes, section-consistency check | [format.md](./format.md) |
| issue-drafts | Issue Drafts lifecycle: write → publish → archive (`.bak/`) → delete from fix_plan | [issue-drafts.md](./issue-drafts.md) |
| model-triage | High-capability model triage: 5 fit categories + anti-fit table + cross-section discovery procedure + dedicated `## <Model> Target Tasks` section operation | [model-triage.md](./model-triage.md) |
| move | `[x]` → Completed summary rules, subtree-move partial completion under unfinished parent, optional abstract RAG dispatch, and `detect_bloated_tasks.py` automated audit | [move.md](./move.md) |
| priority | `[BLOCKED:P0-P3:reason]` GitHub-aligned priority suffix + `external` / `selfable` reason classification + triage workflow | [priority.md](./priority.md) |
| sync | GitHub PR/Issue & Plane REST API state polling (`gh` CLI + `plane_sync.py`) → auto-check `[ ]` → `[x]` on MERGED PR or CLOSED issue; PR CLOSED-without-merge → `[BLOCKED:P2:external]` | [sync.md](./sync.md) |
| sync-automation | Stop-hook checkpoint nudge — reminds to run `sync` when a tracker referencing PR/Issue numbers hasn't been synced in a while, without any network call inside the hook itself | [sync-automation.md](./sync-automation.md) |
| verify | Cross-check commit-hash/file-path references cited in tracker items against local git/filesystem state before trusting a "still unresolved" claim (distinct from `sync`'s external GitHub polling) | [verify.md](./verify.md) |

## Topic Dependencies

```text
fix-plan (schema + lifecycle)
  ├─→ (default, no args) → move (archive-receiver) ──→ format ──→ sync ──→ priority ──→ flowchart-sync
  ├─→ format (entry — section structure + markers)
  ├─→ priority (new convention — BLOCKED P0-P3 + reason)
  │     └─→ depends on sync (Step 0: refresh external state before classifying)
  ├─→ add (authoring act-now items)
  ├─→ claim (multi-session lease) — annotates format's markers; move drops the tag on completion; priority triage excludes fresh-claimed items
  ├─→ model-triage (cross-section discovery → dedicated section; items authored via add's schema)
  ├─→ draft (deferred plan stub → `## Plan Drafts`)
  │     └─→ code-workflow/steps dispatch on promote (research → plan)
  ├─→ move (completion → Completed)
  │     └─→ optional --rag=<skill>:<topic> dispatch for semantic indexing (caller-supplied)
  ├─→ sync (GitHub state polling) — depends on github-flow gh CLI conventions
  │     └─→ sync-automation (Stop-hook nudges this topic when overdue — no direct call dependency)
  ├─→ verify (local git/filesystem staleness check — complements sync's external-state polling)
  ├─→ flowchart (Mermaid priority graph) — step 5 of the default pipeline, drift-checks against priority's output
  └─→ issue-drafts (lifecycle of draft files)
```

- All topics are independently invocable, **except `priority` which invokes `sync` as Step 0 (HARD STOP)** — triage on stale state is the failure mode the dependency prevents (see [priority.md](./priority.md) Triage workflow Step 0)
- `verify` is a recommended pre-check before triaging any `[BLOCKED]`/`[ ]` item that cites a specific commit hash or file path — see [verify.md](./verify.md)
- **Default invocation (no args)**: first runs `move` (or archive-receiver dispatch), then verifies schema via `format`, syncs external state via `sync`, triages blockers via `priority`, and syncs the `## Flow Chart` section's node labels against that triage output via `flowchart` (pm role only — see "Role-based execution").
- `move` topic optionally dispatches to a RAG receiver if the caller supplies `--rag=<skill>:<topic>` — generic skill stays vendor-agnostic; receiver implementation lives in the caller (e.g., ralph wrapper)
- `sync` topic optionally dispatches to a secondary-tracker receiver if the caller supplies `--secondary-sync=<skill>:<topic>` — see [sync.md](./sync.md) "Secondary-tracker sync cadence"
- `draft` topic dispatches to `code-workflow` (`steps`) on promote — turns a deferred stub into a real research → plan

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `claim-ttl` | `4` (hours) | Stale-claim TTL for the `claim` topic — a `[CLAIMED:<sid>:<ts>]` lease older than this (or whose session has ended) is takeable by another session. Set via `--claim-ttl=<hours>`. See [claim.md](./claim.md) |
| `archive-receiver` | (unset) | Optional `<skill>:<topic>` dispatch for **default invocation** (no args). When set, the caller routes the source's `## Completed` section to this receiver for external archiving (weekly report, postmortem log, RAG store, etc.). Receiver harvests + appends to its own report + removes harvested lines from source. Set via `--archive=<skill>:<topic>` CLI flag. See "Default invocation" below |
| `completed-archive-period` | `monthly` | Period for the **receiver-independent local archive** of the `## Completed` section — `monthly` (`YYYY-MM`) or `weekly` (ISO `YYYY-Www`). On the period boundary, older Completed entries move to `<tracker-dir>/.bak/<tracker-stem>-completed-<period>.md` and are removed from the tracker, keeping the live file small. Set via `--completed-archive-period=weekly\|monthly`. See [move.md](./move.md) "Completed-section size management" |
| `rag-receiver` | (unset) | Optional `<skill>:<topic>` dispatch for `move` topic semantic indexing — set via the `--rag=<skill>:<topic>` CLI flag on the `move` topic (see [move.md](./move.md)). No env var or config file is consumed by this skill; the caller routes |
| `role-profile` | (unset) | Execution-role scoping for the default invocation — CLI `--role=<pm\|deep\|impl>`. Values are **abstract profile names** (`pm` = mechanical bookkeeping/recording, `deep` = large-scale classification & audit, `impl` = implementation); this skill never hardcodes model names. Resolution chain: explicit flag → context self-detection → unset = full pipeline (backward compatible). See "Role-based execution" below |
| `secondary-sync-receiver` | (unset) | Optional `<skill>:<topic>` dispatch for the `sync` topic — runs a project's non-GitHub backlog tracker (Plane, Jira, etc.) in the same cadence as this skill's GitHub PR/Issue sync, instead of letting it drift independently. Set via the `--secondary-sync=<skill>:<topic>` CLI flag. No tracker name is hardcoded — the receiver owns all tracker-specific details. See [sync.md](./sync.md) "Secondary-tracker sync cadence" |
| `task-tracker` | `fix_plan.md` | Tracker filename. Use `checklist.md` for non-Ralph workspaces |

## Default invocation (no args)

When `/fix-plan` is invoked with **no args**, it must execute the following sequential pipeline (scoped by the resolved role profile — see "Role-based execution" below):

**Step 0 — Recency check (HARD STOP, runs before task registration)**: before registering pipeline tasks, scan the tracker's pinned/header block (if the tracker has one) for a "last full pipeline run" marker left by a prior invocation of this same default-invocation pipeline. If found and it indicates a very recent completion (same calling context, no new external trigger since), report what that run covered and call `AskUserQuestion` offering: skip entirely (report only) / run selective steps (e.g. Sync only, since external state may have moved) / run the full pipeline anyway. Do not silently start Step 1 when recent-completion evidence is already present in the file being read — the tracker is both the pipeline's operand and, when this marker exists, its own run log. If no marker exists (or the tracker has no pinned block), proceed directly into Step 1 as before — this step is a no-op on trackers that don't use the convention.

**Recency-ask answer reuse (HARD STOP — never re-ask a scope question the user already answered)**: the Step 0 recency ask is a per-day, per-context decision — not a per-invocation ritual. Before calling `AskUserQuestion`, read the tracker's pipeline log for recency-ask answers the user already gave today in the same calling context: (a) if the user already answered a recency ask today, reuse that answer's pattern (e.g. "core only" → skip the steps that would duplicate a same-day 0-change run) instead of re-asking; (b) an explicit role-flagged re-invocation (e.g. `--deep`) made after a same-role run already completed today **is itself the scope answer** — do not ask; skip the pipeline steps that would duplicate that run (report what was skipped and why) and proceed straight to that role's remaining actionable work (for `deep`, the dedicated model-triage section's executable items; for `pm`/`impl`, due REPEAT items and surfaced `selfable` candidates); (c) re-ask only when external state has plausibly moved in a way the user has not seen (new merges/closes since the last run), or an explicit scope argument conflicts with the logged answer. The user answering the same scope question twice in one day is a defect, not diligence.

1. **Move / Archive**: Dispatch to the configured **archive receiver** (or fall back to the `move` topic) to harvest/cleanup Completed entries.
2. **Format**: Verify the schema, markers, and section structure of the tracker.
3. **Sync**: Poll external GitHub states (`gh pr view` / `gh issue view`) for referenced issues/PRs to auto-resolve completed ones.
4. **Priority**: Triage and sort the remaining `[BLOCKED]` list based on the synchronized states.
5. **Flowchart sync**: Compare the `## Flow Chart` section's node labels and dependency edges against the priority tags just produced in step 4 — update any node whose `[P*]` label, or whose backing item's resolved/removed state, has drifted from the live tracker. See [flowchart.md](./flowchart.md) "Sync procedure".

**Recency marker maintenance**: upon completing the full pipeline (through step 5, or through the REPEAT cadence check for the `pm` role profile), stamp/update the "last full pipeline run" marker in the tracker's pinned block with the completion timestamp and the role profile used, so Step 0 of a future invocation can find it. If the tracker has no pinned block, skip this — do not create new tracker structure solely for this marker.

**Register BEFORE execute (HARD STOP)**: before Step 1 (Move) begins — after Step 0's recency check has resolved which steps are actually in scope — `TaskCreate` (or `TodoWrite` if `TaskCreate` is unavailable) must register one task per pipeline step actually being run (Move/Format/Sync/Priority/Flowchart-sync for the full pipeline, fewer for a role-scoped subset or a Step-0-narrowed run — see "Role-based execution" below). A default-invocation `/fix-plan` run is multi-step by definition; "the tracker looks small" is not an exception. If a `TaskCreate` call errors, retry it with the corrected parameters from its own error message before any Move/Sync/Priority/Flowchart Edit proceeds — treating a retry as unnecessary overhead and silently dropping tracking is the exact violation this line prevents. Mirrors `~/.claude/skills/wip/SKILL.md` "Register BEFORE execute".

**Subagent-delegated pipeline runs require artifact verification, not just TaskUpdate trust (HARD STOP)**: when a caller delegates this default pipeline to a subagent (`Agent` spawn) rather than executing it directly, a subagent marking its assigned tasks `TaskUpdate(status: "completed")` is NOT sufficient evidence the corresponding tracker edits actually happened. **No whole-pipeline hand-off**: never hand the whole registered task set to one subagent call as a single "run pm" prompt — dispatch (or check in on) each step individually, and after each reported-done step, independently re-read the tracker yourself (a `git diff`/section-length/marker check against the actual file) before treating the next step as safe to start. Before treating any delegated run as done, the delegating caller must independently confirm at least one concrete artifact change per claimed step — e.g. a new `## Pipeline Execution Log` entry, a diff in the `## Flow Chart` node count, a changed `[BLOCKED:P*]` count, or a new `## Completed` entry. Two consecutive idle/no-evidence status replies from a delegated agent means stop waiting and take the remaining steps over directly, not send a third status request — verify the tracker file directly (line counts, section diffs) and take over the remaining steps yourself if the artifacts show no real change. A subagent's self-reported completion is a claim, not proof. This mirrors a real incident: a subagent given the whole pipeline marked all 6 default-pipeline steps `completed` while leaving the tracker file byte-for-byte unchanged.

### Role-based execution (`role-profile`)

**Plan & Research Reading Prerequisite Gate (HARD STOP)**: When executing tasks from `fix_plan.md` or cited plan snippets, the agent MUST first read the full related research document or plan file (`plan-*.md`, `docs/`) via `view_file` before starting any implementation steps (CLI commands, repo renames, code edits).

The default pipeline is scoped by the execution role, so a high-capability session is not spent on mechanical bookkeeping — and a bookkeeping session does not attempt deep-analysis passes it is unsuited for.

**Role resolution chain** (first match wins):

1. Explicit `--role=<pm|deep|impl>` CLI flag
2. **Context self-detection** — when the invoking agent can identify the model it is running on (from its own runtime context, e.g. a model identifier exposed by the harness) AND the workspace declares a model→profile mapping (a local operating note in the tracker, a project rule — caller-side, never in this skill), resolve the profile from that mapping
3. Neither available → run the **full pipeline** (backward compatible — unchanged behavior for existing users and environments without role mappings)

**Pointer-tracker resolution (HARD STOP)**: Before concluding "no candidates" for a workspace's local `fix_plan.md`/`checklist.md`, check whether its active-work section has been replaced with a redirect note pointing to a parent/org-level tracker (e.g. an HTML comment or line like "this repo's items live in `<parent-path>` — see there" / "moved to `<parent-path>`"). If found, resolve the referenced path and treat **that parent tracker's own top-level `##` sections** (not just the specific subsection the note points at) as in-scope for this invocation's Move/Sync/Priority/impl-candidate steps. A redirect narrowing to one subsection (e.g. `## Fable Target Tasks`) is not evidence the rest of the parent tracker (`## Priority Work`, `## REPEAT`, `## TODO`, etc.) is out of scope — those sections are exactly where `pm`/`impl` candidates live.

**Full-header self-check (HARD STOP)**: If you ran `grep "^#"` (or equivalent) to get the tracker's section list, you must Read **every** top-level `##` section from that list before reporting candidate counts — not just the section you most recently wrote to. Recency (having just edited a section) is not grounds to skip sibling sections; it is exactly the bias that causes a populated `## Priority Work` / `## REPEAT` section to be missed while a freshly-touched `## Fable Target Tasks` gets re-read.

**Per-profile default pipeline**:

| Profile | Steps executed | Skipped (reported as remainder) |
|---------|----------------|--------------------------------|
| `pm` | move → format → sync → priority → flowchart-sync → **REPEAT cadence check** (run all due REPEAT items) | — |
| `deep` | sync (cheap state refresh) → priority (judgment-quality gain) → [model-triage](./model-triage.md) re-discovery + plan-audit candidate scan | move, format, flowchart-sync — surfaced as a delegation remainder for a `pm` session |
| `impl` | sync → priority → **REPEAT overdue check** (run REPEAT items overdue by 24h+), then surface `selfable` implementation candidates | move, format, model-triage, flowchart-sync |
| (unresolved) | full pipeline | — |

- **REPEAT Section Execution Cadence Rule**:
  - **`/fix-plan --pm`**: Check `## REPEAT` section. If any item's due period (its "period" field) has elapsed since its "last run" field, execute it immediately.
  - **`/fix-plan --impl`**: Check `## REPEAT` section. Execute ONLY items whose due period has elapsed AND has been neglected for an additional 24+ hours (period + 24h overdue). Skip others.

- A skipped step is never silently dropped: the run report must list the skipped steps and their pending workload (e.g. "N completed `[x]` items awaiting move") so a later `pm` session picks them up.
- Model names never appear in this skill. The caller-side mapping translates concrete models to `pm` / `deep` / `impl` — the same supply pattern as the `--archive` / `--rag` receiver contracts.

**pm-profile completion handoff**: when a `pm` role-profile default-invocation pipeline finishes (through the REPEAT cadence check), do not close the turn with an open-ended "what's next" prompt. Reuse the `sync`/`priority` state this same run already computed and surface exactly one simple `selfable` candidate from what the `impl` row's own candidate-surfacing step would otherwise report — then confirm it via `AskUserQuestion` (proceed with it / pick something else / skip for now) instead of a generic next-step prompt. This draws from a single already-known role profile's own candidate set computed in this same run, not a speculative multi-source scan — it is a narrower, cheaper handoff than general next-action option construction. If no `selfable` candidate exists this run, skip this step and close normally.

**Mandatory Output Reporting Contract (HARD STOP)**: The agent must physically emit the Step 4 Priority Triage candidate list (P0–P3 sorted by `:selfable` vs `:external`) in the visible response text BEFORE marking the task as completed (`[x]`) or invoking `AskUserQuestion`. Suppressing Step 4's summary table output or marking tasks completed prior to physical output emission is strictly forbidden.

### Receiver contract

The fix-plan skill stays vendor-agnostic — no hardcoded receiver name. The caller (Claude in the user's environment) routes to whichever receiver is registered.

| Field | Value |
|-------|-------|
| Dispatch flag | `--archive=<skill>:<topic>` (CLI) |
| Receiver responsibility | (1) Read source's `## Completed` section, (2) Append items to its own report format, (3) Edit source to remove harvested lines |
| Idempotency | Receiver must be safe to re-invoke — already-harvested items must not double-append |
| Failure handling | If receiver unavailable / errors → log + fall back to `move` topic without touching source |

### Caller auto-dispatch heuristic

The caller decides at invocation time:

1. Check `--archive=<skill>:<topic>` CLI arg → if present, use it
2. Otherwise scan registered skills for a Completed-archive contract (matching topic name or declared `fix-plan-archive` keyword in description)
3. Exactly one match → dispatch automatically
4. Multiple matches → ask the user
5. Zero matches → fall back to `move` topic

### Example receivers (illustrative — not bundled)

The following are environments in which an archive receiver might be registered:

| Environment | Receiver pattern | What it does |
|-------------|-----------------|--------------|
| Weekly-report workflow | a topic that ingests fix_plan Completed into weekly reports | Append by ISO-week + remove from source |
| Postmortem log | a topic that appends to a rolling postmortem document | Append + remove |
| RAG store | a topic that upserts Completed entries into a vector DB | Upsert + remove |

These are **examples**, not dependencies. The fix-plan skill does not import any of them; the caller supplies the receiver.

## Quick Reference

### Default invocation

```bash
/fix-plan                            # dispatch to configured archive-receiver (or fall back to move)
/fix-plan --archive=<skill>:<topic>  # explicit receiver
```

See "Default invocation (no args)" section above.

### Schema (format)

```markdown
# Fix Plan

## Progress

- [ ] {Action}
  - **Why**: {motivation}
  - **How to apply**: {procedure}
- [BLOCKED:P0:external] {Action} (awaiting X)
- [x] {Completed item — pending move}

## Completed

- 2026-06-07 12:00 — {one-line summary} (commit {sha}, PR #{N})
```

See [format.md](./format.md) for full schema.

### BLOCKED priority + reason (priority — NEW convention)

```markdown
- [BLOCKED:P0:external] PR #45 user merge decision
- [BLOCKED:P1:selfable] consolidate Step 2.4 PR create (branch + body ready)
- [BLOCKED:P2:external] CodeRabbit re-review awaiting
```

- **P0**–**P3**: GitHub priority label-aligned (P0 highest)
- **external**: true external dependency
- **selfable**: progressable now (P-rank for immediate action)
- **Triage Step 0 — sync external state first (HARD STOP)**: `/fix-plan priority` invokes `sync` topic before classifying — `gh pr view <N>` + `gh issue view <N>` on every referenced PR/Issue. Auto-resolves merged/closed entries to `[x]` so stale items don't get sorted as live BLOCKERs

See [priority.md](./priority.md) for full convention. When a workspace mirrors backlog into Plane, `P0`-`P3` maps 1:1 onto Plane's native `urgent`/`high`/`medium`/`low` priority (`scripts/plane_sync.py`'s `normalize_priority()`; see [sync.md](./sync.md) "Secondary-tracker sync cadence" and `plane-backlog/SKILL.md` "Plane Issue DELETE Prohibition & Priority Mapping (HARD STOP)").

### Add new item

```markdown
- [ ] {one-sentence Action}
  - **Why**: {motivation 1-2 sentences}
  - **How to apply**: {procedure / tools / commands}
```

See [add.md](./add.md) for length budget + deliverable separation.

### Claim an item in progress (multi-session)

Re-read the tracker, then stamp a lease tag before starting work so a concurrent session does not duplicate it:

```markdown
- [ ] [CLAIMED:<sid>:<YYYY-MM-DDTHH:mm>] {Action}
- [BLOCKED:P1:selfable] [CLAIMED:<sid>:<ts>] {Action}
```

`[CLAIMED]` is a lease annotation (not a checkbox state). Completion (`[x]` → Completed) drops it; a claim older than the TTL (default 4h) or from an ended session is takeable. See [claim.md](./claim.md).

### Record a deferred plan draft

```markdown
## Plan Drafts

- [BLOCKED:P2:selfable] {Purpose — one line}
  - **Defer reason**: {why postponed}
  - **Resume trigger**: {what promotes it}
  - **Expected deliverable**: research | plan | checklist
```

Invoked `/fix-plan draft`. Stub only (no full plan) → promote to `code-workflow` research→plan when the trigger fires.

Plan Drafts are **always** `[BLOCKED:P*:selfable]`, never `[ ]` — `[ ]` would let autonomous loops (e.g. Ralph wrapper) act on the entry, but promote requires a user decision. The reason is always `:selfable` (body file ready, waiting on a user signal, not on a third party). Priority `P0`-`P3` ranks promote urgency relative to other drafts. See [draft.md](./draft.md) and [priority.md](./priority.md).

### Move to Completed

After `[x]` checked, summarize to one line + move to Completed section. See [move.md](./move.md).

### Archive Completed periodically (keep the tracker small)

On a period boundary, move older `## Completed` entries to a local partition file so the tracker never bloats:

```text
<tracker-dir>/.bak/<tracker-stem>-completed-YYYY-MM.md     # monthly (default)
<tracker-dir>/.bak/<tracker-stem>-completed-YYYY-Www.md    # weekly (--completed-archive-period=weekly)
```

Receiver-independent (no external receiver needed). Entries before the current period move out; the current period stays. See [move.md](./move.md) "Completed-section size management".

### Sync GitHub state

```bash
gh pr view <N> --json state,mergedAt   # PR
gh issue view <N> --json state,closedAt # Issue
```

MERGED PR or CLOSED issue → auto `[x]`. PR CLOSED-without-merge → `[BLOCKED:P2:external]`. See [sync.md](./sync.md).

### Issue Drafts lifecycle

`issue-drafts/<slug>.md` → `gh issue create` → archive to `.bak/` → delete from fix_plan. See [issue-drafts.md](./issue-drafts.md).

### Plane Intake Ingestion Gate for PR & Completed Items (HARD STOP)

Work items backed by GitHub PRs or completed during sessions without a Plane identifier (`[ES6KR-<N>]`, `[INFRA-<N>]`, etc.) MUST be ingested into Plane via Intake (`plane_create_issue.py`) to preserve historical audit logs and decisions. See `plane-backlog` skill.

## See Also

- `github-flow` (depends-on) — `gh` CLI conventions for sync + register
- `plane-backlog` (depends-on) — Plane issue/intake lifecycle and sync engine
- Ralph integration is a separate workstream maintained outside this published skill. A Ralph wrapper, when present, owns Ralph-specific concerns: the `## REPEAT` persistent-item section, autonomous-loop `[BLOCKED]` skip semantics, and the caller-side `--rag=<skill>:<topic>` dispatch (this skill exposes only the abstract flag contract). See the Ralph project's documentation for wrapper details
