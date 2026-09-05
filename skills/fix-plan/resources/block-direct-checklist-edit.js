#!/usr/bin/env node
// block-direct-checklist-edit.js
// Physically blocks direct edits on fix_plan.md and checklist.md via Edit/Write tools.
// Enforces that modifications must be routed through fix-plan skill scripts.
//
// Claude Code sessions are exempt: this guard exists to stop lower-capability
// harnesses (e.g. Antigravity/Gemini) from schema-corrupting direct edits.
// add_item.py and update_item.py now cover ADD and marker-flip/note-append
// respectively, but neither covers sync auto-check stamps or
// `## Pipeline Execution Log` entries — Claude Code sessions still need
// direct edits for those. Claude Code exposes CLAUDE_PROJECT_DIR (and, for
// plugin hooks, CLAUDE_PLUGIN_ROOT) to hook processes; other harnesses do
// not — this premise is unverified in this repo (no test asserts it) and
// should be re-checked if the exemption ever misfires.

const fs = require('fs');

if (process.env.CLAUDE_PROJECT_DIR || process.env.CLAUDE_PLUGIN_ROOT) {
  process.exit(0);
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
if (!filePath) {
  filePath = (input.tool_input && input.tool_input.path) || '';
}

if (filePath) {
  const norm = filePath.replace(/\\/g, '/');
  if (norm.endsWith('fix_plan.md') || norm.endsWith('checklist.md') || norm.includes('/fix_plan.md') || norm.includes('/checklist.md')) {
    if (process.env.ALLOW_CHECKLIST_DIRECT_EDIT === '1') {
      process.exit(0);
    }
    process.stderr.write('============================================================\n');
    process.stderr.write('⛔ [BLOCKED: HARD STOP] Direct text edit on checklist is strictly prohibited!\n');
    process.stderr.write(`Target File: ${filePath}\n`);
    process.stderr.write('Reason: Editing fix_plan.md or checklist.md via Edit/Write/replace tools corrupts schema.\n');
    process.stderr.write('Required Action: You MUST run fix-plan scripts in terminal via run_command/Bash:\n');
    process.stderr.write('  - ADD a new item:  python <skill-dir>/scripts/add_item.py --file <path> \\\n');
    process.stderr.write('        --action "..." --why "..." --how "..." [--marker "[BLOCKED:P1:external]"] [--dry-run]\n');
    process.stderr.write('  - UPDATE an existing item (flip marker / append a note): python <skill-dir>/scripts/update_item.py --file <path> \\\n');
    process.stderr.write('        --match "<substring of the action text>" [--set-marker "[x]"] [--append-note "..."] [--dry-run]\n');
    process.stderr.write('  - python <skill-dir>/scripts/detect_bloated_tasks.py --file <path>\n');
    process.stderr.write('  - python <skill-dir>/scripts/stale_check.py --root <path>\n');
    process.stderr.write('  - python <skill-dir>/scripts/cleanup.py --file <path>\n');

    process.stderr.write('============================================================\n');
    process.exit(2);
  }
}

process.exit(0);
