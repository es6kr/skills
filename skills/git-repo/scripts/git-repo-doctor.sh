#!/usr/bin/env bash
# git-repo-doctor.sh — Comprehensive Git repository and hook diagnostics.
#
# Audits Git repository hook wiring, executable permissions, lifecycle guards,
# and conditional domain/file-type validators across Tier 1 (Base) and Tier 2 (Conditional).
#
# Usage:
#   bash skills/git-repo/scripts/git-repo-doctor.sh [repo_path] [--json]
#
# Exit codes:
#   0 = All active checks pass
#   1 = One or more checks failed

set -euo pipefail

# Unset parent git environment variables if invoked from within another git hook/process
unset GIT_DIR GIT_WORK_TREE

REPO_DIR="${1:-.}"
# Normalize Windows backslashes to forward slashes
REPO_DIR="${REPO_DIR//\\//}"

JSON_MODE=0
if [[ "${2:-}" == "--json" ]] || [[ "${1:-}" == "--json" ]]; then
  JSON_MODE=1
  if [[ "${1:-}" == "--json" ]]; then REPO_DIR="."; fi
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

if ! git -C "$REPO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo -e "${RED}ERROR: '$REPO_DIR' is not a valid git repository.${NC}" >&2
  exit 1
fi

REPO_ROOT="$(git -C "$REPO_DIR" rev-parse --show-toplevel)"
cd "$REPO_ROOT"

LOCAL_HOOKS_PATH="$(git config --local --get core.hooksPath 2>/dev/null || true)"
GLOBAL_HOOKS_PATH="$(git config --global --get core.hooksPath 2>/dev/null || true)"
ACTIVE_HOOKS_DIR="$(git rev-parse --git-path hooks)"
REMOTE_URL="$(git config --get remote.origin.url 2>/dev/null || true)"

# Results tracker: id|tier|category|status|message
declare -a RESULTS=()

add_result() {
  local id="$1" tier="$2" cat="$3" status="$4" msg="$5"
  RESULTS+=("$id|$tier|$cat|$status|$msg")
}

# -----------------------------------------------------------------------------
# Triggers & Context Detection
# -----------------------------------------------------------------------------
HAS_MD=0
if git ls-files 2>/dev/null | grep -qiE '\.md$'; then
  HAS_MD=1
fi

HAS_SKILLS=0
if git ls-files 2>/dev/null | grep -q 'SKILL\.md'; then
  HAS_SKILLS=1
fi

HAS_GO=0
if [[ -f "go.mod" ]]; then
  HAS_GO=1
fi

IS_CORP=0
if [[ "$REMOTE_URL" =~ daegunsoftDev ]] || [[ "$REPO_ROOT" =~ daegunsoftDev ]]; then
  IS_CORP=1
fi

IS_PUBLIC=0
if [[ "$REMOTE_URL" =~ es6kr ]] || [[ "$REPO_ROOT" =~ es6kr ]]; then
  IS_PUBLIC=1
fi

# -----------------------------------------------------------------------------
# Tier 1: Base (Universal) Checks
# -----------------------------------------------------------------------------

# BASE-1: core.hooksPath resolution
if [[ -d ".githooks" ]]; then
  RESOLVED_GITHOOKS="$(cd .githooks && pwd)"
  RESOLVED_ACTIVE="$(cd "$ACTIVE_HOOKS_DIR" 2>/dev/null && pwd || echo "$ACTIVE_HOOKS_DIR")"
  if [[ "$RESOLVED_ACTIVE" != "$RESOLVED_GITHOOKS" ]]; then
    add_result "BASE-1" "Base" "Hook Wiring" "FAIL" "'.githooks/' directory exists but active hooks directory is '$ACTIVE_HOOKS_DIR' instead of '.githooks'. Run 'git config core.hooksPath .githooks'."
  else
    add_result "BASE-1" "Base" "Hook Wiring" "PASS" "core.hooksPath correctly wired to '$ACTIVE_HOOKS_DIR'."
  fi
else
  add_result "BASE-1" "Base" "Hook Wiring" "PASS" "Using standard hooks directory '$ACTIVE_HOOKS_DIR'."
fi

