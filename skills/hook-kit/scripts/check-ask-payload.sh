#!/usr/bin/env bash
# check-ask-payload.sh — dry-run a draft AskUserQuestion payload against every
# registered PreToolUse:AskUserQuestion guard, in one call.
#
# Why: composing an ask that trips a guard costs a full round trip — the call is
# denied, the payload is rewritten, and the user waits through both. The guards
# are plain scripts reading a JSON payload on stdin, so they can be run against a
# draft before the real tool call. Doing that by hand means one command per
# guard, and the guard list is spread across settings.json plus every installed
# plugin's hooks.json — which is why it tends to get done partially or not at all.
#
# This is a developer/agent helper, NOT a hook. It is never registered.
#
# Usage:
#   check-ask-payload.sh <payload.json>
#   echo '<json>' | check-ask-payload.sh
#   check-ask-payload.sh --list            # show the guards that would run
#
# Payload shape (the same object a PreToolUse hook receives):
#   {"tool_name":"AskUserQuestion","tool_input":{"questions":[{"question":"...",
#     "options":[{"label":"...","description":"..."}]}]}}
#
# Exit: 0 = every guard allowed, 1 = at least one guard denied, 2 = usage error.

set -uo pipefail

SETTINGS="${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"
MARKETPLACES="${CLAUDE_MARKETPLACES:-$HOME/.claude/plugins/marketplaces}"

usage() { sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

LIST_ONLY=0
PAYLOAD_FILE=""
case "${1:-}" in
  --list) LIST_ONLY=1 ;;
  -h|--help) usage ;;
  "") PAYLOAD_FILE="-" ;;
  *) PAYLOAD_FILE="$1" ;;
esac

command -v jq >/dev/null 2>&1 || { echo "jq is required" >&2; exit 2; }

# --- collect guards -----------------------------------------------------------
# Both settings.json and each plugin's hooks.json use the same shape:
#   .hooks.PreToolUse[] | select(.matcher matches AskUserQuestion) | .hooks[].command
# ${CLAUDE_PLUGIN_ROOT} in a plugin command resolves to that plugin's own root.

collect_from() {  # collect_from <json-file> <plugin-root-or-empty>
  local file="$1" root="${2:-}"
  [[ -f "$file" ]] || return 0
  jq -r '
    (.hooks.PreToolUse // [])[]
    | select((.matcher // "") | test("AskUserQuestion"))
    | (.hooks // [])[]
    | .command // empty
  ' "$file" 2>/dev/null | while IFS= read -r cmd; do
    [[ -z "$cmd" ]] && continue
    cmd="${cmd//\$\{CLAUDE_PLUGIN_ROOT\}/$root}"
    cmd="${cmd//\$CLAUDE_PLUGIN_ROOT/$root}"
    cmd="${cmd//\~/$HOME}"
    echo "$cmd"
  done
}

GUARDS=()
while IFS= read -r c; do [[ -n "$c" ]] && GUARDS+=("$c"); done < <(collect_from "$SETTINGS" "")
# Two layouts coexist: a marketplace that is itself one plugin keeps hooks.json
# at its root, while a multi-plugin marketplace nests one per plugin. Scanning
# only the first layout silently drops every guard belonging to the second —
# which is where the ask-composition guards happen to live.
for hj in "$MARKETPLACES"/*/hooks/hooks.json "$MARKETPLACES"/*/plugins/*/hooks/hooks.json; do
  [[ -f "$hj" ]] || continue
  plugin_root="$(cd "$(dirname "$(dirname "$hj")")" && pwd -P)"
  while IFS= read -r c; do [[ -n "$c" ]] && GUARDS+=("$c"); done < <(collect_from "$hj" "$plugin_root")
done

if [[ ${#GUARDS[@]} -eq 0 ]]; then
  echo "No PreToolUse:AskUserQuestion guards found (settings: $SETTINGS)" >&2
  exit 2
fi

if [[ "$LIST_ONLY" -eq 1 ]]; then
  printf '%s guard(s) registered:\n' "${#GUARDS[@]}"
  printf '  %s\n' "${GUARDS[@]}"
  exit 0
fi

# --- read payload -------------------------------------------------------------
if [[ "$PAYLOAD_FILE" == "-" ]]; then
  PAYLOAD="$(cat)"
else
  [[ -f "$PAYLOAD_FILE" ]] || { echo "No such payload file: $PAYLOAD_FILE" >&2; exit 2; }
  PAYLOAD="$(cat "$PAYLOAD_FILE")"
fi

echo "$PAYLOAD" | jq -e . >/dev/null 2>&1 || { echo "Payload is not valid JSON" >&2; exit 2; }

# A guard that only inspects .tool_input will still refuse to act unless
# tool_name says AskUserQuestion — fill it in when the draft omits it.
if [[ "$(echo "$PAYLOAD" | jq -r '.tool_name // empty')" != "AskUserQuestion" ]]; then
  PAYLOAD="$(echo "$PAYLOAD" | jq '. + {tool_name: "AskUserQuestion"}')"
fi

# --- run ----------------------------------------------------------------------
denied=0
passed=0
broken=0
for cmd in "${GUARDS[@]}"; do
  name="$(basename "${cmd%% *}")"
  out="$(echo "$PAYLOAD" | timeout 30 bash -c "$cmd" 2>&1)"
  rc=$?
  if [[ $rc -eq 0 ]]; then
    passed=$((passed + 1))
  elif [[ $rc -eq 127 || "$out" == *"No such file or directory"* ]]; then
    # Registered but not executable — a ghost hook. Distinct from a denial:
    # the guard is not enforcing anything and nobody would notice, because a
    # hook that cannot run looks exactly like a hook that had no objection.
    broken=$((broken + 1))
    printf '\n=== GHOST (exit %s, registered but not runnable): %s\n' "$rc" "$name"
    printf '%s\n' "$out" | sed 's/^/    /'
    printf '    → fix the registration path in the owning hooks.json\n'
  else
    denied=$((denied + 1))
    printf '\n=== DENIED (exit %s): %s\n' "$rc" "$name"
    printf '%s\n' "$out" | sed 's/^/    /'
  fi
done

printf '\n%s guard(s): %s allowed, %s denied, %s ghost\n' \
  "${#GUARDS[@]}" "$passed" "$denied" "$broken"
[[ $denied -eq 0 && $broken -eq 0 ]] || exit 1
