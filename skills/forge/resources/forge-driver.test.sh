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

# ===== normalized-return methods (output-mock) =====
# Each normalized method makes exactly one host CLI call, so a generic mock that echoes
# $MOCK_OUT regardless of args is enough to drive its normalization path.
gh()   { printf '%s\n' "${MOCK_OUT:-}"; }
glab() { printf '%s\n' "${MOCK_OUT:-}"; }

# --- repo_visibility → PUBLIC|INTERNAL|PRIVATE ---
assert_eq "visibility github private" "PRIVATE" "$( MOCK_OUT=true  FORGE_OVERRIDE=github repo_visibility )"
assert_eq "visibility github public"  "PUBLIC"  "$( MOCK_OUT=false FORGE_OVERRIDE=github repo_visibility )"
assert_eq "visibility github unknown→public" "PUBLIC" "$( MOCK_OUT= FORGE_OVERRIDE=github repo_visibility )"
assert_eq "visibility gitlab internal" "INTERNAL" "$( MOCK_OUT='{"visibility": "internal"}' FORGE_OVERRIDE=gitlab repo_visibility )"
assert_eq "visibility gitlab private"  "PRIVATE"  "$( MOCK_OUT='{"visibility": "private"}'  FORGE_OVERRIDE=gitlab repo_visibility )"
assert_eq "visibility gitlab public"   "PUBLIC"   "$( MOCK_OUT='{"visibility": "public"}'   FORGE_OVERRIDE=gitlab repo_visibility )"
assert_eq "visibility gitea boundary" "# gitea:repo_visibility boundary (tea/API — Phase 2 follow-up)" "$( FORGE_OVERRIDE=gitea repo_visibility )"

# --- auth_status → account=<login> scopes=<csv> ok=<bool> ---
auth_mock=$'  ✓ Logged in to github.com account DrumRobot (keyring)\n  - Token scopes: \'repo\', \'read:org\''
assert_eq "auth github ok" "account=DrumRobot scopes=repo,read:org ok=true" "$( MOCK_OUT="$auth_mock" FORGE_OVERRIDE=github auth_status )"
assert_eq "auth github not-logged" "account= scopes= ok=false" "$( MOCK_OUT= FORGE_OVERRIDE=github auth_status )"
glab_auth=$'  ✓ Logged in to gitlab.com as octocat (job token)'
assert_eq "auth gitlab ok" "account=octocat scopes= ok=true" "$( MOCK_OUT="$glab_auth" FORGE_OVERRIDE=gitlab auth_status )"
assert_eq "auth gitea boundary" "# gitea:auth_status boundary (tea/API — Phase 2 follow-up)" "$( FORGE_OVERRIDE=gitea auth_status )"

# --- pr_view → state=<open|closed|merged> mergeable=<true|false|unknown> ---
assert_eq "pr_view github mergeable" "state=open mergeable=true"      "$( MOCK_OUT=$'OPEN\tMERGEABLE'    FORGE_OVERRIDE=github pr_view PR1 )"
assert_eq "pr_view github conflict"  "state=open mergeable=false"     "$( MOCK_OUT=$'OPEN\tCONFLICTING'  FORGE_OVERRIDE=github pr_view PR1 )"
assert_eq "pr_view github merged"    "state=merged mergeable=unknown" "$( MOCK_OUT=$'MERGED\tUNKNOWN'    FORGE_OVERRIDE=github pr_view PR1 )"
assert_eq "pr_view gitlab open"      "state=open mergeable=true"      "$( MOCK_OUT='{"state": "opened", "merge_status": "can_be_merged"}' FORGE_OVERRIDE=gitlab pr_view MR1 )"
assert_eq "pr_view gitea boundary" "# gitea:pr_view boundary (tea/API — Phase 2 follow-up)" "$( FORGE_OVERRIDE=gitea pr_view PR1 )"

# --- pr_checks → TSV rows <name>\t<state>\t<conclusion> ---
pc_exp=$'build\tcompleted\tsuccess\nlint\tcompleted\tfailure\ndeploy\tpending\t'
pc_act="$( MOCK_OUT=$'build\tpass\t1m\turl\nlint\tfail\t2m\turl\ndeploy\tpending\t\turl' FORGE_OVERRIDE=github pr_checks PR1 )"
assert_eq "pr_checks github normalize" "$pc_exp" "$pc_act"

# --- dep_block → supported/applied capability ---
assert_eq "dep_block github" "supported=true applied=true"   "$( FORGE_OVERRIDE=github dep_block a b )"
assert_eq "dep_block gitlab" "supported=true applied=true"   "$( FORGE_OVERRIDE=gitlab dep_block a b )"
assert_eq "dep_block gitea"  "supported=false applied=false" "$( FORGE_OVERRIDE=gitea dep_block a b )"

# --- review_bots → per-forge bot capability list ---
assert_eq "review_bots github" "copilot coderabbit" "$( FORGE_OVERRIDE=github review_bots )"
assert_eq "review_bots gitlab" "coderabbit"         "$( FORGE_OVERRIDE=gitlab review_bots )"
assert_eq "review_bots gitea"  "coderabbit"         "$( FORGE_OVERRIDE=gitea review_bots )"

if [ "$fail" -eq 0 ]; then echo "PASS: all forge-driver assertions"; else echo "FAILURES present"; fi
exit $fail
