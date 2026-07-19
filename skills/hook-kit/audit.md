# Audit

Check hook scripts for references to non-existent skills, scripts, and agents.

## When to Use

- After hook cleanup, to check for stale references
- After deleting or renaming a skill/agent
- For periodic hook health checks

## Instructions

### 1. Validate script paths in settings.json + settings.local.json

**Inspection targets (include all)**:
- `~/.claude/settings.json` (global)
- `<cwd>/.claude/settings.local.json` (project/workspace-specific, if present)
- `.claude/settings.local.json` in parent directories of cwd (also check workspace if cwd is a sub-project)

```bash
# Extract from both global + local
for f in ~/.claude/settings.json $(find . -maxdepth 4 -name "settings.local.json" -path "*/.claude/*" 2>/dev/null); do
  echo "=== $f ==="
  jq -r '.. | objects | select(.command) | .command' "$f" 2>/dev/null
done
```

For each path, perform the following 4-step validation:

| # | Check | Action |
|---|-------|--------|
| 1 | Is the path a cwd-relative path? (e.g., `.claude/hooks/...`, `./scripts/...`, first char is not `/`/`~`/`$`) | **STALE-RELATIVE** — breaks when cwd changes. Suggest converting to `~/.claude/hooks/...` or `$CLAUDE_PROJECT_DIR/...` |
| 2 | Starts with `~` → substitute `$HOME` then `test -f` | Absent → **MISSING** |
| 3 | Starts with `$CLAUDE_PROJECT_DIR` → substitute based on workspace where settings.local.json lives, then `test -f` | Absent → **MISSING** |
| 4 | Absolute path (`/...`) → `test -f` as-is | Absent → **MISSING** |

**Relative path auto-detection pattern**:
```bash
# If first token is bash/sh, the second token is the script path
script_path=$(echo "$command" | awk '{print $2}')
case "$script_path" in
  /*|~*|\$*) ;;  # OK (absolute/home/env-var)
  *) echo "STALE-RELATIVE: $script_path" ;;  # cwd-dependent
esac
```

### 2. Validate references inside hook scripts

Search all `.sh` files in `~/.claude/hooks/` for the following patterns:

**Skill references**:
```
skill: 'skill-name'
skill="skill-name"
skill: "org:skill-name"
```
→ Verify `~/.claude/skills/skill-name/SKILL.md` or `~/.claude/commands/skill-name.md` exists

