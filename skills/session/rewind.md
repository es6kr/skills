# Session Rewind (Direct JSONL / DB Truncation)

Provides direct truncation of conversation context (JSONL for Claude Code, SQLite DB for Antigravity) without reverting working directory source code files.

## Workflow & Interactive Flags

### 1. Engine Selection (`/session rewind`)

When `/session rewind` is invoked without flags, present an interactive choice for the target engine via `AskUserQuestion`:

- **1. Antigravity IDE** (`~/.gemini/antigravity-ide/conversations/*.db`)
- **2. Antigravity CLI** (`~/.gemini/antigravity-cli/conversations/*.db`)
- **3. Claude Code** (`~/.claude/projects/*/*.jsonl`)

### 2. UUID Selection (`/session rewind --<engine>`)

When invoked with an engine flag (or after engine selection), list recent session UUIDs with `mtime`, `steps/lines` count, and title, then present interactive UUID choices:

```bash
# List recent sessions for an engine
python3 scripts/rewind-session.py --list-sessions <antigravity-ide|antigravity-cli|claude-code>
```

### 3. Checkpoint & Ask Preservation Selection (`/session rewind --<engine> <uuid>`)

When a UUID is selected, fetch rewindable checkpoints (User Prompts & AskQuestions):

```bash
# List checkpoints (step index, type, summary)
python3 scripts/rewind-session.py --list-checkpoints <antigravity-ide|antigravity-cli> --uuid <uuid>
```

- **User Prompt Step**: Rewinds to right before the user prompt was sent.
- **Ask Question Step (Ask Preservation)**: Rewinds right after the `AskUserQuestion` tool call step so that the **Ask question prompt is preserved in context**, allowing the user to select a different answer without re-generating the model's Ask output.

### 4. Direct Truncation Execution

```bash
# Antigravity (IDE/CLI) SQLite DB & transcript.jsonl direct truncation
python3 scripts/rewind-session.py \
  --antigravity-ide \
  --uuid <uuid> \
  --step <cutoff_step_index>

# Claude Code JSONL direct truncation
python3 scripts/rewind-session.py \
  --claude-code \
  --uuid <uuid> \
  --line <keep_line_count>
```

## Safety & Backups

- SQLite DB files are atomically backed up as `<uuid>.db.bak`.
- Transcript logs are backed up as `transcript.jsonl.bak`.
- Local working directory source code files are **100% untouched**.
