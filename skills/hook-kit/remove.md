# Remove

Remove hook entries from settings.json.

## Instructions

1. Read `~/.claude/settings.json`
2. Display all hooks organized by event
3. Use AskUserQuestion(multiSelect:true) to select which hooks to remove
4. Remove selected hook entries from settings.json via Edit
5. Remove the entire block if a matcher group becomes empty
6. Move orphaned scripts to `~/.claude/.bak/` (safe-delete rule)