**Script references**:
```
~/.claude/scripts/xxx.sh
~/.claude/hooks/xxx.sh
$SCRIPT_DIR/xxx.sh
```
→ Verify actual file exists (`$SCRIPT_DIR` is interpreted as the script's dirname)

**Agent references**:
```
subagent_type='agent-name'
subagent_type="agent-name"
```
→ Verify `~/.claude/agents/agent-name.md` exists

### 3. Validate dispatcher internal references

Integrated scripts like `bash-guard.sh` may call sub-scripts via `$SCRIPT_DIR/`.
Verify that referenced sub-scripts also exist in the same directory.

### 3-A. Executable bit check (chmod +x)

Check executable bit on all `~/.claude/hooks/*.sh`. Without `+x`, even a correctly registered hook produces `/bin/sh: ...: Permission denied` (exit 126) on every SessionStart/PreToolUse/PostToolUse call — effectively dead.

```bash
for f in ~/.claude/hooks/*.sh; do
  if [ ! -x "$f" ]; then
    echo "STALE-PERM: $f"
  fi
done
```

| Result | Action |
|--------|--------|
| `+x` present | OK |
| `+x` missing | **STALE-PERM** — auto-suggest `chmod +x <file>` (AskUserQuestion) |

**Violation case**: `~/.claude/hooks/session-id-inject.sh` registered with mode 644, causing exit 126 on every SessionStart. ralph stream log accumulated `Permission denied`. install.md Step 3 performs `chmod +x`, but when files are copied externally or file mode is lost during dual-sync, audit must catch it.

### 3-B. Orphan hook check (no resources source + not in settings)

Validates the "every hook must have an owning skill" policy from `automation.md`. For each `~/.claude/hooks/*.sh`:

| Condition | Classification |
|-----------|----------------|
| No source in any skill's `resources/` + not in settings.json/local.json | **ORPHAN** — unused. Decide to delete or import |
| No resources/ source + registered in settings | **UNMANAGED** — owning skill needs to be determined (recommend importing to hook skill as default installer) |
| resources/ source exists + not registered in settings | **UNREGISTERED** — register via `/hook install` procedure |

```bash
# Skill hook source list — scan both resources/ and scripts/ (sources may be in either;
#   e.g., claude-session/scripts/session-id-inject.sh). macOS-compatible: use sed for basename instead of GNU -printf.
SOURCES=$(find ~/.claude/skills ~/.agents/skills \
  \( -path "*/resources/*.sh" -o -path "*/scripts/*.sh" \) -type f 2>/dev/null \
  | sed 's#.*/##' | sort -u)

# Registered hook basenames from settings.json/local.json — extract *.sh filenames from command strings.
#   (awk '{print $2}' would miss basenames in forms like 'bash ~/x.sh' / '~/.claude/hooks/x.sh')
REGISTERED=$(for f in ~/.claude/settings.json $(find . -maxdepth 4 -name "settings.local.json" -path "*/.claude/*" 2>/dev/null); do
  jq -r '.. | objects | select(.command) | .command' "$f" 2>/dev/null
done | grep -oE '[^ /]+\.sh' | sort -u)

# Classify each ~/.claude/hooks/*.sh — using string + grep -qx (bash 3.2 / zsh compatible instead of mapfile)
for f in ~/.claude/hooks/*.sh; do
  name=$(basename "$f")
  printf '%s\n' "$SOURCES"    | grep -qx "$name" && has_source=1 || has_source=0
  printf '%s\n' "$REGISTERED" | grep -qx "$name" && has_reg=1    || has_reg=0
  if   [ "$has_source" = 0 ] && [ "$has_reg" = 0 ]; then echo "ORPHAN: $name"
  elif [ "$has_source" = 0 ] && [ "$has_reg" = 1 ]; then echo "UNMANAGED: $name"
  elif [ "$has_source" = 1 ] && [ "$has_reg" = 0 ]; then echo "UNREGISTERED: $name"
  fi
done
```

> **macOS/zsh compatibility note**: `mapfile` (bash 4+), `find -printf` (GNU), and `awk '{print $2}'` for basename extraction all fail or produce false positives in macOS default environments (bash 3.2 / BSD find / zsh). The form above (`sed 's#.*/##'` + `grep -oE '[^ /]+\.sh'` + string grep) is cross-platform safe.

**Suggested actions** (AskUserQuestion):

- ORPHAN → (1) mv to `~/.claude/.bak/` (2) keep
- UNMANAGED → (1) import to hook skill resources/ via `/hook install` import procedure (2) mv to domain skill resources/ (3) keep
- UNREGISTERED → register in settings.json via `/hook install`

### 4. Report output

```
=== Hook Audit Report ===

settings.json path validation:
  OK  ~/.claude/hooks/build-confirm.sh
  OK  ~/.claude/hooks/staged-protect.sh
  MISSING  ~/.claude/scripts/old-script.sh  ← file not found

Hook script internal references:
  OK  next-action-trigger.sh → Task(next-action-suggester)
  STALE  old-hook.sh → skill: 'project-automation:next-action'  ← skill not found
  STALE  dispatcher.sh → $SCRIPT_DIR/removed-guard.sh  ← file not found

Executable bit (chmod +x):
  OK  bash-guard.sh
  STALE-PERM  session-id-inject.sh  ← +x missing, exit 126 will occur

Installed file classification (resources / settings mapping):
  ORPHAN       legacy-hook.sh        ← not registered anywhere
  UNMANAGED    user-custom.sh        ← in settings only, no source
  UNREGISTERED experiment.sh         ← has resources source but not in settings

Total: OK 15 / STALE 2 / MISSING 1 / STALE-PERM 1 / ORPHAN 1 / UNMANAGED 1 / UNREGISTERED 1
```

### 5. Fix suggestions

For STALE/MISSING/STALE-PERM/ORPHAN/UNMANAGED/UNREGISTERED items, use AskUserQuestion(multiSelect:true) to choose action:
- **fix**: update to the correct reference
- **chmod +x**: grant executable bit to STALE-PERM items (`chmod +x <file>`)
- **import**: UNMANAGED → mv to owning skill resources/ via `/hook install` import procedure
- **register**: UNREGISTERED → register in settings.json via `/hook install`
- **archive**: ORPHAN → move to `~/.claude/.bak/` (`/safe-delete` or `/archive`)
- **remove**: remove the hook entry (`/hook remove` guidance)
- **skip**: skip for now
