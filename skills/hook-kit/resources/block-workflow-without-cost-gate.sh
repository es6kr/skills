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

# Structural scan (last 400 lines) for the marker + a genuine user reply after
# it. Real user prompts carry string .message.content; tool_result entries
# also have "type":"user" but array .message.content — those must NOT satisfy
# the disclosure duty, or a tool result landing after the marker would pass
# the gate without the user ever seeing the estimate.
STATE=$(tail -n 400 "$TRANSCRIPT" 2>/dev/null | jq -rs '
  def txt(m): [m.content[]? | select(.type? == "text") | .text] | join(" ");
  [ .[] | select(type == "object") ] as $e
  | ([ range(0; ($e|length))
       | select($e[.].type == "assistant"
                and (txt($e[.].message // {}) | test("agent-count estimate:[[:space:]]*~?[0-9]+"; "i"))) ] | max // -1) as $mk
  | ([ range(0; ($e|length))
       | select($e[.].type == "user"
                and ((($e[.].message // {}).content | type) == "string")) ] | max // -1) as $lu
  | "\($mk)\t\($lu)"
' 2>/dev/null)

if [[ -n "$STATE" ]]; then
  MARKER_IDX=$(printf '%s' "$STATE" | cut -f1)
  USER_IDX=$(printf '%s' "$STATE" | cut -f2)
  if [[ "$MARKER_IDX" -ge 0 && "$USER_IDX" -gt "$MARKER_IDX" ]]; then
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
