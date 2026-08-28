#!/usr/bin/env node
// PreToolUse:Edit|Write -block hook-registration edits made without consulting
// hook-kit's canonical inventory (skills/hook-kit/hook-registry.yaml) in this session.
//
// Targets:
//   - <any>/.claude/settings.json | settings.local.json when the edited content touches
//     hook registration keys ("hooks", "matcher", "command")
//   - <any>/hooks/hooks.json and <any>/.claude-plugin/hooks.json (plugin hook surfaces)
//
// Evidence of consultation (either satisfies the guard):
//   - the session transcript contains the literal "hook-registry.yaml" (a Read/Grep/Bash
//     that touched the registry earlier in this session)
//   - the edited content carries the literal token "hook-registry-consulted" (explicit,
//     audited override that stays visible in the file diff)
//
// Fail-open when no transcript path is available: without an evidence source the guard
// cannot evaluate, and blocking every hook edit in that state would be worse than nothing.
//
// Background: failed-attempts class "new hook registered by direct settings.json edit" reached
// its 4th recurrence on 2026-08-27 -hook registrations were triaged by "does a plugin hooks.json
// also list it" instead of by the registry's owner_skill / marketplace / status rows, and the
// registry plan (plan-hook-registry-schema.md) had to be pointed out by the user each time.
// The pattern is deterministic (target path + missing registry read), hence a PreToolUse guard.
// Registry topic: skills/hook-kit/registry.md
'use strict';

const fs = require('fs');

let raw = '';
try {
  raw = fs.readFileSync(0, 'utf8');
} catch (_) {
  process.exit(0);
}

let input;
try {
  input = JSON.parse(raw);
} catch (_) {
  process.exit(0);
}

const tool = String(input.tool_name || '');
if (tool !== 'Edit' && tool !== 'Write') process.exit(0);

const ti = input.tool_input || {};
const filePath = String(ti.file_path || '').replace(/\\/g, '/');
if (!filePath) process.exit(0);

const isHooksJson = /\/(hooks|\.claude-plugin)\/hooks\.json$/.test(filePath);
const isSettings = /\/\.claude\/settings(\.local)?\.json$/.test(filePath);
if (!isHooksJson && !isSettings) process.exit(0);

const content = [ti.content, ti.old_string, ti.new_string]
  .filter((v) => typeof v === 'string' && v.length > 0)
  .join('\n');

// settings.json edits that do not touch hook registration keys are out of scope
// (permissions, env, enabledPlugins, ...).
if (isSettings && !/"(hooks|matcher|command)"\s*:/.test(content)) process.exit(0);

if (content.includes('hook-registry-consulted')) process.exit(0);

let transcript = String(input.transcript_path || process.env.CLAUDE_TRANSCRIPT_PATH || '');
if (!transcript) process.exit(0);
// MSYS/Git-Bash drive prefix (/c/Users/...) is not a valid Windows path for Node - normalize it.
if (process.platform === 'win32' && /^\/[a-zA-Z]\//.test(transcript)) {
  transcript = transcript[1].toUpperCase() + ':' + transcript.slice(2);
}

let text = '';
try {
  text = fs.readFileSync(transcript, 'utf8');
} catch (_) {
  process.exit(0);
}

if (text.includes('hook-registry.yaml')) process.exit(0);

process.stderr.write(
  `[block-hook-registration-without-registry-read] ${filePath}\n\n` +
    'This edit changes hook registrations, but hook-kit\'s canonical inventory\n' +
    '(skills/hook-kit/hook-registry.yaml: owner_skill / marketplace / status / registrations per hook)\n' +
    'has not been read in this session. "A plugin hooks.json also lists it" is not the ownership\n' +
    'criterion -the registry row is.\n\n' +
    'Required before retrying:\n' +
    '  1. Read <marketplace>/skills/hook-kit/hook-registry.yaml (procedure: hook-kit registry.md)\n' +
    '  2. Decide add / remove / re-point / tombstone from that row, not from ad-hoc path checks\n' +
    '  3. Change the registry entry in the same commit as the registration change, then run\n' +
    '     hook_registry_verify.py --check\n' +
    'Explicit override (audited, stays in the diff): put the literal token hook-registry-consulted\n' +
    'in the edited content.\n'
);
process.exit(2);
