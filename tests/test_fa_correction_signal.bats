#!/usr/bin/env bats
# Regression tests for skills/fa/resources/force-fa-on-correction-signal.sh.
#
# Two surfaces are locked down:
#   1. The classifier (`--classify`), which decides whether a user message is an
#      agent-fault correction. This is the part that regresses, because both of
#      its failure directions are costly: a miss means a mistake goes unrecorded,
#      and a false positive forces the FA procedure onto ordinary work, which is
#      how guards get routed around.
#   2. The Stop-event gate, which is the only thing that makes the injected
#      directive binding — an injected instruction the model ignores is not a gate.
#
# Korean fixtures are composed from UTF-8 octal escapes rather than written
# literally. scripts/check-hangul.py rejects Hangul in *.sh / *.md across this
# PUBLIC repo, and composing keeps the fixtures readable on a cp949 console.

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
GUARD="$REPO_ROOT/skills/fa/resources/force-fa-on-correction-signal.sh"

setup() {
  [ -f "$GUARD" ] || skip "guard not found: $GUARD"
  command -v python3 >/dev/null || skip "python3 not available"

  # Korean fixture tokens (romanization - meaning).
  KO_NURAK=$(printf '\353\210\204\353\235\275')                   # nurak      - omission
  KO_JEONGJEONG=$(printf '\354\240\225\354\240\225')              # jeongjeong - correction
  KO_BUJEOKJEOL=$(printf '\353\266\200\354\240\201\354\240\210')   # bujeokjeol - inappropriate
  KO_JOESONG=$(printf '\354\243\204\354\206\214\355\225\251\353\213\210\353\213\244')  # joesong-hamnida - "I am sorry"
  KO_JALMOT=$(printf '\354\236\230\353\252\273')                  # jalmot     - wrong
  KO_ORYU=$(printf '\354\230\244\353\245\230')                    # oryu       - error
  KO_SILSU=$(printf '\354\213\244\354\210\230')                   # silsu      - mistake
  KO_PPAEMEOK=$(printf '\353\271\274\353\250\271')                # ppaemeok   - left out
  KO_WAE=$(printf '\354\231\234')                                 # wae        - why
  KO_NEGA=$(printf '\353\204\244\352\260\200')                    # ne-ga      - you
}

classify() {
  printf '%s' "$1" | bash "$GUARD" --classify
}

assert_correction() {
  local got
  got="$(classify "$1")"
  if [ "$got" != "CORRECTION" ]; then
    echo "expected CORRECTION, got '$got' for: $1" >&2
    return 1
  fi
}

assert_neutral() {
  local got
  got="$(classify "$1")"
  if [ "$got" != "NEUTRAL" ]; then
    echo "expected NEUTRAL, got '$got' for: $1" >&2
    return 1
  fi
}

# --- positives: Korean correction signals ----------------------------------

@test "korean omission signal with accusatory framing is a correction" {
  assert_correction "$KO_WAE $KO_NURAK"
}

@test "korean correction signal with accusatory framing is a correction" {
  assert_correction "$KO_WAE $KO_JEONGJEONG"
}

@test "korean inappropriate signal with second-person framing is a correction" {
  assert_correction "$KO_NEGA $KO_BUJEOKJEOL"
}

@test "korean wrong signal with accusatory framing is a correction" {
  assert_correction "$KO_WAE $KO_JALMOT"
}

@test "korean error signal with second-person framing is a correction" {
  assert_correction "$KO_NEGA $KO_ORYU"
}

@test "korean mistake signal with accusatory framing is a correction" {
  assert_correction "$KO_WAE $KO_SILSU"
}

@test "korean left-out signal with accusatory framing is a correction" {
  assert_correction "$KO_WAE $KO_PPAEMEOK"
}

# --- positives: apology / correction phrasing ------------------------------

@test "korean apology phrase alone is a correction" {
  assert_correction "$KO_JOESONG"
}

@test "english apology phrase alone is a correction" {
  assert_correction "sorry, that was my mistake"
}

# --- positives: pre-existing signals --------------------------------------

@test "the slash-command trigger is a correction" {
  assert_correction "/fix you skipped the test run"
}

@test "the fix: prefix is a correction" {
  assert_correction "fix: why no commit?"
}

@test "a pasted commit subject on a later line is not a correction" {
  # The explicit trigger is a first-line prefix. A git log excerpt whose subject
  # happens to read "fix: ..." is evidence being shown to the agent, not an
  # instruction to the agent.
  assert_neutral "here is the log I was looking at:
fix: tighten the squash gate
feat: add the dependency engine
which one landed first?"
}

@test "why-didnt-you phrasing is a correction" {
  assert_correction "why didn't you commit the change?"
}

@test "second-person omission accusation is a correction" {
  assert_correction "you skipped the verification step again"
}

# --- negatives: signal word in a non-correction context -------------------

@test "a signal word inside a file path is not a correction" {
  assert_neutral "open skills/fa/retrospect.md and the correction-policy.md section"
}

@test "a signal word inside an inline code span is not a correction" {
  assert_neutral 'why do we still need the `omission` flag and `--skip-missing`?'
}

@test "quoted documentation naming a fault is not a correction" {
  assert_neutral '> do not report an omission as fixed. why did you add that rule?'
}

