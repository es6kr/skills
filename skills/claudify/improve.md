# Improve (Self-Improving Loop)

Analyze session episodic data (mistakes, hook/skill behavior, repeated patterns) and improve the system.

## When to Use

- `/claudify improve` — direct invocation
- `/cleanup run` Step 2 — automatic as part of session cleanup

## Workflow

### A. Retrospect (Mistake Analysis)

Scan conversation for mistake signals and record to feedback memory + failed-attempts.md.

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
3. Collect for Phase 2 AskUserQuestion

**FA Prune**: After recording, run [fa-prune.md](../cleanup/fa-prune.md) automatically when any axis in its "Execution trigger (class-based)" table fires. That table is the single source for the trigger — do not restate a section-count threshold here; the flat counts it replaced are deprecated.

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
