#!/bin/bash
# trigger-compile.sh — Reads triggers declarations from SKILL.md, generates dispatcher hook scripts, and registers them in settings.json
# Usage: bash trigger-compile.sh [--dry-run] [--list]
set -euo pipefail

HOOKS_DIR="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"
# NOTE: ~/.claude/skills/<name>/ is often a personal-overlay symlink (data/ only,
# no SKILL.md) in this environment — the skill body lives in a marketplace instead.
# Scan both, or a marketplace-owned skill's `triggers:` (e.g. cleanup's Stop inject)
# silently disappears from the compiled dispatcher.
SKILLS_DIRS=("$HOME/.claude/skills")
for _mp in "$HOME/.claude/plugins/marketplaces"/*/skills; do
  [[ -d "$_mp" ]] && SKILLS_DIRS+=("$_mp")
done
DRY_RUN=false
LIST_ONLY=false
SEP=$'\x1f'   # field separator — unit-separator (0x1F) to avoid collision with '|' inside matcher/pattern values

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --list) LIST_ONLY=true ;;
  esac
done

# --- 1. Collect triggers fields from all SKILL.md files ---
declare -A TRIGGERS_BY_EVENT  # event -> trigger entries
declare -A SEEN_SKILL_DIR     # skill name -> first-scanned skilldir (cross-location dedup)

validate_trigger() {
  local skill_dir="$1" skill="$2" action="$3" scriptpath="$4"
  if [[ "$action" == "script" ]]; then
    if [[ -z "$scriptpath" ]]; then
      echo "ERROR: scriptpath is empty for skill '$skill'" >&2
      exit 1
    fi
    if [[ "$scriptpath" == /* ]] || [[ "$scriptpath" == *..* ]]; then
      echo "ERROR: scriptpath '$scriptpath' contains absolute path or path traversal (..) for skill '$skill'" >&2
      exit 1
    fi
    local local_script_path="$skill_dir/$scriptpath"
    if [[ ! -f "$local_script_path" ]]; then
      echo "ERROR: script file '$local_script_path' not found for skill '$skill'" >&2
      exit 1
    fi
  fi
}

scan_skills() {
  for skills_dir in "${SKILLS_DIRS[@]}"; do
    [[ -d "$skills_dir" ]] || continue
    for skill_dir in "$skills_dir"/*/; do
      local skill_file="$skill_dir/SKILL.md"
      [[ -f "$skill_file" ]] || continue

      local skill_name
      skill_name=$(basename "$skill_dir")
      # Resolve to an absolute path with no trailing slash — this is the
      # directory scriptpath is actually validated against below, and it is
      # NOT always ~/.claude/skills/<skill> (that path is frequently a
      # personal-overlay symlink containing only data/, no resources/ — the
      # real skill body lives in a marketplace dir instead). The generated
      # dispatcher must resolve scripts against this same directory, not a
      # hardcoded ~/.claude/skills guess (2026-08-18 hook-monitoring plan —
      # found via check-hook-failure-gap.js resolving to a missing path).
      local skill_abs_dir
      skill_abs_dir=$(cd "$skill_dir" && pwd)

      # Extract triggers block from frontmatter
      local in_frontmatter=false
      local in_triggers=false
      local current_event="" current_action="" current_matcher="" current_pattern="" current_message="" current_exit_code="" current_script=""

      while IFS= read -r line; do
        # frontmatter boundary
        if [[ "$line" == "---" ]]; then
          if $in_frontmatter; then
            # end of frontmatter — save last trigger
            if [[ -n "$current_event" ]]; then
              validate_trigger "$skill_dir" "$skill_name" "$current_action" "$current_script"
              save_trigger "$skill_name" "$current_event" "$current_action" "$current_matcher" "$current_pattern" "$current_message" "$current_exit_code" "$current_script" "$skill_abs_dir"
            fi
            break
          fi
          in_frontmatter=true
          continue
        fi

        $in_frontmatter || continue

        # start of triggers: block
        if [[ "$line" =~ ^triggers: ]]; then
          in_triggers=true
          continue
        fi

        $in_triggers || continue

        # new entry start (- event:)
        if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*event:[[:space:]]*(.*) ]]; then
          # save previous trigger
          if [[ -n "$current_event" ]]; then
            validate_trigger "$skill_dir" "$skill_name" "$current_action" "$current_script"
            save_trigger "$skill_name" "$current_event" "$current_action" "$current_matcher" "$current_pattern" "$current_message" "$current_exit_code" "$current_script" "$skill_abs_dir"
          fi
          current_event="${BASH_REMATCH[1]}"
          current_action="" current_matcher="" current_pattern="" current_message="" current_exit_code="" current_script=""
          continue
        fi

        # other top-level key that is not triggers (unindented key: or top-level keyword)
        if [[ "$line" =~ ^[a-zA-Z_-]+: ]] && ! [[ "$line" =~ ^[[:space:]] ]]; then
          # save last trigger
          if [[ -n "$current_event" ]]; then
            validate_trigger "$skill_dir" "$skill_name" "$current_action" "$current_script"
            save_trigger "$skill_name" "$current_event" "$current_action" "$current_matcher" "$current_pattern" "$current_message" "$current_exit_code" "$current_script" "$skill_abs_dir"
          fi
          in_triggers=false
          continue
        fi

        # parse attributes
        if [[ "$line" =~ ^[[:space:]]+action:[[:space:]]*(.*) ]]; then
          current_action="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^[[:space:]]+matcher:[[:space:]]*\"(.*)\" ]]; then
          current_matcher="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^[[:space:]]+matcher:[[:space:]]*(.*) ]]; then
          current_matcher="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^[[:space:]]+pattern:[[:space:]]*\"(.*)\" ]]; then
          current_pattern="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^[[:space:]]+pattern:[[:space:]]*(.*) ]]; then
          current_pattern="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^[[:space:]]+message:[[:space:]]*\"(.*)\" ]]; then
          current_message="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^[[:space:]]+message:[[:space:]]*(.*) ]]; then
          current_message="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^[[:space:]]+exit_code_filter:[[:space:]]*(.*) ]]; then
          current_exit_code="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^[[:space:]]+script:[[:space:]]*\"(.*)\" ]]; then
          current_script="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^[[:space:]]+script:[[:space:]]*(.*) ]]; then
          current_script="${BASH_REMATCH[1]}"
        fi

      done < "$skill_file"
    done
  done
}