@test "a signal word inside a fenced code block is not a correction" {
  assert_neutral 'review this:
```
WARN: omission detected, you skipped validation
```
does it look right?'
}

@test "a quoted string naming a fault is not a correction" {
  assert_neutral 'the doc says "you forgot to record the omission" - where is that defined?'
}

@test "neutral technical use of error and wrong is not a correction" {
  assert_neutral "the deploy script raises an error when the manifest is wrong"
}

@test "a third-party bug report without agent framing is not a correction" {
  assert_neutral "the new endpoint doesn't work, can you take a look?"
}

@test "an ordinary feature request is not a correction" {
  assert_neutral "add a regression test for the hangul scanner"
}

@test "a korean signal word inside a path is not a correction" {
  assert_neutral "skills/fa/${KO_NURAK}-check.md"
}

@test "empty input is not a correction" {
  assert_neutral ""
}

# --- UserPromptSubmit surface ---------------------------------------------

@test "UserPromptSubmit injects the FA directive for a correction" {
  run bash -c "python3 -c \"
import json
print(json.dumps({'hook_event_name':'UserPromptSubmit','prompt':'why did not you commit the change?'}))
\" | bash '$GUARD'"
  [ "$status" -eq 0 ]
  [[ "$output" == *"FA_CORRECTION_GATE"* ]]
  [[ "$output" == *"additionalContext"* ]]
}

@test "UserPromptSubmit stays silent for a neutral prompt" {
  run bash -c "python3 -c \"
import json
print(json.dumps({'hook_event_name':'UserPromptSubmit','prompt':'add a regression test for the hangul scanner'}))
\" | bash '$GUARD'"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- Stop surface (the enforcement half) ----------------------------------

# Writes a transcript whose last user message is $1, followed by one assistant
# turn built from the JSON content array $2, then runs the Stop hook over it.
run_stop() {
  local user_text="$1" assistant_content="$2"
  TRANSCRIPT="$BATS_TEST_TMPDIR/transcript.jsonl"
  python3 -c "
import json, sys
user_text, assistant_content, out = sys.argv[1], sys.argv[2], sys.argv[3]
rows = [
    {'type': 'user', 'message': {'role': 'user',
     'content': [{'type': 'text', 'text': user_text}]}},
    {'type': 'assistant', 'message': {'role': 'assistant',
     'content': json.loads(assistant_content)}},
]
with open(out, 'w', encoding='utf-8') as fh:
    for r in rows:
        fh.write(json.dumps(r) + '\n')
" "$user_text" "$assistant_content" "$TRANSCRIPT"
  python3 -c "
import json, sys
print(json.dumps({'hook_event_name': 'Stop',
                  'transcript_path': sys.argv[1],
                  'stop_hook_active': False}))
" "$TRANSCRIPT" | bash "$GUARD"
}

@test "Stop blocks when a correction turn never invoked Skill(fa)" {
  run run_stop "why didn't you commit the change?" '[{"type":"text","text":"Let me analyse."}]'
  [ "$status" -eq 0 ]
  [[ "$output" == *'"decision": "block"'* ]]
  [[ "$output" == *"FA_CORRECTION_GATE"* ]]
}

@test "Stop passes when the correction turn invoked Skill(fa)" {
  run run_stop "why didn't you commit the change?" \
    '[{"type":"tool_use","name":"Skill","input":{"skill":"fa","args":"retrospect"}}]'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "Stop passes for a namespaced Skill(es6kr:fa) invocation" {
  run run_stop "why didn't you commit the change?" \
    '[{"type":"tool_use","name":"Skill","input":{"skill":"es6kr:fa","args":"retrospect"}}]'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "Stop stays silent when the last user message is not a correction" {
  run run_stop "add a regression test for the hangul scanner" '[{"type":"text","text":"On it."}]'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "Stop respects stop_hook_active to avoid a block loop" {
  TRANSCRIPT="$BATS_TEST_TMPDIR/loop.jsonl"
  python3 -c "
import json, sys
rows = [{'type': 'user', 'message': {'role': 'user',
         'content': [{'type': 'text', 'text': \"why didn't you commit?\"}]}}]
with open(sys.argv[1], 'w', encoding='utf-8') as fh:
    for r in rows:
        fh.write(json.dumps(r) + '\n')
" "$TRANSCRIPT"
  run bash -c "python3 -c \"
import json, sys
print(json.dumps({'hook_event_name':'Stop','transcript_path':sys.argv[1],'stop_hook_active':True}))
\" '$TRANSCRIPT' | bash '$GUARD'"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "headless runs are exempt" {
  # The payload comes from a file, not a pipe: a headless run exits before
  # reading stdin, which would make a piped producer emit a BrokenPipeError
  # warning and pollute the assertion with noise the hook did not produce.
  PAYLOAD="$BATS_TEST_TMPDIR/headless.json"
  python3 -c "
import json, sys
with open(sys.argv[1], 'w', encoding='utf-8') as fh:
    json.dump({'hook_event_name': 'UserPromptSubmit',
               'prompt': 'why did not you commit?'}, fh)
" "$PAYLOAD"
  run env AGENT_HEADLESS=1 bash "$GUARD" < "$PAYLOAD"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
