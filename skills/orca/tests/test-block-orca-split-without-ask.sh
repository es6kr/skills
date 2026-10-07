#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
GUARD="$ROOT/resources/block-orca-split-without-ask.sh"

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

PASS=0
FAIL=0

# Build a synthetic transcript JSONL with one assistant turn containing an
# AskUserQuestion tool_use block whose question/header/options are the given
# strings (joined with a space). An empty string means "no AskUserQuestion at
# all in this transcript".
make_transcript() {
  local text=$1 path="$TMPROOT/transcript_$RANDOM.jsonl"
  if [[ -z "$text" ]]; then
    printf '{"type":"user","message":{"role":"user","content":"hi"}}\n' > "$path"
  else
    python3 -c '
import json, sys
text = sys.argv[1]
path = sys.argv[2]
entry = {
    "type": "assistant",
    "message": {
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "name": "AskUserQuestion",
                "input": {
                    "questions": [
                        {
                            "question": text,
                            "header": "h",
                            "options": [{"label": "l", "description": "d"}],
                        }
                    ]
                },
            }
        ],
    },
}
with open(path, "w", encoding="utf-8") as f:
    f.write(json.dumps(entry) + "\n")
' "$text" "$path"
  fi
  printf '%s' "$path"
}

run_case() {
  local command=$1 expected=$2 transcript_text=${3-__none__} output transcript_path payload
  if [[ "$transcript_text" == "__none__" ]]; then
    payload=$(python3 -c '
import json, sys
print(json.dumps({"tool_name": "Bash", "tool_input": {"command": sys.argv[1]}}))
' "$command")
  else
    transcript_path=$(make_transcript "$transcript_text")
    payload=$(python3 -c '
import json, sys
print(json.dumps({
    "tool_name": "Bash",
    "tool_input": {"command": sys.argv[1]},
    "transcript_path": sys.argv[2],
}))
' "$command" "$transcript_path")
  fi
  output=$(printf '%s' "$payload" | "$GUARD" 2>&1 || true)
  if [[ "$expected" == blocked ]]; then
    if grep -q 'BLOCKED: orca terminal split / repo add without a dedicated prior ask' <<<"$output"; then
      PASS=$((PASS + 1))
    else
      FAIL=$((FAIL + 1))
      printf 'FAIL (expected blocked): %s\n  got: %s\n' "$command" "$output" >&2
    fi
  else
    if [[ -z "$output" ]]; then
      PASS=$((PASS + 1))
    else
      FAIL=$((FAIL + 1))
      printf 'FAIL (expected allowed): %s\n  got: %s\n' "$command" "$output" >&2
    fi
  fi
}

# 1. Non-split/non-repo-add command → always allowed, transcript irrelevant
run_case 'orca terminal list --json' allowed ''

# 2. split/repo-add with no transcript_path at all → allowed (cannot verify)
run_case 'orca terminal split --direction vertical' allowed

# 3. split with a transcript that has NO AskUserQuestion at all → blocked
run_case 'orca terminal split --direction vertical' blocked ''

# 4. repo add with a transcript that has NO AskUserQuestion at all → blocked
run_case 'orca repo add /path/to/repo' blocked ''

# 5. split with a confirming ask (harness + scope both present) → allowed
run_case 'orca terminal split --direction vertical' allowed \
  'Launch opus in the new pane for this workspace split?'

# 6. repo add with a confirming ask (model + repo scope) → allowed
run_case 'orca repo add /path/to/repo' allowed \
  'Register this repo add with claude as the harness?'

# 7. split with an ask naming only a harness/model, no split/scope token → blocked
run_case 'orca terminal split --direction vertical' blocked \
  'Should the next task use opus or sonnet?'

# 8. split with an ask naming only scope (repo add), no harness/model → blocked
run_case 'orca terminal split --direction vertical' blocked \
  'Should this repo add proceed for the new workspace?'

# 9. ORCA_ASK_CONFIRMED=1 opt-out bypasses the transcript check entirely
run_case 'ORCA_ASK_CONFIRMED=1 orca terminal split --direction vertical' allowed ''

# 10. orca-ide / orca-dev binary aliases are also gated
run_case 'orca-ide terminal split --direction vertical' blocked ''
run_case 'orca-dev repo add /path/to/repo' blocked ''

# 11. Quoted literal naming split/repo-add is not itself a split/repo-add
run_case 'echo "orca terminal split --direction vertical"' allowed ''

# 12. A Korean scope token (loaded at runtime from split-scope-ko.regex,
# never hardcoded in this .sh file's source) is recognized alongside a
# harness/model keyword.
ko_token=$(grep -vE '^\s*#|^\s*$' "$ROOT/resources/split-scope-ko.regex" | head -1)
run_case 'orca repo add /path/to/repo' allowed "claude harness needs ${ko_token} here"

printf '%d passed, %d failed\n' "$PASS" "$FAIL"
[[ "$FAIL" -eq 0 ]]
