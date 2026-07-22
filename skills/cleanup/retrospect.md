# Retrospect (mistake analysis and feedback recording)

Systematically analyze mistakes made during the session and record them to feedback memory + failed-attempts.md.

## Trigger

- When `/cleanup` args contain mistake/improvement-related keywords (e.g., "improve foolishness", "record mistake", "save feedback")
- Auto-run as Step 0 during `/cleanup run`
- Direct call via `/cleanup retrospect`

## Procedure

### 1. Mistake detection

Scan the entire conversation for the following signals:

| Signal | Example |
|------|------|
| User correction/pointing out | "No, not that", "You didn't check, did you?", "Why only 50?" |
| Wrong judgment | Assumed no model exists, guessed it's a separate issue |
| Ignored existing artifacts | Didn't check an already-existing plan/research file |
| Repeated mistake | Received the same correction 2+ times |
| Rule violation | Performed an action prohibited by rules/conventions |

### 1.5. Recurrence pre-check (MANDATORY — before Step 2 recording)

Before recording a new mistake to failed-attempts.md, **apply the same 2-stage procedure from `fix.md` Step 1 "Recurrence pre-check" (RAG semantic search + grep) verbatim**. Enforcing the same procedure on the retrospect entry path too prevents records made via retrospect from being mislabeled as "1st occurrence" due to a missed recurrence classification.

**Key behavior**:

1. **Stage 0 (RAG)**: if a RAG receiver (`mcp__<vendor>__*-find` tool) is registered in the current environment, call it with the mistake pattern's key keywords → if there's a semantic match hit, classify as an Nth recurrence
2. **Stage 1 (grep)**: recursive grep on `~/.claude/skills/cleanup/data/` (search HOT + archive simultaneously) + grep on `~/.agents/rules/*.md`
3. **On archive-only hit**: call `Skill("cleanup", "fa-prune")` Step 7 restore procedure (return to HOT + recurrence label)
4. **Result**: include the recurrence info in the title label of the per-mistake analysis in Step 2 (e.g., `## ... (2026-MM-DD, 2nd recurrence)`)

**Why retrospect.md also needs separate enforcement**:
- `fix.md` Step 1 is exclusive to the `fix:` trigger path
- retrospect is invoked via `/cleanup run` or a direct `/cleanup retrospect` call — a separate entry point
- The `block-fa-edit-without-rag-search.sh` hook structurally blocks it, but active invocation at the procedure step is more accurate for recurrence labeling than post-hoc blocking

**Single source of truth**: [`~/.claude/skills/fix/SKILL.md`](../fix/SKILL.md) Step 1 "Recurrence pre-check" is the authoritative source. This Step 1.5 only enforces the entry path — no body duplication.

### 2. Per-mistake analysis

For each mistake, organize the following (title includes the recurrence label identified in Step 1.5):

```markdown
## [Mistake title] (date)

### Problem
- What was done wrong

### Cause
- Why it was done wrong (root cause)

### Prevention
- How to prevent it (concrete behavioral rule)
```

### 3. Confirm recording targets via AskUserQuestion

```
AskUserQuestion {
  question: "Recording the following mistakes. Which ones should be saved?",
  multiSelect: true,
  options: [
    { label: "Mistake 1 title", description: "summary" },
    { label: "Mistake 2 title", description: "summary" },
    ...
  ]
}
```

#### AskUserQuestion option-composition guard (HARD STOP)

retrospect is the **step that records the learning trace** — a single recorded violation is the basis on which fix.md's "recurrence pre-check" procedure operates. If the record is missing, the next occurrence of the same violation is misclassified as "1st occurrence," disabling the escalation rule (1st = rule / 2nd = hook review / 3rd = hook mandatory).

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Convert `multiSelect: true` to single-select | Keep `multiSelect: true` — user selects per item, no single "skip all" option |
| 2 | Add **skip options** like "don't record", "self-check only", "pass" to the options | Options must be composed **only of mistake titles**. Skip is expressed by the user selecting 0 items |
| 3 | Self-judge "1 occurrence is already covered by an existing global rule, so no need to record" | Record even 1 occurrence — the record is the violation trace; an existing global rule ≠ exemption from recording |
| 4 | Description saying "trivial, so skip the Recommended one" | Record the Recommended one too — description should state "preserve 1st-occurrence trace → enables identifying the 2nd occurrence when it happens" |

**Self-check (right before writing options)**:
1. Are all options "mistake titles"? → Immediately remove meta-options like "don't record"
2. Is multiSelect `true`? → If false, that's a false positive (forcing the user to select only 1 item is not the intent of retrospect)
3. Does Recommended or default act as "skip"? → If so, it's a violation

For case history, see `~/.claude/skills/cleanup/data/failed-attempts.md` under "retrospect options set to single-select with a default skip."

### 4. Executing the record

For approved items, perform **both of the following simultaneously**:

#### 4-1. Save to feedback memory

**Storage tool priority** (same as `run.md` Step 5):

