#!/usr/bin/env bash
# Unit test (dry-run) for forge-driver.sh — dispatch + command assembly only.
# No live gh/glab/tea calls: DRY_RUN=1 makes methods echo the assembled command.
# Test hook: FORGE_REMOTE_URL overrides `git remote get-url origin` for host detection.
set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./forge-driver.sh
. "$DIR/forge-driver.sh"

fail=0
assert_eq() { # desc expected actual
  if [ "$2" = "$3" ]; then
    echo "ok   - $1"
  else
    echo "FAIL - $1: expected [$2] got [$3]"
    fail=1
  fi
}

# --- forge_detect: explicit override wins ---
assert_eq "detect override gitlab" "gitlab" "$(FORGE_OVERRIDE=gitlab forge_detect)"
assert_eq "detect override gitea"  "gitea"  "$(FORGE_OVERRIDE=gitea forge_detect)"
assert_eq "detect override github" "github" "$(FORGE_OVERRIDE=github forge_detect)"

# --- forge_detect: remote host auto-detect (no override) ---
assert_eq "detect remote gitlab" "gitlab" "$(FORGE_REMOTE_URL='git@gitlab.com:o/r.git' forge_detect)"
assert_eq "detect remote gitea"  "gitea"  "$(FORGE_REMOTE_URL='https://gitea.example.com/o/r.git' forge_detect)"
assert_eq "detect remote github" "github" "$(FORGE_REMOTE_URL='git@github.com:o/r.git' forge_detect)"

# --- forge_detect: unresolved host → github fallback ---
assert_eq "detect fallback github" "github" "$(FORGE_REMOTE_URL='https://unknown.example/o/r.git' forge_detect)"

# --- ref_format: GitLab MR uses !, everything else uses # ---
assert_eq "ref gitlab pr"    "!" "$(FORGE_OVERRIDE=gitlab ref_format pr)"
assert_eq "ref gitlab issue" "#" "$(FORGE_OVERRIDE=gitlab ref_format issue)"
assert_eq "ref github pr"    "#" "$(FORGE_OVERRIDE=github ref_format pr)"
assert_eq "ref gitea pr"     "#" "$(FORGE_OVERRIDE=gitea ref_format pr)"

# --- pr_create dry-run: per-forge command assembly ---
assert_eq "pr_create github" \
  "gh pr create --base main --head feat --title T --body B" \
  "$(FORGE_OVERRIDE=github DRY_RUN=1 pr_create main feat T B)"
assert_eq "pr_create gitlab" \
  "glab mr create --target-branch main --source-branch feat --title T --description B" \
  "$(FORGE_OVERRIDE=gitlab DRY_RUN=1 pr_create main feat T B)"
assert_eq "pr_create gitea" \
  "tea pr create --base main --head feat --title T --description B" \
  "$(FORGE_OVERRIDE=gitea DRY_RUN=1 pr_create main feat T B)"

# --- pr_create draft flag ---
assert_eq "pr_create github draft" \
  "gh pr create --base main --head feat --title T --body B --draft" \
  "$(FORGE_OVERRIDE=github DRY_RUN=1 pr_create main feat T B draft)"

# --- issue_create <title> <body> ---
assert_eq "issue_create github" "gh issue create --title T --body B" \
  "$(FORGE_OVERRIDE=github DRY_RUN=1 issue_create T B)"
assert_eq "issue_create gitlab" "glab issue create --title T --description B" \
  "$(FORGE_OVERRIDE=gitlab DRY_RUN=1 issue_create T B)"
assert_eq "issue_create gitea" "tea issue create --title T --description B" \
  "$(FORGE_OVERRIDE=gitea DRY_RUN=1 issue_create T B)"

# --- issue_edit <ref> <body> ---
assert_eq "issue_edit github" "gh issue edit R1 --body B" \
  "$(FORGE_OVERRIDE=github DRY_RUN=1 issue_edit R1 B)"
assert_eq "issue_edit gitlab" "glab issue update R1 --description B" \
  "$(FORGE_OVERRIDE=gitlab DRY_RUN=1 issue_edit R1 B)"
assert_eq "issue_edit gitea boundary" "# gitea:issue_edit boundary (tea/API — Phase 2 follow-up)" \
  "$(FORGE_OVERRIDE=gitea DRY_RUN=1 issue_edit R1 B)"

# --- pr_merge <ref> <squash|merge|rebase> ---
assert_eq "pr_merge github squash" "gh pr merge R1 --squash" \
  "$(FORGE_OVERRIDE=github DRY_RUN=1 pr_merge R1 squash)"
assert_eq "pr_merge github merge" "gh pr merge R1 --merge" \
  "$(FORGE_OVERRIDE=github DRY_RUN=1 pr_merge R1 merge)"
assert_eq "pr_merge gitlab squash" "glab mr merge R1 --squash" \
  "$(FORGE_OVERRIDE=gitlab DRY_RUN=1 pr_merge R1 squash)"

# --- Gitea boundary (GitLab-first decision: gitea via tea/API is a follow-up) ---
assert_eq "pr_merge gitea boundary" "# gitea:pr_merge boundary (tea/API — Phase 2 follow-up)" \
  "$(FORGE_OVERRIDE=gitea DRY_RUN=1 pr_merge R1 squash)"

if [ "$fail" -eq 0 ]; then echo "PASS: all forge-driver assertions"; else echo "FAILURES present"; fi
exit $fail
