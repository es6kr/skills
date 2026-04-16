#!/usr/bin/env bats
# Structure tests for es6kr/skills
# Only tests git-tracked skills (untracked local skills are ignored)

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
SKILLS_DIR="$REPO_ROOT/skills"

# Helper: list only git-tracked skill directories
tracked_skills() {
  git -C "$REPO_ROOT" ls-files -- 'skills/*/SKILL.md' | sed 's|/SKILL.md$||' | sort -u
}

# --- Flat structure ---

@test "skills/ directory exists" {
  [[ -d "$SKILLS_DIR" ]]
}

@test "every tracked skill has SKILL.md" {
  local missing=()
  for skill in $(git -C "$REPO_ROOT" ls-files -- 'skills/*/' | sed 's|/.*||' | sort -u); do
    git -C "$REPO_ROOT" ls-files --error-unmatch "$skill/SKILL.md" >/dev/null 2>&1 || missing+=("$(basename "$skill")")
  done
  [[ ${#missing[@]} -eq 0 ]] || { echo "Missing SKILL.md: ${missing[*]}"; return 1; }
}

@test "flat structure only — no nested SKILL.md beyond depth 2" {
  local deep
  deep=$(git -C "$REPO_ROOT" ls-files -- 'skills/*/*/SKILL.md' | wc -l | tr -d ' ')
  [[ "$deep" -eq 0 ]]
}

@test "skill directory names are lowercase-hyphen only" {
  local bad=()
  for skill in $(tracked_skills); do
    local name
    name=$(basename "$skill")
    [[ "$name" =~ ^[a-z0-9-]+$ ]] || bad+=("$name")
  done
  [[ ${#bad[@]} -eq 0 ]] || { echo "Bad names: ${bad[*]}"; return 1; }
}

# --- Frontmatter ---

@test "SKILL.md frontmatter has name field" {
  local missing=()
  for skill in $(tracked_skills); do
    head -10 "$REPO_ROOT/$skill/SKILL.md" | grep -q '^name:' || missing+=("$skill")
  done
  [[ ${#missing[@]} -eq 0 ]] || { echo "Missing name: ${missing[*]}"; return 1; }
}

@test "SKILL.md frontmatter has description field" {
  local missing=()
  for skill in $(tracked_skills); do
    head -10 "$REPO_ROOT/$skill/SKILL.md" | grep -q '^description:' || missing+=("$skill")
  done
  [[ ${#missing[@]} -eq 0 ]] || { echo "Missing description: ${missing[*]}"; return 1; }
}

@test "SKILL.md name matches directory name" {
  local mismatches=()
  for skill in $(tracked_skills); do
    local dir_name skill_name
    dir_name=$(basename "$skill")
    skill_name=$(awk '{gsub(/\r/,"")}/^---$/{if(++c==2)exit}c==1&&/^name:/{sub(/^name:[[:space:]]*/,"");print;exit}' "$REPO_ROOT/$skill/SKILL.md")
    [[ "$skill_name" == "$dir_name" ]] || mismatches+=("$dir_name(name=$skill_name)")
  done
  [[ ${#mismatches[@]} -eq 0 ]] || { echo "Mismatches: ${mismatches[*]}"; return 1; }
}

# --- Security ---

@test "no secret patterns in tracked skills" {
  local result
  result=$(git -C "$REPO_ROOT" ls-files -- 'skills/' | xargs grep -P '(glpat-|sk-[a-zA-Z0-9]{20,}|10\.0\.0\.\d+|14\.36\.\d+)' 2>/dev/null || true)
  [[ -z "$result" ]]
}

@test "no Korean in frontmatter" {
  local bad=()
  for skill in $(tracked_skills); do
    local frontmatter
    frontmatter=$(sed -n '/^---$/,/^---$/p' "$REPO_ROOT/$skill/SKILL.md" | head -20)
    if echo "$frontmatter" | grep -P '[가-힣]' >/dev/null 2>&1; then
      bad+=("$skill")
    fi
  done
  [[ ${#bad[@]} -eq 0 ]] || { echo "Korean found: ${bad[*]}"; return 1; }
}

# --- License ---

@test "every tracked skill has LICENSE" {
  if [[ -n "$CI" ]]; then skip "LICENSE check skipped in CI"; fi
  local missing=()
  for skill in $(tracked_skills); do
    [[ -f "$REPO_ROOT/$skill/LICENSE" ]] || missing+=("$(basename "$skill")")
  done
  [[ ${#missing[@]} -eq 0 ]] || { echo "Missing LICENSE: ${missing[*]}"; return 1; }
}

# --- Claude Code Plugin ---

_python() { command -v python3 >/dev/null 2>&1 && python3 "$@" || python "$@"; }
_native_path() { cygpath -w "$1" 2>/dev/null || echo "$1"; }

@test ".claude-plugin/plugin.json exists and is valid JSON" {
  [[ -f "$REPO_ROOT/.claude-plugin/plugin.json" ]]
  _python -m json.tool "$(_native_path "$REPO_ROOT/.claude-plugin/plugin.json")" > /dev/null
}

@test ".claude-plugin/marketplace.json exists and is valid JSON" {
  [[ -f "$REPO_ROOT/.claude-plugin/marketplace.json" ]]
  _python -m json.tool "$(_native_path "$REPO_ROOT/.claude-plugin/marketplace.json")" > /dev/null
}

@test "marketplace.json source is root (./) — superpowers pattern" {
  local fpath
  fpath=$(_native_path "$REPO_ROOT/.claude-plugin/marketplace.json")
  local source
  source=$(_python -c "import json; m=json.load(open(r'$fpath')); print(m['plugins'][0]['source'])")
  [[ "$source" == "./" ]]
}
