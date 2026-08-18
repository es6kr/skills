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

#### 3-A.1 Extend the check to every settings.json-referenced path, not just the fixed hooks directory

A hook's script does not always live under `~/.claude/hooks/` — many are registered directly from a skill's `resources/` directory (`~/.claude/skills/<name>/resources/*.sh`, `~/.agents/skills/<name>/resources/*.sh`, or a marketplace worktree path). Step 1 already resolves and existence-checks every one of these paths. Step 3-A's chmod loop must scan the **same path set Step 1 produced**, not a separate hardcoded glob — otherwise a hook that lives outside `~/.claude/hooks/` can pass Step 1 (file exists) while still being non-executable, and nothing catches it.

```bash
# Reuse Step 1's extracted command list — do not re-glob a fixed directory
for f in $(jq -r '.. | objects | select(.command) | .command' ~/.claude/settings.json 2>/dev/null \
  | awk '{print $NF}' | sed "s|^~|$HOME|"); do
  [ -f "$f" ] || continue   # existence already covered by Step 1 — skip non-matches here
  if [ ! -x "$f" ]; then
    echo "STALE-PERM: $f"
  fi
done
```

| Result | Action |
|--------|--------|
| `+x` present | OK |
| `+x` missing, path under `~/.claude/hooks/` | Same as 3-A above |
| `+x` missing, path under a skill's `resources/` (any skill directory, including marketplace worktrees) | **STALE-PERM** — auto-suggest `chmod +x <file>` (AskUserQuestion). Common cause: the file was copied during a skill split/rename and the copy did not preserve the executable bit |

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat "path exists" (Step 1 pass) as proof the hook is live | Existence and executability are independent checks — a hook can pass Step 1 and still be dead |
| 2 | Scope 3-A's chmod scan to `~/.claude/hooks/*.sh` only, reasoning "that's where hooks live" | Hooks can be registered from any skill's `resources/` directory. Scan the same path set Step 1 already resolved |
| 3 | Skip the extended scan because a skill split/rename "just moves files, permissions carry over" | File copies (not `mv`) commonly reset the executable bit — verify, don't assume |

### 3-A.2 Interpreter mismatch check (shebang content vs. registration prefix)

A registered `command` with no interpreter prefix (bare `${CLAUDE_PLUGIN_ROOT}/.../foo.sh` or `~/.claude/hooks/foo.sh`) only works if the OS honors the file's `#!` shebang line — which Windows Git Bash does **not** for a `.sh`-suffixed file (it falls back to `sh <file>`, executing the file line-by-line regardless of its shebang). A `.sh` file containing Python/Node/Ruby source with a `#!/usr/bin/env python3` shebang but no explicit interpreter prefix in its registration silently fails every invocation with cryptic "command not found" errors on the first non-shell line — and because every hook under the same matcher runs and reports its own failure, this can present as *all* hooks under that matcher failing, not just the broken one.

```bash
# For every resolved command (Step 1's path set), check: does the first line's shebang
# interpreter match the command's own leading token (or is a prefix present at all)?
for f in <resolved-command-paths>; do
  shebang=$(head -1 "$f" 2>/dev/null)
  case "$shebang" in
    '#!'*python*) needs="python3 or python" ;;
    '#!'*node*)   needs="node" ;;
    '#!'*ruby*)   needs="ruby" ;;
    *) continue ;;  # bash/sh shebang or no shebang — bare registration is fine
  esac
  echo "check registration for $f — shebang expects: $needs"
done
```

| Registration form | Shebang content | Verdict |
|---|---|---|
| Bare path, no prefix | `#!/bin/bash` or `#!/bin/sh` or none | OK — matches the fallback interpreter |
| Bare path, no prefix | `#!/usr/bin/env python3` (or node/ruby) | **INTERPRETER-MISMATCH** — add the matching prefix (`python3 <path>`) to the registration |
| Explicit prefix (`python3 <path>`) | matches | OK |

