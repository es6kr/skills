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

### 4. Dual-Sync (reflect in source) — plugin management takes priority

**Before syncing, check whether this script is already plugin-managed** — registered in a marketplace's own `hooks/hooks.json` (pointing at `${CLAUDE_PLUGIN_ROOT}/.../resources/<script>.sh`), not in `~/.claude/settings.json`:

```bash
find ~/.claude/plugins/marketplaces -iname hooks.json -exec grep -l "<script>.sh" {} \;
```

- **Plugin-managed** (a `hooks/hooks.json` references it): that plugin's own `resources/<script>.sh` is the single canonical copy. A loose `~/.claude/hooks/<script>.sh` alongside it is legacy dead weight (usually unregistered anywhere — confirm with `grep -n "<script>.sh" ~/.claude/settings.json` returning nothing). Diff it against the plugin copy to confirm nothing unique, fold in anything unique first, then **delete** the loose file — do not keep dual-maintaining it:
  ```bash
  diff ~/.claude/hooks/<script>.sh <plugin-root>/resources/<script>.sh   # confirm no unique content before deleting
  rm ~/.claude/hooks/<script>.sh
  ```
- **Not plugin-managed** (only ever registered directly in `~/.claude/settings.json`'s own `hooks` block): dual-sync both copies as before.

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

`updatedInput` is a **partial merge** into `tool_input` — only the listed keys are overwritten, everything else (prompt, other params) passes through untouched. Confirmed to work for the `Agent`/`Task` tool specifically (no restriction blocking mutation on it), per the official Claude Code hooks docs. For every other tool, treat this as a confirmed exception, not the default — see "PreToolUse `updatedInput` replaces, does not merge" below.

| # | Don't | Do |
|---|-------|-----|
| 1 | Hard-block (`exit 2`) every time a field is missing when a safe default exists | Auto-inject the default via `updatedInput` + `permissionDecision: "allow"`, exit 0 — the call proceeds corrected instead of forcing a manual retry |
| 2 | Mix a blocking gate and an auto-fix gate in one script without ordering them | If a hard-block condition and an auto-fix condition can both apply to the same call, evaluate the **block first** — an auto-fix branch that exits 0 early will skip any block check that comes after it in the script |
| 3 | Print extra log lines alongside the JSON on stdout | stdout must contain **only** the JSON object — banner/debug text breaks parsing |

## PreToolUse `updatedInput` replaces, does not merge (HARD STOP)

When a PreToolUse hook returns `hookSpecificOutput.updatedInput` to modify the tool call in place (e.g. injecting a default parameter), the harness treats that object as the **full replacement** for `tool_input`, not a merge. Returning a partial object (only the field you're adding) silently drops every other field the caller passed — the tool call then fails schema validation for those missing required fields, even on an otherwise-valid call.

**Exception**: the `Agent`/`Task` tool is confirmed to merge partially (see "Auto-fixing via `updatedInput`" above, per the official Claude Code hooks docs). Treat that as the one verified exception, not the default — for every other tool, assume full replacement until proven otherwise.

| # | Don't | Do |
|---|-------|-----|
| 1 | `updatedInput: { newField: "value" }` — constructs a new object from scratch | `updatedInput: (.tool_input + { newField: "value" })` — merge onto the original `tool_input` read from stdin |
| 2 | `jq -n '{...}'` (no input, builds output from literals only) when the output includes `updatedInput` | `echo "$INPUT" \| jq '{...}'` so `.tool_input` is available to merge from |
| 3 | Assume a hook that "worked in testing" (tested only with a full-field sample payload) generalizes to every real call shape | Test with the *minimal* valid payload for the target tool, not just a fully-populated one — the field-drop only surfaces when the caller omits the field the hook is injecting |
| 4 | Trust a 3-payload smoke test that only checks response *shape* (block / pass / inject) | Also assert that injected responses preserve every original input field, not just that `updatedInput` exists in the response |

## Shared pattern variables across hooks (HARD STOP)

When several hooks load match patterns from one shared data file, a variable defined
there **always wins over each hook's inline fallback** — including hooks whose comments
declare a narrower policy. `HG_X="${HG_X:-<strict default>}"` reads as "strict unless
overridden", but the data file *is* the override, so that strict default is dead code the
moment the data file defines `HG_X`. A hook can therefore document one policy and enforce
a completely different one.

| # | Don't | Do |
|---|-------|-----|
| 1 | Write a narrow inline default, document it as the hook's policy, and leave a shared data file defining the same variable name | Give the narrow consumer its own variable (`HG_X_STRICT`), or narrow the shared value so every consumer agrees |
| 2 | Trust a hook's comment about which patterns it matches | Resolve the variable the way the hook does — source the data file, then echo the value |
| 3 | Widen the shared variable to satisfy one consumer | Widening leaks into every other consumer. Add a variable instead |
| 4 | Match a command-shaped token (`/cleanup`) without a boundary | Anchor it (`(^\|[[:space:]])/cleanup`) — otherwise it matches inside unrelated words such as `wrap-up/cleanup` |

**Self-check (before editing any pattern variable)**:

1. `grep -rn "<VAR_NAME>" resources/ data/` — enumerate every consumer
2. Does the data file define it? If so, every consumer's inline fallback is unreachable
3. Does one consumer need a narrower set? → separate variable, never a shared widening

## Advisory hooks: inspect the edited text, not the whole file

A PostToolUse hook that re-reads its target file sees every pre-existing violation on
every edit, so the advisory fires constantly and stops being read. Inspect the payload's
edited text instead — `tool_input.new_string` (Edit), `tool_input.content` (Write),
`tool_input.edits[].new_string` (MultiEdit) — so the message covers only what this edit
introduced.

| # | Don't | Do |
|---|-------|-----|
| 1 | Read the file at `tool_input.file_path` and scan it whole | Scan the edited text from the payload. Legacy violations stay silent until touched |
| 2 | Hard-block a file that autonomous loops write frequently | Advisory only — report on stderr and let the edit stand. The write already happened |
| 3 | Let two hooks cover overlapping item states | Partition explicitly (one owns completed items, the other open items) so a single item never draws two advisories |

The same scoping trap applies when reading the **transcript**: taking only the last
assistant entry's uuid group misses a turn that emitted text and then ended on a tool
call, because those are separate entries with different uuids. Anchor on the last real
user prompt (a `user` entry whose `content` is a string — `tool_result` entries carry
`type: "user"` with an array content) and concatenate every assistant text after it.

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
| 5 | Register hooks in `~/.gemini/config/hooks.json` without checking the matcher string covers the tools actually invoked | Before registering, verify the matcher (e.g. `Edit\|Write\|replace_file_content\|write_to_file`) matches the real tool names for both runtimes — a mismatched matcher (e.g. `TaskCreate\|TaskUpdate` when the target is a file-edit tool) silently never fires |

**Precedent implementations**: `consolidate/resources/block-noncompliant-review-comment.sh`, `hook-kit/resources/block-wip-register-before-execute.py`, `hook-kit/resources/block-write-file-overwrite.sh`.

## Notes

- Do not confuse Phase 1 (block) and Phase 2 (soft_block/warn) — Phase 1 is grep patterns only, Phase 2 is bash logic
- When using `$GREP -qiP`, macOS requires `ggrep` (auto-detected at the top of the script)
- Commented-out patterns (`# echo "$COMMAND"...`) are intentional deactivations — keep as comments, do not delete
