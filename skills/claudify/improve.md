# Improve (Self-Improving Loop)

Analyze session episodic data (mistakes, hook/skill behavior, repeated patterns) and improve the system.

## When to Use

- `/claudify improve` — direct invocation
- `/cleanup run` Step 2 — automatic as part of session cleanup

## Workflow

### A. Retrospect (Mistake Analysis)

Scan conversation for mistake signals and record to feedback memory + failed-attempts.md.

The record procedure itself is owned by the `fa` skill — invoke `Skill("fa")` (its
[retrospect.md](../fa/retrospect.md) topic) for the actual write; this section only defines
the improve-loop framing around it.

**Signals**:

| Signal | Example |
|--------|---------|
| User correction | "no, not that", "you didn't even verify?" |
| Wrong judgment | Model declared absent, guessed separate issue |
| Ignored artifacts | Existing plan/research files not checked |
| Repeated mistake | Same correction 2+ times |
| Rule violation | Performed prohibited action from rules |

**Per mistake**:
1. Analyze root cause (Why 1-3 minimum)
2. Draft feedback memory entry (rule + Why + How to apply)
3. **If the finding implies future work, register it as a `- [ ]` item in the workspace tracker (`fix_plan.md` / `checklist.md`) — HARD STOP.** See below.
4. Collect for Phase 2 AskUserQuestion

**Findings that imply future work must reach the tracker (HARD STOP)**

The retrospect log records **what went wrong**; the tracker records **what will be done**. They are different media and one does not stand in for the other. A finding whose remediation is not fully executed in this session — a hook the escalation matrix now mandates, a trigger to register, a rule to strengthen, a defect to verify elsewhere — leaves no actionable trace when it lives only in the retrospect entry: nothing surfaces it during the next session's backlog read, so the escalation the entry itself declares never gets executed.

This mirrors the obligation C (Pattern Detect) already carries for its candidates. The asymmetry — candidates registered, retrospect remediations not — is the gap this rule closes.

| # | Don't | Do |
|---|-------|-----|
| 1 | Write the retrospect entry, then treat the retrospect as done | Register every finding's outstanding remediation as a `- [ ]` tracker item, cross-referenced by the entry's class name |
| 2 | Route the "should we do this remediation?" decision to a user ask instead of the tracker | Registering it is not asking to do it — it makes the work visible. Whether to run it now is a separate decision |
| 3 | Skip registration because the retrospect entry already spells out the fix in its Why 5 | A retrospect entry is not read during backlog triage. If it is not in the tracker, it is not scheduled |
| 4 | Register only findings from Pattern Detect because that is where the HARD STOP is written | Retrospect findings carry the same obligation — this section is that missing half |

**Skip condition for registration only**: the finding's remediation was fully executed in this session (state that in the report), or the finding is purely descriptive with no follow-up action.

**FA Prune**: After recording, invoke `Skill("fa", "fa-prune")` and follow [fa-prune.md](../fa/fa-prune.md) when any axis in its "Execution trigger (class-based)" table fires — [cleanup/run.md](../cleanup/run.md) makes that skill call mandatory (a text-only note is ❌), so linking the topic alone leaves this path dispatching differently from the cleanup path. That table is the single source for the trigger — do not restate a section-count threshold here; the flat counts it replaced are deprecated.

**Skip condition**: No mistakes/corrections in conversation.

### B. Automation Review (Hook + Skill Check)

#### Hook Review

1. Collect registered hooks from the canonical inventory first (`Read skills/hook-kit/hook-registry.yaml`, hook-kit `registry.md`), then compare against the live surfaces (settings.json `hooks`, plugin `hooks/hooks.json`) — ownership comes from the registry row, not from "a plugin hooks.json also lists it"
2. **File existence check**: Extract script paths → verify files exist → classify missing as "ghost hooks"
3. Check each hook's session behavior:
   - Triggered + acted on → "OK"
   - Triggered + **ignored** → "Ignored" (most critical)
   - Triggered + error → record error
   - Not triggered → "Not triggered"
   - File missing → "Ghost"
4. **Ignored output detection**: Search for `<skill-trigger>`, `BUILD_COMPLETED`, `AUTO_AGENTIFY_CANDIDATE:` markers
5. Summary report (immediate output):

```
**Hook summary**: 16 registered / 10 OK / 6 not triggered / 0 ignored / 0 error
```

**Skip condition**: None — always run if any hooks registered.

**Self-check (before closing this sub-step)**: did this pass **physically emit** the `**Hook summary**: N registered / M OK / ...` line (with the actual enumerated numbers from settings.json + session behavior classification), or did it collapse to a prose conclusion like "0 ignored" without the enumeration? A conclusion without the format line is not a substitute — go back and produce the line before moving to Skill Check. A "nothing changed since the last pass" judgment does not exempt this sub-step: re-run the enumeration and confirm the counts, even if the conclusion repeats the prior pass's numbers.

#### Skill Check

1. Collect skills invoked via `Skill()` during session
2. Post-execution self-heal checklist per skill:
   - Did trigger fire correctly?
   - Was correct topic selected?
   - Was procedure complete? (no manual correction needed?)
   - Were outputs complete?
3. Malfunctions → collect for Phase 2 AskUserQuestion

**Skip condition**: No skills invoked, or all skills worked correctly.

**Self-check (before closing this sub-step)**: did this pass **list the actual skills invoked this session** (by name) and run the 4-item self-heal checklist against each, or did it collapse to a single unenumerated sentence? Naming zero skills when 1+ were invoked this session is a skipped sub-step, not a clean result.

### C. Pattern Detect (Automation Candidate Discovery)

**Always run — no skip.**

1. Analyze conversation context for automatable repeated patterns
2. On candidate discovery:
   - Maps to existing rule/skill → suggest upgrade in Phase 2
   - **New pattern that fits nowhere → invoke `/skill-kit route`** → auto-chain to upgrade/writer
   - **Candidate is a bug/behavior fix (a hook, script, or guard producing wrong output — not a new topic/doc/skill) → run the `/fix` skill's Step 1 recurrence pre-check (`failed-attempts.md` grep, and a RAG semantic search if a receiver is available) before implementing it in Phase 2.** Reaching a bug fix via this pattern-detect path does not exempt it from the same recurrence discipline a direct `/fix` invocation would require — a bug surfaced here can still be an Nth recurrence of an already-recorded pattern, and implementing it as if newly discovered risks missing that it needs a status update (or a stronger fix) instead of a fresh entry
3. Collect candidates for Phase 2 AskUserQuestion

## Ralph Mode

**Detection**: see SKILL.md "Ralph Mode" — `.ralph/` directory + `RALPH_LOOP=1` env var, both required.

A-C: detect + record to `.ralph/improvements.md` only. No direct modifications.

## Phase 2 Integration

This topic does NOT call AskUserQuestion directly. All findings are returned to the caller (cleanup run.md) for batch Phase 2 confirmation.

**Return format** (internal):
```
{
  retrospect: [{ label, description }],
  hooks: { summary, issues: [{ label, description }] },
  skills: [{ label, description }],
  patterns: [{ label, description, needsRoute: bool }]
}
```
