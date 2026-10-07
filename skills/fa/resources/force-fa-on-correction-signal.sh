#!/usr/bin/env bash
# force-fa-on-correction-signal.sh
#
# Forces the FA (failed-attempts) record procedure to run FIRST when the user's
# message is an agent-fault correction, instead of the agent jumping straight
# into analysis, prose, or a fix.
#
# Two registrations, one file (same shape as edit-guard.sh):
#   UserPromptSubmit -> inject a HARD STOP directive before the turn starts.
#                       This is the only surface that lands BEFORE the model
#                       emits its first token, which is what "before analysis,
#                       prose, or other action" requires.
#   Stop             -> backstop. Verify a real Skill("fa") tool_use happened
#                       after that correction message; block if it did not.
#                       An injected directive the model ignores is not a gate
#                       (same lesson as check-slash-command-skill-invoked.sh:
#                       injected context is not an invocation).
#
# Detection contract — BOTH halves must hold on the SANITIZED text:
#   (1) FAULT SIGNAL  : omission / correction / inappropriate / apology /
#                       wrong / error / mistake / left-out, in Korean or English.
#   (2) AGENT FRAMING : the message points the fault at the agent (second
#                       person, accusatory "why did(n't) you", a bare apology,
#                       or an explicit fix/fa trigger).
#
# Requiring both is what keeps this usable. The single most dangerous failure
# mode for a gate like this is the false positive: "error" and "mistake" are
# everyday technical nouns ("paste the error log", "the test asserts the wrong
# column"). A guard that fires on those teaches people to route around it, so
# signal-alone is deliberately NOT enough.
#
# Sanitization removes the places a signal word appears without being a
# correction: fenced code, inline code spans, blockquoted documentation,
# explicitly quoted strings, URLs, and path-like tokens.
#
# Korean patterns are composed at runtime from UTF-8 octal escapes. This repo
# is PUBLIC and scripts/check-hangul.py rejects literal Hangul in *.sh / *.md;
# composing from escapes is the same technique check-hangul.py uses on itself.
# Each escape is commented with its romanization so the table stays readable.
#
# Test entry point (used by tests/test_fa_correction_signal.bats):
#   printf '%s' "<text>" | force-fa-on-correction-signal.sh --classify
#     -> prints CORRECTION or NEUTRAL, exit 0

set -uo pipefail

# ---------------------------------------------------------------------------
# Pattern table
# ---------------------------------------------------------------------------
# Korean fault signals (the tokens this gate was asked to cover).
KO_NURAK=$(printf '\353\210\204\353\235\275')                  # nurak      - omission
KO_JEONGJEONG=$(printf '\354\240\225\354\240\225')             # jeongjeong - correction
KO_BUJEOKJEOL=$(printf '\353\266\200\354\240\201\354\240\210')  # bujeokjeol - inappropriate
KO_JOESONG=$(printf '\354\243\204\354\206\214')                # joesong    - sorry (apology)
KO_JALMOT=$(printf '\354\236\230\353\252\273')                 # jalmot     - wrong
KO_ORYU=$(printf '\354\230\244\353\245\230')                   # oryu       - error
KO_SILSU=$(printf '\354\213\244\354\210\230')                  # silsu      - mistake
KO_PPAEMEOK=$(printf '\353\271\274\353\250\271')               # ppaemeok   - left out / skipped
KO_PPATTEU=$(printf '\353\271\240\353\234\250')                # ppatteu    - omitted (variant stem)

# Korean agent-framing markers.
KO_WAE=$(printf '\354\231\234')                                # wae     - why
KO_NEGA=$(printf '\353\204\244\352\260\200')                   # ne-ga   - you (casual)
KO_NIGA=$(printf '\353\213\210\352\260\200')                   # ni-ga   - you (casual variant)
KO_DANGSIN=$(printf '\353\213\271\354\213\240')                # dangsin - you (formal)
KO_HAESSEO=$(printf '\355\226\210\354\226\264')                # haesseo - "you did", accusatory
KO_HAENNA=$(printf '\355\226\210\353\202\230')                 # haenna  - "did you", accusatory

# Pre-existing signals carried over from fix-and-ambiguity-guard.sh
# (FIX_CLAIM_PHRASING), split by whether the phrasing is inherently aimed at the
# agent:
#   ACCUSATORY - "didn't you", "why not/again/keep". Simultaneously the fault
#                signal and the agent framing, so it joins BOTH sets.
#   NEUTRAL    - the "X doesn't work" / "X isn't working" family. This is an
#                ordinary bug report about third-party behaviour as often as it
#                is a complaint about the agent, so it is a SIGNAL ONLY and
#                still needs separate framing to fire. Putting it in both sets
#                made "the new endpoint doesn't work" a correction, which is
#                exactly the false positive this gate cannot afford.
FA_EXISTING_CLAIM_ACCUSATORY="${FA_EXISTING_CLAIM_ACCUSATORY:-(did|does|do|is|are|was|were|have|had)[[:space:]]?n.?t[[:space:]]+you|why[[:space:]]+(not|again|keep|no)}"
FA_EXISTING_CLAIM_NEUTRAL="${FA_EXISTING_CLAIM_NEUTRAL:-(did|does|do|is|are|was|were)[[:space:]]?n.?t[[:space:]]+work|is[[:space:]]?n.?t[[:space:]]+working}"

