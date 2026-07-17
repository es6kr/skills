# Install

Install hook scripts from skill resources (source) to `~/.claude/hooks/` and register in settings.json.

## When to Use

- When installing a new hook script for the first time
- When syncing the installed copy in hooks/ with the source in skill resources
- Use when: "hook install", "install hook", "add hook", "hook sync"

## Registration Patterns (Direct Registration preferred)

**New hooks default to direct registration in resources/.** A single-file structure where the settings.json `command` points directly to the resources path. No cp/sync step needed.

```jsonc
{
  "type": "command",
  "command": "bash ~/.agents/skills/hook/resources/<script>.sh"
}
```

| Pattern | Setup | When to use |
|---------|-------|-------------|
| **Direct registration** (resources path in settings) | settings.json command = resources path | New hook · resources in user-managed area (`~/.agents/skills/`) |
| **Dual-Sync** (cp → ~/.claude/hooks/) | source = resources/, installed = ~/.claude/hooks/, settings.json command = ~/.claude/hooks/ | resources is a marketplace cache path with auto-update risk / direct Edit-to-production is undesirable / security guard requiring isolation |

### Plugin Bundle Decision (determine owning skill first)

Before deciding the owning skill (where resources/ lives), assess whether a plugin bundle is needed:

1. **Identify the invoked skill** — which skill does this hook call/enforce? Judge by **content** (what command/pattern does the hook check?), never by where the file currently sits. A hook file discovered already staged/created inside `hook-kit/resources/` (or any other skill's `resources/`) is not evidence that skill owns it — a `pm2 start`/`pm2 resurrect` guard belongs to `pm2`, a `semaphore` task guard belongs to `semaphore`, regardless of which directory it was first written into. If content-owner ≠ current directory, `mv` it to the owning skill's `resources/` before registering (same as the ORPHAN case below).
2. **Assess coupling scope** — do that skill + its `depends-on` skills form a single deployable unit? (e.g., ask-user plugin's guards/question/secrets + enforcement hook bundle)

| Decision | Branch |
|----------|--------|
| **Plugin creation appropriate** (skill group + hook form a deployment unit) | **Draft a creation plan** — record stub only via `/fix-plan draft` (purpose + hold reason + resume trigger + expected artifacts) → proceed to plugin creation when ready. Do not create immediately |
| **Not appropriate** (single skill + hook) | Proceed with registration below → that skill owns the hook in its `resources/` |

- Even if a plugin bundle is appropriate, **do not create it immediately** — record a stub via `/fix-plan draft` and proceed through the plan phase (research → plan → implement)
- The not-appropriate branch follows the same orphan hook prohibition policy (`automation.md` "Hook owning skill policy") — hook source must live in the owning skill's `resources/`

### New hook registration procedure (Direct pattern)

1. Write in resources/ → `chmod +x`
2. Register `bash ~/.agents/skills/<owner>/resources/<script>.sh` in settings.json
3. Done — no cp step

### Convert existing Dual-Sync hook to Direct

**Use `mv` not `cp` when converting**. mv automatically moves `~/.claude/hooks/<x>.sh` to the source location (orphan → resources import) or prompts user decision on conflict. cp followed by separate delete is forbidden (`common.md` "move is mv, copy is cp" rule).

| Case | Command |
|------|---------|
| **SAME** (source exists + content identical) | `rm ~/.claude/hooks/<x>.sh` (mv = same result as overwriting source) + update settings.json command path |
| **DIFF** (source exists + content differs) | **Call the `diff-merge` skill** to compare and integrate both sides → apply result to both source/installed → handle as SAME. Do not simply trust one side (content loss risk) |
| **ORPHAN** (no source) | `mv ~/.claude/hooks/<x>.sh ~/.agents/skills/<owner>/resources/<x>.sh` — after determining owning skill |

### New hook Dual-Sync choice (exceptions only)

Dual-Sync is maintained only for:
- resources is a marketplace cache path (`~/.claude/plugins/marketplaces/<m>/.../resources/`) — risk of cache overwrite
- Security guard hook + isolation required (direct Edit-to-production is a concern)
- Explicit user instruction

Everything else uses the Direct pattern.

## Instructions

### 1. Check source

```bash
ls ~/.claude/skills/hook/resources/*.sh
```

Verify that the target script to install exists in the resources directory.

### 2. Diff comparison

If an installed copy already exists, compare with the source:

```bash
diff ~/.claude/skills/hook/resources/bash-guard.sh ~/.claude/hooks/bash-guard.sh
```

- No difference → already in sync, skip
- Difference → AskUserQuestion to choose direction:
  - **source → installed** (overwrite with resources as reference)
  - **installed → source** (reflect hooks/ modifications back to resources)
  - **skip** (skip for now)

### 3. Install (copy)

#### 3-0. Source executable permission pre-check (HARD STOP)

**`cp` copies the mode of the source.** If the source comes in as `-rw-r--r--`, the installed copy is also 644, and forgetting the `chmod +x ~/.claude/hooks/<script>.sh` line in Step 3-1 means every hook call fails with `/bin/sh: <path>: Permission denied`. Moreover, the next sync will cp from the source again, reproducing the same defect.

**The source (`resources/<script>.sh`) must always be kept `chmod +x`.**

| # | Don't | Do (correct alternative) |
|---|-------|--------------------------|
| 1 | Leave source as `-rw-r--r--` and apply `chmod +x` only to installed copy | Apply `chmod +x` to both source + installed. Source is the SoT, so source permissions must be correct |
| 2 | Finish with just `cp` + one `chmod +x` on installed (source unchanged) | Step 3-0: `chmod +x` source first → Step 3-1: cp + `chmod +x` installed |
| 3 | Assert "no problem as long as installed is executable" | Next sync will cp source's 644 back to installed → recurrence. Source permission is the root cause |
| 4 | Judge sync state by diff only (Step 2) | `diff` checks content only. Permission mismatch requires separate `stat`/`ls -la` comparison |

```bash
chmod +x ~/.claude/skills/hook/resources/<script>.sh
test -x ~/.claude/skills/hook/resources/<script>.sh || { echo "FAIL: source not executable"; exit 1; }
```

#### 3-1. cp + installed chmod

```bash
cp ~/.claude/skills/hook/resources/<script>.sh ~/.claude/hooks/<script>.sh
chmod +x ~/.claude/hooks/<script>.sh
```

### 4. Register in settings.json

Register the installed script in the settings.json hooks section:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "bash ~/.claude/hooks/bash-guard.sh" }
        ]
      }
    ]
  }
}
```

- If already registered, skip
- Determine matcher and event type from script naming convention:
  - `bash-*` → PreToolUse, matcher: "Bash"
  - `trigger-PostToolUse*` → PostToolUse, matcher: "Bash"
  - `session-*` → SessionStart / UserPromptSubmit
  - `trigger-Stop*` → Stop

#### Path format (HARD STOP — no cwd-relative paths)

**Claude Code runs hooks from the current cwd.** Using a cwd-relative path in the registered command causes `bash: <path>: No such file or directory` on every hook call whenever cwd changes to a project/sub-dir.

| # | Don't | Do (correct alternative) |
|---|-------|--------------------------|
| 1 | `"command": "bash .claude/hooks/x.sh"` (cwd-relative) | `"command": "bash ~/.claude/hooks/x.sh"` (global) or `"command": "bash $CLAUDE_PROJECT_DIR/.claude/hooks/x.sh"` (project-specific) |
| 2 | `"command": "./scripts/hook.sh"` | `"command": "$CLAUDE_PROJECT_DIR/scripts/hook.sh"` |
| 3 | `"command": "hook.sh"` (PATH-dependent) | Specify absolute path |

**Scope**: `~/.claude/settings.json` (global) + all `<workspace_or_project>/.claude/settings.local.json` (project-specific).

**Workspace vs project-specific hook choice**:
- Always active across all projects → `~/.claude/hooks/` + `~/.claude/settings.json`
- Workspace/project-specific → `<workspace>/.claude/hooks/` + `<workspace>/.claude/settings.local.json`. Command must use `$CLAUDE_PROJECT_DIR/.claude/hooks/...` format

**Violation case**: `~/ghq/github.com/<org>/.claude/settings.local.json` registered with `"command": "bash .claude/hooks/block-compound-commands.sh"`. Hook fails with "No such file or directory" on every Bash call when cwd changes to a sub-project (e.g. `<repo>/`). User reported "hook skill improvement and fix" → install.md got HARD STOP path format rule + audit.md got settings.local.json + relative-path auto-detection.

### 5. Verify

```bash
# settings.json validity
jq . ~/.claude/settings.json > /dev/null

