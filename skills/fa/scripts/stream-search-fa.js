#!/usr/bin/env node
// stream-search-fa.js — streaming/async recurrence-check search over the FA store.
//
// Why this exists: fix/SKILL.md Step1 Stage1 ("exact-match grep") runs against
// failed-attempts.md, which grows unbounded (10K+ lines in an active install)
// plus its archive/ siblings. A single blocking `grep -r` over the whole store
// pays the full-file cost on every call and, on this machine, has failed
// outright mid-scan with no partial result. This script reads each file as a
// stream and emits matches as they're found (one JSON line per match), so a
// slow or interrupted run still surfaces whatever it already matched instead
// of returning nothing.
//
// Usage:
//   node stream-search-fa.js <pattern> [--dir <FA_DATA_DIR>] [--ignore-case]
//     [--max-matches N] [--json]
//
// <pattern> is a plain-text substring (not a regex) — the same "2-3 key
// keywords" fix.md's Stage 1 asks for. Matching is per-line, case-sensitive
// by default.
//
// Exit code is always 0 (a "no matches" result is not an error — the caller
// still needs to proceed to Stage 0/2 either way). stderr carries only
// fatal setup errors (e.g. the target directory does not exist).

"use strict";

const fs = require("fs");
const path = require("path");
const readline = require("readline");

function parseArgs(argv) {
  const args = { pattern: null, dir: null, ignoreCase: false, maxMatches: 500, json: false };
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--dir") { args.dir = argv[++i]; continue; }
    if (a === "--ignore-case" || a === "-i") { args.ignoreCase = true; continue; }
    if (a === "--max-matches") { args.maxMatches = parseInt(argv[++i], 10) || args.maxMatches; continue; }
    if (a === "--json") { args.json = true; continue; }
    if (a === "--help" || a === "-h") { args.help = true; continue; }
    rest.push(a);
  }
  args.pattern = rest[0] || null;
  return args;
}

function usage() {
  process.stdout.write(
    "Usage: node stream-search-fa.js <pattern> [--dir <FA_DATA_DIR>] [--ignore-case] [--max-matches N] [--json]\n"
  );
}

// Walk a directory tree, yielding regular file paths. Skips dotfiles/backup
// artifacts (*.bak*, *sync-conflict*) that the FA store accumulates.
function* walk(dir) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const ent of entries) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) {
      yield* walk(full);
    } else if (ent.isFile()) {
      if (/\.bak|sync-conflict|\.tmp$/i.test(ent.name)) continue;
      yield full;
    }
  }
}

async function searchFile(filePath, needle, opts, onMatch) {
  const rl = readline.createInterface({
    input: fs.createReadStream(filePath, { encoding: "utf8" }),
    crlfDelay: Infinity,
  });
  let lineNo = 0;
  for await (const line of rl) {
    lineNo++;
    const hay = opts.ignoreCase ? line.toLowerCase() : line;
    if (hay.includes(needle)) {
      onMatch({ file: filePath, line: lineNo, text: line.trim().slice(0, 300) });
    }
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || !args.pattern) {
    usage();
    process.exit(args.help ? 0 : 1);
  }

  const dataDir =
    args.dir ||
    process.env.FA_DATA_DIR ||
    path.join(require("os").homedir(), ".claude", "skills", "cleanup", "data");

  if (!fs.existsSync(dataDir)) {
    process.stderr.write(`FA store directory not found: ${dataDir}\n`);
    process.exit(1);
  }

  const needle = args.ignoreCase ? args.pattern.toLowerCase() : args.pattern;
  let matchCount = 0;
  let fileCount = 0;

  for (const file of walk(dataDir)) {
    fileCount++;
    if (matchCount >= args.maxMatches) break;
    await searchFile(file, needle, args, (m) => {
      if (matchCount >= args.maxMatches) return;
      matchCount++;
      if (args.json) {
        process.stdout.write(JSON.stringify(m) + "\n");
      } else {
        process.stdout.write(`${m.file}:${m.line}: ${m.text}\n`);
      }
    });
  }

  if (!args.json) {
    process.stdout.write(
      `-- ${matchCount} match(es) across ${fileCount} file(s) under ${dataDir} (pattern: ${args.pattern})\n`
    );
    if (matchCount >= args.maxMatches) {
      process.stdout.write(`-- stopped at --max-matches ${args.maxMatches}; results may be incomplete\n`);
    }
  }

  process.exit(0);
}

main().catch((err) => {
  process.stderr.write(`stream-search-fa.js fatal error: ${err && err.stack ? err.stack : err}\n`);
  process.exit(0); // never block the caller's Stage 1 on a script bug
});
