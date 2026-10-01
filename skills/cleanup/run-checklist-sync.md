# Step 4 / 4.5: Checklist & Backlog Sync, Comprehensive Result Report

Steps 4 and 4.5 of the `run` pipeline. Entry point: [run.md](./run.md).

## Step 4: Checklist & Backlog Sync

Record and synchronize the work performed in this conversation with the checklist and external backlog trackers (`Skill("backlog")`).

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

2.5. **Step B-gate — canonical medium check before any append (HARD STOP — creation direction)**: the last two rows of the table above **create** entries. Before appending either, determine whether this checklist file is the canonical backlog or an index into an external tracker. This is the mirror of the "Plane-indexed item completion order" gate earlier in this file — that one guards the **completion** direction (do not flip `[x]` locally before the external record reflects it); this one guards the **creation** direction (do not append locally without creating the external record first). Guarding only one direction leaves every newly created item unprotected.

   Detect the canonical medium from **both** signals — either alone is insufficient:

   - **Pinned header declaration**: read the file's top block (roughly the first 10 lines). A tracker delegating to an external system declares it there. Note that cleanup normally reaches this file by keyword grep (Step A) — grep never surfaces the header, so this read is a separate, deliberate step.
   - **Existing index-line density**: count entries carrying an external reference suffix (e.g. `→ <Tracker> (<issue URL>)`). A file where such entries dominate is an index in practice, whatever the header says.

   | Canonical medium | Handling for the two creating rows |
   |------------------|------------------------------------|
   | This file | Append normally, per the table above |
   | External tracker | **Create the item in the external tracker first**, then append the local line as an index carrying the returned URL. If the external tracker is unreachable this run, say so explicitly in the Step 5 report and register a retry — do not silently append local-only |

   | # | Don't | Do |
   |---|-------|-----|
   | 1 | Append `- [ ]` / `- [ ] [BLOCKED]` per the table and treat the item as recorded | Run this gate first. Under an external canonical medium a local-only append is a pointer to nothing, and it is lost the moment the file is regenerated or overwritten by a concurrent writer |
   | 2 | Rely on Step A's grep having "read the file" | Step A greps by keyword; it never returns the header where delegation is declared. The header read is its own step |
   | 3 | Assume the completion-direction Plane gate covers this | That gate fires only when flipping an existing marker to `[x]`. A brand-new item never passes through it |
   | 4 | Append locally now and plan to sync later in the same run | An unsynced local-only entry is exactly the state this gate prevents. Either create externally first, or report the failure and register a retry |

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
| 8 | Put the `/rename` command in a fenced code block (triple-backtick fence) — a fence with no language specifier renders as plain monospace with no color highlight, so the command reads as unhighlighted plain text and does not stand out | Use an **inline code span** — `` `/rename <name>` `` — which renders with a highlighted background, making the single runnable command visually distinct at a glance. "code span" throughout this row means the inline single-backtick form, never a fenced block |

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

**Procedure**: in addition to emitting the comprehensive matrix as response text (unchanged), write (or, on a 2nd+ cleanup pass this session, incrementally update) the same content to a file named `walkthrough-<topic>-<sessid8>.md`, using the workspace artifacts storage path (`$WSCFG_ARTIFACTS_PATH` or fallback: `{ws}/.agents/docs/generated/` → `{ws}/.ralph/docs/generated/` → `{ws}/docs/generated/`). `<topic>` and `<sessid8>` follow the same convention as the `/rename` recommendation (dominant-work topic, kebab-case; session UUID's leading 8 hex).

**Content**: the walkthrough file body is a narrative account of the session's work — not merely a copy of the comprehensive matrix table. Include what was attempted, what was found, what decisions were made and why, and what the matrix's rows summarize in table form. The matrix table itself may be embedded at the end of the file as a quick-reference appendix.

**Incremental update, not overwrite-then-forget**: if `/cleanup` fires more than once in the same session, append/update the existing walkthrough file (matching the file already written earlier in the session) rather than creating a second one — mirrors Antigravity's incremental-update requirement.

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat the chat-text comprehensive report as sufficient state preservation | Also write it to a `walkthrough-<topic>-<sessid8>.md` file — chat text is ephemeral, the file persists |
| 2 | Copy the matrix table verbatim as the entire file body | Write a narrative account (what/why/decisions), with the matrix as an appendix |
| 3 | Create a new walkthrough file on every `/cleanup` firing within the same session | Update the existing session walkthrough file incrementally |
| 4 | Guess a storage path | Follow the workspace-configured `WSCFG_ARTIFACTS_PATH` or `.agents/docs/generated/` fallback |

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
| 7 | Emit the Step 4.5 matrix and then re-emit a near-identical full table again as the session-end report after Step 5 | One full matrix per cleanup pass. The later session-end report follows the "Same-pass duplication rule" (see the Mandatory Rows section): always-repeat rows (Session identity + RAG chunk counts) + post-matrix delta + a one-line reference |

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
