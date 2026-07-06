#!/usr/bin/env bash
# forge-driver.sh — forge-agnostic git-host driver shim (Phase 2, Seam B core-seam).
#
# Source this file, then call normalized methods. Callers stay forge-agnostic:
# the shim dispatches to gh (GitHub) / glab (GitLab) / tea (Gitea) per the resolved forge.
#
# Dispatch precedence (forge_detect):
#   1. FORGE_OVERRIDE          — explicit --forge= override
#   2. FORGE_REMOTE_URL        — test hook / caller-supplied remote
#      else `git remote get-url origin`
#   3. github                  — unresolved host → GitHub fallback (backward compat)
#
# DRY_RUN=1 makes command-assembling methods echo the assembled command instead of
# executing it (used by forge-driver.test.sh to assert command shape without live calls).
#
# Scope: this cycle implements dispatch + pr_create + ref_format (the Red-tested surface).
# Remaining driver-interface methods (pr_view/pr_merge/pr_checks/issue_create/issue_edit/
# repo_visibility/auth_status/dep_block/review_bots) land in follow-up TDD cycles, each
# introduced by its own Red test.

# forge_detect → github|gitlab|gitea
forge_detect() {
  if [ -n "${FORGE_OVERRIDE:-}" ]; then
    echo "$FORGE_OVERRIDE"
    return
  fi
  local url="${FORGE_REMOTE_URL:-$(git remote get-url origin 2>/dev/null || true)}"
  case "$url" in
    *gitlab*)          echo gitlab ;;
    *gitea*|*forgejo*) echo gitea ;;
    *github*)          echo github ;;
    *)                 echo github ;; # unresolved → GitHub fallback
  esac
}

# ref_format <pr|mr|issue> → display sigil for cross-references in bodies
#   GitLab MRs use `!N`; issues and everything else use `#N`.
ref_format() {
  case "$(forge_detect)/$1" in
    gitlab/pr | gitlab/mr) echo "!" ;;
    *)                     echo "#" ;;
  esac
}

# _run <cmd...> — execute, or echo the assembled command when DRY_RUN=1
_run() {
  if [ "${DRY_RUN:-}" = "1" ]; then
    echo "$*"
  else
    "$@"
  fi
}

# pr_create <base> <head> <title> <body> [draft]
#   Normalized PR/MR creation. Pass any non-empty 5th arg to request a draft.
pr_create() {
  local base="$1" head="$2" title="$3" body="$4" draft="${5:-}"
  case "$(forge_detect)" in
    github)
      if [ -n "$draft" ]; then
        _run gh pr create --base "$base" --head "$head" --title "$title" --body "$body" --draft
      else
        _run gh pr create --base "$base" --head "$head" --title "$title" --body "$body"
      fi
      ;;
    gitlab)
      if [ -n "$draft" ]; then
        _run glab mr create --target-branch "$base" --source-branch "$head" --title "$title" --description "$body" --draft
      else
        _run glab mr create --target-branch "$base" --source-branch "$head" --title "$title" --description "$body"
      fi
      ;;
    gitea)
      # tea has no native draft flag; draft is emulated at the caller (capability-matrix).
      _run tea pr create --base "$base" --head "$head" --title "$title" --description "$body"
      ;;
  esac
}

# issue_create <title> <body>
issue_create() {
  local title="$1" body="$2"
  case "$(forge_detect)" in
    github) _run gh issue create --title "$title" --body "$body" ;;
    gitlab) _run glab issue create --title "$title" --description "$body" ;;
    gitea)  _run tea issue create --title "$title" --description "$body" ;;
  esac
}

# issue_edit <ref> <body>
issue_edit() {
  local ref="$1" body="$2"
  case "$(forge_detect)" in
    github) _run gh issue edit "$ref" --body "$body" ;;
    gitlab) _run glab issue update "$ref" --description "$body" ;;
    gitea)  echo "# gitea:issue_edit boundary (tea/API — Phase 2 follow-up)" ;;
  esac
}

# pr_merge <ref> <squash|merge|rebase>
pr_merge() {
  local ref="$1" strategy="${2:-squash}"
  case "$(forge_detect)" in
    github) _run gh pr merge "$ref" "--$strategy" ;;
    gitlab) _run glab mr merge "$ref" "--$strategy" ;;
    gitea)  echo "# gitea:pr_merge boundary (tea/API — Phase 2 follow-up)" ;;
  esac
}