save_trigger() {
  local skill="$1" event="$2" action="$3" matcher="$4" pattern="$5" message="$6" exit_code="$7" script="${8:-}" skilldir="${9:-}"

  # Cross-location dedup (2026-08-18, drift investigation): this environment
  # commonly has the same skill name shipped from 2+ independent sources —
  # ~/.claude/skills/<name> (personal-overlay clone) AND one or more installed
  # marketplaces (e.g. es6kr-skills vs the legacy es6kr-plugins/claude-plugins
  # repo, or a personal fork like dgs-plugins). Since `suggest`-action triggers
  # never call process.exit(), two drifted copies of the same skill both firing
  # on one matched event print duplicate/conflicting <skill-trigger> blocks.
  # First-scanned skilldir wins per skill name (SKILLS_DIRS order: local
  # overlay first, then marketplaces in glob order) — later locations for the
  # SAME skill name are skipped with a warning. A single skilldir declaring
  # multiple distinct triggers (e.g. cleanup's script+inject, dgs's 2 SSH
  # matchers) is unaffected — this only skips a different skilldir.
  local seen_dir="${SEEN_SKILL_DIR[$skill]:-}"
  if [[ -n "$seen_dir" ]] && [[ "$seen_dir" != "$skilldir" ]]; then
    echo "WARNING: skipping duplicate skill '$skill' trigger from '$skilldir' — already registered from '$seen_dir'" >&2
    return
  fi
  SEEN_SKILL_DIR[$skill]="$skilldir"

  local entry="${skill}${SEP}${action}${SEP}${matcher}${SEP}${pattern}${SEP}${message}${SEP}${exit_code}${SEP}${script}${SEP}${skilldir}"
  # prevent exact-duplicate re-declaration within the same skilldir
  local existing="${TRIGGERS_BY_EVENT[$event]:-}"
  if [[ "$existing" == *"$entry"* ]]; then
    return
  fi
  TRIGGERS_BY_EVENT[$event]="${existing}${existing:+$'\n'}$entry"
}

