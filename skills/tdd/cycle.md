# TDD Cycle (Red → Green → Refactor)

Core cycle and principles of Test-Driven Development.

## Core: Define Expected Behavior First

```
1. Define expected behavior as a test — naturally fails because there is no implementation (Red)
2. Write the minimum code to make the test pass (Green)
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

## Anti-Patterns

| Anti-Pattern | Correct Approach |
|---------|-----------|
| Hardcoded platform values | Use `os.homedir()`, `path.sep` |
| Skipping platforms with `skipIf` | Run tests, fail on target platform |
| Testing with logic different from production | Replicate exact production code logic |
| Writing tests by guessing without reading source code | Verify exact lines with `grep -n`, etc. |
| Creating tests forced to fail | Define expected behavior → natural failure due to missing implementation |

## Checklist

- [ ] Did you read the production code accurately?
- [ ] Are you using actual functions? (not hardcoded)
- [ ] Does it not duplicate existing tests?
- [ ] Are you using OS native APIs?
- [ ] Is there no personal information in test data?
