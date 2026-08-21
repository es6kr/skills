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
    // "## Completed" must match only as a line-start heading — a bare substring
    // split also matches backticked mentions inside item bodies, shifting the
    // scan window onto active sections and producing false stale counts.
    const headingMatch = content.match(/(?:^|\n)## Completed[ \t]*\r?(?:\n|$)/);
    if (headingMatch) {
      // The heading's remainder runs to end-of-file; stop at the next top-level
      // "## " heading (e.g. "## REPEAT") so later sections aren't mis-scanned
      // as Completed entries.
      const rest = content.slice(headingMatch.index + headingMatch[0].length);
      const nextHeadingMatch = rest.match(/(?:^|\n)## /);
      const completedSection = nextHeadingMatch ? rest.slice(0, nextHeadingMatch.index) : rest;
      // Only top-level entries (marker at column 0) count as "completed items" —
      // matches cleanup.py's own entry-boundary logic (indent == 0). A `.trim()`
      // before the startsWith check would also match indented sub-bullets like
      // "  - **Why**: ..." whose prose can cite unrelated historical dates
      // (e.g. the item's original registration date), which is not the entry's
      // completion date and must not be scanned for staleness.
      const items = completedSection.split('\n').filter((line) => /^-\s/.test(line));

      const today = new Date();
      // Current week starts on Monday.
      const dayOfWeek = (today.getDay() + 6) % 7; // Mon=0 ... Sun=6
      const monday = new Date(today);
      monday.setDate(today.getDate() - dayOfWeek);
      monday.setHours(0, 0, 0, 0);
      const mondayStr = localDateStr(monday);

      // Anchored at the start of the item's text (after the "- " marker) —
      // matches cleanup.py's own date extraction (re.match(r"^(\d{4}-\d{2}-\d{2})",
      // node.text), which is also start-anchored). A date appearing later in the
      // line (e.g. a "(YYYY-MM-DD 추가)" registration-date aside before a later
      // "완료(YYYY-MM-DD)" mention) is prose, not the entry's own leading date —
      // scanning it produced false "stale" hits on entries cleanup.py itself
      // never considers dated at all.
      const dateRegex = /^-\s*(20\d{2})-(\d{2})-(\d{2})\b/;
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
