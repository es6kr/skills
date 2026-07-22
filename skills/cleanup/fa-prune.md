# FA Prune (failed-attempts cleanup)

Detects items in failed-attempts.md that are already reflected in rules/skills and proposes deletion.

## Procedure

### 1. Rules duplication analysis

For each section, check whether the "prevention" content already exists as a rule in the rules files:

```bash
# Analysis target
Each ## section in ~/.claude/skills/cleanup/data/failed-attempts.md

# Comparison target rules
~/.agents/rules/*.md (excluding the failed-attempts.md stub itself)
```

**Matching criterion**: If the section's "prevention" key keywords already exist as a rule in a rules file, classify as COVERED.

### 2. Skill reflection check

If a section's "prevention" mentions a specific skill, check whether it has actually been reflected in that skill:
- "Added to skill" → Grep to confirm in the skill file
- "Added logic to build.sh" → Grep to confirm in the script

### 3. Classification output

| Classification | Criterion | Action |
|------|------|------|
| COVERED | Reflected as a rule in rules | Delete |
| SKILL_DONE | Reflected in a skill | Delete |
| PROMOTE | Generalizable rule | Promote to rules, then delete |
| KEEP | Project-specific case | Keep |

### 4. Execution

After user approval in Phase 2 (AskUserQuestion):
- COVERED/SKILL_DONE: delete the section
- PROMOTE: add the rule to the appropriate rules file, then delete the section

### 5. Lifecycle auto-classification (HOT/COLD)

Apply a self-improving pattern. Classify sections as HOT/COLD based on section date and reference frequency:

| Classification | Criterion | Location |
|------|------|------|
| HOT | Occurred within the last 30 days **OR** has recurrence history **OR** has a future hook obligation | Kept in `~/.claude/skills/cleanup/data/failed-attempts.md` |
| COLD | Older than 30 days + no recurrence + COVERED/SKILL_DONE + no future hook obligation | Moved to `~/.claude/skills/cleanup/data/archive/failed-attempts-archive-<YYYY-MM-DD>.md` (see Section 6) |

**Date detection**: Extract the latest date from the `(YYYY-MM-DD)` or `(YYYY-MM-DD, MM-DD)` pattern in the section title.

**Recurrence detection (HARD STOP — cross-verification mandatory)**:

Before COLD classification, verify **all three** of the following for **each section**:

| # | Check | Method | COLD-blocking condition |
|---|------|------|---------------|
| 1 | Recurrence marker in title | Title contains "Nth recurrence", "recurred N times", "2nd time", "3rd time", etc. | If present, HOT |
| 2 | Follow-up recurrence date in body | Body contains a `(YYYY-MM-DD)` date later than the title date | If present, HOT |
| 3 | Future hook obligation | Body contains "hook on Nth occurrence", "hook automation on next occurrence" | If present, HOT |

**If any one applies, COLD classification is forbidden.**

**Exception — recurrence-resolved (unblocks when recurrence risk is resolved)**:

Even if checks #1 (recurrence marker) or #3 (future hook obligation) apply, if the same section body contains a **resolution marker**, that block does not apply — the recurrence risk has already been handled (hook/escalation implementation completed), so the section regains COLD eligibility. The date condition (older than 30 days) + Phase 2 user approval still apply.

| Resolution marker (unblocks) | Not a resolution (still HOT) |
|---------------------|----------------------|
| "hook escalation completed" | "hook implementation mandatory" |
| "hook implementation/automation/registration/installation completed" | "hook automation under review" |
| "escalation completed" | "hook implementation to execute immediately" |
| "recurrence prevention/resolution completed", "auto-block/prevention completed" | "not yet implemented", "hook on Nth occurrence" |

Key criterion: **only completed (past-tense) markers resolve.** Future obligation/review/mandatory markers do not resolve. Check #2 (follow-up recurrence date in body) is not subject to this exception — even with a resolution marker, if there's a recurrence date after the title date, it stays HOT (strict-mode basis).

**Relaxed policy — stale-recurrence demotion (option B, user-approved default operating policy)**:

Recurrence markers are interpreted not as a permanent trigger but as a **recency-based trigger**. If the section's **newest date (including both title and body recurrence dates)** is older than the cutoff (default 30 days), the section is COLD-eligible even with a recurrence marker.

