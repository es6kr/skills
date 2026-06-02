# TDD Cycle (Red → Green → Refactor)

Core cycle and principles of Test-Driven Development.

## Trigger entry — Red authoring is the FIRST action (HARD STOP)

**Right after the tdd skill is invoked, the first tool call MUST be TaskCreate/TodoWrite registration + Red test authoring.** Diagnosis, planning, option asks, medium decisions, and implementation entry are only allowed **after** Red is authored, executed, and failure is confirmed. This is enforced before any text output.

### Don't / Do table

| # | Don't | Do |
|---|-------|-----|
| 1 | After tdd invocation, jump to "current behavior diagnosis → medium decision ask" (skipping Red authoring) | First action after tdd invocation = TaskCreate (`Red`, `Green`, `Refactor`, `Verify`) + Red test authoring + execution |
| 2 | "Root cause found = decide solution medium" thinking (Red step deprioritized) | Even after root cause is found, author + execute Red first to secure regression-prevention evidence. Medium decision is part of Green step |
| 3 | After diagnosis report, immediately AskUserQuestion "how to solve?" | Author Red + execute (confirm failure + report output) → then ask about Green medium |
| 4 | "Regression test is authored after implementation" thinking (Test-After) | TDD = Test-First. Red is mandatory before any implementation/deployment |
| 5 | Skipping Red authoring and going straight to Green under the pretext of "environment constraint blocks Red execution" | Author Red (test file in committable state) → state execution-blocked reason → plan CI/manual verification medium → Green |

### Self-check (every time, immediately before the first response after tdd invocation)

1. Was the tdd skill triggered? — Apply the same enforcement strength as fix.md "Step 0 TodoWrite (first action, no exceptions)"
2. Is the first tool call a TaskCreate (Red/Green/Refactor/Verify 4 stages) or Red test file Edit/Write? — Only Yes passes
3. Was the first action diagnosis/analysis/medium ask? → Violation. Stop immediately and return to Red authoring
4. After Red authoring, did execution happen (or was the inability to execute stated)? → Forbid Green medium ask before reporting execution result

### Entry pattern (correct)

```text
tdd invoked
  ↓ (first tool call)
TaskCreate: Red authoring (in_progress), Green (pending), Refactor (pending), Verify (pending)
  ↓
Red test file Edit/Write (state expected behavior — natural failure)
  ↓
Run tests (npm test / pytest / playwright) — confirm failure
  ↓ (only after failure evidence is captured)
AskUserQuestion: Green medium decision (implementation direction)
  ↓ (user decision)
Green implementation
  ↓
Re-run tests — confirm pass
  ↓
Refactor + Verify + commit
```

In this flow, **skipping the Red authoring + execution step is a violation**. The "Red can be added later" mindset itself is a Test-After anti-pattern.

### Exceptions (Red authored but cannot be executed)

- Test environment not ready (CI-only execution, local env differences, etc.) — commit Red authoring + tag commit message with `[CI-VERIFY]` + mark Green as incomplete until the CI result is confirmed
- The test infrastructure itself is the work being done (E2E env absent) — build infrastructure + author Red together (do not skip Red)

## Core: Define Expected Behavior First

```
1. Define expected behavior as a test — naturally fails because there is no implementation (Red)
2. Write the minimum code to make the test pass (Green)
   → Green pass criterion: run the test written in Red and confirm PASS. Do not substitute with curl/manual verification.
   → If the test cannot be run locally (environment constraint): delegate to CI, mark the commit message with "[CI-VERIFY]", and treat Green as incomplete until the result is confirmed.
3. Refactor (Refactor)
4. Verify existing tests are not broken
```

**Prohibited:** Creating tests that are forced to fail. Tests must have correct expected values and fail due to the absence of implementation, not because the test itself is wrong.

## Prerequisites Before Writing Tests

1. **Read the exact production code** — don't guess, check the source
2. **Use actual functions** — call production code functions, not hardcoded values
3. **Explore existing tests first** — identify already-covered cases in related `*.test.*`, `*.spec.*` files
4. **No duplicate tests** — if the same logic is already tested in another file, extend that test

## Bug-Fix TDD

**Don't argue or re-explain. Write a test immediately.**

```
1. Define the behavior the user expects as a test
2. Run the test → confirm failure (naturally fails because the bug exists)
3. Fix the implementation (minimum fix to make the test pass)
4. Run the test → confirm it passes
```

If the test passes immediately → the test didn't catch the bug. Fix the test.

## Platform-Specific Tests

```typescript
// Use OS native APIs — no hardcoding
const homeDir = os.homedir()        // NOT 'C:\Users\test'
const filePath = path.join(a, b)    // NOT manual string concatenation
```

- Use `path.join()`, `os.homedir()`, `path.sep`
- Don't skip with `skipIf` — tests should run and fail on the target platform

## Test Data Rules

- No personal/real paths (`/Users/es6kr/...` → `/home/user/projects/work`)
- Use actual functions over mocks (`folderNameToPath(name)` > `'~/projects/work'`)

## Commit Rules

**Red→Green→Refactor is ONE atomic unit. Do not commit or push between stages.**

- Red only (test written, no implementation) → **commit forbidden**
- Red + Green (test passes) → commit allowed
- Red + Green + Refactor → ideal commit point

If the test cannot run locally (environment constraint), the Green stage must still be attempted before committing. "Can't run locally" is not grounds for skipping Green — find an alternative (different test runner, mock, CI-only verification plan documented in commit message).

### TodoWrite/TaskCreate for TDD tracking

At the start of TDD, register each stage in TodoWrite or TaskCreate to track progress:

```
TaskCreate([
  { subject: "🔴 Red: <test description>", status: "in_progress" },
  { subject: "🟢 Green: <implementation description>", status: "pending" },
  { subject: "🔵 Refactor", status: "pending" },
  { subject: "✅ Verify + commit", status: "pending" },
])
```

- Red complete → switch to Green. **Do not switch to commit/push during Red.**
- Green complete → switch to Refactor.
- Refactor complete → at Verify + commit, run the tests, confirm, then commit.
- Commit is only allowed once every stage is completed.

## Anti-Patterns

| Anti-Pattern | Correct Approach |
|---------|-----------|
| Hardcoded platform values | Use `os.homedir()`, `path.sep` |
| Skipping platforms with `skipIf` | Run tests, fail on target platform |
| Testing with logic different from production | Replicate exact production code logic |
| Writing tests by guessing without reading source code | Verify exact lines with `grep -n`, etc. |
| Creating tests forced to fail | Define expected behavior → natural failure due to missing implementation |
| Committing after Red only (no Green) | Complete Red→Green→Refactor before commit |

## Checklist

- [ ] Did you read the production code accurately?
- [ ] Are you using actual functions? (not hardcoded)
- [ ] Does it not duplicate existing tests?
- [ ] Are you using OS native APIs?
- [ ] Is there no personal information in test data?