# Read active hook files
PRE_COMMIT_CONTENT=""
PRE_PUSH_CONTENT=""
COMMIT_MSG_CONTENT=""

if [[ -f "$ACTIVE_HOOKS_DIR/pre-commit" ]]; then
  PRE_COMMIT_CONTENT="$(cat "$ACTIVE_HOOKS_DIR/pre-commit" 2>/dev/null || true)"
fi
if [[ -f "$ACTIVE_HOOKS_DIR/pre-push" ]]; then
  PRE_PUSH_CONTENT="$(cat "$ACTIVE_HOOKS_DIR/pre-push" 2>/dev/null || true)"
fi
if [[ -f "$ACTIVE_HOOKS_DIR/commit-msg" ]]; then
  COMMIT_MSG_CONTENT="$(cat "$ACTIVE_HOOKS_DIR/commit-msg" 2>/dev/null || true)"
fi

# Also check .githooks if configured
if [[ -d ".githooks" ]]; then
  [[ -z "$PRE_COMMIT_CONTENT" && -f ".githooks/pre-commit" ]] && PRE_COMMIT_CONTENT="$(cat ".githooks/pre-commit" 2>/dev/null || true)"
  [[ -z "$PRE_PUSH_CONTENT" && -f ".githooks/pre-push" ]] && PRE_PUSH_CONTENT="$(cat ".githooks/pre-push" 2>/dev/null || true)"
  [[ -z "$COMMIT_MSG_CONTENT" && -f ".githooks/commit-msg" ]] && COMMIT_MSG_CONTENT="$(cat ".githooks/commit-msg" 2>/dev/null || true)"
fi

# BASE-2: Executable bit (+x) check
EXEC_FAIL=0
for h in "$ACTIVE_HOOKS_DIR"/*; do
  if [[ -f "$h" && ! "$h" =~ \.(sample|bak)$ ]]; then
    if [[ ! -x "$h" ]]; then
      EXEC_FAIL=1
      add_result "BASE-2" "Base" "Permissions" "FAIL" "Hook file '$(basename "$h")' is not executable. Run 'chmod +x $h'."
    fi
  fi
done
if [[ $EXEC_FAIL -eq 0 ]]; then
  add_result "BASE-2" "Base" "Permissions" "PASS" "All active hook files have executable permissions."
fi

# BASE-3: pre-push Zero-SHA / branch deletion early exit
if [[ -n "$PRE_PUSH_CONTENT" ]]; then
  if echo "$PRE_PUSH_CONTENT" | grep -qE '(0000000000000000000000000000000000000000|\(delete\))'; then
    add_result "BASE-3" "Base" "Pre-push Deletion" "PASS" "pre-push hook handles zero-SHA branch deletion early exit."
  else
    add_result "BASE-3" "Base" "Pre-push Deletion" "FAIL" "pre-push hook lacks zero-SHA (40 zeros) branch deletion early exit (wastes CI runs on branch deletion)."
  fi
else
  add_result "BASE-3" "Base" "Pre-push Deletion" "WARN" "No pre-push hook found."
fi

# BASE-4: pre-push 'local' branch guard
if [[ -n "$PRE_PUSH_CONTENT" ]]; then
  if echo "$PRE_PUSH_CONTENT" | grep -qE 'refs/heads/local'; then
    add_result "BASE-4" "Base" "Local Branch Guard" "PASS" "pre-push hook contains 'local' stage-branch push guard."
  else
    add_result "BASE-4" "Base" "Local Branch Guard" "FAIL" "pre-push hook lacks 'local' stage-branch push guard."
  fi
else
  add_result "BASE-4" "Base" "Local Branch Guard" "WARN" "No pre-push hook found."
fi

# BASE-5: pre-commit secret & IP scan
if [[ -n "$PRE_COMMIT_CONTENT" ]]; then
  if echo "$PRE_COMMIT_CONTENT" | grep -qE '(192\.168|10\.[0-9]|RFC1918|secret|check-personal-path|personal_path)'; then
    add_result "BASE-5" "Base" "Secret & IP Guard" "PASS" "pre-commit hook contains secret / IP / path protection guard."
  else
    add_result "BASE-5" "Base" "Secret & IP Guard" "WARN" "pre-commit hook does not scan for internal RFC1918 IPs or secrets."
  fi
else
  add_result "BASE-5" "Base" "Secret & IP Guard" "WARN" "No pre-commit hook found."
fi

# BASE-6: pre-push commit count limit guard (prevents pushing massive commits from wrong base)
if [[ -n "$PRE_PUSH_CONTENT" ]]; then
  if echo "$PRE_PUSH_CONTENT" | grep -qE '(PUSH_MAX_COMMITS|PUSH_COMMIT_LIMIT_OVERRIDE|rev-list.*--count|MAX_COMMITS)'; then
    add_result "BASE-6" "Base" "Push Commit Limit" "PASS" "pre-push hook contains commit count limit guard against wrong-base divergence."
  else
    add_result "BASE-6" "Base" "Push Commit Limit" "FAIL" "pre-push hook lacks commit count limit guard (prevents pushing diverged commits from wrong base branch)."
  fi
else
  add_result "BASE-6" "Base" "Push Commit Limit" "WARN" "No pre-push hook found."
fi

# BASE-7: pre-push merge-conflict-marker guard (blocks pushing commits whose message
# still carries the auto-generated "Conflicts:" residue from a non-interactive merge commit)
if [[ -n "$PRE_PUSH_CONTENT" ]]; then
  if echo "$PRE_PUSH_CONTENT" | grep -qE '(Conflicts:|CONFLICT_COMMITS|PUSH_CONFLICT_MSG_OVERRIDE)'; then
    add_result "BASE-7" "Base" "Conflict Marker Guard" "PASS" "pre-push hook scans outgoing commit messages for leftover '# Conflicts:' residue."
  else
    add_result "BASE-7" "Base" "Conflict Marker Guard" "FAIL" "pre-push hook lacks a guard blocking commits whose message still contains a literal '# Conflicts:' section (leftover from a non-interactively committed merge)."
  fi
else
  add_result "BASE-7" "Base" "Conflict Marker Guard" "WARN" "No pre-push hook found."
fi

# -----------------------------------------------------------------------------
# Tier 2: Conditional Checks
# -----------------------------------------------------------------------------

# Strip comment lines from hook contents to avoid matching explanatory comments
CLEAN_HOOKS_CONTENT="$(echo "$PRE_COMMIT_CONTENT $PRE_PUSH_CONTENT $COMMIT_MSG_CONTENT" | sed 's/#.*//g')"

