#!/usr/bin/env node
// Stop event — Detect a cleanup/session-end completion report that includes
// the "Session ID:" identity line but omits the accompanying `/rename`
// recommendation (2-3 candidates) required by cleanup/run.md Step 5's
// "Session identity (mandatory)" row.
//
// Trigger: assistant response contains cleanup-completion or session-end markers
//          AND a "Session ID:" line
// Detection: no `/rename ` command token anywhere in the same response.
// Locale-specific marker variants live in ../../hook-kit/data/hangul-patterns.regex
// (git-ignored — this repo is PUBLIC, English-only source).
// Action: emit a block decision on stdout and exit 2, which stops the Stop event
//         and injects the reason as context for the next turn.
//
// Node rather than bash+jq: hook latency matters most on Windows, where every
// subshell and every `jq` invocation is a process spawn. The bash predecessor
// spawned `jq` up to three times and `grep` up to six times per Stop event.
//
// Locale-blindness background (why the union below is load-bearing):
// the predecessor sourced the same data file, but that file did not exist on the
// operator machine for 15 recorded recurrences of this class. The guard stayed
// registered and syntactically correct the whole time while its entry gate only
// ever saw the English baseline, so non-English completion reports never reached
// the check. Treat a missing/empty locale file as a live risk, not a no-op: an
// unpopulated extension point is indistinguishable from a disabled guard.

'use strict'

const fs = require('fs')
const path = require('path')

if (process.env.RALPH_LOOP === '1') process.exit(0)

// --- locale data ------------------------------------------------------------
// Format contract (mirrored in the data file's own header): one assignment per
// line, exactly NAME="<ERE alternation>". Comments and blanks ignored.
function loadLocalePatterns () {
  const file = path.join(__dirname, '..', '..', 'hook-kit', 'data', 'hangul-patterns.regex')
  const out = {}
  let raw
  try {
    raw = fs.readFileSync(file, 'utf8')
  } catch {
    return out // absent file → English baseline only (see header note)
  }
  for (const line of raw.split('\n')) {
    const m = /^([A-Z_]+)="(.*)"\s*$/.exec(line.trim())
    if (m) out[m[1]] = m[2]
  }
  return out
}

const LOCALE = loadLocalePatterns()

// Union, not override: the committed English baseline stays authoritative and
// the git-ignored file may only ADD variants. Which set wins must never depend
// on whether an untracked file happens to exist.
function union (localeKey, baseline) {
  const extra = LOCALE[localeKey]
  return extra ? `${extra}|${baseline}` : baseline
}

// Completion phrasings are included deliberately: a real wrap-up report is far
// more likely to be headed "cleanup complete" / "cleanup pass 2 complete" than
// to repeat the literal invocation "/cleanup run".
const CLEANUP_MARKERS = union(
  'HG_CLEANUP_MARKERS',
  '(^|\\s)/cleanup|cleanup run|cleanup wrap-up|cleanup complete|cleanup pass|cleanup finished|Session Ended|Session Cleanup|session-end report'
)
const SESSION_ID_MARKERS = union('HG_SESSION_ID_MARKERS', 'Session ID:|session\\s+id:')
// Words that, together with a markdown table, mark a response as the completion
// report itself rather than a mid-cleanup progress message. Used only to decide
// whether an ABSENT Session ID line is already due (see the omission branch).
const COMPLETION_WORDS = union('HG_COMPLETION_WORDS', 'complete|completed|finished|Session Ended|wrap-up')
// Row labels unique to run.md's Step 5 mandatory-rows table. Requiring one of
// these keeps the omission branch off unrelated "<something> cleanup finished"
// reports that merely happen to contain a table.
const CLEANUP_STEP_ROWS = union(
  'HG_CLEANUP_STEP_ROWS',
  'Self-Improve|Knowledge Persist|RAG Store|wip task|TaskList|Task prune|Weekly Report'
)

const hasI = (text, pattern) => new RegExp(pattern, 'i').test(text)

// --- input ------------------------------------------------------------------
function readStdin () {
  try {
    return fs.readFileSync(0, 'utf8')
  } catch {
    return ''
  }
}

function lastAssistantText (transcriptPath) {
  let raw
  try {
    raw = fs.readFileSync(transcriptPath, 'utf8')
  } catch {
    return ''
  }
  const lines = raw.split('\n').filter(Boolean).slice(-50)
  for (let i = lines.length - 1; i >= 0; i--) {
    let rec
    try {
      rec = JSON.parse(lines[i])
    } catch {
      continue
    }
    if (rec && rec.type === 'assistant') {
      const content = (rec.message && rec.message.content) || []
      return content.map((c) => (c && c.text) || '').join('\n')
    }
  }
  return ''
}

let input = {}
try {
  input = JSON.parse(readStdin() || '{}')
} catch {
  process.exit(0)
}

let response = input.response || input.transcript || input.assistant_message || ''
if (!response && input.transcript_path) response = lastAssistantText(input.transcript_path)
if (!response) process.exit(0)

function block (reason) {
  process.stdout.write(JSON.stringify({ decision: 'block', reason }, null, 2) + '\n')
  process.exit(2)
}

// --- checks -----------------------------------------------------------------

// Only fire on cleanup/session-end context responses.
if (!hasI(response, CLEANUP_MARKERS)) process.exit(0)

// A cleanup response that never reaches Step 5 is not a violation of this row
// yet — that is why an absent Session ID line cannot simply be treated as a
// violation. Split the two cases: still exempt mid-cleanup progress messages,
// but treat the omission as a violation once the response is clearly the
// completion report itself (a markdown table plus completion wording).
if (!hasI(response, SESSION_ID_MARKERS)) {
  const hasTable = /^\s*\|/m.test(response)
  if (hasTable && hasI(response, COMPLETION_WORDS) && hasI(response, CLEANUP_STEP_ROWS)) {
    block(
      "Cleanup/session-end completion report omits the 'Session identity (mandatory)' row entirely — no `Session ID:` line and therefore no `/rename` candidates either. cleanup/run.md Step 5's mandatory-rows table requires this row in BOTH the cleanup wrap-up table and any separate session-end report. Re-read that section's literal row text (do not reconstruct the table from memory of a prior pass — it silently drops rows) and re-emit the report with every mandatory row present: Session identity, 0 TaskList, 1 Commit, 2 Self-Improve, 3 Knowledge Persist, 3-C.1 RAG Store (separate row), 3-C.2 structured discovery chunk, 3-C.4 fix_plan sync when applicable, 4 Weekly Report, 5 wip task registration."
    )
  }
  process.exit(0)
}

// The row is satisfied if a `/rename` command token appears anywhere in the
// response (candidates are often listed as separate code spans).
if (/\/rename\s/.test(response)) process.exit(0)

block(
  "Cleanup/session-end report includes a 'Session ID:' line but no accompanying `/rename <model>-<topic>-<sessid8>` recommendation (2-3 candidates). cleanup/run.md Step 5's 'Session identity (mandatory)' row requires both together — re-read the row's literal text (do not reconstruct it from memory of a prior pass) and add the rename candidates as standalone `/rename ...` code spans (no label/colon inside the span, so a single copy-paste is directly runnable)."
)
