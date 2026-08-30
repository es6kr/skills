#!/usr/bin/env node
// session-id-inject.js — Inject session/message context only when the current
// prompt asks for it (regex match on the prompt body).
//
// Usage: node session-id-inject.js [EventName]
//   - EventName defaults to "UserPromptSubmit"
//   - SessionStart is also supported but no-ops by default (use this hook on
//     UserPromptSubmit; the previous SessionStart registration was removed).
//
// Prompt patterns:
//   /(claude-)?session id ...                  → session UUID + transcript (legacy parity)
//   /<namespace> (qdrant-)?import ...          → session UUID + transcript + current message UUID
//   /cleanup [run]                             → same as import (cleanup's 3-C.1 calls RAG import)
//   anything else                              → exit 0 (no injection — saves context tokens)
//
// Keyword fallback rationale: when the user types "search qdrant" / "was this
// session saved" / etc. without an explicit slash command, the LLM still needs the
// current session UUID to query or correlate RAG chunks. Cheaper to inject
// proactively than to make the LLM guess the session UUID via heuristics (mtime
// of JSONLs is unreliable across split/compact). Per user request 2026-05-28.
//
// IMPORTANT: When adding a new caller that invokes the RAG import topic,
// update this regex AND the RAG import skill's matching pattern documentation.
//
// Ported from session-id-inject.sh (2026-07-30) — this rewrite exists purely to
// avoid MSYS2/Git-Bash per-pipe-stage fork/exec overhead on Windows (jq × several
// + sed + grep per invocation, measured ~3-4x slower than doing the same work
// in one Node process). Logic is kept 1:1 with the bash version.

const fs = require('fs');

const EVENT_NAME = process.argv[2] || 'UserPromptSubmit';

function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

function safeParse(str) {
  try {
    return JSON.parse(str);
  } catch {
    return {};
  }
}

const input = safeParse(readStdin());
const SESSION_ID = input.session_id || '';
const TRANSCRIPT = input.transcript_path || '';
const PROMPT = input.prompt || '';
const PROMPT_ID = input.prompt_id || '';

// Unix path conversion (Windows backslash + drive letter) — display only.
let TRANSCRIPT_UNIX = '';
if (TRANSCRIPT) {
  TRANSCRIPT_UNIX = TRANSCRIPT.replace(/\\/g, '/').replace(/^C:/, '/c');
}

// Read the trailing chunk of a file without loading huge transcripts whole.
function tailLines(filePath, maxLines, maxBytes = 2 * 1024 * 1024) {
  let fd;
  try {
    fd = fs.openSync(filePath, 'r');
  } catch {
    return [];
  }
  try {
    const size = fs.fstatSync(fd).size;
    const start = Math.max(0, size - maxBytes);
    const length = size - start;
    const buf = Buffer.alloc(length);
    fs.readSync(fd, buf, 0, length, start);
    const lines = buf.toString('utf8').split('\n').filter(Boolean);
    return maxLines ? lines.slice(-maxLines) : lines;
  } catch {
    return [];
  } finally {
    fs.closeSync(fd);
  }
}

// Resolve the current model id from the transcript's last assistant entry.
// The hook stdin JSON carries no model field; assistant entries in the JSONL do
// (.message.model). Trailing-chunk read keeps the scan cheap on large transcripts;
// empty at the very first prompt of a session (no assistant entry yet).
function resolveModel() {
  if (!TRANSCRIPT || !fs.existsSync(TRANSCRIPT)) return '';
  const lines = tailLines(TRANSCRIPT, 400);
  let model = '';
  for (const line of lines) {
    const obj = safeParse(line);
    if (obj.type === 'assistant' && obj.message && obj.message.model) {
      model = obj.message.model;
    }
  }
  return model;
}

function emitSessionOnly(extra) {
  const model = resolveModel();
  const modelLine = model ? `\nCurrent model: ${model}` : '';
  const additionalContext =
    `Current session ID: ${SESSION_ID}\n` +
    `Transcript: ${TRANSCRIPT_UNIX || 'unknown'}${modelLine}${extra}\n` +
    `Use this session ID and transcript path for /session repair, etc. Do not search for them.\n` +
    `To rename this session, use the /rename built-in command (do NOT call rename-session.sh, which is only for other sessions by ID).`;
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: EVENT_NAME,
        additionalContext,
      },
    }) + '\n'
  );
}

// Extract the most recent user message uuid from JSONL if prompt_id is absent.
// UserPromptSubmit usually fires after the prompt is appended; the tail-based
// lookup is the robust fallback.
function resolveMessageUuid() {
  if (PROMPT_ID) return PROMPT_ID;
  if (!TRANSCRIPT || !fs.existsSync(TRANSCRIPT)) return '';
  try {
    const stat = fs.statSync(TRANSCRIPT);
    const bufferSize = Math.min(stat.size, 65536); // read up to last 64KB
    if (bufferSize <= 0) return '';
    const buffer = Buffer.alloc(bufferSize);
    const fd = fs.openSync(TRANSCRIPT, 'r');
    try {
      fs.readSync(fd, buffer, 0, bufferSize, stat.size - bufferSize);
    } finally {
      fs.closeSync(fd);
    }
    const tailStr = buffer.toString('utf8');
    const lines = tailStr.split('\n').filter(Boolean);
    for (let i = lines.length - 1; i >= 0; i--) {
      const obj = safeParse(lines[i]);
      if (obj && obj.type === 'user' && typeof (obj.message && obj.message.content) === 'string') {
        if (obj.uuid) return obj.uuid;
      }
    }
  } catch (_) {}
  return '';
}

// Guard: bail if we don't even have a session id
if (!SESSION_ID) process.exit(0);

// SessionStart path: inject the session id + transcript path once, at session
// start, so the model always knows the current 36-char UUID without having to be
// asked. (SessionStart has no `.prompt`, so only the session-only payload applies.)
if (EVENT_NAME === 'SessionStart') {
  emitSessionOnly('');
  process.exit(0);
}

// session-only injection (no message UUID): /session id, and /fix-plan.
if (
  /^\/(claude-)?session[ \t]+id([ \t]|$)/.test(PROMPT) ||
  /^\/fix-plan($|[ \t])/.test(PROMPT)
) {
  emitSessionOnly('');
  process.exit(0);
}

if (
  /^\/[a-zA-Z0-9_-]+[ \t]+(qdrant-)?import([ \t]|$)/.test(PROMPT) ||
  /^\/cleanup($|[ \t]run([ \t]|$))/.test(PROMPT)
) {
  const muuid = resolveMessageUuid();
  if (muuid) {
    emitSessionOnly(`\nCurrent message UUID: ${muuid}`);
  } else {
    emitSessionOnly('\nCurrent message UUID: (unresolved — check JSONL tail)');
  }
  process.exit(0);
}

// Keyword fallback: prompt body mentions "qdrant", "rag", or "session" (case-insensitive).
if (/(^|[^A-Za-z])(qdrant|rag|session)([^A-Za-z]|$)/i.test(PROMPT)) {
  emitSessionOnly('');
  process.exit(0);
}

// Default: no injection.
process.exit(0);