# --- 2. Print trigger list ---
list_triggers() {
  echo "=== Registered Triggers ==="
  echo ""
  for event in "${!TRIGGERS_BY_EVENT[@]}"; do
    echo "[$event]"
    while IFS="$SEP" read -r skill action matcher pattern message exit_code script _skilldir; do
      [[ -z "$skill" ]] && continue
      printf "  %-20s action=%-8s" "$skill" "$action"
      [[ -n "$script" ]] && printf " script=%s" "$script"
      [[ -n "$matcher" ]] && printf " matcher=%s" "$matcher"
      [[ -n "$pattern" ]] && printf " pattern=\"%s\"" "$pattern"
      echo ""
    done <<< "${TRIGGERS_BY_EVENT[$event]}"
    echo ""
  done
}

# --- 3. Generate dispatcher scripts ---
generate_dispatcher() {
  local event="$1"
  local entries="${TRIGGERS_BY_EVENT[$event]}"
  # order terminal actions by priority: script > suggest > block > inject (fallback last),
  # so a matching script/regex trigger surfaces its decision before the once-per-session inject
  if [[ -n "$entries" ]]; then
    local _ranked="" _l _act _r
    while IFS= read -r _l; do
      [[ -z "$_l" ]] && continue
      _act=$(printf '%s' "$_l" | cut -d"$SEP" -f2)
      case "$_act" in script) _r=0 ;; suggest) _r=1 ;; block) _r=2 ;; inject) _r=3 ;; *) _r=4 ;; esac
      _ranked+="${_r}${SEP}${_l}"$'\n'
    done <<< "$entries"
    entries=$(printf '%s' "$_ranked" | sort -t"$SEP" -k1,1n -s | cut -d"$SEP" -f2-)
  fi
  local output_file="$HOOKS_DIR/trigger-${event}.js"
  local timestamp
  timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  # js_str <text> — emit a double-quoted JS string literal for <text> (jq handles all escaping)
  js_str() { jq -Rn --arg s "$1" '$s'; }

  local script="#!/usr/bin/env node
// AUTO-GENERATED by skill-kit trigger compiler
// DO NOT EDIT — regenerate with: /skill-kit trigger compile
// Generated: $timestamp

const fs = require('fs');
const path = require('path');
const os = require('os');

function readStdin() {
  try { return fs.readFileSync(0, 'utf8'); } catch (e) { return ''; }
}
function safeParse(s) {
  try { return JSON.parse(s); } catch (e) { return {}; }
}

// Records one NDJSON line per action:script trigger invocation (2026-08-18,
// hook-monitoring plan) — the reap-orphaned-helper-procs.log that motivated
// this has no known writer script in this environment (settings.json / hooks.json
// / scheduled tasks all came up empty; likely Claude Code CLI internal), so this
// self-instrumentation is the only per-hook-name failure signal available.
// Fails open — monitoring must never break the hook it observes.
const __HOOK_STATE_DIR = path.join(os.homedir(), '.claude', 'skills', 'hook-kit', '.state');
function recordHookInvocation(entry) {
  try {
    fs.mkdirSync(__HOOK_STATE_DIR, { recursive: true });
    fs.appendFileSync(path.join(__HOOK_STATE_DIR, 'hook-invocations.ndjson'), JSON.stringify(entry) + '\\n', 'utf8');
  } catch (e) { /* fail open */ }
}

