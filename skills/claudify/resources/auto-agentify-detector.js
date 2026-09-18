#!/usr/bin/env node
// Auto-Agentify Detector Hook
// Called from the PostToolUse hook to detect repeated tool-use patterns.
//
// Usage: pass tool_name as an argument from the PostToolUse hook
// Output: prints "AUTO_AGENTIFY_CANDIDATE: ..." when a pattern is detected
//
// Ported from auto-agentify-detector.sh (2026-07-30) — same Windows MSYS2
// subprocess-spawn rationale as session-id-inject.js. Logic kept 1:1,
// including the pre-existing quirk that settings.json registers this hook
// with no argument, so TOOL_NAME always falls back to "unknown" in practice.

const fs = require('fs');
const os = require('os');
const path = require('path');

const TOOL_NAME = process.argv[2] || 'unknown';
const HOME = os.homedir();
const BUFFER_FILE = path.join(HOME, '.claude', 'data', 'tool-buffer.txt');
const PATTERN_FILE = path.join(HOME, '.claude', 'data', 'detected-patterns.jsonl');

fs.mkdirSync(path.dirname(BUFFER_FILE), { recursive: true });

// Ensure buffer file exists, then append the current tool.
if (!fs.existsSync(BUFFER_FILE)) fs.writeFileSync(BUFFER_FILE, '');
fs.appendFileSync(BUFFER_FILE, TOOL_NAME + '\n');

// Cap buffer size (most recent 30 lines).
let lines = fs
  .readFileSync(BUFFER_FILE, 'utf8')
  .split('\n')
  .filter((l) => l.length > 0);
lines = lines.slice(-30);
fs.writeFileSync(BUFFER_FILE, lines.join('\n') + (lines.length ? '\n' : ''));

function detectPatterns() {
  // 1. Detect 3+ consecutive identical tools (scans oldest→newest within the
  // window and stops at the first run that reaches 3, matching the original
  // bash loop order — not necessarily the most recent run).
  let consecutiveCount = 1;
  let prevTool = '';
  for (const tool of lines) {
    if (tool === prevTool) {
      consecutiveCount += 1;
    } else {
      consecutiveCount = 1;
    }
    prevTool = tool;

    if (consecutiveCount >= 3) {
      console.log(`AUTO_AGENTIFY_CANDIDATE: ${tool} 연속 ${consecutiveCount}회 반복`);
      return true;
    }
  }

  // 2. Detect a repeated 3-tool sequence (simple approach): compare the first
  // 3 of the last 6 tools against the last 3 tools.
  if (lines.length >= 6) {
    const last6 = lines.slice(-6);
    const seq1 = last6.slice(0, 3).join('→');
    const seq2 = last6.slice(3, 6).join('→');

    if (seq1 === seq2) {
      console.log(`AUTO_AGENTIFY_CANDIDATE: ${seq1} (2회 반복)`);
      fs.appendFileSync(
        PATTERN_FILE,
        JSON.stringify({ pattern: seq1, count: 2, time: new Date().toISOString() }) + '\n'
      );
      return true;
    }
  }

  return false;
}

detectPatterns();
process.exit(0);
