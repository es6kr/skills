# Session Repair

Detects and repairs structural issues in session JSONL files.

## Quick Start

**Primary method — fully automated via `scripts/repair-session.py`** (backup → dedup → 400 error removal → orphan tool_result removal → chain repair → orphan parent repair → validation, all in one):

```bash
# Repair a specific session
python3 ~/.claude/skills/claude-session/scripts/repair-session.py <session_file>

# Preview without changes
python3 ~/.claude/skills/claude-session/scripts/repair-session.py <session_file> --dry-run
```

The script uses `os.replace` for atomic file swap, bypassing macOS zsh `mv -i` alias prompts that would hang background bash calls. Use the script even when running checks manually — it is the source of truth for the repair pipeline.

**Skill command invocation** (resolves session ID, then calls the script):

```bash
/session repair                          # Default: current session (uses SessionStart-hook-injected ID)
/session repair <session_id>             # Repair a specific session
/session repair --dry-run                # Preview only, no changes
/session repair --check-only             # Validate only (no repair)
```

**Manual fallback** (when the script is unavailable, or for surgical edits): jq/Python queries in the [Diagnostic Queries](#diagnostic-queries) and [jq Queries](#jq-queries) sections below. Avoid for routine repair — the manual flow has alias traps and surrogate-pair pitfalls (see §6 Invalid Surrogate Pair).

## Detectable Issues

### 1. Broken Chain

Treated as a broken chain if any of the following conditions apply:

1. A message with `isSidechain: false` is **missing the `parentUuid` field entirely**
2. A message has `saved_hook_context` (abnormal session termination)
3. A message has a `stop` field (forced session interruption)

**Important**: `parentUuid: null` is normal (e.g., first message). Only missing fields are problematic.

**Symptoms**: Session load failure, missing conversation history

```
msg1 (uuid: aaa, parentUuid: null)      ← Normal (null value)
msg2 (uuid: bbb, parentUuid: aaa)       ← Normal
msg3 (uuid: ccc)                        ← Problem! parentUuid field missing
msg4 (uuid: ddd, saved_hook_context: {})← Problem! Abnormal termination trace
msg5 (uuid: eee, stop: true)            ← Problem! Forced interruption trace
```

### 2. Orphan Tool Result

The `tool_use_id` in a `tool_result` block does not match any `tool_use` block in a previous message.

**Symptoms**: API Error 400
```
messages.N.content.0: unexpected tool_use_id found in tool_result blocks: toolu_xxx.
Each tool_result block must have a corresponding tool_use block in the previous message.
```

**Causes**: Message ordering issues, missing intermediate messages, or sync errors

### 3. Invalid Thinking Block Signature

A `thinking` block inside an assistant message has a corrupted or invalid `signature` field.

**Symptoms**: API Error 400
```
messages.N.content.0: Invalid `signature` in `thinking` block
```

**Causes**: Syncthing sync corruption, interrupted writes, or session file manipulation

**Fix**: Remove all thinking blocks from message content arrays:
```bash
jq -c --slurp '
  .[] |
  if (.message.content | type == "array") then
    .message.content = [.message.content[] | select(type != "object" or .type != "thinking")]
  else . end
' session.jsonl > session.tmp && mv session.tmp session.jsonl
```

**Important**: Removing thinking blocks alone does NOT remove existing `isApiErrorMessage: true` lines — those must be removed separately. Always run both steps together.

### 4. Duplicate UUIDs

Multiple messages with the same `uuid`.

**Symptoms**: Chain tracking errors, unexpected branching

### 5. Duplicate Messages (same message.id, different UUID)

The same API response recorded multiple times with different UUIDs due to **Syncthing sync conflicts**.

**Symptoms**: Abnormally large session file, repeated identical messages

**Detection method**:
```bash
# Check duplicates by message.id
grep -o '"id":"msg_[^"]*"' session.jsonl | sort | uniq -c | sort -rn | head -10
```

**Characteristics**:
- `uuid` is different but `message.id` is identical
- `requestId` is often also identical
- progress type entries can repeat thousands of times with identical content

### 6. Orphan Parent UUID

A message's `parentUuid` field is set to a value that **does not match any other message's `uuid`** in the same file. The field exists and is non-null, so the field-presence check (`has("parentUuid") | not`) misses it entirely.

**Symptoms**:
- Chain tracking errors despite the file passing the "missing `parentUuid` field" validation
- Session viewer rendering gaps (the parent reference dangles)
- Common after dedup: when `dedup-session.py` removes a duplicate, its dependents may still point at the removed UUID

**Causes**:
- Post-dedup leftovers — the removed message's UUID is still referenced by surviving children
- Syncthing/manual edits that delete a message but leave references
- Split operations that move a message without updating downstream references

**Detection**:
```bash
# Python — cross-reference all parentUuid values against the UUID set
python3 - <<'EOF'
import json, sys
path = sys.argv[1]
uuids = set()
records = []
with open(path, encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        try:
            obj = json.loads(line)
        except Exception:
            continue
        records.append((i, obj))
        if obj.get('uuid'):
            uuids.add(obj['uuid'])
for i, obj in records:
    parent = obj.get('parentUuid')
    if parent is not None and parent not in uuids:
        print(f"L{i}: uuid={obj.get('uuid','?')[:8]} parent={parent[:8]} type={obj.get('type')}")
EOF
```

**Fix**: Resolve the orphan `parentUuid` to the nearest **surviving ancestor** — follow the removed-node chain (a message this repair deleted → its own parent) until a message that still exists, or set `null` (a new root) when the ancestry is truly lost. **Never** re-link to the immediately preceding *file-order* message (see "File order ≠ chain order" below). `scripts/repair-session.py` handles this in pass [6/7] automatically (`_resolve_surviving_ancestor`); `scripts/dedup-session.py` does the same in its own Pass 6 (`resolve_parent`).

**Disclosure requirement (HARD STOP — do not report "repair complete" without this)**: when the ancestry is truly lost, both scripts print a `[WARN] N chain repair(s) had NO recoverable ancestor` block listing the affected `line`/`uuid`/`old_parent` — this is a genuine, pre-existing hole in the session's history (the true ancestor is missing from the file itself, not something the repair caused), and it is **irrecoverable from this file alone**. `Validation: PASS` only certifies structural soundness (no dangling references) — it says nothing about whether all history is chain-reachable. Before reporting a repair as complete:
1. If the `[WARN]` block is non-empty, quote the affected line/uuid list to the user — do not fold it into a blanket "repair complete" / "Validation: PASS" summary.
2. Cross-reference each affected line against nearby messages for a native compact-boundary marker (a `type: "user"` message whose entire `message.content` is the CLI's own locale-specific "compacted" notice, e.g. the English "Compacted" or its localized equivalent) or other user-visible content. If one lands there, explicitly tell the user that history above that point is genuinely missing from the file, that this predates the repair (verifiable against the `.bak` backup), and that it is not something the repair introduced or can restore.
3. Only after this disclosure — and only if the user asks for further recovery — investigate whether the lost content is retrievable through an out-of-band channel (RAG/Qdrant index if this session was ever ingested, another host's Syncthing copy, Time Machine, etc.). None of these are guaranteed; state plainly when no such copy exists.

### 7. Invalid Surrogate Pair (Broken Unicode)

A line contains a malformed `\uXXXX\uXXXX` UTF-16 surrogate pair (e.g., a high surrogate without a matching low surrogate). The session file itself becomes invalid JSON.

**Symptoms**:
- API Error 400: `The request body is not valid JSON: no low surrogate in string: line 1 column NNNNN`
- `jq` aborts mid-file with `parse error: Invalid \uXXXX\uXXXX surrogate pair escape at line N, column M`
- Manual `jq -c '...' session.jsonl > out` produces **silent truncation** — everything after the broken line is dropped without warning

**Causes**: Streaming response cut mid-character (network error, crash during write), Syncthing sync mid-write, or session file manipulation that split a multi-byte character.

**Why `jq` is dangerous here**: `jq -c` reads line-by-line but on parse error it aborts the entire stream. If the broken line is at position N of M, you lose lines N..M without any explicit error in the output file. The downstream procedure (mv tmp → session.jsonl) then silently truncates the session.

**Detection**:
```bash
# 1. Locate the parse error line
jq empty session.jsonl 2>&1 | head -3
#   parse error: Invalid \uXXXX\uXXXX surrogate pair escape at line 4524, column 765

# 2. Confirm via Python (json.loads gives a precise error position)
python3 -c "
import json, sys
with open('session.jsonl', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        try:
            json.loads(line)
        except json.JSONDecodeError as e:
            print(f'L{i}: {e}')
" | head -5
```

**Fix**: Drop the broken line. `scripts/repair-session.py` handles this automatically — broken lines parse to `data=None` and are passed through, then the validation step counts `invalid_json` to surface them. To drop instead of preserve:

```bash
# Python is preferred — drop lines that fail json.loads
python3 -c "
import json
import sys
import pathlib
src = pathlib.Path(sys.argv[1])
ok, dropped = [], 0
for line in src.read_text(encoding='utf-8').splitlines():
    if not line.strip():
        continue
    try:
        json.loads(line)
        ok.append(line)
    except json.JSONDecodeError:
        dropped += 1
src.with_suffix('.jsonl.bak2').write_text('\n'.join(ok) + '\n', encoding='utf-8')
print(f'dropped: {dropped}')
" session.jsonl
```

Then `mv session.jsonl.bak2 session.jsonl` (or use `os.replace` via Python to bypass `mv -i` alias).

## Instructions

### 1. Determine Target Session

**Default (no session ID argument): repair the current session.** Use the `Current session ID: {uuid}` line that the SessionStart hook (`~/.claude/hooks/session-id-inject.sh`) injects into conversation context — this is the same fast path used by `id.md`. The current session is the most common repair target (self-repair after a crash or chain break).

If session ID is provided as an argument:
- Treat that UUID as the target. Skip the prompt.

If no ID argument **and** the hook injection is missing (rare — hook misconfiguration or other environment):
1. Call `mcp__claude-sessions-mcp__list_projects`
2. Ask user to select a project
3. Call `mcp__claude-sessions-mcp__list_sessions`
4. Ask user to select a session

**Self-repair caveat**: Repairing the current session while it is loaded by Claude Code may cause the IDE to read stale data. After repair, advise the user to reload the window (`Cmd-R`) or restart the Extension Host. The destroy topic (`/session destroy`) has a related but distinct purpose (delete + restart).

### 2. Session File Path

```bash
~/.claude/projects/{project_name}/{session_id}.jsonl
```

### 3. Detection Order (all must be run)

1. **Detect duplicate message.id** (Syncthing conflict) — `grep -o '"id":"msg_[^"]*"' session.jsonl | sort | uniq -c | sort -rn | head -10`
2. **Detect API 400 error lines** — `grep -c '"isApiErrorMessage":true' session.jsonl`
   - If found, check error message: `grep '"isApiErrorMessage":true' session.jsonl | jq -r '.message.content[0].text' | head -3`
   - `Invalid signature in thinking block` → run thinking block removal first (see §3)
   - `unexpected tool_use_id` → orphan tool_result issue
3. **Detect broken chains** — jq query (missing `parentUuid` field)
4. **Detect orphan parent UUIDs** — Python cross-reference (parentUuid value not present as any uuid)
5. **Detect orphan tool_results** — jq query
6. **Detect duplicate UUIDs** — jq query

**Important**: If duplicate message.ids are found, **run dedup first** before the remaining checks. Other check results are unreliable while duplicates are present.

### 4. Repair Logic

#### Remove Duplicate Messages (by message.id)

Duplicates caused by Syncthing sync conflicts:

```bash
# Preview
python scripts/dedup-session.py session.jsonl --dry-run

# Execute (creates .dedup file)
python scripts/dedup-session.py session.jsonl
```

Script: [scripts/dedup-session.py](./scripts/dedup-session.py)

**When running from Claude Code**: Reference `scripts/dedup-session.py` relative to the skill base directory

#### Repair Broken Chain

**File order ≠ chain order (HARD invariant).** Do NOT rewrite a message's `parentUuid` to the previous *file-order* message. Claude Code sessions interleave sidechains (subagents), compact/resume boundaries, and branch points, so the true parent (`parentUuid`) frequently differs from the preceding line. Force-linearizing the chain to file order splices unrelated history into one mega-chain — it changes the effective leaf/root and re-attaches pre-compact history onto post-compact history, **inflating the active context** ("the context sizes merge across the compact boundary"). Measured on a real 30k-line session, the old force-sequential rebuild rewrote 6056 `parentUuid`s (3265 with a still-valid parent) and grew the leaf's active chain from ~70 to 10343 hops.

Correct handling per message:
- `parentUuid == null` → keep (chain ROOT / compact boundary — never bridge)
- parent points to a surviving `uuid` → keep exactly (valid parent)
- parent was a deduplicated / removed copy → resolve to the nearest **distinct surviving ancestor** (walk the dropped-copy remap / removed-node chain, stepping out of the message's own streaming group to avoid a self-loop)
- parent truly gone → set `null` (a new root), never bridge to the file-order-previous line

`scripts/dedup-session.py` Pass 6 (`resolve_parent`) and `scripts/repair-session.py` (`repair_orphan_parents` / `_resolve_surviving_ancestor`) implement this. `repair-session.py` also emits a `[WARN]` when a repair changes the active leaf or balloons the active-chain hop count — the regression signal for this class of bug.

#### Repair Orphan Tool Result

Options:
1. **Delete**: Remove the tool_result message
2. **Attempt matching**: Find a nearby tool_use block and link them (risky)

Deletion is the safer choice in most cases.

### 5. Output Results

**Dry-run/Check-only mode**:
```
## Session Repair Preview

Session: {session_id}

| Check Item | Result |
|------------|--------|
| Duplicate message.id | 0 |
| Broken chains | 2 (1 first message = normal) |
| Orphan tool_results | 1 |
| Duplicate UUIDs | 0 |
| Total messages | 150 |

### Broken Chains (needs fix: 1)
| Line | UUID | Type | Fix |
|------|------|------|-----|
| 5 | a129f842 | assistant | → 270fe00a |

### Orphan Tool Results (needs deletion: 1)
| Line | UUID | orphan_ids |
|------|------|------------|
| 23 | 747d9a2d | toolu_01HEm... |

### Duplicate UUIDs (needs deletion: 3)
| Line | UUID | Type |
|------|------|------|
| 45 | a129f842 | assistant |
| 78 | a129f842 | assistant |
| 120 | b234c567 | user |

### Null-rooted orphan parents (irrecoverable — needs disclosure, not silence: 1)
| Line | UUID | Old parent (not found in file) |
|------|------|--------------------------------|
| 17697 | 91a6a600 | f34c0f68 |

Run without --dry-run to apply fixes.
```

**Note**: The first user message (Line 2) in a broken chain is excluded because `parentUuid: null` is normal. The "Null-rooted orphan parents" table is different from a normal broken-chain fix — it lists messages whose true ancestor could not be found ANYWHERE in the file (see repair-session.py / dedup-session.py's `[WARN] N chain repair(s) had NO recoverable ancestor` output). This table is present whether or not `--dry-run` is used; it must be surfaced to the user, not summarized away as "0 broken chains".

**Execute mode**:
```
## Session Repair Complete

- Backup: {session_id}.jsonl.bak
- Fixed chains: 2
- Removed orphan tool_results: 1
- Removed duplicate UUIDs: 3
- Total messages: 150 → 146
- Validation: PASS (structurally sound — see caveat below if any null-rooted lines exist)
```

**If the script's `[WARN] N chain repair(s) had NO recoverable ancestor` block is non-empty**, append this section — do not omit it even when validation otherwise shows PASS:

```
### ⚠️ Irrecoverable history gap(s): N

| Line | UUID | Old parent | Note |
|------|------|------------|------|
| 17697 | 91a6a600 | f34c0f68 | true ancestor not found anywhere in this file — pre-dates this repair |

History above these line(s) is disconnected from the active chain and this repair cannot restore it (the ancestor data is missing from the file, not merely mis-linked). Confirmed pre-existing by comparing against `{session_id}.jsonl.bak`. If one of these lines is a compact-boundary marker (the CLI's own "compacted" notice), rewinding past that point is not possible via this file.
```

## Diagnostic Queries

### Quick Status Check

```bash
# File size and line count
ls -lh session.jsonl && wc -l < session.jsonl

# Distribution by type
jq -r '.type // "null"' session.jsonl | sort | uniq -c | sort -rn

# Duplicate message.id (top 10)
grep -o '"id":"msg_[^"]*"' session.jsonl | sort | uniq -c | sort -rn | head -10

# Count of duplicate message.ids
grep -o '"id":"msg_[^"]*"' session.jsonl | sort | uniq -d | wc -l
```

## jq Queries

### Broken Chain Detection

**Important**: `parentUuid: null` is normal. Detect if any of the following conditions apply:
1. The `parentUuid` field is entirely absent
2. `saved_hook_context` is present (abnormal termination)
3. The `stop` field is present (forced interruption)

```bash
# Note: after to_entries, apply has() to .value
jq -c --slurp '
  . as $all |
  to_entries |
  map(select(
    .value.isSidechain == false and
    (.value.type | test("file-history-snapshot") | not) and
    .key > 0 and
    (
      (.value | has("parentUuid") | not) or
      (.value | has("saved_hook_context")) or
      (.value | has("stop"))
    )
  )) |
  map({
    line: (.key + 1),
    uuid: .value.uuid[0:8],
    type: .value.type,
    reason: (
      if (.value | has("saved_hook_context")) then "saved_hook_context"
      elif (.value | has("stop")) then "stop"
      else "missing_parentUuid"
      end
    ),
    fix: $all[.key - 1].uuid[0:8]
  })
' session.jsonl
```

### Orphan Tool Result Detection

**Important**: Must check whether the corresponding tool_use exists anywhere in the entire file (checking only previous messages will miss matches).

```bash
# Collect all tool_use ids from the entire file, then find tool_results with no match
# Note: use type check instead of select(.value.message.content != null) (shell escape issue)
jq -c --slurp '
  [.[] | .message.content? // [] | if type == "array" then .[] else empty end | select(.type == "tool_use") | .id] as $all_tool_uses |
  to_entries |
  map(
    select(.value.message.content | type == "array") |
    select([.value.message.content[] | select(type == "object" and .type == "tool_result")] | length > 0) |
    {
      line: (.key + 1),
      tool_use_ids: [.value.message.content[] | select(.type == "tool_result") | .tool_use_id],
      uuid: .value.uuid[0:8]
    } |
    select(([.tool_use_ids[] | select(. as $id | $all_tool_uses | index($id) | not)] | length) > 0) |
    {
      line: .line,
      uuid: .uuid,
      orphan_ids: [.tool_use_ids[] | select(. as $id | $all_tool_uses | index($id) | not) | .[0:20]]
    }
  )
' session.jsonl
```

**Repair method**: Delete lines containing orphan tool_results (starting from the highest line number!)
```bash
cp session.jsonl session.jsonl.bak
# Delete from the highest line number to avoid shifting line numbers
sed -i '' '40d' session.jsonl
sed -i '' '13d' session.jsonl
```

### Duplicate UUID Detection

```bash
# Use has() — != null causes shell escape issues
jq -s '
  [.[] | select(has("uuid")) | .uuid] |
  group_by(.) |
  map(select(length > 1) | {uuid: .[0][0:8], count: length})
' session.jsonl
```

### Remove Duplicate UUIDs

**Principle**: Among identical UUIDs, **keep only the first**, delete the rest.

```bash
# 1. Backup
cp session.jsonl session.jsonl.bak

# 2. Remove duplicates (keep first)
jq -c --slurp '
  reduce .[] as $item (
    {seen: {}, result: []};
    if $item.uuid == null then
      .result += [$item]
    elif .seen[$item.uuid] then
      .  # already seen — skip
    else
      .seen[$item.uuid] = true |
      .result += [$item]
    end
  ) | .result[]
' session.jsonl.bak > session.jsonl
```

**Detailed detection** (including line numbers to delete):
```bash
jq -c --slurp '
  reduce to_entries[] as $e (
    {seen: {}, dups: []};
    if $e.value.uuid == null then .
    elif .seen[$e.value.uuid] then
      .dups += [{line: ($e.key + 1), uuid: $e.value.uuid[0:8], type: $e.value.type}]
    else
      .seen[$e.value.uuid] = true
    end
  ) | .dups
' session.jsonl
```

### Repair Broken Chain

**Important**: `parentUuid: null` is normal — do not touch. Only add the field when it is missing entirely.

```bash
# 1. Backup
cp session.jsonl session.jsonl.bak

# 2. Apply repair (only when parentUuid field is missing)
jq -c --slurp '
  . as $all |
  to_entries |
  map(
    if (.value.isSidechain == false and
        (.value | has("parentUuid") | not) and
        (.value.type | test("file-history-snapshot") | not) and
        .key > 0)
    then .value + {parentUuid: $all[.key - 1].uuid}
    else .value
    end
  ) | .[]
' session.jsonl.bak > session.jsonl
```

### Remove Orphan Tool Results

```bash
# Get the list of line numbers containing orphan tool_results, then remove them
# Complex — running the skill is recommended
```

## Repair Incorrect Split

If messages ended up in the wrong session after `split_session`, recover by direct file manipulation.

### Scenario: Move the last N messages of a session to another session

```python
# uv run python - <<'EOF'
import json, shutil
from pathlib import Path

# ~ paths must be expanded with expanduser() (Python open() does not auto-expand ~)
SRC = Path('~/.claude/projects/{project}/{wrong_session}.jsonl').expanduser()
DST = Path('~/.claude/projects/{project}/{target_session}.jsonl').expanduser()
SPLIT_IDX = 309  # starting line to move (0-indexed)

# 1. Backup
shutil.copy2(SRC, str(SRC) + '.bak')
shutil.copy2(DST, str(DST) + '.bak')

# 2. Read SRC
with open(SRC, encoding='utf-8') as f:
    src_lines = f.readlines()

keep = src_lines[:SPLIT_IDX]
move = src_lines[SPLIT_IDX:]

# 3. Find last UUID in DST (new parentUuid)
with open(DST, encoding='utf-8') as f:
    dst_lines = f.readlines()

new_parent = next(
    json.loads(l)['uuid'] for l in reversed(dst_lines)
    if json.loads(l).get('uuid')
)

# 4. Messages to move: update parentUuid + sessionId
dst_session_id = DST.stem  # remove .jsonl
modified = []
for i, line in enumerate(move):
    obj = json.loads(line)
    if i == 0:
        obj['parentUuid'] = new_parent
    if 'sessionId' in obj:
        obj['sessionId'] = dst_session_id
    modified.append(json.dumps(obj, ensure_ascii=False) + '\n')

# 5. Append to DST, shrink SRC
with open(DST, 'a', encoding='utf-8') as f:
    f.writelines(modified)
with open(SRC, 'w', encoding='utf-8') as f:
    f.writelines(keep)
# EOF
```

### Chain Validation

After moving, verify the chain in the DST file is not broken:

```bash
jq -s '[.[1:] | .[] |
  select(.isSidechain == false and
         (.type | test("file-history-snapshot") | not) and
         (has("parentUuid") | not))
] | length' dst_session.jsonl
# Result should be: 0
```

## Edge Cases

### Items to Skip
- `file-history-snapshot` type: normal even without parentUuid
- `parentUuid: null` value: normal (first message, system messages, etc.)
- `isSidechain: true` messages: separate branch, different chain rules

### parentUuid Decision Criteria
- `parentUuid: null` → **Normal** (explicitly set to null)
- `parentUuid` field missing → **Problem** (field itself is absent)

### tool_result Special Cases
- Responses to multiple tool_uses can exist in a single message
- tool_use and tool_result can exist in the same message (parallel calls)

## Validation

Validate after repair:
```bash
# 1. Check duplicate message.id (Syncthing conflict)
grep -o '"id":"msg_[^"]*"' session.jsonl | sort | uniq -d | wc -l
# Result: 0

# 2. Check broken chains (only when parentUuid field is missing)
# Note: after slurp, has() can be used directly
jq -s '[.[1:] | .[] |
  select(.isSidechain == false and
         (.type | test("file-history-snapshot") | not) and
         (has("parentUuid") | not))
] | length' session.jsonl
# Result: 0

# 2b. Check orphan parent UUIDs (parentUuid value not present in file)
python3 - <<'EOF' session.jsonl
import json, sys
uuids = set()
records = []
with open(sys.argv[1], encoding='utf-8') as f:
    for line in f:
        try:
            obj = json.loads(line)
        except Exception:
            continue
        records.append(obj)
        if obj.get('uuid'):
            uuids.add(obj['uuid'])
orphans = sum(
    1 for obj in records
    if (p := obj.get('parentUuid')) is not None and p not in uuids
)
print(f"orphan parents: {orphans}")
EOF
# Result: orphan parents: 0

# 3. Check orphan tool_results (re-run detection query above)
# Result: []

# 4. Check duplicate UUIDs
jq -s '[.[] | select(has("uuid")) | .uuid] | group_by(.) | map(select(length > 1)) | length' session.jsonl
# Result: 0

# 5. JSON validity
jq empty session.jsonl && echo "Valid JSON"
```

## Requirements

- claude-sessions-mcp MCP server (for session list lookup)
- jq (for JSON parsing)
- Write permission on session files

## Notes

### jq Shell Escape Issues
- Avoid `!=` operator → use `test() | not` or `type == "array"` pattern instead
- Use `select(.field | type == "array")` or `select(has("field"))` instead of `select(.field != null)`

### has() Placement When Using to_entries
- `to_entries` transforms to `{key, value}` form
- **Wrong**: `has("parentUuid")` → applied to the entry object, always false
- **Correct**: `.value | has("parentUuid")` → applied to the original object

### Repair Order
1. Backup first (`.bak` extension)
2. **Run `dedup-session.py`** — must run before all other repairs
   - Removes duplicates based on message.id (including streaming intermediate results)
   - Auto-deletes orphan tool_results (5th pass)
   - Auto-repairs chain (6th pass)
3. **Remove 400 error lines** — lines with `isApiErrorMessage: true` + the preceding user message
4. Remove duplicate UUIDs (keep first only)
5. **Delete orphan tool_results** — manual line removal in steps 3–4 can create new orphans
6. **Repair broken chains** — line deletions in steps 3–5 break the chain; detect with jq query then repair
7. Always run validation queries after repair
8. **Check the `[WARN] N chain repair(s) had NO recoverable ancestor` output** — `Validation: PASS` only means no dangling references remain, not that every message's full history is chain-reachable. Report any such lines to the user explicitly (see "Detectable Issues" §6 disclosure requirement and the "Output Results" template above) instead of a blanket "repair complete"

### Cautions
- Deleting orphan tool_results can affect conversation flow
- `parentUuid: null` is normal (only repair when the field itself is absent)

### Syncthing Sync Conflicts
- Syncing `~/.claude/projects/` with Syncthing can cause conflicts
- The same message gets recorded multiple times with different UUIDs
- Mainly occurs in `assistant` and `progress` types with large-scale duplication
- Diagnose with: `grep -o '"id":"msg_[^"]*"' session.jsonl | sort | uniq -c | sort -rn`
- 8x or more duplicates suggest a Syncthing conflict
