# Archive

Move a completed session out of an active project key to a long-term archive location, preserving the session's `.jsonl` and any associated metadata (custom-title, agent-name records that live inside the file itself).

## When to Use

- Session work is finished, but the transcript should be kept (not purged)
- The active project listing is getting noisy (too many old completed sessions)
- A specific session needs to be quoted/referenced later but not auto-loaded by Claude Code

## When NOT to Use

| Situation | Use instead |
|-----------|-------------|
| Session is dead (no assistant response, < 10 lines) | `purge` — permanent deletion is appropriate |
| Active session, just want a custom title | `rename` — keeps it loadable |
| Moving between active projects (not archiving) | `move` |
| Generic file archive (not a session `.jsonl`) | general-purpose `/archive` skill (`.bak/` move) |

## Destination

`~/.claude/.archive/<project-key>/<uuid>.jsonl`

- Outside `~/.claude/projects/` → not picked up by Claude Code's session loader, but still readable via `Read` / `jq`
- Preserves the original project key as a subdirectory so the source context is retrievable
- Filename keeps the original UUID — no rename, so URL references and chain links remain valid

## Procedure

### 1. Identify source

```bash
SESSION_ID="<uuid>"
SRC=$(find ~/.claude/projects -name "${SESSION_ID}.jsonl" -type f 2>/dev/null | head -1)
test -n "$SRC" || { echo "Session not found: $SESSION_ID"; exit 1; }
PROJECT_KEY=$(basename "$(dirname "$SRC")")
echo "Source: $SRC"
echo "Project: $PROJECT_KEY"
```

### 2. Verify session is archive-worthy

| Check | Command | Pass condition |
|-------|---------|----------------|
| File size > 0 | `[ -s "$SRC" ]` | Non-empty |
| Has assistant response | `jq -r 'select(.type=="assistant")' "$SRC" \| head -1` | Output non-empty |
| Not the current session | Compare `SESSION_ID` to `~/.claude/hooks/session-id-inject.sh` output | Must differ |

If the session is the **currently active** session (Claude Code has it open), the harness may rewrite the file at any moment. Defer archive until the user ends that session.

### 3. Pre-flight preview

```bash
DST_DIR="$HOME/.claude/.archive/$PROJECT_KEY"
DST="$DST_DIR/${SESSION_ID}.jsonl"

echo "Will move:"
echo "  FROM: $SRC ($(wc -c < "$SRC") bytes)"
echo "  TO:   $DST"
[ -e "$DST" ] && echo "WARN: destination already exists — abort"
```

Always show the preview before invoking the destructive move.

### 4. Execute archive

Use the script:

```bash
bash ~/.claude/skills/claude-session/scripts/archive-session.sh <session_id>
```

Or inline (single session):

```bash
mkdir -p "$DST_DIR"
mv "$SRC" "$DST"
```

### 5. Verify

```bash
[ -f "$DST" ] && [ ! -f "$SRC" ] && echo "OK: archived" || echo "FAIL"
ls -la "$DST"
```

### 6. Optional — record archive ledger

Append an entry to `~/.claude/.archive/INDEX.md` (or similar) so you can grep what was archived when:

```bash
LEDGER="$HOME/.claude/.archive/INDEX.md"
mkdir -p "$(dirname "$LEDGER")"
echo "- $(date +%Y-%m-%d) $PROJECT_KEY/$SESSION_ID — $(jq -r 'select(.type=="custom-title") | .customTitle' "$DST" 2>/dev/null | head -1)" >> "$LEDGER"
```

## Restoration

To bring an archived session back as an active project entry:

```bash
SESSION_ID="<uuid>"
PROJECT_KEY="<project>"
SRC="$HOME/.claude/.archive/$PROJECT_KEY/${SESSION_ID}.jsonl"
DST="$HOME/.claude/projects/$PROJECT_KEY/${SESSION_ID}.jsonl"
mkdir -p "$(dirname "$DST")"
mv "$SRC" "$DST"
```

After restore, Claude Code's session list will pick it up on next refresh.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Use `rm` after `cp` ("safe-copy-first") | `mv` — atomic, mv failure preserves source |
| 2 | Rename the file (UUID prefix, date suffix, etc.) | Keep `<uuid>.jsonl` — chain links + `/session url` rely on the UUID |
| 3 | Flatten into a single archive root without project subfolder | Preserve `<project-key>/<uuid>.jsonl` — source context is recoverable |
| 4 | Archive the **currently active** session | Wait until the session is closed; harness can rewrite an open file |
| 5 | Archive multiple sessions in a `find ... -exec` loop without preview | Single-session at a time; archive script reports each result |

## Self-check (before invoking)

1. Is the session file actually present in `~/.claude/projects/`?
2. Is the session **not** the current session (`/session id` differs)?
3. Has the destination path been previewed and confirmed not to already exist?
4. Did you preserve the UUID filename (no rename)?
5. Is the project subdirectory under `~/.claude/.archive/` getting created with the original key?
