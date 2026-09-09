#!/usr/bin/env bash
# Stop hook — an absence claim that rests on exactly one probe medium.
#
# Trigger: the last assistant response asserts that something does not exist,
#          AND the tool calls made since the last real user prompt used exactly
#          ONE probe medium (one way of looking).
# Action:  emit {"decision":"block","reason":"..."} — the Stop event schema does
#          not accept hookSpecificOutput.additionalContext, so decision+reason is
#          the only way to feed text back (same shape as
#          check-ask-bypass-keywords.sh).
#
# Why exactly one, not zero or one:
#   Zero probes usually means the response is restating something established in
#   an earlier turn — firing there is noise. One probe is the actual failure
#   shape: a single lookup came back empty and its emptiness was read as the
#   absence of the target. See failed-attempts.md class
#   `empty-output-read-as-absence` (status=hook-mandatory). The canonical case:
#   `pm2 list` returned nothing, so "there is no local service by that name" was
#   concluded — while `which <name>`, `~/.<name>/`, the OS startup entries and
#   the tool's own `status` subcommand all would have found it.
#
# Why the medium of the FIRST pipeline segment decides:
#   `tasklist | grep -i hermes` is one probe, not two — grep is filtering the
#   output of the single medium that was consulted. Counting the filter as a
#   second medium would have silenced this hook on the very case that motivated
#   it. So each command contributes the medium of its first segment, and
#   filters (grep/sed/awk/jq/head/…) only count when they lead the command.
#
# Advisory by design: it cannot see whether the claim is true, only whether the
# evidence behind it is single-sourced. The reminder asks for one cross-check,
# it does not assert the claim is wrong.

set -uo pipefail

# Korean absence phrasing lives in the git-ignored data file so this PUBLIC repo
# stays English-only (same arrangement as check-ask-bypass-keywords.sh). Absent
# file => never-match => the hook still works on English phrasing.
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [ -f "$HG_DATA_FILE" ]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
HG_ABSENCE_CLAIM_PATTERN="${HG_ABSENCE_CLAIM_PATTERN:-__NEVER_MATCH__}"
HG_ABSENCE_SCOPE_PATTERN="${HG_ABSENCE_SCOPE_PATTERN:-__NEVER_MATCH__}"

# Categorical absence: "the thing itself is not there", as opposed to a scoped
# measurement ("0 hits on this branch"), which is a legitimate report.
ABSENCE_EN='(does not exist|does not seem to exist|doesn'"'"'t exist|no such (file|directory|skill|hook|script|repo|repository|branch|command|tool|entry|record)|not found anywhere|nowhere to be found|(is|are) absent from|never existed|not present anywhere|no (implementation|equivalent|prior art|precedent|counterpart)( that)? (exists|exist|is registered)|has to be (written|built) from scratch|needs to be (written|built) from scratch|there (is|are) no [a-z])'

# Scope qualifiers that turn a claim into a measurement report. When the same
# line carries one of these, the claim already states what was actually
# searched, which is the behaviour this hook is trying to produce.
SCOPE_EN='(on this branch|at this ref|in this (repo|repository|checkout|worktree|directory|file)|under |within |0-hit|zero hits|scanned|searched [0-9]|checked [0-9]|as far as .{0,20}(searched|checked)|according to)'

INPUT_MODE="stdin"
if [ "${1:-}" = "--test" ]; then
  INPUT_MODE="test"
fi