const INPUT = readStdin();
const _input = safeParse(INPUT);
const TOOL_NAME = _input.tool_name || '';
const COMMAND = (_input.tool_input && _input.tool_input.command) || '';
const FILE_PATH = (_input.tool_input && _input.tool_input.file_path) || '';
const EXIT_CODE = process.env.EXIT_CODE || '0';
"

  while IFS="$SEP" read -r skill action matcher pattern message exit_code_filter scriptpath skilldir; do
    [[ -z "$skill" ]] && continue

    local condition_start="" condition_end=""

    # build matcher/pattern condition (JS regex test — matcher may be an alternation e.g. "Edit|Write")
    if [[ -n "$matcher" ]] || [[ -n "$pattern" ]] || [[ -n "$exit_code_filter" ]]; then
      local conditions=()
      [[ -n "$matcher" ]] && conditions+=("new RegExp($(js_str "^($matcher)\$")).test(TOOL_NAME)")
      # pattern regex covers both Bash command and Edit/Write file_path
      [[ -n "$pattern" ]] && conditions+=("new RegExp($(js_str "$pattern")).test(COMMAND + ' ' + FILE_PATH)")
      [[ -n "$exit_code_filter" ]] && conditions+=("EXIT_CODE === $(js_str "$exit_code_filter")")

      condition_start="if (${conditions[0]}"
      for ((i=1; i<${#conditions[@]}; i++)); do
        condition_start="$condition_start && ${conditions[$i]}"
      done
      condition_start="$condition_start) {"
      condition_end="}"
    fi

    script+="
// $skill ($event, action=$action)
"
    [[ -n "$condition_start" ]] && script+="$condition_start
"

    case "$action" in
      suggest)
        script+="console.log('<skill-trigger name=\"$skill\">');
console.log($(js_str "$message"));
console.log('Call the Skill(\"$skill\") tool.');
console.log('</skill-trigger>');
"
        ;;
      block)
        script+="console.log($(js_str "$message"));
process.exit(1);
"
        ;;
      inject)
        script+="// fire once per session; if already fired, fall through to lower-priority triggers
{
  const path = require('path');
  const os = require('os');
  const FIRE_FLAG = path.join(os.homedir(), '.claude', 'data', 'trigger-stop-${skill}');
  if (!fs.existsSync(FIRE_FLAG)) {
    fs.mkdirSync(path.dirname(FIRE_FLAG), { recursive: true });
    fs.writeFileSync(FIRE_FLAG, '');
    console.log(JSON.stringify({
      decision: 'block',
      reason: $(js_str "$skill trigger"),
      systemMessage: $(js_str "$message")
    }));
    process.exit(0);
  }
}
"
        ;;
      script)
        script+="// dispatch to skill-owned resource script; pass hook stdin through
{
  const { spawnSync } = require('child_process');
  const scriptPath = path.join($(js_str "$skilldir"), $(js_str "$scriptpath"));
  const __interpreter = scriptPath.endsWith('.js') ? 'node' : 'bash';
  const __t0 = Date.now();
  const result = spawnSync(__interpreter, [scriptPath], { input: INPUT, encoding: 'utf8', timeout: 8000 });
  recordHookInvocation({
    ts: new Date().toISOString(),
    skill: $(js_str "$skill"),
    script: $(js_str "$scriptpath"),
    event: $(js_str "$event"),
    durationMs: Date.now() - __t0,
    exitCode: result.status,
    signal: result.signal || null,
    error: result.error ? String(result.error.message || result.error) : null,
  });
  const out = (result.stdout || '').trim();
  if (out) {
    console.log(out);
    process.exit(0);
  }
}
"
        ;;
    esac

    [[ -n "$condition_end" ]] && script+="$condition_end
"
  done <<< "$entries"

  script+="
process.exit(0);
"

  if $DRY_RUN; then
    echo "=== Would generate: $output_file ==="
    echo "$script"
    echo ""
  else
    echo "$script" > "$output_file"
    chmod +x "$output_file"
    echo "Generated: $output_file"
  fi
}