| Priority | Condition | Storage method |
|---------|------|------|
| 1 | Serena MCP active | `activate_project` → `write_memory("feedback-[keyword]", content)` |
| 2 | No Serena (fallback) | Create a file in the `memory/` directory + add to the `MEMORY.md` index + dual-sync |

**Confirming Serena is active**: if the `mcp__serena__list_memories()` call succeeds, use Serena.

##### When saving via Serena

```
activate_project("{project-name}")
write_memory("feedback-[keyword]", "[rule]\n\n**Why:** [root cause]\n**How to apply:** [when and how to apply]")
```

##### Claude Code fallback

Create a feedback-type memory file in the `memory/` directory:

```markdown
---
name: feedback_[keyword]
description: [one-line description]
type: feedback
---

[rule]

**Why:** [root cause]
**How to apply:** [when and how to apply]
```

+ add a pointer to the `MEMORY.md` index
+ **dual-sync**: save on both WSL and Windows (follow the dual-sync rule in `~/.agent/rules/common.md`)

#### 4-2. Add to failed-attempts.md

Add a section to `~/.claude/skills/cleanup/data/failed-attempts.md` (HOT). This is skill data, not a rules file — `~/.agents/rules/failed-attempts.md` only contains a location-pointer stub.

**Profanity masking (MANDATORY)**: when recording FA, exclude or mask the user's profanity/swearing with `****`/`XX`. If the anger-signal context needs to be preserved, describe it with a neutral term ("anger") or quote with masking in the form "(profanity masked: ...****...)". Do not record raw profanity verbatim. **Same rule applies to `fix.md` Step 2 FA recording** (cross-ref).

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Quote the user's profanity verbatim | Mask with `****`/`XX`, or exclude that part |
| 2 | Keep raw profanity to preserve the anger context | Preserve the context via a neutral term like "anger" + masked quotation |

**Title label (MANDATORY)**: reflect the recurrence info identified in Step 1.5 in the title — `(YYYY-MM-DD)` for the 1st occurrence, `(YYYY-MM-DD, Nth recurrence)` for the Nth. Omitting the recurrence label disables fix.md's escalation rule (1st = rule / 2nd = hook review / 3rd = hook mandatory).

```markdown
## [Mistake title] (YYYY-MM-DD[, Nth recurrence])

### Problem
- ...

### Cause
- ...

### Resolution and Prevention
- ...
```

### 5. Skill malfunction check

Check the skills used in the session to identify any that need improvement.

**Check signals:**

| Signal | Example |
|------|------|
| Manual correction after skill execution | The skill ran but the result was fixed via Edit |
| Script error | Following the skill procedure, script exited non-zero, path error, missing command, etc. |
| Wrong topic selection | A different topic should have been invoked but the wrong one matched |
| Trigger failure | The skill should have activated in a given situation but didn't |
| Incomplete procedure | The skill procedure was followed but a step was missing |

**Handling on discovery:**
- Run upgrade only with user approval

### 6. FA Prune (failed-attempts cleanup) — MANDATORY execution step

After completing retrospect recording, **always** do the following:

1. **Check stale COLD candidates** (required):
   ```bash
   uv run python ~/.claude/skills/cleanup/scripts/fa-classify.py --relaxed | head -2
   ```
2. **If COLD candidates ≥1 — calling `Skill("cleanup", "fa-prune")` is mandatory** (HARD STOP):
   - Apply `skill-usage.md` "Execute the procedure immediately after Skill tool returns" — merely announcing "fa-prune is needed" as text without executing it violates this step
   - Trigger = relaxed staleness (consistent with fa-prune.md Section 5 policy). The numeric-cap trigger (old 20) is deprecated
3. **If COLD candidates = 0**: report "FA Prune skipped (0 stale COLD candidates)" and move to the next step

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Write "if more than 5, auto-run" as text without actually calling Skill() | Always confirm the count via grep → call `Skill("cleanup", "fa-prune")` immediately if exceeded |
| 2 | End retrospect assuming "it'll auto-run" | This is an explicitly defined procedural step — the caller (me) is responsible for the direct call |
| 3 | Stick to numeric thresholds (5/20) for triggering | Trigger based on relaxed staleness candidates (consistent with fa-prune.md Section 5 policy) |

### 7. Completion report

Concisely report the number of recorded items and the file list.

**RAG store quantity reporting obligation (HARD STOP)**: if this retrospect made a store call to the RAG receiver, **state the number of chunks added quantitatively at the end of the response**. Status-only reports like "RAG store complete (qdrant)" are forbidden. Format:

```
RAG store summary: N chunks added (receiver: <skill>:<topic>)
  - chunk-id-1: <one-line>
  - chunk-id-2: <one-line>
  ...
```