**Scope note**: this check applies to every `command` resolved in Step 1 — including a **plugin's own `hooks/hooks.json`** (`${CLAUDE_PLUGIN_ROOT}/...` entries), not just `~/.claude/settings.json`/`settings.local.json`. A plugin-level hooks.json bug reproduces for every user of that marketplace plugin, so it is worth flagging even more than a local settings.json entry.

| # | Don't | Do |
|---|-------|-----|
| 1 | Assume a bare `.sh` registration is safe because "the shebang will handle it" | Verify per-OS — Windows Git Bash does not honor shebangs on `.sh`-suffixed files; check content against registration explicitly |
| 2 | Diagnose "every Bash hook is broken" as an environment-wide failure before checking for one bad entry among many | One INTERPRETER-MISMATCH entry under a shared matcher (e.g. `PreToolUse:Bash`) can make the whole matcher's hook chain report errors on every call — audit each entry individually before concluding the whole environment is broken |
| 3 | Fix only `~/.claude/settings.json` and skip plugin-distributed `hooks/hooks.json` files | Scan plugin hooks.json too — those bugs affect every installer of that marketplace plugin |

### 3-B. Orphan hook check (no resources source + not in settings)

Validates the "every hook must have an owning skill" policy from `automation.md`. For each `~/.claude/hooks/*.sh`:

| Condition | Classification |
|-----------|----------------|
| No source in any skill's `resources/` + not in settings.json/local.json | **ORPHAN** — unused. Decide to delete or import |
| No resources/ source + registered in settings | **UNMANAGED** — owning skill needs to be determined (recommend importing to hook skill as default installer) |
| resources/ source exists + not registered in settings | **UNREGISTERED** — register via `/hook install` procedure |

```bash
# Skill hook source list — scan both resources/ and scripts/ (sources may be in either;
#   e.g., session/scripts/session-id-inject.sh). macOS-compatible: use sed for basename instead of GNU -printf.
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

### 3-C. Duplicate basename check (same hook script in 2+ resources/ directories)

When the same script basename exists under two or more different skills' `resources/` (or `scripts/`) directories **and both are wired into hooks.json/settings.json**, both copies register as independent hooks under the same matcher — the hook fires twice per event, and if the two copies have diverged (one patched, one stale), they can produce contradictory verdicts on the exact same input. This is a distinct failure mode from 3-B's ORPHAN/UNMANAGED/UNREGISTERED classification, which is scoped to a single canonical copy; duplicate-basename detection catches the case where *multiple* canonical-looking copies coexist.

**Scope note (avoids false positives on unregistered utility scripts)**: a same-named file under two skills' `scripts/` directories that is not itself wired into any hooks.json/settings.json entry is a harmless naming coincidence (e.g., two skills each shipping their own private helper that happens to share a filename) — it does not fire twice because it does not fire automatically at all. Intersect the duplicate-basename list against `REGISTERED` (3-B's variable) before flagging.

```bash
# Reuse 3-B's REGISTERED set (registered hook basenames from settings.json/local.json
# — also union in any plugin's own hooks/hooks.json per 3-A.2's scope note).
# Cross-platform basename dedup, then intersect with REGISTERED.
find ~/.claude/skills ~/.agents/skills \
  \( -path "*/resources/*.sh" -o -path "*/scripts/*.sh" -o -path "*/resources/*.py" -o -path "*/scripts/*.py" \) -type f 2>/dev/null \
  | awk -F/ '{print $NF, $0}' | sort | awk '
    { if ($1 == prev_name) { print prev_line; print $0; dup=1 }
      else if (dup) { dup=0 }
      prev_name=$1; prev_line=$0 }
  ' | while read -r name path; do
      printf '%s\n' "$REGISTERED" | grep -qx "$name" && echo "$name $path"
      true
    done
