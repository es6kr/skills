#!/usr/bin/env bats
# Structure tests for es6kr/skills

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
SKILLS_DIR="$REPO_ROOT/skills"

# --- Flat structure ---

@test "skills/ directory exists" {
  [[ -d "$SKILLS_DIR" ]]
}

@test "every skill has SKILL.md" {
  local missing=()
  for skill in "$SKILLS_DIR"/*/; do
    [[ -f "$skill/SKILL.md" ]] || missing+=("$(basename "$skill")")
  done
  [[ ${#missing[@]} -eq 0 ]] || { echo "Missing SKILL.md: ${missing[*]}"; return 1; }
}

@test "flat structure only — no nested SKILL.md beyond depth 2" {
  local deep
  deep=$(find "$SKILLS_DIR" -name "SKILL.md" -mindepth 3 2>/dev/null | wc -l | tr -d ' ')
  [[ "$deep" -eq 0 ]]
}

@test "skill directory names are lowercase-hyphen only" {
  local bad=()
  for skill in "$SKILLS_DIR"/*/; do
    local name
    name=$(basename "$skill")
    [[ "$name" =~ ^[a-z0-9-]+$ ]] || bad+=("$name")
  done
  [[ ${#bad[@]} -eq 0 ]] || { echo "Bad names: ${bad[*]}"; return 1; }
}

# --- Frontmatter ---

@test "SKILL.md frontmatter has name field" {
  local missing=()
  while read -r skill; do
    head -10 "$skill" | grep -q '^name:' || missing+=("$skill")
  done < <(find "$SKILLS_DIR" -name "SKILL.md" -maxdepth 2)
  [[ ${#missing[@]} -eq 0 ]] || { echo "Missing name: ${missing[*]}"; return 1; }
}

@test "SKILL.md frontmatter has description field" {
  local missing=()
  while read -r skill; do
    head -10 "$skill" | grep -q '^description:' || missing+=("$skill")
  done < <(find "$SKILLS_DIR" -name "SKILL.md" -maxdepth 2)
  [[ ${#missing[@]} -eq 0 ]] || { echo "Missing description: ${missing[*]}"; return 1; }
}

@test "SKILL.md name matches directory name" {
  local mismatches=()
  while read -r skill; do
    local dir_name skill_name
    dir_name=$(basename "$(dirname "$skill")")
    skill_name=$(awk '{gsub(/\r/,"")}/^---$/{if(++c==2)exit}c==1&&/^name:/{sub(/^name:[[:space:]]*/,"");print;exit}' "$skill")
    [[ "$skill_name" == "$dir_name" ]] || mismatches+=("$dir_name(name=$skill_name)")
  done < <(find "$SKILLS_DIR" -name "SKILL.md" -maxdepth 2)
  [[ ${#mismatches[@]} -eq 0 ]] || { echo "Mismatches: ${mismatches[*]}"; return 1; }
}

# --- Security ---

@test "no secret patterns in skills" {
  local result
  result=$(grep -rP '(glpat-|sk-[a-zA-Z0-9]{20,}|10\.0\.0\.\d+|14\.36\.\d+)' "$SKILLS_DIR" 2>/dev/null || true)
  [[ -z "$result" ]]
}

@test "no Korean in frontmatter" {
  local bad=()
  while read -r skill; do
    local frontmatter
    frontmatter=$(sed -n '/^---$/,/^---$/p' "$skill" | head -20)
    if echo "$frontmatter" | grep -P '[가-힣]' >/dev/null 2>&1; then
      bad+=("$skill")
    fi
  done < <(find "$SKILLS_DIR" -name "SKILL.md" -maxdepth 2)
  [[ ${#bad[@]} -eq 0 ]] || { echo "Korean found: ${bad[*]}"; return 1; }
}

# --- License ---

@test "every skill has LICENSE" {
  local missing=()
  for skill in "$SKILLS_DIR"/*/; do
    [[ -f "$skill/LICENSE" ]] || missing+=("$(basename "$skill")")
  done
  [[ ${#missing[@]} -eq 0 ]] || { echo "Missing LICENSE: ${missing[*]}"; return 1; }
}

# --- Claude Code Plugin ---

@test ".claude-plugin/plugin.json exists and is valid JSON" {
  [[ -f "$REPO_ROOT/.claude-plugin/plugin.json" ]]
  python3 -m json.tool "$REPO_ROOT/.claude-plugin/plugin.json" > /dev/null
}

@test ".claude-plugin/marketplace.json exists and is valid JSON" {
  [[ -f "$REPO_ROOT/.claude-plugin/marketplace.json" ]]
  python3 -m json.tool "$REPO_ROOT/.claude-plugin/marketplace.json" > /dev/null
}

@test "marketplace.json source is root (./) — superpowers pattern" {
  local source
  source=$(python3 -c "import json; m=json.load(open('$REPO_ROOT/.claude-plugin/marketplace.json')); print(m['plugins'][0]['source'])")
  [[ "$source" == "./" ]]
}
