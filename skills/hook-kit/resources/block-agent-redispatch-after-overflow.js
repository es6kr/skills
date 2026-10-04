#!/usr/bin/env node
// PreToolUse:Agent — deny a repeat Agent dispatch after one has already died of context overflow.
//
// Why this exists
// ---------------
// "Agent terminated early due to an API error: Prompt is too long" has recurred 10 times
// (failed-attempts class code-reviewer-dispatch-model-policy-not-consulted, status=hook-mandatory).
// Measurements taken 2026-09-28 close the two causes that earlier rounds suspected: the failure
// reproduces across BOTH model tiers, across BOTH tool-set sizes (a `Tools: *` agent and an
// 8-tool agent), with a ~500-byte prompt, and after the subagent merely read one 54KB file.
// The binding constraint is therefore the SUBAGENT'S OWN context budget — not the caller's
// prompt length, not the model tier, not the tool-schema size.
//
// Two corollaries the deny message states explicitly, because each was tried and failed:
//   - moving a long brief out of the prompt into a file the subagent reads does not help
//     (the bytes move from prompt into a Read; the subagent still holds them)
//   - per-file payload chunking is a closed direction (tried and failed twice)
//
// So once one dispatch in a session has overflowed, another of the same shape is a
// known-deterministic waste. The caller should move down the escalation ladder in
// consolidate/internal.md (rung 2 = a separate autonomous session, rung 3 = self-analysed)
// rather than re-dispatching.
//
// Node (not bash) deliberately: this parses a multi-MB JSONL transcript, and a
// jq-per-line pipeline is markedly slower on Windows where every subshell spawns a process.
//
// Bypass: put `[rung-escalated]` in the Agent prompt. A trailing reason is accepted in either
// spelling — `[rung-escalated] <reason>` and `[rung-escalated: <reason>]` both pass. That
// tolerance is deliberate: a sibling hook matched its `[bg-inherit-ok]` marker as an exact
// substring, so both natural spellings were rejected and the caller was re-blocked three times
// in a row. Match the marker's opening token, never the whole bracket.

'use strict';

const fs = require('fs');

const EXIT_ALLOW = 0;
const EXIT_DENY = 2;

// The failure sentence the harness emits. Matched case-insensitively, but only inside a
// structural failure carrier (see isFailureCarrier) — never in free prose.
const FAILURE_RE = /Agent terminated early due to an API error:\s*Prompt is too long/i;

// Opening token of the bypass marker. `\b` lets `]`, `:` or whitespace follow.
const MARKER_RE = /\[rung-escalated\b/i;

function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

// Does this transcript entry carry a REAL agent failure, as opposed to prose that merely
// quotes the sentence? This distinction is the whole false-positive defence: once a session
// has written the sentence into a commit message, a recurrence-log entry, or its own
// narration, a naive substring scan would block every later Agent spawn in that session.
//
// Accepted carriers:
//   1. a tool_result block (role=user, content array) — how a failed Agent spawn reports back
//   2. a <task-notification> string carrying status failed — how a background agent reports
function isFailureCarrier(entry) {
  const msg = entry && entry.message;
  if (!msg) return false;
  const content = msg.content;

  if (Array.isArray(content)) {
    for (const block of content) {
      if (!block || typeof block !== 'object') continue;
      if (block.type !== 'tool_result') continue;
      const text = typeof block.content === 'string'
        ? block.content
        : JSON.stringify(block.content || '');
      if (FAILURE_RE.test(text)) return true;
    }
    return false;
  }

  if (typeof content === 'string') {
    // A task-notification is the background-agent equivalent of a tool_result. Require the
    // notification wrapper so that ordinary prose quoting the sentence does not qualify.
    if (content.includes('<task-notification>') && FAILURE_RE.test(content)) return true;
  }

  return false;
}

function countPriorOverflows(transcriptPath) {
  let raw;
  try {
    raw = fs.readFileSync(transcriptPath, 'utf8');
  } catch {
    return 0;
  }
  let n = 0;
  for (const line of raw.split('\n')) {
    const s = line.trim();
    if (!s) continue;
    // Cheap pre-filter: skip lines that cannot possibly match before paying for JSON.parse.
    if (!FAILURE_RE.test(s)) continue;
    let entry;
    try {
      entry = JSON.parse(s);
    } catch {
      continue;
    }
    if (isFailureCarrier(entry)) n += 1;
  }
  return n;
}

function deny(count) {
  const plural = count === 1 ? 'dispatch has' : 'dispatches have';
  process.stderr.write(`[hook:block-agent-redispatch-after-overflow] BLOCKED (exit 2)

${count} Agent ${plural} already died of context overflow in this session
("Agent terminated early due to an API error: Prompt is too long").

Another dispatch of the same shape is a known-deterministic waste, not a retry.
This failure class has recurred 10 times, and these axes are CLOSED by measurement
— re-testing any of them spends a dispatch to reproduce a known result:

  - model tier        — reproduces on both a high and a low tier
  - tool-set size     — reproduces with a full tool set and with an 8-tool agent
  - prompt length     — reproduces with a ~500-byte prompt
  - brief-by-file     — moving the brief into a file the subagent reads does NOT help
                        (bytes move from the prompt into a Read; the subagent still holds them)
  - payload chunking  — per-file chunking was tried and failed twice

The binding constraint is the subagent's own context budget, which none of the above change.

Take the next rung of the escalation ladder in consolidate/internal.md instead:
  rung 2 — hand the whole task to a separate autonomous session
  rung 3 — do it yourself inline and disclose the engine in the output

If you ARE moving down the ladder and still need an Agent for it, say so in the prompt:
add [rung-escalated] (a trailing reason in either spelling is fine).
`);
}

function main() {
  const input = readStdin();
  if (!input.trim()) return EXIT_ALLOW;

  let payload;
  try {
    payload = JSON.parse(input);
  } catch {
    // Unparseable payload: fail open. A guard that blocks on its own parse error would
    // wedge every Agent spawn on a harness format change.
    return EXIT_ALLOW;
  }

  if (payload.tool_name !== 'Agent') return EXIT_ALLOW;

  const transcriptPath = payload.transcript_path;
  if (!transcriptPath || !fs.existsSync(transcriptPath)) return EXIT_ALLOW;

  const toolInput = payload.tool_input || {};
  const prompt = typeof toolInput.prompt === 'string' ? toolInput.prompt : '';
  if (MARKER_RE.test(prompt)) return EXIT_ALLOW;

  const count = countPriorOverflows(transcriptPath);
  if (count === 0) return EXIT_ALLOW;

  deny(count);
  return EXIT_DENY;
}

process.exit(main());
