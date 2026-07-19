# Hook Error Review (Step 1)

Detect hook execution errors and non-firing hooks during the session, and suggest improvements.

## Trigger

- Auto-run as Step 1 (right after retrospect) during `/cleanup run`
- Direct call via `/cleanup hook-review`

## Procedure

### 1. Detect hook errors during the session

Scan the entire conversation for the following signals:

| Signal | Example |
|------|------|
| Hook script exit code != 0 | `hook error`, `non-zero exit` |
| Error message in hook output | `command not found`, `No such file`, `Permission denied` |
| Hook should have fired but did not | Matcher pattern mismatch, script path error |
| Hook fired unintentionally | Matcher too broad, firing in unwanted situations |
| Hook output was excessively long | Verbose output that wastes conversation context |

### 1.5. Non-firing hook analysis

Cross-reference the tools used in the session with the matchers of registered hooks to detect **hooks that should have fired but didn't**.

**Analysis procedure**:
1. Extract every hook's `event` + `matcher` combination from settings.json
2. Collect the list of tools actually used in the session conversation (Bash, Edit, Write, Read, etc.)
3. Identify cases where a matcher matches a used tool but no hook output appeared

**Non-firing cause classification**:

| Cause | Diagnosis method |
|------|----------|
| Matcher pattern mismatch | Compare the registered pattern with the actual tool call (e.g., `Bash(git:*)` vs `Bash(git *)`) |
| Script path error | `test -f <path>` + `test -x <path>` |
| Silent script exit | Exit 0 but nothing printed due to a conditional branch (may be intentional) |
| Event type mismatch | PreToolUse vs PostToolUse confusion |

**Distinguishing intentional silence from errors**:
- If the script has an internal conditional branch (`if`/`case`) and exits silently when the condition is not met → **normal** (no report needed)
- If the matcher matched but the script did not execute at all → **error** (should be reported)

### 2. settings.json hook status check

```bash
# Extract all hook command paths from settings.json and verify existence
```

For each hook:
- **Script existence**: whether the file at the path actually exists
- **Execute permission**: whether `chmod +x` was applied
- **Matcher validity**: whether the matched tool is actually used

### 3. `/hook audit` integration

Also include the checks from the existing `hook audit` skill:
- settings.json path validation (MISSING files)
- Stale references inside hook scripts (deleted skills/agents)
- Existence of dispatcher subscripts

### 4. Result output

```
## Hook Error Review

### Errors during the session
- **[hook name]**: [error content] → suggestion: [fix]

### Status check
- OK: N / errors: N / warnings: N

### Improvement suggestions
1. **[item]**: [current problem] → [improvement]
```

### 5. Handling (by mode)

**User session**: AskUserQuestion (multiSelect: true)
- Options: each improvement suggestion + "skip"
- Execute the fix only for approved items

**Ralph mode**: record to `.ralph/improvements.md`
- Record each error/improvement suggestion with a `[NEEDS_REVIEW]` tag
- Do not directly modify hook scripts

## Skip Conditions

- Skip if there were no hook-related errors in the session, no suspected non-firing hooks, and no changes to settings.json
