'use strict';
const assert = require('node:assert');
const { test } = require('node:test');
const { selectTargets } = require('../resources/reap-orphaned-helper-procs.js');

// 1=Orca, 2=Orca child shell, 3=jq under that shell (Orca descendant -> protected)
// 10=orphan jq (parent 999 gone), 11=live jq (parent 1 alive), 12=orphan node hook
const PROCS = [
  { ProcessId: 1,  ParentProcessId: 0,   Name: 'Orca.exe',                  CommandLine: 'Orca.exe' },
  { ProcessId: 2,  ParentProcessId: 1,   Name: 'bash.exe',                  CommandLine: 'bash -c hook' },
  { ProcessId: 3,  ParentProcessId: 2,   Name: 'jq.exe',                    CommandLine: 'jq -r .a' },
  { ProcessId: 10, ParentProcessId: 999, Name: 'jq.exe',                    CommandLine: 'jq -r .a' },
  { ProcessId: 11, ParentProcessId: 1,   Name: 'jq.exe',                    CommandLine: 'jq -r .b' },
  { ProcessId: 12, ParentProcessId: 998, Name: 'node.exe',                  CommandLine: 'node C:\\Users\\x\\.claude\\hooks\\t.js' },
  { ProcessId: 13, ParentProcessId: 997, Name: 'node.exe',                  CommandLine: 'node C:\\app\\server.js' },
  { ProcessId: 14, ParentProcessId: 996, Name: 'cygwin-console-helper.exe', CommandLine: null },
];

test('orphaned leak processes are selected', () => {
  const ids = selectTargets(PROCS).map(p => p.ProcessId).sort((a, b) => a - b);
  assert.deepStrictEqual(ids, [10, 12, 14]);
});

test('Orca descendants are protected even at depth 2', () => {
  // pid 3 is Orca -> bash -> jq. A single-pass parent check would miss it.
  const ids = selectTargets(PROCS).map(p => p.ProcessId);
  assert.ok(!ids.includes(3), 'depth-2 Orca descendant must not be reaped');
});

test('processes whose parent is alive are never selected', () => {
  const ids = selectTargets(PROCS).map(p => p.ProcessId);
  assert.ok(!ids.includes(11));
});

test('unrelated node processes are not selected', () => {
  const ids = selectTargets(PROCS).map(p => p.ProcessId);
  assert.ok(!ids.includes(13));
});

test('null CommandLine does not throw', () => {
  assert.doesNotThrow(() => selectTargets(PROCS));
});
