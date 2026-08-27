#!/usr/bin/env node
// UserPromptSubmit hook: when the user message contains a task-completion keyword,
// inject a system-reminder guiding "verify + delete the task".
//
// Ported from wip-task-complete-detect.sh (2026-07-30) — same Windows MSYS2
// subprocess-spawn rationale as the other ports in this batch. Logic kept 1:1,
// including reading CLAUDE_USER_PROMPT from the environment (not stdin JSON —
// that's how the original script is wired) and loading locale detection
// patterns from the git-ignored data/ file with an English-only fallback so
// the PUBLIC copy of this hook works without that file.

const fs = require('fs');
const path = require('path');

const USER_MSG = process.env.CLAUDE_USER_PROMPT || '';

// Parses simple `VAR='value'` / `VAR="value"` bash-style assignment lines —
// matches the shape of hangul-patterns.regex data files across skills.
function loadBashVars(filePath) {
  const vars = {};
  if (!fs.existsSync(filePath)) return vars;
  const content = fs.readFileSync(filePath, 'utf8');
  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const m = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!m) continue;
    let [, name, rawValue] = m;
    rawValue = rawValue.trim();
    if (
      (rawValue.startsWith("'") && rawValue.endsWith("'")) ||
      (rawValue.startsWith('"') && rawValue.endsWith('"'))
    ) {
      rawValue = rawValue.slice(1, -1);
    }
    vars[name] = rawValue;
  }
  return vars;
}

// Matches the original's `dirname "$0"`/../data/hangul-patterns.regex — this
// resolves to ~/.claude/data/hangul-patterns.regex, which does not currently
// exist, so production runs on the English-only fallback below (same as the
// .sh version). Not "fixed" to point at the wip skill's data/ source — that
// would be a behavior change beyond a straight port.
const dataFile = path.join(__dirname, '..', 'data', 'hangul-patterns.regex');
const dataVars = loadBashVars(dataFile);

// Mirrors bash's ${VAR:-default} — falls back on unset OR empty string.
const WIP_COMPLETE_KEYWORDS =
  dataVars.WIP_COMPLETE_KEYWORDS ||
  'finished|completed|done in another session|handled it|already (did|handled)';
const WIP_TASKREF_PATTERN = dataVars.WIP_TASKREF_PATTERN || '(#[0-9]+|task [0-9]+)';

let completeRegex;
try {
  completeRegex = new RegExp(WIP_COMPLETE_KEYWORDS, 'i');
} catch (e) {
  process.exit(0);
}

if (completeRegex.test(USER_MSG)) {
  // No 'i' flag here — matches the original's `grep -oE` (no -i) for task refs.
  let matches = [];
  try {
    const taskrefRegex = new RegExp(WIP_TASKREF_PATTERN, 'g');
    matches = USER_MSG.match(taskrefRegex) || [];
  } catch (e) {
    matches = [];
  }
  const taskRefs = matches.slice(0, 5).join('\n');

  if (taskRefs) {
    process.stdout.write(
      `<system-reminder>\n[WIP Task Complete Detect] The user mentioned task completion: ${taskRefs}\nVerify the task via TaskGet, then delete it with TaskUpdate(status: "deleted").\nIf the user's message also contains other questions/instructions, handle those too.\n</system-reminder>\n`
    );
  } else {
    process.stdout.write(
      `<system-reminder>\n[WIP Task Complete Detect] The user mentioned task completion.\nCheck current tasks with TaskList and delete completed ones via TaskUpdate(status: "deleted").\nIf the user's message also contains other questions/instructions, handle those too.\n</system-reminder>\n`
    );
  }
}
