---
metadata:
  author: es6kr
  version: "0.1.4"
name: fix
description: >-
  User behavior correction skill. Triggered by "fix:" prefix feedback (e.g., "fix: why didn't you commit?").
  Analyzes the mistake, improves the relevant rule/skill/hook to prevent recurrence,
  then fixes the current issue. TodoWrite required for all steps.
  Use when "fix:", "fix this", "correct", "why not", "why missing", "behavior fix" is mentioned.
---

# Fix: Behavior Correction Skill

Activated when user gives feedback with "fix:" prefix. Finds the root cause of the mistake, improves rules/skills/hooks, and fixes the current issue.

## Trigger

- Messages with `fix:` prefix
- Behavior correction feedback: "fix this", "correct", "why not", "why missing"

## Procedure

### Step 0. TodoWrite (MANDATORY — first action, no exceptions)

**Before any analysis or text output**, register TODO items:

```text
TodoWrite([
  { id: "fix-0", content: "fix: {user feedback summary} — root cause analysis", status: "in_progress" },
  { id: "fix-1", content: "Root cause fix", status: "pending" },
  { id: "fix-2", content: "Resume original work: {원래 작업 한 줄 요약}", status: "pending" },
  { id: "fix-3", content: "Completion report + cleanup", status: "pending" },
])
```

- `fix-2`의 `{원래 작업}` 은 fix 진입 **직전에 수행 중이던 작업**을 구체적으로 기재 (e.g., "session classify 결과 테이블 출력")
- fix-2 = "원래 작업을 수정된 접근법으로 끝까지 완료" — 스킬/룰 수정 자체가 아닌 **사용자가 원래 요청한 결과물 산출**이 목표
- Step 0 is **the first tool call** after /fix activation. Text output before TodoWrite = violation.

### 1. Root Cause Analysis (5-Why depth)

Don't stop at the direct cause. Dig at least **3 levels deep**:

```
Why 1: What went wrong? (symptom — the immediate mistake)
Why 2: Why did I make that decision? (judgment — missing knowledge/rule)
Why 3: Why was that knowledge/rule missing? (structural — skill/rule gap)
```

- Fixing only Why 1 = patching a symptom. It recurs in a different form.
- Why 2-3 reveal **structural causes** (platform ignorance, DRY violation, etc.) — these go into rules/skills.
- Search for the responsible **skill/rule/hook** files (Grep/Glob)

### 2. Root Cause Fix (Prevent Recurrence)

Priority (check in order — **stop at the first match**):

| Priority | Target | Condition | Example |
|----------|--------|-----------|---------|
| **1st** | **Skill** (`~/.claude/skills/`, `.claude/skills/`) | Skill is incomplete or has wrong procedure | Fix procedure step missing |
| 2nd | **Rule** (`~/.agent/rules/`, `.claude/rules/`) | Behavior rule is missing or insufficient | Add to failed-attempts.md |
| 3rd | **Hook** (`settings.json` hooks) | Automation needed for repeated mistakes | Add PostToolUse hook |
| 4th | **SKILL.md docs** | Documentation doesn't match actual behavior | Update section |

When fixing:
- **Skill is 1st priority** — if the problem is a skill's incomplete procedure, fix the skill. Don't skip to failed-attempts.md
- Rule location must be confirmed via **AskUserQuestion**
- failed-attempts.md recording is **only for cases not covered by skill/rule/hook** — no duplicate recording if root cause is already reflected in a skill or rule

### 3. Resume Original Work (fix-2)

**This is the most important step.** The user's original request must be completed — not just the fix itself.

1. Re-read `fix-2` subject to recall the original task
2. Execute the original task using the corrected approach
3. Produce the **original deliverable** the user asked for (e.g., classification table, plan document, deploy result)
4. Verify the deliverable is complete

**Anti-pattern**: "스크립트 생성 완료. 다음에 실행하면 됩니다" — fix는 도구 개선이 목적이 아니라 **원래 작업 완료**가 목적. 도구 개선은 수단일 뿐.

### 4. Completion Report + Cleanup

```
Fix complete:
- Root cause: {what was missing}
- Improvement: {which file was modified and how}
- Current fix: {result of fixing the current issue}
```

**After reporting, delete all TODO items created in Step 0** — fix TODOs are temporary session-level tracking only; must not persist after completion.

## Anti-patterns

- Repeating "already fixed" without actually fixing the root cause
- Patching only the current issue without improving skills/rules/hooks
- Text response without TodoWrite after /fix activation
- Recording in failed-attempts.md when the root cause is a skill defect (skill fix is 1st priority)
- **Stopping at Why 1** — fixing the symptom without asking Why 2-3 (structural cause)
- **Not cleaning up TODO/Task after completion** — must delete all fix TODOs when done