| # | Don't | Do |
|---|-------|----|
| 1 | Status-only "RAG store complete (qdrant)" | "RAG store summary: 3 chunks added" + 1-line ID/summary per chunk |
| 2 | Omit reporting because RAG store is a cross-topic task with ambiguous responsibility | If retrospect made the call, retrospect owns the report. State it quantitatively |
| 3 | Mention only mid-response, omit at the end | State the RAG summary **again** at the end of the response — lets the user immediately confirm whether it was stored |

Detailed format rule: see `~/.agents/rules/skill-usage.md` "RAG store report format obligation" section.

## Skip Conditions

- Skip if there were no mistakes/corrections in the conversation
- If the same content already exists in feedback memory or **HOT or archive**, branch handling (not a plain skip):
  - **In HOT** (`cleanup/data/failed-attempts.md`) → just add a recurrence marker
  - **In archive** (`cleanup/data/archive/*.md`) → restore to HOT via `/cleanup fa-prune` Step 7 procedure + add recurrence marker

## Pre-search Obligation (HARD STOP)

Before recording, always search in this order:

```bash
# 1. HOT + archive simultaneous grep (recursive)
grep -rlE "<2-3 key keywords>" ~/.claude/skills/cleanup/data/

# 2. feedback memory grep
ls ~/.claude/projects/*/memory/feedback_*.md 2>/dev/null | xargs grep -l "<keyword>"
```

- No results → new entry (1st occurrence)
- HOT match → recurrence (mark as N+1th occurrence)
- Archive match → restore to HOT via fa-prune Step 7 procedure, then mark as N+1th occurrence

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Grep HOT only → miss archive | Use `grep -rl ~/.claude/skills/cleanup/data/` for recursive search |
| 2 | Treat an archive match as a new entry anyway | Call the restore procedure (fa-prune Step 7) to return to HOT |

## Notes

- Mistake analysis must be **fact-based only** (no guessing/excuses)
- Dig for the **root cause** (do not just note the surface-level cause)
- Write prevention as a **concrete, verifiable behavioral rule**

---

## Prohibition on writing violation cases in skill/rule files (HARD STOP)

**Violation cases · "Nth-occurrence records" · case history belong in a single location: `~/.claude/skills/cleanup/data/failed-attempts.md`.** Do not write violation cases / "Violation case (YYYY-MM-DD, Nth occurrence)" / "Accumulated violation cases" / "N recurrences" / quoted body text in skill files (`*/SKILL.md`, `*/<topic>.md`) or rule files (`~/.agents/rules/*.md`, `<repo>/.claude/rules/*.md`).

### Don't / Do

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Add a "Violation case (YYYY-MM-DD, Nth occurrence)" subsection to the same file after strengthening a rule | Skills/rules contain **only rules (Don't/Do + self-checks)**. Violation cases are recorded to failed-attempts.md (HOT) via `/cleanup retrospect` |
| 2 | Reasoning that "citing the violation case next to the rule strengthens the prevention rationale" | The rule's effectiveness is sufficient on its own. If a case citation is needed, use a single reference line: "(see failed-attempts.md '<keyword>')" |
| 3 | Duplicate the same case in both failed-attempts.md HOT and the skill | Single medium. Use failed-attempts.md only. Skills get the rule + a one-line reference |
| 4 | Embed date/occurrence-count metadata like "(2026-MM-DD 1st occurrence)" in the skill | Date/occurrence count are attributes of the failed-attempts.md entry. Skills do not carry time/occurrence-count info |
| 5 | "Same fix/session context, so write it alongside" | Even within the same fix/session, separate media: rules go in skill/rule files, cases go in failed-attempts.md |
| 6 | **Directly quote a specific violation case (date · session ID · PR number · user quote) in a Don't/Do table cell (Don't or Do body)** | Don't/Do cells contain **only pattern · trigger · replacement behavior**. Specific cases go to failed-attempts.md (HOT). Do not embed "(2026-MM-DD user said ~)" in a cell |
| 7 | Reasoning that "citing an actual occurred case in this cell's Don't pattern increases persuasiveness" | Persuasiveness comes from clarity of the Don't pattern + accuracy of the self-check. Embedding cases in cells increases cell width + hurts rule abstraction |
| 8 | Quote case metadata like "N violations accumulated", "user anger signal" in self-check procedure body | Self-checks contain **only the verification action sequence**. Metadata belongs in the failed-attempts.md entry |

### Self-check (right before editing a skill/rule file)

1. Does the text you're adding contain "violation case", "Nth occurrence", "recurrence", or a "YYYY-MM-DD" date line?
2. **Does a Don't/Do table cell body contain a date · session ID · PR number · user quote?** — If yes, remove it from the cell + register the case separately in failed-attempts.md
3. Does a self-check procedure item quote "N accumulated occurrences", "user pointed out", or other case metadata? — If yes, remove it
4. Anything matching Yes above must be written to failed-attempts.md (HOT) — remove from the Edit target
5. Rule bodies consist only of Don't/Do + self-checks + procedures
6. If a case reference is truly needed, use only a single line: `(see failed-attempts.md "<keyword>")`