# COND-MD: Markdown lint hook requirement
if [[ $HAS_MD -eq 1 ]]; then
  if echo "$CLEAN_HOOKS_CONTENT" | grep -qE '(check-hangul|lint-frontmatter|validate-md|markdownlint|md-ref)'; then
    add_result "COND-MD" "Conditional" "Markdown Lint" "PASS" "Markdown files present and validated by hook."
  else
    add_result "COND-MD" "Conditional" "Markdown Lint" "FAIL" "Repository contains .md files but lacks a markdown lint or reference validation hook."
  fi
fi

# COND-MD-STYLE: genuine markdown STYLE lint (trailing whitespace, heading/list
# rules, etc.) — distinct from COND-MD above, which is satisfied by narrow
# tools like check-hangul.py (Korean-text-only) or lint-frontmatter.sh
# (frontmatter-only). Neither of those catches trailing whitespace, so a
# COND-MD PASS gives false confidence that markdown "quality" is covered.
# Detection source depends on what tooling manifests the repo actually has
# (Makefile / package.json / scripts/) — each is probed only if present.
if [[ $HAS_MD -eq 1 ]]; then
  MD_STYLE_TOOL_PATTERN='(markdownlint|remark-lint|remark\.config|remarkrc|mdl\b|prettier[^"]*\.md)'
  LINT_MANIFEST_SOURCES=""
  HAS_MD_STYLE_TOOL=0

  if [[ -f "Makefile" ]]; then
    LINT_MANIFEST_SOURCES="${LINT_MANIFEST_SOURCES}Makefile "
    if grep -qiE "$MD_STYLE_TOOL_PATTERN" Makefile 2>/dev/null; then
      HAS_MD_STYLE_TOOL=1
    fi
  fi

  if [[ -f "package.json" ]]; then
    LINT_MANIFEST_SOURCES="${LINT_MANIFEST_SOURCES}package.json "
    if grep -qiE "$MD_STYLE_TOOL_PATTERN" package.json 2>/dev/null; then
      HAS_MD_STYLE_TOOL=1
    fi
  fi

  if [[ -d "scripts" ]]; then
    LINT_MANIFEST_SOURCES="${LINT_MANIFEST_SOURCES}scripts/ "
    if ls scripts 2>/dev/null | grep -qiE 'markdown|mdlint|md-lint|remark'; then
      HAS_MD_STYLE_TOOL=1
    fi
  fi

  if [[ -z "$LINT_MANIFEST_SOURCES" ]]; then
    add_result "COND-MD-STYLE" "Conditional" "Markdown Style Lint" "WARN" "No Makefile, package.json, or scripts/ directory found — cannot verify markdown style/whitespace lint coverage from project tooling manifests."
  elif [[ $HAS_MD_STYLE_TOOL -eq 0 ]]; then
    add_result "COND-MD-STYLE" "Conditional" "Markdown Style Lint" "WARN" "Checked ${LINT_MANIFEST_SOURCES}but found no markdown style/whitespace lint tool (markdownlint/remark-lint/mdl/prettier --check *.md). check-hangul/lint-frontmatter (if present) do not catch trailing whitespace or markdown style issues."
  else
    CI_WORKFLOW_CONTENT=""
    if [[ -d ".github/workflows" ]]; then
      CI_WORKFLOW_CONTENT="$(cat .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null || true)"
    fi
    if echo "$CLEAN_HOOKS_CONTENT $CI_WORKFLOW_CONTENT" | grep -qiE "${MD_STYLE_TOOL_PATTERN}|make lint|npm run lint|pnpm( run)? lint"; then
      add_result "COND-MD-STYLE" "Conditional" "Markdown Style Lint" "PASS" "Markdown style/whitespace lint tool declared (${LINT_MANIFEST_SOURCES}) and wired into pre-commit, pre-push, or CI."
    else
      add_result "COND-MD-STYLE" "Conditional" "Markdown Style Lint" "FAIL" "Markdown style lint tool declared in ${LINT_MANIFEST_SOURCES}but not invoked from pre-commit, pre-push, or CI workflows — declared tooling is dead weight."
    fi
  fi
