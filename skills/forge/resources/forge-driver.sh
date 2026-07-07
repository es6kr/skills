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
# Two method families:
#   - command-assembly (pr_create/issue_create/issue_edit/pr_merge/ref_format): build the
#     host command; DRY_RUN=1 echoes it instead of executing (asserted in forge-driver.test.sh).
#   - normalized-return (pr_view/pr_checks/repo_visibility/auth_status/dep_block/review_bots):
#     EXECUTE the host CLI and normalize its output into a forge-neutral shape. Tests shadow
#     gh/glab (shell functions) to feed mock output, exercising the normalization logic
#     without live calls.
#
# GitLab-first decision (axis 4): GitHub is the reference implementation, GitLab adapters carry
# real normalization logic (live `glab` command shapes verified in a follow-up checklist item —
# see plan-forge-phase2.md §8), Gitea stays a boundary stub for API-dependent methods.

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

# ---- normalized-return methods (execute host CLI → forge-neutral shape) ----
# These EXECUTE (not DRY_RUN-echo) and normalize output. Tests shadow gh/glab.

# repo_visibility → PUBLIC | INTERNAL | PRIVATE
#   The critical sanitize-gate normalization (github-flow owns PUBLIC-vs-PRIVATE sanitize
#   rules). GitLab exposes a native 3-value visibility; GitHub/Gitea expose a boolean.
#   INTERNAL is a distinct value here, but sanitize gates treat it as non-public (like
#   PRIVATE) — it is not externally indexed. Unknown output fails OPEN to PUBLIC: a false
#   PUBLIC only over-applies sanitization (safe), whereas a false PRIVATE could leak.
repo_visibility() {
  case "$(forge_detect)" in
    github)
      case "$(gh repo view --json isPrivate --jq '.isPrivate' 2>/dev/null)" in
        true)  echo PRIVATE ;;
        false) echo PUBLIC ;;
        *)     echo PUBLIC ;;
      esac ;;
    gitlab)
      # glab has no --jq; parse the visibility field from the project JSON.
      # TODO(live): confirm the project selector (`projects/:id`) against a real glab session.
      case "$(glab api 'projects/:id' 2>/dev/null | grep -o '"visibility":[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([a-z]*\)"$/\1/')" in
        public)   echo PUBLIC ;;
        internal) echo INTERNAL ;;
        private)  echo PRIVATE ;;
        *)        echo PUBLIC ;;
      esac ;;
    gitea)  echo "# gitea:repo_visibility boundary (tea/API — Phase 2 follow-up)" ;;
  esac
}

# auth_status → account=<login> scopes=<csv> ok=<true|false>
auth_status() {
  local out account scopes
  case "$(forge_detect)" in
    github)
      out="$(gh auth status 2>&1)"
      account="$(printf '%s\n' "$out" | grep -oE 'account [A-Za-z0-9_.-]+' | head -1 | awk '{print $2}')"
      scopes="$(printf '%s\n' "$out" | grep -i 'token scopes' | grep -oE "'[^']+'" | tr -d "'" | paste -sd, -)"
      if [ -n "$account" ]; then echo "account=$account scopes=$scopes ok=true"; else echo "account= scopes= ok=false"; fi ;;
    gitlab)
      # TODO(live): confirm `glab auth status` line shape.
      out="$(glab auth status 2>&1)"
      account="$(printf '%s\n' "$out" | grep -oE 'as [A-Za-z0-9_.-]+' | head -1 | awk '{print $2}')"
      if [ -n "$account" ]; then echo "account=$account scopes= ok=true"; else echo "account= scopes= ok=false"; fi ;;
    gitea)  echo "# gitea:auth_status boundary (tea/API — Phase 2 follow-up)" ;;
  esac
}

