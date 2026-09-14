#!/usr/bin/env node
// check-plugin-load-failures.js — SessionStart hook.
//
// `claude plugin list` failures are silent: a plugin whose hooks/skills never
// load produces no crash and no error surfaced to the session — it just runs
// with that plugin's guards permanently absent. The only way to notice is to
// run `claude plugin list` by hand and read the Status lines. This hook runs
// that check once at every session start and surfaces any failure via
// additionalContext, so it can no longer go unnoticed for days.
//
// Real incident this closes: daegunsoftDev/skills' .claude-plugin/marketplace.json
// declared `name: dgs-plugins` while the marketplace was actually registered as
// `dgs` — 6 plugins (ask-user, code-quality, dgs, next-invocation-guard, wiki,
// agentify) silently failed to load for days, taking the ask/next enforcement
// guards and the TaskCreate tool down with them, with nothing in the session
// transcript to hint at it.
//
// Usage: node check-plugin-load-failures.js [EventName]
// Registered on: SessionStart

const fs = require('fs');
const { execSync } = require('child_process');

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

// Pure parse: given `claude plugin list` output text, return one string per
// failed plugin (name prefixed when resolvable from the preceding `❯ <name>`
// line, else the raw failing line). No side effects — kept separate from
// main() so a test can feed it canned text without spawning a real process.
function findFailures(output) {
  const failures = [];
  let currentPlugin = null;
  for (const line of output.split('\n')) {
    const nameMatch = line.match(/^\s*❯\s+(.+)$/);
    if (nameMatch) {
      currentPlugin = nameMatch[1].trim();
      continue;
    }
    if (line.includes('failed to load')) {
      failures.push(currentPlugin ? `${currentPlugin} — ${line.trim()}` : line.trim());
    }
  }
  return failures;
}

function buildAdditionalContext(failures) {
  return (
    `⚠️ ${failures.length} plugin(s) failed to load this session — their hooks/skills are silently absent:\n` +
    failures.map((f) => `  - ${f}`).join('\n') +
    `\nRun \`claude plugin list\` for full detail. A marketplace name mismatch ` +
    `(.claude-plugin/marketplace.json \`name\` vs the registered marketplace name in ` +
    `known_marketplaces.json) is a common cause.`
  );
}

function main() {
  const input = safeParse(readStdin());
  const EVENT_NAME = process.argv[2] || input.hook_event_name || 'SessionStart';

  let output;
  try {
    output = execSync('claude plugin list', { encoding: 'utf8', timeout: 5000 });
  } catch {
    // `claude` not resolvable on PATH, or the command errored/timed out.
    // Fail open — a broken check must not block session start. It is
    // indistinguishable from "all healthy" in this case, which is an
    // accepted trade-off for a non-blocking advisory hook.
    process.exit(0);
  }

  const failures = findFailures(output);
  if (failures.length === 0) process.exit(0);

  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: EVENT_NAME,
        additionalContext: buildAdditionalContext(failures),
      },
    }) + '\n'
  );
}

if (require.main === module) {
  main();
}

module.exports = { findFailures, buildAdditionalContext };