```

| Result | Classification |
|--------|----------------|
| Basename appears under exactly 1 `resources/`/`scripts/` directory | OK |
| Basename appears under 2+ distinct `resources/`/`scripts/` directories, none registered as a hook | OK — naming coincidence only, no double-fire |
| Basename appears under 2+ distinct `resources/`/`scripts/` directories AND is registered in hooks.json/settings.json | **DUPLICATE** — both copies fire independently under the same matcher; diverging content risks contradictory verdicts on identical input |

**Case history**: `block-cleanup-option-below-context-gate.sh` existed in both `hook-kit/resources/` and `es6p-hooks/resources/` simultaneously — both registered under the same `PreToolUse:AskUserQuestion` matcher, and after the two copies drifted apart they returned conflicting percentage-threshold verdicts (62.8%/24.0% vs 42.7%/51%+) on the same payload. Root-caused and the placement itself was fixed in PR #330, but no automated check existed to catch a recurrence — this section closes that gap.

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat 3-B's UNREGISTERED/UNMANAGED classification as sufficient duplicate coverage | 3-B classifies a single file against settings.json; it says nothing about a second file with the *same basename* existing elsewhere. Run 3-C separately |
| 2 | Assume duplicate basenames are always accidental copies safe to just delete one of | Diff the two copies first — either side may hold content the other lacks (a fix applied to only one copy after they forked). Merge the content, then remove the redundant copy |
| 3 | Scope the scan to one marketplace/plugin only | Duplicate hazards are cross-marketplace by construction (the PR #330 incident spanned `hook-kit` and `es6p-hooks`) — scan every `~/.claude/skills` and `~/.agents/skills` tree in one pass |

### 3-D. Marketplace checkout vs. plugin cache desync (design — not yet automated)

A marketplace entry under `~/.claude/plugins/marketplaces/<name>` is a symlink to a git checkout. What Claude Code actually executes at hook-run time is a **separate** copy under `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/...`, whose path comes from `~/.claude/plugins/installed_plugins.json`'s `installPath` field for that `<plugin>@<marketplace>` key. Editing (or committing) a hook script in the marketplace checkout does **not** guarantee the cache copy updates — a fix applied only to the checkout can silently fail to take effect while every symptom looks like "the fix didn't work."

**Verified 2026-08-18 (two different marketplaces, two different failure shapes — do not assume either is universal)**:
- `daegunsoftDev/skills` (`dgs-plugins` marketplace): `installPath` **exists on disk** and was **stale** — a `next-trigger.sh` fix committed to the checkout had zero effect until the cache copy was manually force-synced (`cat <checkout-file> > <cache-file>`; a plain `cp` failed silently on an interactive overwrite prompt). This is the failure mode this check exists to catch.
- `es6kr/skills` (`es6kr-skills` marketplace): `installPath` (`~/.claude/plugins/cache/es6kr-skills/es6kr/0.1.0`) **does not exist on disk at all**. Editing the checkout took effect immediately in this session — Claude Code appears to fall back to reading the marketplace source directly when no cache copy exists — but this fallback behavior is an empirical observation from one session, not a documented contract; do not hard-code an assumption that a missing cache dir is always safe.

**Detection procedure (design)**:
1. For a given marketplace checkout path (or a git commit's changed-file list within one), resolve which marketplace it is: match the checkout's `realpath` against every symlink target under `~/.claude/plugins/marketplaces/*`.
2. Look up that marketplace's plugin(s) and `installPath` in `~/.claude/plugins/installed_plugins.json` (key format `<plugin>@<marketplace>`).
3. `installPath` missing on disk → report **NO-CACHE** (informational — behavior unconfirmed beyond the one observed case above, flag for awareness rather than auto-fix).
4. `installPath` exists → for each changed/hook-relevant file, diff the checkout's copy against the corresponding cache-path copy. Differ → **STALE-CACHE** (the exact bug this section documents).

```bash
# Sketch — not yet wired into a hook or a report loop; resolve $CHECKOUT_PATH and
# $CHANGED_FILES from the caller's context (e.g. git diff --name-only HEAD~1).
MARKETPLACE=$(for m in ~/.claude/plugins/marketplaces/*; do
  [ "$(cd "$m" && pwd -P)" = "$(cd "$CHECKOUT_PATH" && pwd -P)" ] && basename "$m" && break
done)
[ -z "$MARKETPLACE" ] && { echo "not a known marketplace checkout"; exit 0; }

INSTALL_PATH=$(python3 -c "
import json
d = json.load(open('$HOME/.claude/plugins/installed_plugins.json'))
for key, entries in d.get('plugins', {}).items():
    if key.endswith('@$MARKETPLACE'):
        for e in entries:
            print(e.get('installPath', ''))
")

if [ -z "$INSTALL_PATH" ] || [ ! -d "$INSTALL_PATH" ]; then
  echo "NO-CACHE: $MARKETPLACE has no populated cache dir — verify fallback behavior before trusting this is safe"
else
  for f in $CHANGED_FILES; do
    diff -q "$CHECKOUT_PATH/$f" "$INSTALL_PATH/$f" >/dev/null 2>&1 \
      || echo "STALE-CACHE: $f differs between checkout and $INSTALL_PATH"
  done
fi
```

**Remaining implementation candidates (fix_plan.md, not done in this pass)**:
- Wire this into a `PostToolUse:Bash(git commit)` hook so it fires automatically after a commit to any marketplace-checkout repo, rather than requiring a manual `/hook-kit audit` invocation
- Confirm empirically (across more than the one `es6kr-skills` observation) whether a missing `installPath` reliably means "harness reads from marketplace source directly," or whether that was specific to this session's environment/timing

| # | Don't | Do |
|---|-------|-----|
| 1 | Assume a fix committed to a marketplace checkout is live because the commit succeeded | The checkout and the executing cache copy are different files on disk — verify the cache copy too, or run this check |
| 2 | Treat a missing `installPath` as proof the fallback-to-source behavior is safe/guaranteed | It is one session's empirical observation for one marketplace, not a documented Claude Code contract — flag as NO-CACHE, don't silently treat it as fine |
| 3 | Assume `claudify`'s "Auto-sync hook: plugin-cache-sync.sh" text describes a real, active mechanism | Verified absent 2026-08-18 — no live file, no settings.json/hooks.json registration. The claudify SKILL.md text was corrected in the same pass that added this section |

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

Duplicate basename check:
  OK         bash-guard.sh
  DUPLICATE  block-cleanup-option-below-context-gate.sh
    ~/.claude/skills/hook-kit/resources/block-cleanup-option-below-context-gate.sh
    ~/.claude/skills/es6p-hooks/resources/block-cleanup-option-below-context-gate.sh

Total: OK 15 / STALE 2 / MISSING 1 / STALE-PERM 1 / ORPHAN 1 / UNMANAGED 1 / UNREGISTERED 1 / DUPLICATE 1
```

### 5. Fix suggestions

For STALE/MISSING/STALE-PERM/ORPHAN/UNMANAGED/UNREGISTERED/DUPLICATE items, use AskUserQuestion(multiSelect:true) to choose action:
- **fix**: update to the correct reference
- **chmod +x**: grant executable bit to STALE-PERM items (`chmod +x <file>`)
- **import**: UNMANAGED → mv to owning skill resources/ via `/hook install` import procedure
- **register**: UNREGISTERED → register in settings.json via `/hook install`
- **archive**: ORPHAN → move to `~/.claude/.bak/` (`/safe-delete` or `/archive`)
- **merge-and-remove**: DUPLICATE → diff both copies, merge any content unique to either side into one, then delete the redundant copy and (if needed) its hooks.json/settings.json registration
- **remove**: remove the hook entry (`/hook remove` guidance)
- **skip**: skip for now