emit_reminder() {
  local media="$1"
  local reason
  reason="[hook:check-absence-claim-single-probe] The response asserts that something does not exist, but every tool call in this turn used the same probe medium (${media}).

failed-attempts.md class \`empty-output-read-as-absence\` (status=hook-mandatory) is exactly this shape: one lookup came back empty and the emptiness was read as the absence of the target. An empty result proves the query found nothing, not that the target is missing — the query itself may be wrong (wrong path, wrong pattern, wrong host, a runtime that hides the service name, a ref that does not exist so the command failed on stderr while printing nothing to stdout).

Before this claim stands, do one of these:
1. Probe a second medium. For a process/service: \`which <name>\`, the config dir (\`~/.<name>/\`), OS startup entries, and the tool's own \`status\` subcommand. For a file/symbol: a different pattern, a different repo, or a direct \`ls\` of the parent directory. For a git object: \`git rev-parse\` the ref before reading absence out of an empty listing.
2. Or scope the claim to what was actually checked — \"not on this branch\", \"no match for this pattern\" — instead of the unqualified form.

A claim about to be persisted (RAG chunk, skill topic, rule, wiki page, commit message) carries the heavier burden: a wrong fact that outlives the session is worse than no fact."
  jq -n --arg msg "$reason" '{decision: "block", reason: $msg}'
}

run_hook() {
  local input transcript last_msg last_text
  input=$(cat)

  transcript=$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2>/dev/null)
  [ -f "$transcript" ] || return 0

  last_msg=$(jq -s 'map(select(.type == "assistant")) | last // empty' "$transcript" 2>/dev/null)
  [ -n "$last_msg" ] && [ "$last_msg" != "null" ] || return 0

  last_text=$(printf '%s' "$last_msg" \
    | jq -r '.message.content // [] | map(select(.type == "text") | .text) | join("\n")' 2>/dev/null)
  [ -n "$last_text" ] || return 0

  # Lines carrying a categorical absence claim, minus those that already scope
  # themselves.
  local claim_lines
  claim_lines=$(printf '%s\n' "$last_text" \
    | grep -iE "$ABSENCE_EN|$HG_ABSENCE_CLAIM_PATTERN" 2>/dev/null \
    | grep -ivE "$SCOPE_EN|$HG_ABSENCE_SCOPE_PATTERN" 2>/dev/null || true)
  [ -n "$claim_lines" ] || return 0

  # Probe media used since the last real user prompt. A transcript entry of type
  # "user" whose content is an array of tool_result blocks is a tool response,
  # not a prompt — only a string content (or an array with no tool_result) marks
  # a genuine turn boundary.
  local media
  media=$(jq -rs '
    . as $all
    | ([ range(0; ($all | length)) as $i
         | select($all[$i].type == "user" and (
             ($all[$i].message.content | type) == "string"
             or (($all[$i].message.content // []) | map(select(.type == "tool_result")) | length) == 0
           ))
         | $i ] | last // -1) as $start
    | $all[($start + 1):]
    | map(select(.type == "assistant"))
    | map(.message.content // [] | map(select(.type == "tool_use")))
    | flatten
    | map(if .name == "Bash" then (.input.command // "") else ("TOOL:" + .name) end)
    | .[]
  ' "$transcript" 2>/dev/null | classify_media | sort -u)

  local count
  count=$(printf '%s\n' "$media" | grep -c '[^[:space:]]' || true)
  [ "$count" = "1" ] || return 0

  emit_reminder "$(printf '%s' "$media" | tr '\n' ' ' | sed 's/ *$//')"
}

# Map each command (or tool marker) to one probe medium, reading only the first
# pipeline/compound segment so that a trailing filter does not masquerade as a
# second way of looking.
classify_media() {
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    case "$line" in
      TOOL:*)
        case "${line#*TOOL:}" in
          Grep) echo content-search ;;
          Glob) echo filesystem ;;
          Read|NotebookRead) echo file-read ;;
          WebFetch|WebSearch) echo network ;;
          *) : ;;  # Skill/Agent/Write/Edit and friends are not probes
        esac
        continue
        ;;
    esac
    # First segment of the first command in the line
    local head_cmd
    head_cmd=$(printf '%s' "$line" \
      | sed -E 's/^[[:space:]]*//; s/^[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+//g' \
      | cut -d'|' -f1 | cut -d';' -f1 | sed -E 's/&&.*//' \
      | awk '{print $1}' \
      | sed -E 's#.*/##')
    case "$head_cmd" in
      grep|rg|ag|ack|egrep|fgrep) echo content-search ;;
      ls|find|fd|tree|stat|dir) echo filesystem ;;
      cat|head|tail|sed|awk|less|more|wc|jq) echo file-read ;;
      git) echo git ;;
      gh|glab) echo forge ;;
      curl|wget|nc|ping|dig|nslookup|host) echo network ;;
      ps|tasklist|pgrep|pm2|systemctl|launchctl|service|sc) echo process ;;
      which|command|type|whereis|where) echo path-lookup ;;
      kubectl|docker|podman|helm|colima|k3s) echo orchestrator ;;
      npm|pnpm|yarn|pip|pip3|uv|uvx|brew|scoop|choco|apt|apt-get) echo package ;;
      node|python|python3|ruby|perl|bash|sh|wsl) echo runtime ;;
      ssh|scp|rsync|sshpass) echo remote ;;
      "") : ;;
      *) echo "other:$head_cmd" ;;
    esac
  done
}

# ----- Self-test mode -----
if [ "$INPUT_MODE" = "test" ]; then
  PASS=0; FAIL=0; FAILED_NAMES=()
  TMPDIR_T=$(mktemp -d)
  trap 'rm -rf "$TMPDIR_T"' EXIT

  # Build a transcript: a user prompt, then one assistant message carrying the
  # given tool_use commands and final text.
  make_transcript() {
    local file="$1" text="$2"; shift 2
    : > "$file"
    printf '%s\n' '{"type":"user","message":{"content":"do the thing"}}' >> "$file"
    local uses="" c
    for c in "$@"; do
      case "$c" in
        # "@Grep" stands for a non-Bash tool_use so the TOOL: branch of
        # classify_media is exercised, not only the Bash command path.
        @*) uses="$uses$(jq -nc --arg n "${c#@}" '{type:"tool_use",name:$n,input:{}}')," ;;
        *)  uses="$uses$(jq -nc --arg c "$c" '{type:"tool_use",name:"Bash",input:{command:$c}}')," ;;
      esac
    done
    uses="${uses%,}"
    jq -nc --arg t "$text" --argjson u "[$uses]" \
      '{type:"assistant",message:{content:($u + [{type:"text",text:$t}])}}' >> "$file"
  }

  test_case() {
    local name="$1" expect_block="$2" text="$3"; shift 3
    local tf="$TMPDIR_T/t.jsonl" out
    make_transcript "$tf" "$text" "$@"
    out=$(jq -nc --arg p "$tf" '{transcript_path:$p}' | "$0" 2>/dev/null || true)
    local got=0
    printf '%s' "$out" | grep -q '"decision"' && got=1
    if [ "$got" = "$expect_block" ]; then
      echo "  PASS: $name"; PASS=$((PASS+1))
    else
      echo "  FAIL: $name (expected block=$expect_block got=$got)"
      FAIL=$((FAIL+1)); FAILED_NAMES+=("$name")
    fi
  }

  echo "=== Positive fixtures (should warn) ==="
  test_case "single process probe then categorical absence" 1 \
    "There is no local gateway by that name; no such service exists on this machine." \
    "pm2 list"
  test_case "single process probe with trailing filter is still one medium" 1 \
    "No such process. The tool does not exist locally." \
    "tasklist | grep -i hermes"
  test_case "single content-search then greenfield claim" 1 \
    "No counterpart exists in the codebase, so it has to be written from scratch." \
    "grep -rn 'handleRetry' src/"

  echo ""
  echo "=== Negative fixtures (should stay silent) ==="
  test_case "two media before the claim" 0 \
    "There is no local gateway by that name; no such service exists." \
    "pm2 list" "which hermes"
  test_case "scoped measurement report, not a categorical claim" 0 \
    "0-hit on this branch: there is no matching entry in this checkout." \
    "grep -rn 'foo' skills/"
  test_case "no absence claim at all" 0 \
    "Found 3 matching entries and updated the tracker accordingly." \
    "grep -rn 'foo' skills/"
  test_case "zero probes (restating an earlier finding)" 0 \
    "As established earlier, no such hook exists." \
    ""
  test_case "single probe but claim names its scope" 0 \
    "Not found under skills/hook-kit/resources — searched 1 pattern only." \
    "ls skills/hook-kit/resources"
  test_case "single probe, success report with the word absent nearby" 0 \
    "The guard is registered and the debug log shows it firing." \
    "git log --oneline -5"
  test_case "three media, categorical claim" 0 \
    "No such file or directory anywhere; the script does not exist." \
    "ls ~/.claude" "which foo" "git log --oneline -1"

  echo ""
  echo ""
  echo "=== Non-Bash tool_use fixtures (TOOL: branch) ==="
  test_case "single Grep tool then categorical absence" 1     "No such hook anywhere in the tree; it does not exist."     "@Grep"
  test_case "Grep plus Glob is two media" 0     "No such hook anywhere in the tree; it does not exist."     "@Grep" "@Glob"
  test_case "Grep plus a Write is still one probe medium" 1     "No such hook anywhere in the tree; it does not exist."     "@Grep" "@Write"
  test_case "Grep plus a Skill call is still one probe medium" 1     "No counterpart exists, so it needs to be built from scratch."     "@Grep" "@Skill"

  echo ""
  echo "PASS=$PASS FAIL=$FAIL"
  if [ "$FAIL" -gt 0 ]; then
    printf 'failed: %s\n' "${FAILED_NAMES[@]}"
    exit 1
  fi
  exit 0
fi

run_hook
exit 0