# Executable permission on both source + installed
test -x ~/.claude/skills/hook/resources/<script>.sh || { echo "FAIL: source not +x"; exit 1; }
test -x ~/.claude/hooks/<script>.sh                 || { echo "FAIL: installed not +x"; exit 1; }
```

- Ending with missing source permission causes the same defect on next sync (see Step 3-0)
- The `audit.md` chmod +x detection check also inspects both source/installed

## Import External Script (external hook script → resources)

Use this when importing hook scripts found in a workspace/project `.claude/hooks/` or arbitrary location into the standard hook skill management flow.

### 1. Identify import targets

Search for hook scripts scattered in workspaces/projects:

```bash
find ~/ghq -path "*/.claude/hooks/*.sh" -type f 2>/dev/null
```

Use AskUserQuestion to ask about each script's usage scope (global vs workspace-specific):
- **Apply to all projects** → global import (resources/ → ~/.claude/hooks/) recommended
- **Specific workspace only** → keep in that workspace's hooks/ + register with `$CLAUDE_PROJECT_DIR/...` path in settings.local.json

### 2. mv to resources/

When global import is decided (mv not cp — no duplicate in workspace):

```bash
mv <external_path>/hook-name.sh ~/.claude/skills/hook/resources/hook-name.sh
```

### 3. Apply install procedure

Apply this document's Step 3 (cp resources → ~/.claude/hooks/) + Step 4 (settings.json registration) + Step 5 (verification) in order.

### 4. Clean up workspace settings.local.json

If the imported hook was registered in workspace settings.local.json, remove it (prevent duplication since it moved to global ~/.claude/settings.json):

```bash
# Remove hook entry from settings.local.json
jq 'del(.hooks)' <workspace>/.claude/settings.local.json
```

### 5. Clean up empty workspace hooks/ directory

```bash
ls -A <workspace>/.claude/hooks/   # check if empty
rmdir <workspace>/.claude/hooks/   # remove if empty (or use /rmdirs skill)
```

### Example

`~/ghq/github.com/<org>/.claude/hooks/block-compound-commands.sh` was registered workspace-only, causing hook failures when cwd changed to a sub-project. Since global scope was intended:

1. `mv ~/ghq/github.com/<org>/.claude/hooks/block-compound-commands.sh ~/.claude/skills/hook/resources/`
2. `cp ~/.claude/skills/hook/resources/block-compound-commands.sh ~/.claude/hooks/`
3. `chmod +x ~/.claude/hooks/block-compound-commands.sh`
4. Add entry to `~/.claude/settings.json` PreToolUse:Bash matcher
5. Delete hooks block from workspace `settings.local.json` + clean up empty hooks directory

## Sync All (bulk sync)

Sync all resources at once — check both content diff and permission mismatch simultaneously:

```bash
for src in ~/.claude/skills/hook/resources/*.sh; do
  name=$(basename "$src")
  dest=~/.claude/hooks/"$name"

  # Source permission self-check (SoT must be +x)
  [ -x "$src" ] || echo "PERM_SRC: $name (source not +x)"

  if [ -f "$dest" ]; then
    diff -q "$src" "$dest" >/dev/null || echo "DIFF: $name"
    [ -x "$dest" ] || echo "PERM_DEST: $name (installed not +x)"
  else
    echo "NEW: $name"
  fi
done
```

- `DIFF:` → content mismatch (AskUserQuestion to choose direction)
- `PERM_SRC:` / `PERM_DEST:` → apply `chmod +x` (both sides)
- `NEW:` → installed copy missing. Proceed with Step 3-0 + Step 3-1 + Step 4

Use AskUserQuestion(multiSelect) to batch-process DIFF/NEW/PERM items.