| Condition | Relaxed verdict |
|------|-------------|
| Newest date (title+body) < cutoff | COLD-eligible (regardless of recurrence marker) |
| Unresolved hook obligation (no resolution marker) | **Still blocked** (stays HOT) |
| Section with no date | Stays HOT (prevents false positives — top of file = newest item) |
| Phase 2 user approval | Still required — no auto-demotion |

Demoted sections move to archive + RAG store, so recurrence detection (Section 7-1 recursive grep + semantic search) is preserved. On recurrence, the Section 7 restore procedure works normally to bring the section back to HOT + accumulate recurrence count.

**Auto-classification script**: `scripts/fa-classify.py` implements the entire classification above (recurrence/hook/resolution detection + COLD verdict) — a successor to fa-analyze.py, including the resolution exception.

```bash
uv run python ~/.claude/skills/cleanup/scripts/fa-classify.py                     # strict summary + COLD candidates (R = demoted via resolution exception)
uv run python ~/.claude/skills/cleanup/scripts/fa-classify.py --relaxed           # relaxed mode (S = stale-recurrence demotion) — default operating policy
uv run python ~/.claude/skills/cleanup/scripts/fa-classify.py --relaxed --cut /tmp/fa-cold  # separate COLD body files + index.json (Section 8 RAG store input)
```

**Goal**: no numeric cap — **the relaxed staleness rule is the control mechanism**. In every fa-prune run, demoting sections whose newest date exceeds 30 days naturally converges HOT toward "live patterns from the last 30 days + unresolved hook obligations." (The former "max 20 sections" numeric target is deprecated as incompatible with permanent recurrence-marker triggers.)

**Execution trigger threshold = 160 sections** (user-approved threshold): do not create/recommend an fa-prune task while HOT section count is below 160. Only propose a relaxed staleness run when it reaches 160 or more. (The old "threshold 20" notation is a leftover from the deprecated numeric cap — correct it to this value if it reappears in a task subject, etc.)

### 6. Archive file management

`~/.claude/skills/cleanup/data/archive/failed-attempts-archive-<YYYY-MM-DD>.md`:
- Stores COLD-demoted sections in date order
- Location: `~/.claude/skills/cleanup/data/archive/` (same directory as the HOT body → automatically included in recursive Grep)
- **The archive is not loaded always_on** (the `data/` directory is on-demand only)
- On name collision, distinguish with a date suffix (e.g., `failed-attempts-archive-YYYY-MM-DD.md`)

### 7. Restore procedure (COLD → HOT, MANDATORY)

**When the same pattern recurs, the archived section must be restored to the HOT body for the escalation rule (Nth-occurrence classification) to work correctly.** If restoration is omitted, the archived case is misclassified as "1st occurrence," disabling the hook automation trigger.

#### 7-1. Automatic pre-search (on entering retrospect/fix)

Before recording a new case / classifying recurrence, always:

```bash
# Search HOT + archive simultaneously (recursive)
grep -rlE "<key-keywords>" ~/.claude/skills/cleanup/data/
```

- Match in HOT only → new (1st occurrence)
- Match in archive only → **restore required** (procedure 7-2)
- Match in both HOT and archive → already in HOT. Just add the recurrence marker (means it was never demoted)

#### 7-2. Executing the restore

When the section is found in archive:

1. Cut the section from the archive file (from the `## ` line to just before the next `## `)
2. Paste it into the top of the HOT body (`failed-attempts.md`) or in date order
3. Add a recurrence marker to the section title (e.g., `## ... — 2nd recurrence (YYYY-MM-DD)`)
4. Add "restore reason + new recurrence entry" at the end of the body
5. Report the restore result in chat (for user review)

#### 7-3. Don't / Do

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Classify as "1st occurrence" without searching archive when entering retrospect/fix | Search both HOT + archive with recursive grep + RAG semantic search (when Section 8 dispatch is available) |
| 2 | Add a new entry to HOT without restoring, even when the same keyword exists in archive | Restore → add recurrence marker → append new entry body |
| 3 | Assume "archive is a permanent cleanup" | Archive = COLD cache. Can return to HOT immediately on recurrence |

### 8. RAG dispatch (`--rag=<skill>:<topic>`, vendor-agnostic)

Same abstract contract as the `/archive` skill. Simultaneously store COLD-demoted sections to a RAG receiver to strengthen semantic search / recurrence detection (Section 7-1).

**Invocation format**:

```
/cleanup fa-prune --rag=<skill>:<topic>
```

