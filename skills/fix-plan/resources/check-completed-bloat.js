#!/usr/bin/env node
// check-completed-bloat.js
// Blocks edits if there are completed items older than the current week.
//
// Ported from check-completed-bloat.sh (2026-07-30) — the original shelled
// out to jq (x2) + a python one-liner per invocation (PreToolUse:Edit|Write,
// so on every file edit). Reimplemented fully in-process: no subprocess
// spawns at all. Logic kept 1:1.

const fs = require('fs');

// Local-date "YYYY-MM-DD" formatter. toISOString() converts to UTC first,
// which shifts the displayed date by a day in timezones ahead of UTC (e.g.
// KST) — dates here must stay in local-calendar terms to match the original
// python script's datetime.date (naive, local) behavior.
function localDateStr(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function safeParse(str) {
  try {
    return JSON.parse(str);
  } catch {
    return {};
  }
}

function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

const input = safeParse(readStdin());
let filePath = (input.tool_input && input.tool_input.file_path) || '';
if (!filePath) {
  filePath = (input.tool_input && input.tool_input.TargetFile) || '';
}

if (filePath && (filePath.includes('fix_plan.md') || filePath.includes('checklist.md'))) {
  if (fs.existsSync(filePath)) {
    const content = fs.readFileSync(filePath, 'utf8');
    const parts = content.split('## Completed');
    if (parts.length >= 2) {
      // parts[1] runs to end-of-file; stop at the next top-level "## " heading
      // (e.g. "## REPEAT") so later sections aren't mis-scanned as Completed entries.
      const rest = parts[1];
      const nextHeadingMatch = rest.match(/\n## /);
      const completedSection = nextHeadingMatch ? rest.slice(0, nextHeadingMatch.index) : rest;
      const items = completedSection.split('\n').filter((line) => line.trim().startsWith('-'));

      const today = new Date();
      // Current week starts on Monday.
      const dayOfWeek = (today.getDay() + 6) % 7; // Mon=0 ... Sun=6
      const monday = new Date(today);
      monday.setDate(today.getDate() - dayOfWeek);
      monday.setHours(0, 0, 0, 0);
      const mondayStr = localDateStr(monday);

      const dateRegex = /\b(20\d{2})-(\d{2})-(\d{2})\b/;
      const staleItems = [];

      for (const item of items) {
        const m = item.match(dateRegex);
        if (m) {
          const [, y, mo, d] = m;
          const itemDate = new Date(Number(y), Number(mo) - 1, Number(d));
          if (!Number.isNaN(itemDate.getTime()) && itemDate < monday) {
            staleItems.push([localDateStr(itemDate), item.trim().slice(0, 60)]);
          }
        }
      }

      if (staleItems.length > 0) {
        process.stderr.write(
          `ERROR: Completed section has ${staleItems.length} entries older than the current week (start: ${mondayStr}).\n`
        );
        process.stderr.write('Please run the weekly archiving script before editing.\n');
        for (const [d, text] of staleItems.slice(0, 5)) {
          process.stderr.write(`  - [${d}] ${text}...\n`);
        }
        process.exit(2);
      }
    }
  }
}

process.exit(0);
