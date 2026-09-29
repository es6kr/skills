#!/usr/bin/env node
// check-self-task-open-at-wrapup.js — Stop hook.
//
// Detects a cleanup/fix skill declaring its own wrap-up "complete" in the
// last assistant message while the self-registered tracking task it created
// for this very run (via TaskCreate, subject matching cleanup/fix's own
// naming convention) never reached a completed/deleted status via TaskUpdate.
//
// Responsibility: cleanup (run.md Step 5.5 "Self-Task Cleanup") + fix
// (step4-wrapup.md Measure 3) jointly own the underlying rule this backs.
// 3rd occurrence of failed-attempts.md class self-task-prune-gap-at-skill-wrapup
// (1st: fix/SKILL.md Step 4 prefix-based prune miss; 2nd: cleanup's own
// pre-registered Step 0-4.5+5 tasks left completed-but-unpruned; 3rd/this:
// cleanup's own Step-tracking task left at pending — never transitioned at
// all despite a "complete" report) — matrix commits 3rd occurrence to a
// mandatory hook, so this is that hook rather than another rule-only pass.
//
// Design mirrors check-session-import-gap.sh's envelope convention: reads
// transcript_path from stdin JSON, scans the JSONL directly (no TaskList API
// access from a hook process), emits a "decision":"block" reminder — never a
// hard failure, since a false positive here should not break unrelated work.

const fs = require('fs');

function safeParse(str) {
  try {
    return JSON.parse(str);
  } catch {
    return null;
  }
}

function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

const input = safeParse(readStdin()) || {};
if (input.stop_hook_active) process.exit(0);

const transcriptPath = input.transcript_path || '';
if (!transcriptPath || !fs.existsSync(transcriptPath)) process.exit(0);

let lines;
try {
  lines = fs.readFileSync(transcriptPath, 'utf8').split('\n').filter(Boolean);
} catch {
  process.exit(0);
}

// Self-tracking subject patterns owned by cleanup/fix's own procedures.
const SELF_TRACK_RE = /(^|[^a-zA-Z])(\/?cleanup\b)|^(🔍|🔧|🛠|🧪|🔄|📋)\s*fix:/u;
// A completion-declaration marker in the assistant's own prose — scoped to
// this class (cleanup/fix wrap-up), not a generic "done" detector.
const COMPLETE_MARKER_RE = /(cleanup\s*(완료|complete)|✅\s*cleanup|⚠️\s*cleanup\s*FAILED|fix.{0,20}(wrap-?up).{0,20}(완료|complete))/i;

const createdSubjectById = new Map(); // taskId -> subject
const finalStatusById = new Map(); // taskId -> last-seen status
let lastAssistantText = '';

for (const line of lines) {
  let entry;
  try {
    entry = JSON.parse(line);
  } catch {
    continue;
  }
  const message = entry && entry.message;
  if (!message || !Array.isArray(message.content)) continue;

  if (message.role === 'assistant') {
    for (const block of message.content) {
      if (block && block.type === 'text' && typeof block.text === 'string') {
        lastAssistantText = block.text;
      }
      if (block && block.type === 'tool_use' && block.name === 'TaskUpdate' && block.input) {
        const taskId = String(block.input.taskId || '');
        const status = block.input.status;
        if (taskId && status) finalStatusById.set(taskId, status);
      }
    }
  }

  if (message.role === 'user' && Array.isArray(message.content)) {
    for (const block of message.content) {
      if (block && block.type === 'tool_result' && block.content) {
        const text = Array.isArray(block.content)
          ? block.content.map((c) => (c && c.text) || '').join('')
          : String(block.content);
        const m = text.match(/^Task #(\d+) created successfully: (.+)$/m);
        if (m) createdSubjectById.set(m[1], m[2].trim());
      }
    }
  }
}

if (!COMPLETE_MARKER_RE.test(lastAssistantText)) process.exit(0);

const openSelfTracked = [];
for (const [taskId, subject] of createdSubjectById) {
  if (!SELF_TRACK_RE.test(subject)) continue;
  const status = finalStatusById.get(taskId);
  if (status !== 'completed' && status !== 'deleted') {
    openSelfTracked.push(`#${taskId} (${status || 'pending'}) ${subject}`);
  }
}

if (openSelfTracked.length === 0) process.exit(0);

const reason =
  '<skill-trigger name="cleanup">완료 보고와 동시에 자체 등록한 추적 task가 아직 completed/deleted로 전환되지 않았습니다: ' +
  openSelfTracked.join('; ') +
  '. TaskUpdate로 실제 상태를 갱신한 뒤 보고를 마무리하세요 (cleanup/run.md Step 5.5, fix/step4-wrapup.md Measure 3 참조).</skill-trigger>';

process.stdout.write(JSON.stringify({ decision: 'block', reason }));
process.exit(0);
