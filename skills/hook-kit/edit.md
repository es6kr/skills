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

## Cross-platform (Claude Code + Antigravity) dual I/O

A hook meant to run in **both** Claude Code and Antigravity needs to detect which runtime invoked it and speak that runtime's I/O contract — the two use different payload shapes and different blocking mechanisms, and a script written for one silently never fires on the other's real payload.

| | Claude Code | Antigravity |
|---|---|---|
| stdin shape | `{tool_name, tool_input, transcript_path}` | `{toolCall: {name, args}}` |
| block mechanism | stderr message + `exit 2` | stdout `{"decision":"deny","reason":...}` + `exit 0` |
| allow mechanism | `exit 0` (no stdout) | `exit 0` (no stdout, or omit the `decision` key) |
| registration | `~/.claude/settings.json` | `~/.gemini/config/hooks.json` |

**Detection**: branch on which runtime-specific field is present, not on an env var or file check — `tool_name` (Claude) vs `toolCall.name` (Antigravity) are mutually exclusive in the real payload.

```bash
CLAUDE_TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
AG_TOOL=$(echo "$INPUT" | jq -r '.toolCall.name // empty')

if [[ -n "$AG_TOOL" ]]; then
  # Antigravity branch — block via stdout JSON, exit 0
  [[ "$AG_TOOL" == "<target-tool>" ]] || exit 0
  # ...condition check on toolCall.args...
  echo '{"decision":"deny","reason":"<message>"}'
  exit 0
elif [[ -n "$CLAUDE_TOOL" ]]; then
  # Claude Code branch — block via stderr, exit 2
  [[ "$CLAUDE_TOOL" == "<target-tool>" ]] || exit 0
  # ...condition check on tool_input...
  echo "<message>" >&2
  exit 2
fi
exit 0
```

The same shape applies in Python (`payload.get("tool_name")` vs `payload.get("toolCall", {}).get("name")`) — see `block-wip-register-before-execute.py` for a full worked example, including a `deny_antigravity()` helper that wraps the stdout-JSON branch.

| # | Don't | Do |
|---|-------|-----|
| 1 | Write a hook against only `tool_name`/`tool_input` and register it in `~/.gemini/config/hooks.json` too, assuming the Claude Code shape "should" also work there | Antigravity never populates `tool_name` — a Claude-only hook registered there silently never fires. Add the `toolCall.name`/`toolCall.args` branch before dual-registering |
| 2 | Block on `stderr` + `exit 2` in the Antigravity branch (copy-pasting the Claude Code block path) | Antigravity does not read stderr/exit-code as a block signal — it reads stdout `{"decision":"deny"}` with `exit 0`. Wrong branch = silent allow, not a loud failure |
| 3 | Guess Antigravity arg key names (`TargetFile` vs `path` vs `file_path`) without flagging the guess | Antigravity's exact key casing is often unconfirmed until live-verified in a real session — try multiple candidate keys and document the guess as an explicit unverified note rather than presenting it as confirmed |
| 4 | Register the dual-I/O script in only one runtime's config file | Register in **both** `~/.claude/settings.json` and `~/.gemini/config/hooks.json` — that's the entire point of writing the dual branch |

**Precedent implementations**: `consolidate/resources/block-noncompliant-review-comment.sh`, `wip/resources/block-wip-register-before-execute.py`, `hook-kit/resources/block-write-file-overwrite.sh`.

## Notes

- Do not confuse Phase 1 (block) and Phase 2 (soft_block/warn) — Phase 1 is grep patterns only, Phase 2 is bash logic
- When using `$GREP -qiP`, macOS requires `ggrep` (auto-detected at the top of the script)
- Commented-out patterns (`# echo "$COMMAND"...`) are intentional deactivations — keep as comments, do not delete
