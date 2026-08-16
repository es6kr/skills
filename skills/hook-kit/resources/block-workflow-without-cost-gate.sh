#!/usr/bin/env bash
# PreToolUse:Workflow — Block agent fan-out launches without a disclosed,
# user-acknowledged agent-count estimate.
#
# Trigger: any Workflow tool call when the transcript lacks the canonical
#          cost-disclosure marker `agent-count estimate: <N>` in an assistant
#          TEXT block that is followed by at least one user entry (i.e. the
#          user saw the number and responded before the launch).
# Action: Deny with instructions to state the numeric upper bound + caps +
#         session-boundness, get approval, then retry.
#
# Background: an audit workflow was launched with an option-level "cost
# opt-in" phrase but no numeric scale (a 100+ agent worst case), no budget
# cap, and no session-boundness disclosure — the process exited and the
# entire spend produced nothing. The disclosure duty is the assistant's, so
# the marker is only honored inside assistant text blocks (tool echoes and
# user text do not satisfy it). Tracked in failed-attempts.md (grep
# "workflow.*budget").

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "Workflow" ]]; then
  exit 0
fi

TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
if [[ -z "$TRANSCRIPT" || ! -f "$TRANSCRIPT" ]]; then
  # No transcript to judge — conservative pass (headless/test harnesses).
  exit 0
fi

# Line number of the LAST assistant text block carrying the marker. Anchored to
# assistant .message.content[] text blocks — tool_use echoes and user text must
# not satisfy the disclosure duty.
MARKER_LINE=$(grep -n '"type":"assistant"' "$TRANSCRIPT" 2>/dev/null | while IFS=: read -r n j; do
  t=$(printf '%s' "$j" | jq -Rr 'fromjson? // empty | select(.type=="assistant") | [.message.content[]? | select(.type=="text") | .text] | join(" ")' 2>/dev/null) || true
  if printf '%s' "$t" | grep -qiE 'agent-count estimate:[[:space:]]*~?[0-9]+'; then
    echo "$n"
  fi
done | tail -1)

if [[ -n "$MARKER_LINE" ]]; then
  # Approval proxy: a user-type entry AFTER the disclosure (reply or ask answer).
  LAST_USER_LINE=$(grep -n '"type":"user"' "$TRANSCRIPT" 2>/dev/null | tail -1 | cut -d: -f1)
  if [[ -n "$LAST_USER_LINE" && "$LAST_USER_LINE" -gt "$MARKER_LINE" ]]; then
    exit 0
  fi
fi

{
  echo "DENIED: Workflow launch without a disclosed + acknowledged agent-count estimate."
  echo ""
  echo "Why blocked:"
  echo "  - Multi-agent fan-outs spend real tokens; an option-level 'cost opt-in' phrase"
  echo "    is not a numeric disclosure. A prior unbounded launch (100+ agent worst case,"
  echo "    no budget cap) died with the session and produced nothing."
  echo ""
  echo "Required action before retrying:"
  echo "  1. Tell the user the numeric upper bound using the canonical marker, e.g.:"
  echo "     'agent-count estimate: 24 (8 finders x 1 round + <=16 verifiers; hard caps in script)'"
  echo "  2. Disclose session-boundness for long runs (process exit kills the run)"
  echo "  3. Wait for the user's reply/ask answer approving that number"
  echo "  4. Ensure the script itself carries hard caps (rounds/maxItems/budget guard)"
  echo ""
  echo "Reference: workspace CLAUDE.md 'Agent Comms' fan-out cost gate;"
  echo "  failed-attempts.md (grep \"workflow.*budget\")"
} >&2

exit 2
