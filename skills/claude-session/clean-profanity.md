# Clean Profanity

Scrub profanity tokens from a session JSONL file in place. Designed for sanitizing captured conversations before sharing or archiving.

## When to use

- Sharing a session externally and want to redact slurs
- Preparing an archive bundle that should not contain profanity
- Sanitizing transcripts before publishing as samples

## Usage

```bash
# Single session
python3 ~/.claude/skills/claude-session/scripts/clean-profanity.py <session_file.jsonl>

# Multiple sessions in one call
python3 ~/.claude/skills/claude-session/scripts/clean-profanity.py file1.jsonl file2.jsonl
```

Replaces matched tokens with `****` and rewrites the file in place. Reports `N lines modified` per file.

## Locating a target session

The script takes a file path, not a UUID. Resolve the UUID to a path first:

```bash
# Cross-project search by UUID
find ~/.claude/projects -name "<uuid>.jsonl"
```

Apply the script to the discovered path.

## Pattern source

Patterns are loaded from `~/.claude/skills/claude-session/data/profanity-patterns.json` (an array of `{pattern, replacement}` regex entries). If the file is absent, the script falls back to a minimal built-in pattern set.

To extend coverage, add entries to `data/profanity-patterns.json`. Use `\b` word boundaries to avoid matching substrings inside legitimate identifiers (e.g., `\bass\b` won't match `assistant`).

## Safety

- **Backup first**: the script overwrites the file in place. Copy to `*.bak` before running if reverting matters.
- **Run on closed sessions only**: do not run while the IDE has the session open (write race).
- **Verify after run**: `diff <backup> <cleaned>` to confirm only intended tokens were replaced.

## Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat `<uuid> remove profanity` as a rename — `rename-session.sh <uuid> "remove profanity"` sets the **title** to "remove profanity" and does NOT touch content | Use `clean-profanity.py <session_file>` to actually sanitize content |
| 2 | Run on the live current session JSONL | Apply to closed sessions only. The IDE writes to the open session asynchronously |
| 3 | Skip the backup on an irreplaceable session | Copy to `.bak` first, run the script, then diff to verify |
| 4 | Pass a UUID directly to the script | Script takes a file path. Resolve UUID → path via `find ~/.claude/projects -name "<uuid>.jsonl"` first |
