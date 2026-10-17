# Step 4: Backlog & Comprehensive Result Report

Steps 4-A and 4-B of the `run` pipeline. Entry point: [run.md](./run.md).

## Step 4-A: Checklist Record (Completed Work)

Delegate to `Skill("backlog", "record", mode="completed")`.

Full procedure and rules: **[record.md](../backlog/record.md)**.
- Checklist file decision order (`fix_plan.md` / `checklist.md`)
- Script Helper Gate & Prohibit Direct Text Edit (HARD STOP)
- Handling procedure when using a session-log file (Step A keyword grep, Step B branch, Step B-gate canonical check, Step C forbidden date headers)
- Recording targets and Don't/Do table

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

## Step 4-B: Comprehensive Result Report (HARD STOP — mandatory right before entering Step 4-C)

**Immediately before** entering Step 4-C (backlog next-session wip registration), report the entire session's artifacts as a **single comprehensive matrix**. The Step 4-A inline report is just a per-step progress report, not a comprehensive report. It's a separate medium.

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
| Session ID | `Session ID: <full-36-UUID>` (consistent with the "Session Identity Rule" above) |
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
| 1 | Enter the Step 4-C wip call using only the Step 4-A inline report | Output the Step 4-B comprehensive matrix report, then proceed to Step 4-C |
| 2 | Interpret the "no direct recommendation text output" rule as "the comprehensive report is also forbidden" | Comprehensive report ≠ next-action recommendation. Only the Step 4-C recommendation ask is forbidden; the Step 4-B comprehensive report is mandatory |
| 3 | Reason that "accumulated per-step inline reports are sufficient" | Per-step reports = progress reports. Comprehensive matrix = whole-session summary. Separate media. The user must be able to review everything at once |
| 4 | Omit some items like Session ID, commits, files | All 8 rows above are mandatory. State "N/A" explicitly for any that don't apply |
| 5 | Compress the comprehensive report text into the next option description | The comprehensive report is a separate response text. next options are a separate medium for deciding the next action |
| 6 | Emit the comprehensive matrix as response text only, with no `walkthrough-<topic>-<sessid8>.md` file written | The walkthrough file is a mandatory row, not an optional enhancement — chat text alone does not persist across compact/session boundaries |
| 7 | Emit the Step 4-B matrix and then re-emit a near-identical full table again as the session-end report after Step 4-C | One full matrix per cleanup pass. The later session-end report follows the "Same-pass duplication rule" (see the Mandatory Rows section): always-repeat rows (Session identity + RAG chunk counts) + post-matrix delta + a one-line reference |

### Self-check (immediately before the Step 4-C wip call every time)

1. Does the response text contain the 36-character Session ID UUID at least once? **Cross-check the exact UUID against the most recent hook-injected `Current session ID:` line in this turn (or a marker-method result) — a UUID copied from a memory file's `originSessionId` frontmatter, an old chat reference, or "the one I've been using all session" is not a valid source. If a RAG import earlier in the session used a different UUID than what's injected right now, that import targeted the wrong session's JSONL — re-run it with the correct UUID before finalizing this row.**
2. Are all 8 rows of the matrix above included, INCLUDING a literal `3-C.1 RAG Store` row (bold/highlighted per the mandatory-rows table)? A comprehensive report that reports RAG results only in earlier prose and omits the dedicated row is incomplete — go back and add it. (also state N/A explicitly for any non-applicable row)
3. Does the commits row state this session's SHA + repository + branch?
4. Does the files row state all paths Edit/Write-targeted this session?
5. Are the Step 4-B comprehensive report and the Step 4-C wip call clearly separated as separate responses or separate sections?
6. **Does the BLOCKED row contain a RAG store failure item?** If yes, entering Step 4-C is **forbidden** — try all of workflow.md's "session-end RAG persistence obligation" medium matrix (MCP / vendor script / direct REST API). Only after all three media fail is entering next allowed. **Simply "stating BLOCKED" ≠ "qualified to enter next" — attempting medium alternatives is a prior obligation**
7. **Has the `walkthrough-<topic>-<sessid8>.md` file actually been written/updated on disk (not just planned in text)?** Verify with a real file check before citing its path in the Walkthrough file row — a described-but-unwritten path is a violation of this same gate

**Skip condition**: same as the Step 4 skip condition (no conversation content or only simple questions)

---
