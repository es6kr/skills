---
metadata:
  author: es6kr
  version: "0.1.0"
name: fa
depends-on:
  - fix
description: |
  FA (failed-attempts) lifecycle owner — record a misbehavior, evaluate recurrence risk (procedural
  gap / script defect), and report its escalation stage. Offers an immediate fix ask via
  AskUserQuestion when deterministic recurrence is high, WITHOUT running fix's full Step 0-4
  procedure unless escalated.
  retrospect - mistake analysis + record to feedback memory/failed-attempts [retrospect.md],
  fa-prune - deduplicate failed-attempts rules [fa-prune.md].
  Use when "fa", "record this", "log this mistake", "just record it", "fa prune" is mentioned.
---

# FA: Failed-Attempts Lifecycle Owner

Callable directly — no topic, no sub-argument — the same way `/fix` is called. Records a
misbehavior, evaluates the recurrence risk of underlying procedural gaps or script defects,
and reports its escalation stage (or offers an immediate fix ask).

This skill owns the FA record procedure ([retrospect.md](./retrospect.md)) and the FA store
hygiene procedure ([fa-prune.md](./fa-prune.md)). Other skills (e.g. `cleanup`'s session-end
pipeline via `claudify` improve) reference this skill — not the other way around.

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| retrospect | Mistake detection + recurrence pre-check + record (FA HOT / feedback memory / RAG) | [retrospect.md](./retrospect.md) |
| fa-prune | Deduplicate / archive stale failed-attempts entries (HOT ↔ COLD lifecycle) | [fa-prune.md](./fa-prune.md) |

## FA data store

The FA store location is resolved via the `FA_DATA_DIR` environment variable with a
backward-compatible default: `${FA_DATA_DIR:-$HOME/.claude/skills/cleanup/data}`.
A future physical relocation only changes this default — callers and scripts must not
hardcode the path.

The `fa` topics refer to the resolved directory as `$FA_STORE`. Resolve it once per shell
before running any command that touches the store:

```bash
FA_STORE="${FA_DATA_DIR:-$HOME/.claude/skills/cleanup/data}"
```

This covers the whole store — the HOT body, `archive/`, and `rag-pending/` alike. Honouring
`FA_DATA_DIR` for one of them and hardcoding the others splits the store in half, so a
configured run would classify one file while recurrence checks and archive moves read another.

## Procedure

1. **Recurrence pre-check** — run the Stage 0 (RAG) + Stage 1 (grep) procedure exactly as
   defined in [`fix/SKILL.md`](../fix/SKILL.md) Step 1 "Recurrence pre-check" (single source
   of truth — not duplicated here).
2. **Perform the write** — follow [retrospect.md](./retrospect.md) (this skill's own topic)
   Steps 2-4: Problem/Cause/Prevention write + feedback memory + FA HOT entry + RAG store.
3. **Read back the Nth-count** and look up the escalation stage from
   [`fix/step2-improvement.md`](../fix/step2-improvement.md)'s "4-stage progressive" matrix
   (single source of truth for the matrix itself).
4. **Evaluate Recurrence Risk & Defect Nature (Deterministic Flaw Assessment)**:
   - Analyze whether the identified root cause exhibits:
     - **Procedural Absence**: Missing validation step, absent verification gate, or lack of standard workflow phase.
     - **Script / Tool Defect**: Broken fallback logic, silent payload truncation, API contract mismatch, or variable expansion bugs.
     - **High Recurrence Probability**: Flaws that will deterministically repeat on subsequent identical triggers.
   - **Immediate Fix Escalation Ask (Optional Fast-Track)**:
     - When a deterministic procedural absence or script bug is identified (even on 1st/2nd occurrence), do NOT silently bury it as harmless record-only.
     - Prompt the user via `AskUserQuestion`:
       - Question: `High recurrence risk detected due to procedural gap or script defect. Would you like to fix this immediately via /fix or keep it as record-only?`
       - Options:
         - `(Recommended) Fix immediately: Launch /fix to patch the rule/script/procedure`
         - `Keep record-only: Proceed without immediate rule/script patch`
     - If the user selects **Fix immediately**, immediately handover to `/fix` to execute the full root cause correction and resume workflow.
5. **Report the stage** — when not fast-tracked to immediate fix:
   - **1st-2nd**: "Recorded. No action needed yet (stage: record-only)."
   - **3rd**: "Recorded — 3rd occurrence. 4-filter gate applies; run `/fix` to evaluate + apply
     a rule edit if it passes." If the pattern looks deterministic (4-filter filter #3
     candidate), mark the FA entry `status=hook-pending`; otherwise `status=watch`.
   - **4th+**: "Recorded — 4th+ occurrence. Hook implementation is mandatory per the matrix;
     run `/fix` to author + register it."
6. **Stop.** This skill never autonomously edits rule/hook files directly without `/fix` handover — rule edits remain `/fix`'s job.

   **Scope of "Stop" (HARD STOP — do not over-read it)**: this clause withholds *authority over
   rule/hook/skill files*, not permission to leave a broken artifact broken. When the violation
   you just recorded names a defect in an artifact that **currently exists** — a posted review
   comment, a tracker entry, a file written earlier this session — correcting that artifact is
   the **remaining part of the original work**, not `/fix`'s Step 3, and it belongs in this same
   turn. Only the rule/hook/skill edit waits for `/fix`. Ending the turn with a prose question
   ("let me know if you want it corrected") while the defective artifact stands is the exact
   failure this note exists to prevent — the record is written and the defect survives.

   | # | Don't | Do |
   |---|-------|-----|
   | 1 | Read "never performs Step 3 Resume" as "change nothing this turn" | It scopes *file ownership*. Fix the defective artifact the record points at; leave rule/hook edits to `/fix` |
   | 2 | Record the violation, then ask the user whether to correct the artifact | Correct it, then report what changed. Ask only when the correction itself needs a decision the user alone can make |
   | 3 | Treat "recorded" as "handled" when the artifact is still wrong | The record and the correction are separate deliverables — a record alone leaves the defect in place |

## Skip conditions

[retrospect.md](./retrospect.md) Steps 5 (skill-malfunction scan) and 6 (FA Prune mandatory
check) still run — they are cheap (a grep + one script call) and keep the corpus healthy.
Not opt-out.

## Anti-patterns

- Improvising the write inline instead of following [retrospect.md](./retrospect.md)'s
  procedure (its recurrence labeling, profanity masking, and RAG-store obligations are the
  contract — an inline paraphrase silently drops them)
- Performing a rule/hook Edit from inside this skill without escalating to `/fix`
- Blindly treating deterministic script/procedure bugs with 100% recurrence risk as harmless record-only without offering the immediate fix ask
- Treating a stage-3/4 report as optional to act on — the caller must actually invoke `/fix`
  once this skill reports that threshold, or the recorded pattern silently never escalates