fi

# COND-SKILL: Skills structure lint hook requirement
if [[ $HAS_SKILLS -eq 1 ]]; then
  if echo "$CLEAN_HOOKS_CONTENT" | grep -qE '(lint-frontmatter|frontmatter-lint|skill-yaml-validate)'; then
    add_result "COND-SKILL" "Conditional" "Skill Frontmatter Lint" "PASS" "Skill files present and verified by metadata/frontmatter lint hook."
  else
    add_result "COND-SKILL" "Conditional" "Skill Frontmatter Lint" "FAIL" "Repository contains skills (skills/*/SKILL.md) but lacks a frontmatter/semver lint hook."
  fi
fi

# COND-AGENT: Agent runtime workspace
if [[ -f "fix_plan.md" ]] || [[ "$REPO_ROOT" =~ (\.agents|\.ralph)$ ]]; then
  if echo "$PRE_COMMIT_CONTENT" | grep -qE 'fix_plan\.md'; then
    add_result "COND-AGENT" "Conditional" "Tracker Guard" "PASS" "Untracked fix_plan.md staging block guard present in pre-commit."
  else
    add_result "COND-AGENT" "Conditional" "Tracker Guard" "WARN" "Agent workspace detected but pre-commit lacks untracked fix_plan.md staging block guard."
  fi
fi

# COND-GO: Go project checks
if [[ $HAS_GO -eq 1 ]]; then
  if echo "$PRE_COMMIT_CONTENT $PRE_PUSH_CONTENT" | grep -qE '(gofmt|go vet|go test)'; then
    add_result "COND-GO" "Conditional" "Go Toolchain" "PASS" "Go toolchain validation wired in hooks."
  else
    add_result "COND-GO" "Conditional" "Go Toolchain" "WARN" "Go project (go.mod) detected but pre-commit/pre-push lacks gofmt / go vet / go test."
  fi
fi

