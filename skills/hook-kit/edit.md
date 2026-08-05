# Edit

Modify hook script content and sync with the source resource.

## When to Use

- When adding new patterns/checks to a hook script
- When modifying or removing existing block rules
- Use when: "hook edit", "edit hook", "edit guard", "modify bash-guard", "add block"

## Instructions

### 1. Identify the target

```bash
# Currently registered hook list
jq -r '.hooks | to_entries[] | .key as $event | .value[] | .hooks[]? | "\($event): \(.command)"' ~/.claude/settings.json
```

Open the target script with Read to inspect its current content.

### 2. Make the edit

Use the Edit tool to directly modify `~/.claude/hooks/<script>.sh`.

**Rules when modifying bash-guard.sh:**

| Block level | Function | Location | Exit code |
|-------------|----------|----------|-----------|
| Hard block (unconditional) | `block()` | Phase 1 | 2 |
| Soft block (conditional) | `soft_block()` | Phase 2 | 1 |
| Warn only (no block) | `warn()` | Phase 2 | 0 |

**Phase 1 pattern addition example:**
```bash
echo "$COMMAND" | $GREP -qiP 'pattern' && block "description"
```

**Phase 2 check addition example:**
```bash
if [[ "$COMMAND" =~ pattern ]]; then
  soft_block "description"
fi
```

### 3. Test

Quick dry-run after modification:

```bash
echo '{"tool_input":{"command":"git reset --hard"}}' | bash ~/.claude/hooks/bash-guard.sh
echo $?  # 2 = blocked
```

```bash
echo '{"tool_input":{"command":"ls -la"}}' | bash ~/.claude/hooks/bash-guard.sh
echo $?  # 0 = allowed
```

### 4. Dual-Sync (reflect in source)

If the modification was made in hooks/, reverse-sync to resources:

```bash
cp ~/.claude/hooks/<script>.sh ~/.claude/skills/hook/resources/<script>.sh
```

If the modification was made in resources/, sync to hooks/:

```bash
cp ~/.claude/skills/hook/resources/<script>.sh ~/.claude/hooks/<script>.sh
```

**Whichever side was modified, the other side must be updated** — verify with diff before copying.

### 5. Verify

```bash
# JSON validity (if settings.json was modified)
jq . ~/.claude/settings.json > /dev/null

# Script syntax
bash -n ~/.claude/hooks/<script>.sh
```

## Auto-fixing via `updatedInput` instead of hard-blocking

A PreToolUse hook is not limited to allow/deny — it can also **rewrite the tool call before it executes**, so a missing/wrong field gets silently corrected instead of forcing a retry. Print JSON to stdout and exit 0 (JSON is only parsed on exit code 0; any extra text on stdout breaks parsing):

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "<why this field was auto-filled>",
    "updatedInput": { "<field>": "<corrected-value>" }
  }
}
```

`updatedInput` is a **partial merge** into `tool_input` — only the listed keys are overwritten, everything else (prompt, other params) passes through untouched. Confirmed to work for the `Agent`/`Task` tool specifically (no restriction blocking mutation on it), per the official Claude Code hooks docs.

| # | Don't | Do |
|---|-------|-----|
| 1 | Hard-block (`exit 2`) every time a field is missing when a safe default exists | Auto-inject the default via `updatedInput` + `permissionDecision: "allow"`, exit 0 — the call proceeds corrected instead of forcing a manual retry |
| 2 | Mix a blocking gate and an auto-fix gate in one script without ordering them | If a hard-block condition and an auto-fix condition can both apply to the same call, evaluate the **block first** — an auto-fix branch that exits 0 early will skip any block check that comes after it in the script |
| 3 | Print extra log lines alongside the JSON on stdout | stdout must contain **only** the JSON object — banner/debug text breaks parsing |

## Notes

- Do not confuse Phase 1 (block) and Phase 2 (soft_block/warn) — Phase 1 is grep patterns only, Phase 2 is bash logic
- When using `$GREP -qiP`, macOS requires `ggrep` (auto-detected at the top of the script)
- Commented-out patterns (`# echo "$COMMAND"...`) are intentional deactivations — keep as comments, do not delete
