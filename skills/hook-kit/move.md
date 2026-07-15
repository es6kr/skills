# Move

Move hook scripts from `~/.claude/scripts/` to `~/.claude/hooks/` and update paths in settings.json.

## Instructions

1. Read `~/.claude/settings.json`
2. Extract list of hooks using `~/.claude/scripts/` paths from settings.json
3. Use AskUserQuestion(multiSelect:true) to select which hooks to move
4. mv selected scripts to `~/.claude/hooks/`
5. Edit paths in settings.json to `~/.claude/hooks/`
6. Update paths for sub-scripts called by dispatchers (exclude those using SCRIPT_DIR-relative references)

**Note**: For dispatchers (like `bash-pretooluse-dispatcher.sh`) that call sub-scripts via `$SCRIPT_DIR` relative paths, the sub-scripts must be moved together to avoid broken references. Confirm via AskUserQuestion.