# A bare apology is itself a fault acknowledgement, so it satisfies both halves.
FA_APOLOGY_PATTERN="${FA_APOLOGY_PATTERN:-${KO_JOESONG}|sorry|apolog(y|ies|ise|ize)|my (bad|mistake)}"

FA_FAULT_SIGNAL="${FA_FAULT_SIGNAL:-${KO_NURAK}|${KO_JEONGJEONG}|${KO_BUJEOKJEOL}|${KO_JALMOT}|${KO_ORYU}|${KO_SILSU}|${KO_PPAEMEOK}|${KO_PPATTEU}|${FA_APOLOGY_PATTERN}|omitt?(ed|ing)|omission|left[[:space:]]+out|skipped|missing|missed|forgot|inappropriate|incorrect|wrong|mistake|misread|misreported|fabricat(ed|ion)|${FA_EXISTING_CLAIM_ACCUSATORY}|${FA_EXISTING_CLAIM_NEUTRAL}}"

FA_AGENT_FRAME="${FA_AGENT_FRAME:-${KO_WAE}|${KO_NEGA}|${KO_NIGA}|${KO_DANGSIN}|${KO_HAESSEO}|${KO_HAENNA}|${FA_APOLOGY_PATTERN}|why[[:space:]]+(did|do|does|is|are|was|were|have|not|again|keep)|you[[:space:]]+(did|do|forgot|missed|skipped|ignored|never|again)|your[[:space:]]+(answer|report|claim|analysis|output|change|edit|commit|summary|last)|don.?t[[:space:]]+(do|just|assume|guess)|stop[[:space:]]+(doing|assuming)|${FA_EXISTING_CLAIM_ACCUSATORY}}"

# Explicit triggers that are already a correction by definition.
FA_EXPLICIT_TRIGGER="${FA_EXPLICIT_TRIGGER:-^[[:space:]]*(/(fix|fa)([[:space:]]|$)|(fix|fa):)}"

# Optional locale overrides, same git-ignored data file the sibling guards read.
HG_DATA_FILE="$(dirname "$0")/../../hook-kit/data/hangul-patterns.regex"
[ -f "$HG_DATA_FILE" ] && . "$HG_DATA_FILE"
FA_FAULT_SIGNAL="${HG_FA_FAULT_SIGNAL:-$FA_FAULT_SIGNAL}"
FA_AGENT_FRAME="${HG_FA_AGENT_FRAME:-$FA_AGENT_FRAME}"

# ---------------------------------------------------------------------------
# sanitize — drop the contexts where a signal word is not a correction.
# ---------------------------------------------------------------------------
sanitize() {
  python3 -c '
import re
import sys

text = sys.stdin.read()

# Fenced code blocks, including an unterminated trailing fence.
text = re.sub(r"(?s)```.*?(```|\Z)", " ", text)
text = re.sub(r"(?s)~~~.*?(~~~|\Z)", " ", text)
# Inline code spans - the usual way a signal word gets named as an identifier.
text = re.sub(r"`[^`\n]*`", " ", text)
# Blockquoted documentation / pasted rule text.
text = re.sub(r"(?m)^[ \t]*>.*$", " ", text)
# Explicitly quoted strings (straight and typographic).
text = re.sub(r"\"[^\"\n]*\"", " ", text)
text = re.sub("“[^”\n]*”", " ", text)
# URLs.
text = re.sub(r"\bhttps?://\S+", " ", text)
# Path-like tokens: anything containing a slash, or a bare <name>.<ext>.
text = re.sub(r"\S*/\S*", " ", text)
text = re.sub(r"\S+\.(md|sh|py|js|ts|json|ya?ml|txt|log|regex|bats|toml|cfg|ini)\b", " ", text)
# Long-option flags (--no-verify, --skip-missing).
text = re.sub(r"(?<!\S)--[A-Za-z0-9][-A-Za-z0-9_]*", " ", text)

sys.stdout.write(text)
'
}

# ---------------------------------------------------------------------------
# classify — CORRECTION when (explicit trigger) OR (fault signal AND framing).
# ---------------------------------------------------------------------------
classify() {
  local raw clean
  raw="$(cat)"
  if [ -z "$raw" ]; then echo "NEUTRAL"; return 0; fi

  # Matched on the RAW FIRST LINE only: "/fix" and "fix:" are structural
  # prefixes, so sanitization would not change the verdict - but scanning every
  # line would also fire on a pasted Conventional Commit subject ("fix: ..." in
  # a git log excerpt), which is quoted evidence rather than a trigger.
  if printf '%s' "$raw" | head -1 | grep -qiE "$FA_EXPLICIT_TRIGGER"; then
    echo "CORRECTION"
    return 0
  fi

  clean="$(printf '%s' "$raw" | sanitize 2>/dev/null)" || clean=""
  if [ -z "${clean//[[:space:]]/}" ]; then echo "NEUTRAL"; return 0; fi

  if printf '%s' "$clean" | grep -qiE "$FA_FAULT_SIGNAL" \
     && printf '%s' "$clean" | grep -qiE "$FA_AGENT_FRAME"; then
    echo "CORRECTION"
    return 0
  fi
  echo "NEUTRAL"
}

