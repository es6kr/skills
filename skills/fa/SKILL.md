---
metadata:
  author: es6kr
  version: "0.1.0"
name: fa
depends-on:
  - cleanup
  - fix
description: |
  Lightweight FA-record entry point — record a misbehavior and report its escalation stage
  WITHOUT running fix's full Step 0-4 procedure (no TodoWrite, no 5-Why, no Resume, no wrap-up).
  Callable directly, no topic needed, the same way /fix is called. Use directly instead of /fix
  when the mistake is 1st/2nd occurrence or you just want the count + stage logged. /fix remains
  the only skill that actually edits a rule or hook file.
  Use when "fa", "record this", "log this mistake", "just record it" is mentioned.
---

# FA: Lightweight Record Entry Point

Callable directly — no topic, no sub-argument — the same way `/fix` is called. Records a
misbehavior and reports its escalation stage; never edits a rule/hook file itself.

## Procedure

1. **Recurrence pre-check** — run the Stage 0 (RAG) + Stage 1 (grep) procedure exactly as
   defined in [`fix/SKILL.md`](../fix/SKILL.md) Step 1 "Recurrence pre-check" (single source
   of truth — not duplicated here).
2. **Delegate the write** — call `Skill("cleanup", "retrospect")` to perform the actual
   Problem/Cause/Prevention write + feedback memory + FA HOT entry + RAG store (retrospect's
   Steps 2-4). Do not reimplement the write here.
3. **Read back the Nth-count** and look up the escalation stage from
   [`fix/step2-improvement.md`](../fix/step2-improvement.md)'s "4-stage progressive" matrix
   (single source of truth for the matrix itself).
4. **Report the stage** — plain text only, no Edit performed by this skill:
   - **1st-2nd**: "Recorded. No action needed yet (stage: record-only)."
   - **3rd**: "Recorded — 3rd occurrence. 4-filter gate applies; run `/fix` to evaluate + apply
     a rule edit if it passes." If the pattern looks deterministic (4-filter filter #3
     candidate), mark the FA entry `status=hook-pending`; otherwise `status=watch`.
   - **4th+**: "Recorded — 4th+ occurrence. Hook implementation is mandatory per the matrix;
     run `/fix` to author + register it."
5. **Stop.** This skill never performs `/fix`'s Step 0 TodoWrite, Step 1 5-Why, Step 2
   Edit/Write on rule/hook files, Step 3 Resume, or Step 4 wrap-up — those stay `/fix`'s job.

## Skip conditions inherited from retrospect

Retrospect Steps 5 (skill-malfunction scan) and 6 (FA Prune mandatory check) still run — they
are cheap (a grep + one script call) and keep the corpus healthy. Not opt-out.

## Anti-patterns

- Reimplementing retrospect's write logic here instead of calling `Skill("cleanup", "retrospect")`
- Performing a rule/hook Edit from inside this skill — that is exclusively `/fix`'s job
- Treating a stage-3/4 report as optional to act on — the caller must actually invoke `/fix`
  once this skill reports that threshold, or the recorded pattern silently never escalates
