#!/bin/bash
# Validate SKILL.md YAML frontmatter before write
# Triggered by: PreToolUse (Edit|Write)
# Returns exit 1 to block on validation error

# Only check SKILL.md files
if ! echo "$CLAUDE_FILE_PATHS" | grep -qE 'SKILL\.md$'; then
  exit 0
fi

FILE="$CLAUDE_FILE_PATHS"

# Skip if file doesn't exist yet (new file)
if [ ! -f "$FILE" ]; then
  exit 0
fi

# Check frontmatter opening
if ! head -1 "$FILE" | grep -q '^---$'; then
  echo "[yaml-validate] Error: SKILL.md must start with ---"
  exit 1
fi

# Extract frontmatter (lines between first and second ---)
FRONTMATTER=$(sed -n '2,/^---$/p' "$FILE" | head -n -1)

# Check required fields
if ! echo "$FRONTMATTER" | grep -q '^name:'; then
  echo "[yaml-validate] Error: Missing 'name' field in frontmatter"
  exit 1
fi

if ! echo "$FRONTMATTER" | grep -q '^description:'; then
  echo "[yaml-validate] Error: Missing 'description' field in frontmatter"
  exit 1
fi

# Check name format (lowercase, hyphens, numbers only)
NAME=$(echo "$FRONTMATTER" | grep '^name:' | sed 's/name: *//')
if ! echo "$NAME" | grep -qE '^[a-z0-9-]+$'; then
  echo "[yaml-validate] Error: name must be lowercase letters, numbers, hyphens only: $NAME"
  exit 1
fi

# Check description length (max 1024)
DESC=$(echo "$FRONTMATTER" | grep '^description:' | sed 's/description: *//')
DESC_LEN=${#DESC}
if [ "$DESC_LEN" -gt 1024 ]; then
  echo "[yaml-validate] Error: description exceeds 1024 chars ($DESC_LEN)"
  exit 1
fi

exit 0