# --- 4. Register hooks in settings.json ---
register_hooks() {
  if $DRY_RUN; then
    echo "=== Would register in settings.json ==="
  fi

  local tmp_settings
  tmp_settings=$(mktemp)
  cp "$SETTINGS" "$tmp_settings"

  for event in "${!TRIGGERS_BY_EVENT[@]}"; do
    local hook_cmd="node ~/.claude/hooks/trigger-${event}.js"
    local matcher=""

    # collect matchers for PostToolUse/PreToolUse
    if [[ "$event" == "PostToolUse" ]] || [[ "$event" == "PreToolUse" ]]; then
      local matchers=()
      while IFS="$SEP" read -r skill action m pattern message exit_code script _skilldir; do
        [[ -n "$m" ]] && matchers+=("$m")
      done <<< "${TRIGGERS_BY_EVENT[$event]}"

      # unique matchers
      if [[ ${#matchers[@]} -gt 0 ]]; then
        matcher=$(printf '%s\n' "${matchers[@]}" | sort -u | paste -sd '|')
      fi
    fi

    if $DRY_RUN; then
      echo "  Event: $event"
      echo "  Command: $hook_cmd"
      [[ -n "$matcher" ]] && echo "  Matcher: $matcher"
      echo ""
    else
      # remove existing trigger- prefixed hooks, then re-add
      local hook_entry
      if [[ -n "$matcher" ]]; then
        hook_entry=$(jq -n --arg cmd "$hook_cmd" --arg m "$matcher" '{
          matcher: $m,
          hooks: [{ type: "command", command: $cmd, timeout: 10 }]
        }')
      else
        hook_entry=$(jq -n --arg cmd "$hook_cmd" '{
          hooks: [{ type: "command", command: $cmd, timeout: 10 }]
        }')
      fi

      # remove existing trigger- hooks + add new entry
      jq --arg event "$event" --arg cmd "$hook_cmd" --argjson entry "$hook_entry" '
        .hooks[$event] = (
          (.hooks[$event] // [])
          | map(select(.hooks[0].command | test("trigger-") | not))
          | . + [$entry]
        )
      ' "$tmp_settings" > "${tmp_settings}.new"
      mv "${tmp_settings}.new" "$tmp_settings"

      echo "Registered: $event → $hook_cmd"
    fi
  done

  if ! $DRY_RUN; then
    cp "$tmp_settings" "$SETTINGS"
    echo ""
    echo "settings.json updated."
  fi
  rm -f "$tmp_settings"
}

# --- Main ---
mkdir -p "$HOOKS_DIR"
scan_skills

if [[ ${#TRIGGERS_BY_EVENT[@]} -eq 0 ]]; then
  echo "No triggers found in any SKILL.md."
  exit 0
fi

if $LIST_ONLY; then
  list_triggers
  exit 0
fi

echo "Found triggers in ${#TRIGGERS_BY_EVENT[@]} event(s):"
list_triggers

for event in "${!TRIGGERS_BY_EVENT[@]}"; do
  generate_dispatcher "$event"
done

register_hooks

# --- 5. Verify generated scripts ---
echo ""
echo "=== Verification ==="
errors=0
for event in "${!TRIGGERS_BY_EVENT[@]}"; do
  script_file="$HOOKS_DIR/trigger-${event}.js"
  if node --check "$script_file" 2>/dev/null; then
    echo "  ✓ trigger-${event}.js syntax OK"
  else
    echo "  ✗ trigger-${event}.js syntax ERROR:"
    node --check "$script_file" 2>&1 | head -5
    errors=$((errors + 1))
  fi
done

if jq . "$SETTINGS" > /dev/null 2>&1; then
  echo "  ✓ settings.json valid JSON"
else
  echo "  ✗ settings.json invalid JSON!"
  errors=$((errors + 1))
fi

if [[ $errors -gt 0 ]]; then
  echo ""
  echo "ERROR: $errors verification failure(s). Fix before restarting Claude Code."
  exit 1
fi

echo ""
echo "Done. Restart Claude Code to apply."
