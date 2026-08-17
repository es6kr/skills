#!/bin/bash
# complex-logic-guard.sh
# PreToolUse:Edit hook - re-confirm requirements and require tests on complex logic changes

# Read tool input from stdin
INPUT=$(cat)

# Extract file path from tool input
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Skip if not a source file
if [[ ! "$FILE_PATH" =~ \.(ts|js|tsx|jsx|svelte|py|go|rs)$ ]]; then
  exit 0
fi

# Extract the changes (old_string and new_string)
OLD_STRING=$(echo "$INPUT" | jq -r '.tool_input.old_string // empty')
NEW_STRING=$(echo "$INPUT" | jq -r '.tool_input.new_string // empty')

# Count lines changed
OLD_LINES=$(echo "$OLD_STRING" | wc -l)
NEW_LINES=$(echo "$NEW_STRING" | wc -l)
TOTAL_LINES=$((OLD_LINES + NEW_LINES))

# Check for complex patterns that often cause bugs
COMPLEX_PATTERNS=(
  "Map<"           # Map operations - often need careful key handling
  "\.get("         # Map/Object lookups - null checks needed
  "for.*of"        # Loops - iteration logic
  "Effect\."       # Effect-TS - complex async handling
  "async"          # Async code - race conditions
  "Promise"        # Promise handling
  "reduce("        # Array reduce - complex accumulation
  "\.filter.*\.map\|\.map.*\.filter"  # Chained array operations
)

HAS_COMPLEX_PATTERN=false
MATCHED_PATTERNS=()

for pattern in "${COMPLEX_PATTERNS[@]}"; do
  if echo "$NEW_STRING" | grep -qiE "$pattern"; then
    HAS_COMPLEX_PATTERN=true
    MATCHED_PATTERNS+=("$pattern")
  fi
done

# Output reminder if:
# 1. Large change (>20 lines) OR
# 2. Contains complex patterns
if [[ $TOTAL_LINES -gt 20 ]] || [[ "$HAS_COMPLEX_PATTERN" == "true" ]]; then
  echo "---"
  echo "[complex-logic-guard] Complex logic change detected"
  echo ""
  echo "Change size: ${OLD_LINES} lines -> ${NEW_LINES} lines"

  if [[ "$HAS_COMPLEX_PATTERN" == "true" ]]; then
    echo "Complex patterns: ${MATCHED_PATTERNS[*]}"
  fi

  echo ""
  echo "Checklist:"
  echo "- [ ] Did you re-confirm what the original requirement was?"
  echo "- [ ] Does this change precisely satisfy the requirement?"
  echo "- [ ] If anything was ambiguous, did you use AskUserQuestion?"
  echo "- [ ] Did you write a unit test or run the existing tests?"
  echo "- [ ] Did you consider edge cases? (null, other sessions, missing data)"
  echo "---"
fi

exit 0
