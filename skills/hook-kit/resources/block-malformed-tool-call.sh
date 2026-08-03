#!/usr/bin/env bash
# Stop hook — detect a malformed tool call emitted as plain response text.
#
# Failure mode this guards (2026-07-03): the assistant sometimes serializes a
# tool call in the bare `<invoke name="X"><parameter name="Y">...` dialect
# (occasionally with a stray `course` prefix line) instead of the harness's
# antml:function_calls / antml:invoke envelope. The harness cannot parse the
# bare dialect, so it is rendered as conversation text and the tool NEVER RUNS.
# This is a generation-layer serialization glitch — no rule/skill/memory can
# prevent it, so a Stop-hook re-emit prompt is the only enforcement medium.
#
# Detection: the LAST assistant turn contains a literal `<invoke name="` marker
# OUTSIDE any fenced code block or inline-code span. Legitimate discussion of
# this bug wraps the marker in backticks (stripped below), so a bare occurrence
# is almost certainly an unparsed tool call.
#
# On match: exit 2 (block) with a reminder to re-emit using antml:invoke.

set -uo pipefail

INPUT=$(cat)

TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)

# Extract the last assistant turn's text. Prefer an inline payload; fall back to
# the transcript tail (mirrors block-cleanup-without-rag.sh).
RESPONSE=$(echo "$INPUT" | jq -r '.response // .assistant_message // empty' 2>/dev/null)
if [[ -z "$RESPONSE" && -n "$TRANSCRIPT_PATH" && -f "$TRANSCRIPT_PATH" ]]; then
  RESPONSE=$(tail -40 "$TRANSCRIPT_PATH" \
    | jq -r 'select(.type=="assistant") | .message.content[]?.text? // empty' 2>/dev/null \
    | tail -200)
fi

[[ -z "$RESPONSE" ]] && exit 0

# Pick a working python (Windows-safe probe — mirror check-hangul.sh).
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1 \
    && "$cand" -c "import sys; sys.exit(0 if sys.version_info[0]==3 else 1)" >/dev/null 2>&1; then
    PY="$cand"; break
  fi
done
[[ -z "$PY" ]] && exit 0   # no python → fail open (never block on infra gap)

HIT=$(printf '%s' "$RESPONSE" | "$PY" -c '
import sys, re
text = sys.stdin.read()
# Strip fenced code blocks and inline code so bug-discussion (backticked) is exempt.
text = re.sub(r"```.*?```", "", text, flags=re.S)
text = re.sub(r"`[^`]*`", "", text)
# Bare malformed tool-call marker (antml:invoke would carry the namespace prefix).
print("HIT" if re.search(r"<invoke\s+name=", text) else "")
' 2>/dev/null)

if [[ "$HIT" == "HIT" ]]; then
  cat >&2 <<'MSG'
BLOCKED: a tool call was serialized as plain text (`<invoke name="...">`), so the
harness did not parse it and the tool DID NOT RUN.

Re-emit the call using the antml:function_calls / antml:invoke envelope (the same
form every executed tool call in this session used). Do not output a bare
`<invoke>` / `<parameter>` element, and do not prefix it with a stray token.

If you were only DISCUSSING this format, wrap the marker in backticks so it is
treated as inline code, then resend.
MSG
  exit 2
fi

exit 0