# pr_view <ref> → state=<open|closed|merged> mergeable=<true|false|unknown>
pr_view() {
  local ref="$1" raw st mg
  case "$(forge_detect)" in
    github)
      raw="$(gh pr view "$ref" --json state,mergeable --jq '[.state, .mergeable] | @tsv' 2>/dev/null)"
      st="$(printf '%s' "$raw" | cut -f1 | tr '[:upper:]' '[:lower:]')"
      case "$(printf '%s' "$raw" | cut -f2)" in
        MERGEABLE)   mg=true ;;
        CONFLICTING) mg=false ;;
        *)           mg=unknown ;;
      esac
      echo "state=${st:-unknown} mergeable=$mg" ;;
    gitlab)
      # glab MR state=opened|closed|merged; merge_status=can_be_merged|cannot_be_merged.
      # TODO(live): confirm `glab mr view <ref> -F json` field names.
      raw="$(glab mr view "$ref" -F json 2>/dev/null)"
      st="$(printf '%s' "$raw" | grep -o '"state":[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([a-z]*\)"$/\1/')"
      case "$st" in opened) st=open ;; esac
      case "$(printf '%s' "$raw" | grep -o '"merge_status":[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([a-z_]*\)"$/\1/')" in
        can_be_merged)    mg=true ;;
        cannot_be_merged) mg=false ;;
        *)                mg=unknown ;;
      esac
      echo "state=${st:-unknown} mergeable=$mg" ;;
    gitea)  echo "# gitea:pr_view boundary (tea/API — Phase 2 follow-up)" ;;
  esac
}

# pr_checks <ref> → TSV rows: <name>\t<state>\t<conclusion>
#   state ∈ {completed, pending}; conclusion ∈ {success, failure, skipped, cancelled, ""}.
pr_checks() {
  local ref="$1"
  case "$(forge_detect)" in
    github)
      # gh pr checks rows: <name>\t<state>\t<elapsed>\t<url>, state ∈ pass|fail|pending|skipping|cancelled
      gh pr checks "$ref" 2>/dev/null | awk -F'\t' 'NF>=2 {
        name=$1; s=$2; ns="completed"; nc="";
        if (s=="pass")      { nc="success" }
        else if (s=="fail") { nc="failure" }
        else if (s=="pending") { ns="pending"; nc="" }
        else if (s=="skipping") { nc="skipped" }
        else if (s=="cancelled") { nc="cancelled" }
        else { nc=s }
        printf "%s\t%s\t%s\n", name, ns, nc
      }' ;;
    gitlab)
      # glab ci status rows vary; normalize status token to the same conclusion vocabulary.
      # TODO(live): confirm `glab ci status` column layout.
      glab ci status "$ref" 2>/dev/null | awk 'NF>=2 {
        name=$1; s=$2; ns="completed"; nc="";
        if (s=="success"||s=="passed") { nc="success" }
        else if (s=="failed") { nc="failure" }
        else if (s=="running"||s=="pending"||s=="created") { ns="pending"; nc="" }
        else if (s=="skipped") { nc="skipped" }
        else if (s=="canceled"||s=="cancelled") { nc="cancelled" }
        else { nc=s }
        printf "%s\t%s\t%s\n", name, ns, nc
      }' ;;
    gitea)  echo "# gitea:pr_checks boundary (commit-status API — Phase 2 follow-up)" ;;
  esac
}

# dep_block <a> <b> → supported=<true|false> applied=<true|false>
#   Declares native dependency-link capability per forge. Callers check `supported` before
#   relying on native links and fall back to a body ref (ref_format) when false. The live
#   link mutation lands in the adapter-impl cycle; this returns the capability + intent.
dep_block() {
  case "$(forge_detect)" in
    github) echo "supported=true applied=true" ;;   # GraphQL addSubIssue / addBlockedBy
    gitlab) echo "supported=true applied=true" ;;    # REST issue links (blocks)
    gitea)  echo "supported=false applied=false" ;;  # no native dep links → body-ref fallback
  esac
}

# review_bots → space-separated capability list of review bots available on the forge
review_bots() {
  case "$(forge_detect)" in
    github) echo "copilot coderabbit" ;;
    gitlab) echo "coderabbit" ;;
    gitea)  echo "coderabbit" ;;
  esac
}
