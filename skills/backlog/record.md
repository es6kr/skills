# Backlog Record

Unified record and synchronization topic for session completed work and next-session candidates.

## Overview

The `record` topic handles recording completed session work into workspace markdown files (`fix_plan.md`, `checklist.md`) and registering next-session work candidates into session-scoped task backlogs (`Skill("wip")`).

## Invocation Modes

Call via `Skill("backlog", "record", mode="completed" | "next-session")`.

- `mode="completed"`: Record completed work into checklist files (`fix_plan.md` / `checklist.md`).
- `mode="next-session"`: Register next-session work candidates into `Skill("wip")`.

---

## Mode: `completed` (Checklist Record)

Record and synchronize the work performed in this conversation with the checklist and external backlog trackers.

### Script Helper Gate & Prohibit Direct Text Edit (HARD STOP)

In Antigravity (Gemini) and interactive sessions, modifying `fix_plan.md` or `checklist.md` directly via raw text editing (`replace_file_content`, `multi_replace_file_content`, `write_to_file`) is **strictly prohibited (`HARD STOP`)**.
- All checklist mutations (completing items via `--set-marker '[x]'`, moving to Completed via `--move`, appending progress notes via `--append-note`) **MUST** be performed by executing dedicated CLI scripts:
  - `python skills/fix-plan/scripts/update_item.py --file <path> --match "<keyword>" --set-marker '[x]'`
  - `python skills/fix-plan/scripts/update_item.py --file <path> --match "<keyword>" --move`
  - `python skills/fix-plan/scripts/add_item.py`
  - `Skill("backlog")` / `skills/backlog/scripts/plane_sync.py` (when Plane or secondary tracker is canonical)
- Bypassing script helpers by performing raw string replacements is a direct rule violation.

### Checklist file decision order

1. **If the user explicitly named a checklist file, use it** (e.g., `checklist.md`, `tasks.md`, `progress.md`, etc. — a file quoted in this session's messages)
2. **If `.ralph/fix_plan.md` exists in the workspace, use it** (default 1st priority — applies equally in Ralph environments and non-Ralph regular sessions. fix_plan.md is already structured with Priority Work · BLOCKED · Completed sections, making it a suitable medium for session-work records)
3. **If only an artifact folder is specified and no checklist file exists**, use `<artifact-path>/checklist.md` as the default file (create if it doesn't exist)
4. **If none of the above applies**:
   - Search the workspace root (`pwd`) in order: `.ralph/docs/generated/checklist.md`, `.omc/plans/checklist.md`, `checklist.md`
   - Use the file found
   - If none are found, confirm the location via AskUserQuestion (options: create a new `checklist.md` at the workspace root / a different path / skip)

### Handling procedure when using a session-log file (`fix_plan.md` / `checklist.md`) (HARD STOP — matching existing items is priority 1)

The core purpose is **tidying (state refresh + pruning completed items)**, not "adding session-work records." Creating a new section is a fallback for matching failure, not the default.

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
| Matches an existing `- [ ]` or `[BLOCKED]` item | **Update that item to `- [x]`** + append 1 line of completion info (commit/file/verification). Do not add a new row. **If the line carries a `→ Plane (<url>)` index suffix, apply the Plane-indexed item completion order gate first** — do not flip to `[x]` until Plane itself reflects completion |
| Matches an existing `- [x]` item (already complete) | **Skip the update** (already complete) |
| No matching item + work is complete | Append `- [x] {summary} (session <UUID>)` at the end of the `## Completed` section |
| No matching item + remaining work | Append `- [ ]` to `## Priority Work` or the appropriate category |
| No matching item + waiting externally | Append `- [ ] [BLOCKED] {summary}` to the `## Hold` section |

2.5. **Step B-gate — canonical medium check before any append (HARD STOP — creation direction)**: the last two rows of the table above **create** entries. Before appending either, determine whether this checklist file is the canonical backlog or an index into an external tracker.
   Detect the canonical medium from **both** signals:
   - **Pinned header declaration**: read the file's top block (first 10 lines).
   - **Existing index-line density**: count entries carrying an external reference suffix (e.g. `→ <Tracker> (<issue URL>)`).

   | Canonical medium | Handling for the two creating rows |
   |------------------|------------------------------------|
   | **Canonical** (this file holds the real backlog) | Append to this file via script helper (`add_item.py` / `python skills/fix-plan/scripts/update_item.py`) |
   | **Index into an external tracker** | **First create the issue/item in the external tracker** (via `Skill("backlog", "create")` or Plane API), then append an index line (`- [ ] {summary} → <Tracker> (<issue URL>)`) to this file |

3. **Step C — forbidden actions (HARD STOP)**:
   - Creating a new date header section (`## 2026-09-24`, `### Session Work 2026-09-24`, etc.)
   - Appending duplicate `- [x]` entries for an item already registered as `- [ ]` elsewhere in the same file
   - Editing lines outside the target item's matched line range
   - Modifying `fix_plan.md` directly via raw text edits without script helpers

---

## Mode: `next-session` (Register Next-Session Work as wip)

Delegate via a `Skill("wip")` call to register N task candidates for next-session resume via multi-select.

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
  "cleanup Step 4-C end point — register N task candidates for next-session resume via multi-select.

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
- Only enumerating next-work candidates as chat text (not registered as wip tasks) — impossible to resume in the next session

### No Re-recommending Existing TaskList Items + Routing Ralph-autonomous Items to /fix-plan (HARD STOP)

**A task already registered in TaskList is itself a rewind-preservation medium — do not re-recommend/re-register it via wip.** In cleanup Step 0, completed tasks are auto-cleaned (deleted) and incomplete tasks remain as-is, visible as-is in the next session. wip's re-registration target is **only candidates newly discovered this session that aren't yet in TaskList**. Re-listing existing items as wip options causes duplicate registration + noise.

Among remaining incomplete tasks, ones that the **Ralph autonomous loop can execute autonomously** (not gated on a user decision/external state) are routed to `Skill("fix-plan")` for fix_plan.md so Ralph can pick them up. User-gated ones (waiting for merge approval / external PR state / user branch, etc.) stay in TaskList.

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Re-list/re-recommend an existing TaskList item (#N pending) as a wip AskUserQuestion option | Existing items are already preserved — exclude from re-recommendation. wip targets are **only new candidates not in TaskList** |
| 2 | Re-register a completed task as "to do next too" | Completed tasks are deleted in Step 0. Only incomplete ones remain |
| 3 | Leave a Ralph-autonomously-executable remaining task only in TaskList and abandon it | Route via `Skill("fix-plan")` to fix_plan.md → Ralph autonomous pickup |
| 4 | Route a user-gated task (waiting for merge/approval/external state) to fix_plan | User-gated tasks stay in TaskList — Ralph cannot proceed autonomously |
