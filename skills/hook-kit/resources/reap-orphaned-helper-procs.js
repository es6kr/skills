#!/usr/bin/env node
// Stop hook (async): reap orphaned helper processes on Windows.
//
// Root cause this addresses: when Claude Code force-kills a hook parent
// (bash.exe) on Windows, the kill does not cascade to pipe-connected
// grandchildren. A `... | jq ...` invocation's jq then blocks forever on a
// stdin read that never sees EOF, and it keeps the hook's inherited stdout
// write handle open -- so the hook runner never observes EOF and the Stop
// event never completes. This script is a single process with no pipeline,
// so it cannot create that class of orphan itself.
//
// Windows-only. No-op elsewhere. Always exits 0.
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const LEAK_NAME = /^(jq|cygwin-console-helper|ssh|git|git-remote-https)\.exe$/i;
const NODE_LEAK = /(\.claude|hooks|check-checklist|check-completed|ccstatusline|statusline)/i;
const PROTECTED_NAME = /(orca|OpenConsole)/i;

/**
 * Pure selection logic -- no I/O, unit-testable.
 * A process is reaped only when all three hold:
 *   1. its name matches a known leak type,
 *   2. its parent PID no longer exists in the snapshot,
 *   3. it is not inside the descendant closure of an Orca/console-host process.
 */
function selectTargets(procs) {
  const alive = new Set();
  const children = new Map();
  for (const p of procs) {
    alive.add(p.ProcessId);
    if (!children.has(p.ParentProcessId)) children.set(p.ParentProcessId, []);
    children.get(p.ParentProcessId).push(p.ProcessId);
  }

  // Full descendant closure via BFS. A single pass over an unordered list
  // protects descendants deeper than one level only by luck of iteration order.
  const guarded = new Set();
  const queue = [];
  for (const p of procs) {
    if (PROTECTED_NAME.test(p.Name || '') || /orca/i.test(p.CommandLine || '')) {
      if (!guarded.has(p.ProcessId)) { guarded.add(p.ProcessId); queue.push(p.ProcessId); }
    }
  }
  while (queue.length) {
    for (const kid of children.get(queue.shift()) || []) {
      if (!guarded.has(kid)) { guarded.add(kid); queue.push(kid); }
    }
  }

  return procs.filter((p) => {
    const name = p.Name || '';
    const isLeak = LEAK_NAME.test(name)
      || (/^node\.exe$/i.test(name) && NODE_LEAK.test(p.CommandLine || ''));
    return isLeak && !alive.has(p.ParentProcessId) && !guarded.has(p.ProcessId);
  });
}

function snapshot() {
  const ps = 'Get-CimInstance Win32_Process | '
    + 'Select-Object ProcessId,ParentProcessId,Name,CommandLine | '
    + 'ConvertTo-Json -Compress -Depth 2';
  const r = spawnSync(
    'powershell.exe',
    ['-NoProfile', '-NonInteractive', '-Command', ps],
    { encoding: 'utf8', timeout: 20000, stdio: ['ignore', 'pipe', 'ignore'], windowsHide: true },
  );
  if (r.status !== 0 || !r.stdout) return null;
  let parsed;
  try { parsed = JSON.parse(r.stdout); } catch { return null; }
  return Array.isArray(parsed) ? parsed : [parsed];
}

function appendLog(killed) {
  try {
    const dir = path.join(os.homedir(), '.claude', 'logs');
    fs.mkdirSync(dir, { recursive: true });
    fs.appendFileSync(
      path.join(dir, 'reap-orphaned-helper-procs.log'),
      `${new Date().toISOString()}\treaped ${killed.length} orphan(s): ${killed.join(',')}\n`,
      'utf8',
    );
  } catch { /* logging must never break the hook */ }
}

function main() {
  // Always drain stdin so the caller's pipe reaches EOF even on an early exit.
  try { fs.readFileSync(0); } catch { /* no stdin attached */ }

  if (process.platform !== 'win32') return;

  const procs = snapshot();
  if (!procs) return;

  const killed = [];
  for (const t of selectTargets(procs)) {
    try { process.kill(t.ProcessId); killed.push(`${t.Name}:${t.ProcessId}`); } catch { /* already gone */ }
  }
  if (killed.length) appendLog(killed);
}

if (require.main === module) { main(); process.exit(0); }

module.exports = { selectTargets };