# COND-PUBLIC: Public repository hangul gate
if [[ $IS_PUBLIC -eq 1 && $HAS_MD -eq 1 ]]; then
  if echo "$PRE_COMMIT_CONTENT" | grep -qE '(check-hangul|hangul_hits|ac00-d7a3)'; then
    add_result "COND-PUBLIC" "Conditional" "Public English Gate" "PASS" "Public English repository contains check-hangul gate in pre-commit."
  else
    # In public repo with md/sh, should have hangul check
    if [[ "$REPO_ROOT" =~ skills ]]; then
      add_result "COND-PUBLIC" "Conditional" "Public English Gate" "FAIL" "Public skills repository lacks check-hangul gate in pre-commit."
    fi
  fi
fi

# COND-CORP: Corporate repository main push block
if [[ $IS_CORP -eq 1 ]]; then
  if echo "$PRE_PUSH_CONTENT" | grep -qE '(daegunsoftDev|main|master)'; then
    add_result "COND-CORP" "Conditional" "Corp Main Push Block" "PASS" "Corporate repository contains direct main/master push protection."
  fi
fi

# -----------------------------------------------------------------------------
# Output & Summary
# -----------------------------------------------------------------------------
TOTAL_FAILS=0
TOTAL_WARNS=0
TOTAL_PASS=0

if [[ $JSON_MODE -eq 1 ]]; then
  for r in "${RESULTS[@]}"; do
    IFS='|' read -r id tier cat status msg <<< "$r"
    [[ "$status" == "FAIL" ]] && TOTAL_FAILS=$((TOTAL_FAILS + 1))
    [[ "$status" == "WARN" ]] && TOTAL_WARNS=$((TOTAL_WARNS + 1))
    [[ "$status" == "PASS" ]] && TOTAL_PASS=$((TOTAL_PASS + 1))
  done
  printf '%s\n' "${RESULTS[@]}" | jq -R -s \
    --arg repo "$REPO_ROOT" \
    --argjson pass "$TOTAL_PASS" \
    --argjson warn "$TOTAL_WARNS" \
    --argjson fail "$TOTAL_FAILS" \
    'split("\n") | map(select(length > 0) | split("|")) | {
      repository: $repo,
      results: map({
        id: .[0],
        tier: .[1],
        category: .[2],
        status: .[3],
        message: (.[4:] | join("|"))
      }),
      summary: {pass: $pass, warn: $warn, fail: $fail}
    }'
else
  echo -e "\n${BLUE}========================================================================${NC}"
  echo -e "${BLUE}  Git Repository & Hook Doctor: ${NC}$REPO_ROOT"
  echo -e "${BLUE}========================================================================${NC}"
  printf '%-10s %-12s %-22s %-8s %s\n' "ID" "TIER" "CATEGORY" "STATUS" "DETAILS"
  echo "------------------------------------------------------------------------"

  for r in "${RESULTS[@]}"; do
    IFS='|' read -r id tier cat status msg <<< "$r"
    if [[ "$status" == "PASS" ]]; then
      status_colored="${GREEN}PASS${NC}"
      TOTAL_PASS=$((TOTAL_PASS + 1))
    elif [[ "$status" == "WARN" ]]; then
      status_colored="${YELLOW}WARN${NC}"
      TOTAL_WARNS=$((TOTAL_WARNS + 1))
    else
      status_colored="${RED}FAIL${NC}"
      TOTAL_FAILS=$((TOTAL_FAILS + 1))
    fi
    printf '%-10s %-12s %-22s ' "$id" "$tier" "$cat"
    echo -e "$status_colored  $msg"
  done

  echo "------------------------------------------------------------------------"
  echo -e "Summary: ${GREEN}$TOTAL_PASS Passed${NC} | ${YELLOW}$TOTAL_WARNS Warnings${NC} | ${RED}$TOTAL_FAILS Failed${NC}"

  if [[ $TOTAL_FAILS -gt 0 ]]; then
    echo -e "\n${RED}❌ Doctor found $TOTAL_FAILS issue(s). Follow details above to resolve.${NC}\n"
  else
    echo -e "\n${GREEN}✓ Repository hook diagnostics clean!${NC}\n"
  fi
fi

if [[ $TOTAL_FAILS -gt 0 ]]; then
  exit 1
fi
exit 0
