#!/bin/bash
# Validate SKILL.md YAML frontmatter before write
# Triggered by: PreToolUse (Edit|Write)
# Returns exit 1 to block on validation error

# Only check SKILL.md files
MATCHED_FILES=$(echo "$CLAUDE_FILE_PATHS" | tr ' ' '\n' | grep -E 'SKILL\.md$' || true)
if [ -z "$MATCHED_FILES" ]; then
  exit 0
fi

for FILE in $MATCHED_FILES; do
  # Skip if file doesn't exist yet (new file)
  if [ ! -f "$FILE" ]; then
    continue
  fi

  # Check frontmatter opening
  if ! head -1 "$FILE" | grep -q '^---$'; then
    echo "[yaml-validate] Error: SKILL.md must start with ---: $FILE"
    exit 1
  fi

  # Require closing frontmatter delimiter
  if [ "$(grep -c '^---$' "$FILE")" -lt 2 ]; then
    echo "[yaml-validate] Error: Missing closing frontmatter delimiter in $FILE"
    exit 1
  fi

  # Extract frontmatter (lines between first and second ---)
  FRONTMATTER=$(sed -n '2,/^---$/p' "$FILE" | head -n -1)

  # Check required fields
  if ! echo "$FRONTMATTER" | grep -q '^name:'; then
    echo "[yaml-validate] Error: Missing 'name' field in frontmatter: $FILE"
    exit 1
  fi

  if ! echo "$FRONTMATTER" | grep -q '^description:'; then
    echo "[yaml-validate] Error: Missing 'description' field in frontmatter: $FILE"
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
    echo "[yaml-validate] Error: description exceeds 1024 chars ($DESC_LEN) in $FILE"
    exit 1
  fi
done

exit 0