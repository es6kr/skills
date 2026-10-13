#!/usr/bin/env bash
# Unit tests for block-skill-language-mismatch.sh — explicit frontmatter
# `language:` field must take priority over the description-Hangul heuristic.
set -uo pipefail

HOOK_DIR="$(cd "$(dirname "$0")/../resources" && pwd)"
HOOK="$HOOK_DIR/block-skill-language-mismatch.sh"
FIXTURE="$(cd "$(mktemp -d)" && pwd -P)"
trap 'rm -rf "$FIXTURE"' EXIT

pass=0
fail=0

check() {
  local name="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    pass=$((pass+1))
    echo "PASS  $name"
  else
    fail=$((fail+1))
    echo "FAIL  $name: expected=[$expected] actual=[$actual]"
  fi
}

run_hook() {
  local file_path="$1" new_string="$2"
  jq -n --arg fp "$file_path" --arg ns "$new_string" \
    '{tool_name: "Edit", tool_input: {file_path: $fp, new_string: $ns}}' \
    | "$HOOK" >/dev/null 2>&1
  echo "$?"
}

# Hangul test fixture content, built from the UTF-8 bytes of U+AC00 ("GA")
# rather than literal Hangul source characters -- this repo's pre-commit
# hook denies any literal Hangul byte in a tracked .md/.sh file (PUBLIC,
# English-only). The hook under test only checks the Unicode range
# [가-힣] (U+AC00-U+D7A3), so a repeated placeholder syllable exercises
# the exact same branch as real Korean text without tripping that gate.
HANGUL=$'\xEA\xB0\x80\xEA\xB0\x80\xEA\xB0\x80\xEA\xB0\x80'

mkdir -p "$FIXTURE/skills/en-desc-ko-frontmatter"
cat > "$FIXTURE/skills/en-desc-ko-frontmatter/SKILL.md" <<'EOF'
---
name: en-desc-ko-frontmatter
language: ko
description: Sync config files between Claude Code and Antigravity
---

# Body
EOF

mkdir -p "$FIXTURE/skills/en-desc-en-frontmatter"
cat > "$FIXTURE/skills/en-desc-en-frontmatter/SKILL.md" <<'EOF'
---
name: en-desc-en-frontmatter
language: en
description: Sync config files between Claude Code and Antigravity
---

# Body
EOF

mkdir -p "$FIXTURE/skills/en-desc-no-frontmatter"
cat > "$FIXTURE/skills/en-desc-no-frontmatter/SKILL.md" <<'EOF'
---
name: en-desc-no-frontmatter
description: Sync config files between Claude Code and Antigravity
---

# Body
EOF

mkdir -p "$FIXTURE/skills/ko-desc"
printf -- '---\nname: ko-desc\ndescription: %s\n---\n\n# Body\n' "$HANGUL" > "$FIXTURE/skills/ko-desc/SKILL.md"

# T1 (regression): English description, no frontmatter override, Korean content -> DENY
res="$(run_hook "$FIXTURE/skills/en-desc-no-frontmatter/notes.md" "$HANGUL")"
check "T1 english-desc no-override + korean content -> deny(2)" "2" "$res"

# T2 (regression): Korean description -> permissive regardless of content
res="$(run_hook "$FIXTURE/skills/ko-desc/notes.md" "$HANGUL")"
check "T2 korean-desc -> allow(0)" "0" "$res"

# T3 (regression): English description + English content -> ALLOW
res="$(run_hook "$FIXTURE/skills/en-desc-no-frontmatter/notes.md" 'plain english text')"
check "T3 english-desc + english content -> allow(0)" "0" "$res"

# T4 (NEW — fix target): English description BUT explicit language: ko frontmatter
# + Korean content -> ALLOW (frontmatter override wins over description heuristic)
res="$(run_hook "$FIXTURE/skills/en-desc-ko-frontmatter/notes.md" "$HANGUL")"
check "T4 english-desc + language:ko override + korean content -> allow(0)" "0" "$res"

# T5 (NEW): English description + explicit language: en frontmatter + Korean
# content -> still DENY (explicit override confirms strict mode too)
res="$(run_hook "$FIXTURE/skills/en-desc-en-frontmatter/notes.md" "$HANGUL")"
check "T5 english-desc + language:en override + korean content -> deny(2)" "2" "$res"

echo "---"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
