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

## Notes

- Do not confuse Phase 1 (block) and Phase 2 (soft_block/warn) — Phase 1 is grep patterns only, Phase 2 is bash logic
- When using `$GREP -qiP`, macOS requires `ggrep` (auto-detected at the top of the script)
- Commented-out patterns (`# echo "$COMMAND"...`) are intentional deactivations — keep as comments, do not delete