if [ "${1:-}" = "--classify" ]; then
  classify
  exit 0
fi

# ---------------------------------------------------------------------------
# Hook runtime
# ---------------------------------------------------------------------------
# Headless self-suppression — the directive assumes a human-facing session,
# matching fix-and-ambiguity-guard.sh.
if [ "${RALPH_LOOP:-}" = "1" ] || [ "${AGENT_HEADLESS:-}" = "1" ]; then
  exit 0
fi

INPUT="$(cat)"
if [ -z "$INPUT" ]; then exit 0; fi

json_get() {
  printf '%s' "$INPUT" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
v = d.get(sys.argv[1], "")
print("" if v is None else (v if isinstance(v, str) else ("1" if v else "")))
' "$1" 2>/dev/null || true
}

DIRECTIVE='[FA_CORRECTION_GATE] This message is an agent-fault correction.

HARD STOP - before ANY analysis, prose, explanation, apology, tool call, or fix:
  1. Invoke Skill("fa") (the record topic is Skill("fa", "retrospect")).
  2. Follow its recurrence pre-check -> record -> escalation-stage procedure.
  3. Only then address the underlying issue.

Do NOT open with an explanation, a defence, or a restatement of the problem.
Reading this injected text is NOT an invocation - the procedure starts only at
a real Skill("fa") tool call, and a Stop-event gate verifies that call happened.'

EVENT="$(json_get hook_event_name)"

if [ "$EVENT" = "Stop" ]; then
  if [ -n "$(json_get stop_hook_active)" ]; then exit 0; fi
  TRANSCRIPT="$(json_get transcript_path)"
  if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then exit 0; fi

  # Anchor on the last genuine user-typed message, then report whether a
  # Skill("fa") tool_use (or a compact boundary) follows it. Window-bounded so
  # an old, long-since-handled correction stops nagging.
  STATE="$(tail -n "${FA_GATE_WINDOW:-400}" "$TRANSCRIPT" 2>/dev/null | python3 -c '
import base64, json, sys

rows = []
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    if isinstance(d, dict):
        rows.append((d, line))

def user_text(d):
    """Genuine user-typed text, or None for tool results / injected blocks."""
    if d.get("type") != "user" or d.get("isCompactSummary"):
        return None
    c = (d.get("message") or {}).get("content")
    if isinstance(c, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
            return None
        txt = " ".join(
            b.get("text", "") for b in c
            if isinstance(b, dict) and b.get("type") == "text"
        )
    elif isinstance(c, str):
        txt = c
    else:
        return None
    txt = txt.strip()
    # System-injected envelopes start with a tag or a bracketed marker.
    if not txt or txt[0] in "<[":
        return None
    return txt

idx, text = -1, ""
for i, (d, _) in enumerate(rows):
    t = user_text(d)
    if t is not None:
        idx, text = i, t
if idx < 0:
    sys.exit(0)

tail = "\n".join(raw for _, raw in rows[idx + 1:])
has_fa = "1" if '"'"'"skill":"fa"'"'"' in tail.replace(" ", "") or '"'"'"skill":"es6kr:fa"'"'"' in tail.replace(" ", "") else ""
compacted = "1" if '"'"'"isCompactSummary":true'"'"' in tail.replace(" ", "") else ""
print("\t".join([base64.b64encode(text.encode("utf-8")).decode("ascii"), has_fa, compacted]))
' 2>/dev/null)" || STATE=""

  if [ -z "$STATE" ]; then exit 0; fi
  B64="$(printf '%s' "$STATE" | cut -f1)"
  HAS_FA="$(printf '%s' "$STATE" | cut -f2)"
  COMPACTED="$(printf '%s' "$STATE" | cut -f3)"

  # Already recorded, or a compact boundary erased the tool_use evidence (its
  # absence is then not proof the call never happened) -> stay silent.
  if [ -n "$HAS_FA" ] || [ -n "$COMPACTED" ]; then exit 0; fi

  VERDICT="$(printf '%s' "$B64" | base64 -d 2>/dev/null | classify)"
  if [ "$VERDICT" != "CORRECTION" ]; then exit 0; fi

  python3 -c 'import json,sys; print(json.dumps({"decision":"block","reason":sys.argv[1]}))' "$DIRECTIVE"
  exit 0
fi

PROMPT="$(json_get prompt)"
if [ -z "$PROMPT" ]; then exit 0; fi
VERDICT="$(printf '%s' "$PROMPT" | classify)"
if [ "$VERDICT" != "CORRECTION" ]; then exit 0; fi

python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":sys.argv[1]}}))' "$DIRECTIVE"
exit 0