Or when invoking `Skill("cleanup", "fa-prune")`, include `--rag=<skill>:<topic>` in args. The caller (Claude) specifies the receiver available in the environment — the vendor name is the caller's domain; the callee (fa-prune) only receives the receiver identifier and dispatches.

#### Applicable matrix

| Task | Dispatch target | Default behavior |
|------|-------------|------------|
| COLD-demoted sections (after Section 4 execution) | Store 1 per section to the receiver | `--rag` not specified = no dispatch |
| Backfill (bulk-store existing archive to the receiver) | All archive sections | Explicit `--rag` + `--backfill` flag |

#### Receiver protocol (vendor-agnostic)

The receiver accepts the following inputs (same pattern as the `/archive` skill's "RAG dispatch" section):

| Env var | Content |
|---------|------|
| `FA_PRUNE_SECTION_TITLE` | Section title (e.g., `Assuming no fix_plan work needed just because issue CLOSED (YYYY-MM-DD)`) |
| `FA_PRUNE_SECTION_BODY` | Section body (markdown) |
| `FA_PRUNE_SOURCE_FILE` | Archive file name (e.g., `failed-attempts-archive-YYYY-MM-DD.md`) |
| `FA_PRUNE_SECTION_DATE` | Latest date extracted from the section title/body (YYYY-MM-DD) |
| `FA_PRUNE_METADATA_JSON` | Serialized metadata: `{type: "archived-failure-pattern", project, date, category: "fa-prune-archive", source_file, section_title, chunk_key}` |

The receiver uses an idempotent id (e.g., sha1(`fa-archive:<file>:<title>`)) for safe re-execution. Backend choice (which vector DB, which embedding model) is the receiver skill's domain — fa-prune only passes the receiver identifier.

#### Don't / Do

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Hardcode a specific vendor (vector DB / embedding model / MCP tool name directly in fa-prune.md) | Let the caller specify the receiver via `--rag=<skill>:<topic>`. Keep the callee vendor-agnostic |
| 2 | Ignore section-level granularity and store an entire archive file as 1 chunk | Store per-section — Section 7-1 semantic search depends on section-level matching |
| 3 | Omit metadata | 4 metadata keys required (type/project/date/category) + source_file/section_title |
| 4 | Auto-dispatch when `--rag` is not specified | If not specified = no dispatch. Auto-supply is the caller's (Claude's) responsibility (`skill-usage.md` "Auto-supply available vendor dispatch when invoking a shared skill") |
| 5 | Also delete from the receiver on restore (Section 7-2) | Restore only brings back to HOT. Receiver data is kept (archive history also helps semantic search) |

**HTTP fallback script (when receiver MCP is down)**: `scripts/fa-batch-store.py` — consumes `--cut-dir` output or `--backfill <archive.md>` + `--skip-existing` (idempotent). Do not write ad-hoc inline store scripts.

#### Self-check (right before running fa-prune)

1. Is the `--rag=<skill>:<topic>` flag included in the invocation?
2. If not included + a RAG receiver is available (a RAG store tool exists in the caller's environment) → the caller must auto-supply (skill-usage.md HARD STOP)
3. On COLD demote, call the receiver for each section, then write to the archive file
4. Backfill mode: bulk-store existing archive files to the receiver via `--backfill --rag=<skill>:<topic>`

#### RAG store quantity reporting obligation (HARD STOP)

After fa-prune completes, **state the number of chunks added quantitatively at the end of the response**. If N sections were demoted to COLD + N were stored to the RAG receiver, state that number exactly.

```
RAG store summary: N chunks added (receiver: <skill>:<topic>)
Archive file: <path>
COLD demoted sections: N
  - <section-title-1>
  - <section-title-2>
```

| # | Don't | Do |
|---|-------|----|
| 1 | Status-only "RAG store per section complete" | Quantitative "RAG store summary: 3 chunks added (receiver: <skill>:<topic>)" |
| 2 | Report only mid-response, omit from the end | Show the RAG summary block **again** at the end of the response |
| 3 | Mismatch between demote count and store count (e.g., 3 demoted but only 2 stored) | demote count = store count = reported count to the user. Verify all 3 match |

Detailed format rule: see `~/.agents/rules/skill-usage.md` "RAG store report format obligation" section.

## Skip Conditions

- Skip if failed-attempts.md does not exist
- Skip if `fa-classify.py --relaxed` reports 0 COLD candidates (no cleanup needed)

## Ralph Mode

Record detection results to `.ralph/improvements.md`. Do not directly delete/modify.
