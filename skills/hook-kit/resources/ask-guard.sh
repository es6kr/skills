#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — consolidated guard for AskUserQuestion-stage anti-patterns.
#
# Consolidates 4 source hooks (a 5th, TaskList #NN ambiguity, was re-homed to
# todowrite/resources/block-tasklist-id-in-conversation.sh — that check is
# domain-specific to TaskList conventions, not a general AskUserQuestion
# concern, per automation.md's hook-ownership policy. A 6th, the PR-URL gate
# that used to live bundled inside the old TaskList-ID hook's file, was split
# out to github-flow/resources/block-pr-url-gate.sh for the same reason):
#   1. block-merge-without-review.sh           (merge option without AI Review Summary + Test Plan)
#   2. block-release-please-close-without-verification.sh (release-please/semantic-release close without verification)
#   3. block-vendor-in-generic-skill.sh        (AskUserQuestion branch: vendor names not introduced by user)
#   4. block-supervisor-loop-work-recommend.py (Ralph supervisor session recommending Ralph-loop work)
#
# Strategy:
#   - Single jq pass extracts ASK_TEXT, OPTIONS_BLOB, TRANSCRIPT path
#   - Lazy load USER_TEXT (full transcript user messages) — only for vendor / supervisor checks
#   - Lazy load CONTEXT_BLOB (last 200 transcript lines) — only for supervisor check
#   - Run checks in cost order (no-I/O first). First deny → exit 2.

set -uo pipefail

# Load locale-specific regex patterns from data/. The file is git-ignored so
# the public es6kr/skills repo never contains Korean characters. When the data
# file is missing (e.g., fresh clone in a non-Korean environment), each
# variable falls back to an English-only pattern via ${VAR:-default} below.
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
HG_ASK_ACTIVE_MERGE_KO="${HG_ASK_ACTIVE_MERGE_KO:-}"
HG_ASK_ACTIVE_MERGE_EN="${HG_ASK_ACTIVE_MERGE_EN:+${HG_ASK_ACTIVE_MERGE_EN}|}Squash and merge|squash and merge|squash merge|Squash merge|merge it|proceed with merge|do merge|Merge this"
# Known limitation: bare \bmerge\b over-matches git branch-merge / conflict-resolution
# asks (e.g. "merge origin/main into next-fix"), non-PR "merge" nouns (e.g. "plan
# merge", "doc merge", "consolidation"), task-clustering "merge/split", PR-state
# "await-merge", and meta-discussion of this very guard ("ask-guard merge-keyword
# false positive") — none of which are PR-merge recommendations.
# Mitigated by HG_ASK_RETROSPECT_MERGE below (includes "merge origin/", "conflict
# resolution", "resolve conflict", "plan merge", "consolidat*", "merge/split",
# "merge-keyword", "await-merge", "ask-guard") — phrase such asks with those tokens
# to pass. Strong merge intent ("Squash and merge", "merge it") still hits
# HG_ASK_ACTIVE_MERGE_EN and is gated regardless of these exclusions.
# Convention for the HG_* pattern vars below: `:+…|` (additive), not `:-` (override).
# The locale data file is sourced first, so `:-` made ITS value replace everything
# here — the committed patterns became dead code on any machine that happens to have
# the untracked file, and which set wins depended on that file's existence rather than
# on intent. Union keeps the committed baseline authoritative and lets the git-ignored
# file only ADD locale variants.
#
# NOT applied to vars whose inline default is EMPTY (the locale-only ones, e.g. the
# *_KO pairs): `${VAR:+$VAR|}` with an empty default yields a trailing `|`, and an ERE
# ending in `|` matches the empty string — i.e. the guard would match everything and
# silently open. Those vars have no override problem to fix in the first place, so they
# keep `:-`. Same for file-path vars and the `_NEVER_MATCH` sentinels (deliberate no-ops).
HG_ASK_MERGE_KEYWORDS="${HG_ASK_MERGE_KEYWORDS:+${HG_ASK_MERGE_KEYWORDS}|}\bmerge\b|\bMerge\b|\bMERGE\b|\bSquash\b|\bsquash\b"
HG_ASK_RETROSPECT_MERGE="${HG_ASK_RETROSPECT_MERGE:+${HG_ASK_RETROSPECT_MERGE}|}merged|MERGED|after merge|post-merge|squash type|squash subject|squash commit|merge time|validation|verification|merge --abort|merge abort|conflict resolution|resolve conflict|resolving conflict|review ?anchor|merge origin/|plan merge|doc merge|docs? merge|consolidat[a-z]*|merges? into|merge target|merge base|base branch|merge option|merge ask|merge gating|merge check|[a-z-]*-merge-[a-z-]*\.sh|block-merge-without-review"
# Append-guarantee (recurrence fix): the locale data file (data/hangul-patterns.regex)
# fully REDEFINES HG_ASK_RETROSPECT_MERGE (Korean + a snapshot of the English set).
# A stale locale snapshot silently drops English exclusions added to the :- default
# above — the recurring root cause of the merge-keyword false positive. Append the
# English non-PR-merge exclusions unconditionally AFTER any override so no stale
# locale file can re-open them. Append-only is safe: retrospect exclusions only ever
# make an ask PASS. NEW English non-PR-merge senses belong on THIS append line, not
# the :- default, so they survive a locale override.
# "[Mm]erge[ -][Rr]isk" is a review-tool verdict label (CodeRabbit prints
# "Merge Risk: Critical" on its PR walkthrough), not a proposal to merge. Quoting a
# PR's review status in an option description is the most ordinary thing an ask can
# do, and it tripped this gate twice in one session — the second time on the very ask
# that was reporting the first as a defect.
HG_ASK_RETROSPECT_MERGE="${HG_ASK_RETROSPECT_MERGE}|merge/split|split/merge|merge[- ]?keyword|merge[- ]?fp|merge[- ]?false[- ]?positive|await[- ]?merge|awaiting[- ]?merge|class[- ]?merge|merge[- ]?class|ask-guard|[Mm]erge[ -][Rr]isk"
HG_ASK_SUMMARY_ATTESTATION="${HG_ASK_SUMMARY_ATTESTATION:+${HG_ASK_SUMMARY_ATTESTATION}|}AI Review Summary.*(completed|posted|✅)|github\.com/.+/pull/[0-9]+#issuecomment-[0-9]+"
HG_ASK_TESTPLAN_ATTESTATION="${HG_ASK_TESTPLAN_ATTESTATION:+${HG_ASK_TESTPLAN_ATTESTATION}|}Test Plan.*(all).*\[x\]|Test Plan [0-9]+/[0-9]+ ✅|Test Plan.*✅"
HG_ASK_CLOSE_KEYWORDS="${HG_ASK_CLOSE_KEYWORDS:+${HG_ASK_CLOSE_KEYWORDS}|}close"
# bash's ${VAR:-default} parser brace-matches literal `{`/`}` inside the
# default word even though they're not part of a nested ${...} — an
# unescaped `{0,15}` here gets its closing `}` misread as ending the
# expansion, corrupting the resulting pattern (verified: the runtime value
# silently drops the `}` after `15` and gains a stray one at the end,
# producing "grep: invalid repetition count(s)" wherever this var is used).
# Fix: keep the default in a separate quoted constant with no bare `${:-}`
# nesting, so no default-word brace-matching happens.
_HG_ASK_RETROSPECT_CLOSE_DEFAULT="close deferred|deferred[^.]{0,15}close|cannot close|not close|closeable|becomes close"
HG_ASK_RETROSPECT_CLOSE="${HG_ASK_RETROSPECT_CLOSE:-$_HG_ASK_RETROSPECT_CLOSE_DEFAULT}"
HG_ASK_VERIFICATION_ATTESTATION="${HG_ASK_VERIFICATION_ATTESTATION:+${HG_ASK_VERIFICATION_ATTESTATION}|}gh pr (view|diff)|base=|pinned|counter only|verified|diff URL|issuecomment"
HG_ASK_PUSH_KO="${HG_ASK_PUSH_KO:-}"
HG_ASK_COMMIT_KO="${HG_ASK_COMMIT_KO:-}"
HG_ASK_PR_STRONG_KO="${HG_ASK_PR_STRONG_KO:-}"
HG_ASK_PR_READY_KO="${HG_ASK_PR_READY_KO:-}"
HG_ASK_STATEFUL_RESOURCE="${HG_ASK_STATEFUL_RESOURCE:+${HG_ASK_STATEFUL_RESOURCE}|}longhorn|replica|PVC|persistentvolume|volume\.longhorn|storage|snapshot|etcd|vault|qdrant.*data|postgres.*data|mysql.*data|database.*volume"
HG_ASK_DESTRUCTIVE_VOLUME_OP="${HG_ASK_DESTRUCTIVE_VOLUME_OP:+${HG_ASK_DESTRUCTIVE_VOLUME_OP}|}PV[[:space:]]+(recreate|delete|wipe|reset)|volume[[:space:]]+(recreate|delete|wipe|reset|purge)|PVC[[:space:]]+(delete|recreate)|replica[[:space:]]+(force[[:space:]]*delete|force[[:space:]]*remove|wipe)|snapshot[[:space:]]+(delete|purge)|wipe[[:space:]]+(data|volume)|fresh[[:space:]]+volume"
HG_ASK_DATA_SAFETY_CLAIM="${HG_ASK_DATA_SAFETY_CLAIM:+${HG_ASK_DATA_SAFETY_CLAIM}|}no[[:space:]]+data[[:space:]]+loss|data[[:space:]]+(safe|intact|preserved|integrity)|auto[- ]?recover|salvage|safely[[:space:]]+(delete|remove)|safe[[:space:]]+to[[:space:]]+(delete|remove|recreate)"
HG_ASK_STATE_ATTESTATION="${HG_ASK_STATE_ATTESTATION:+${HG_ASK_STATE_ATTESTATION}|}kubectl[[:space:]]+(get|describe)[[:space:]]+(replica|volume|pv|pvc|snapshot)|replica[[:space:]]+count[[:space:]]*(=|:)|spec\.numberOfReplicas|status\.robustness|replica[[:space:]]*(verified)|primary[- ]?source[[:space:]]+(verified|checked)|attestation|attested|state[[:space:]]+verified"

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" != "AskUserQuestion" ]] && exit 0

# Extract two views of the question text:
#   ASK_TEXT     = question + option labels + descriptions, newline-separated
#   OPTIONS_BLOB = option labels + descriptions, newline-joined (excludes question text)
ASK_TEXT=$(echo "$INPUT" | jq -r '
  .tool_input.questions[]? |
  (.question // ""),
  (.options[]? | (.label // ""), (.description // ""))
' 2>/dev/null)

OPTIONS_BLOB=$(echo "$INPUT" | jq -r '
  [.tool_input.questions[]?.options[]? | (.label // ""), (.description // "")]
  | join("\n")
' 2>/dev/null)

[[ -z "$ASK_TEXT" ]] && exit 0

TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)

# Interpreter resolution: probe for a WORKING python, not merely a name on
# PATH. The Windows py3 shim is a Microsoft Store stub that exits 49 without
# running anything, so a name-only check leaves every python-backed check
# silently dead (stderr is discarded and the caller fails open).
PY=""
for _c in python3 python; do
  if command -v "$_c" >/dev/null 2>&1 && "$_c" -c "pass" >/dev/null 2>&1; then
    PY="$_c"; break
  fi
done

# Lazy loaders for transcript-derived blobs
USER_TEXT=""
USER_TEXT_LOADED=0
CONTEXT_BLOB=""
CONTEXT_BLOB_LOADED=0

load_user_text() {
  [[ "$USER_TEXT_LOADED" -eq 1 ]] && return 0
  USER_TEXT_LOADED=1
  if [[ -z "$TRANSCRIPT" || ! -f "$TRANSCRIPT" ]]; then
    return 0
  fi
  if [[ -z "$PY" ]]; then
    echo "WARN: no working python interpreter found — user-text-dependent checks (vendor-leak exemption, supervisor-loop check) are skipped this call" >&2
    return 0
  fi

  USER_TEXT=$("$PY" - "$TRANSCRIPT" <<'PYEOF' 2>/dev/null
import json, sys
path = sys.argv[1]
out = []
with open(path, encoding="utf-8", errors="ignore") as fh:
    for line in fh:
        try:
            d = json.loads(line)
        except Exception:
            continue
        msg = d.get("message") or {}
        if msg.get("role") == "user":
            c = msg.get("content")
            if isinstance(c, str):
                out.append(c)
            elif isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "text":
                        out.append(b.get("text", ""))
print(" ".join(out))
PYEOF
)
}

load_context_blob() {
  [[ "$CONTEXT_BLOB_LOADED" -eq 1 ]] && return 0
  CONTEXT_BLOB_LOADED=1
  if [[ -z "$TRANSCRIPT" || ! -f "$TRANSCRIPT" ]]; then
    return 0
  fi
  CONTEXT_BLOB=$(tail -n 200 "$TRANSCRIPT" 2>/dev/null)
}

# Check 1 (TaskList #NN ambiguity) re-homed to
# todowrite/resources/block-tasklist-id-in-conversation.sh — registered as its
# own PreToolUse:AskUserQuestion hook, see automation.md's hook-ownership policy.

# ============================================================================
# Check 2: Merge option without AI Review Summary + Test Plan attestation
# ============================================================================
check_merge_without_review() {
  [[ -z "$OPTIONS_BLOB" ]] && return 0

  # Active merge intent — explicit recommendation to merge now.
  # Locale-specific phrasing comes from data/hangul-patterns.regex; the
  # English-only fallback is sufficient when the data file is absent.
  local active_merge=0
  if [[ -n "$HG_ASK_ACTIVE_MERGE_KO" ]] && echo "$OPTIONS_BLOB" | grep -qE "$HG_ASK_ACTIVE_MERGE_KO"; then
    active_merge=1
  elif echo "$OPTIONS_BLOB" | grep -qE "$HG_ASK_ACTIVE_MERGE_EN"; then
    active_merge=1
  fi

  if [[ "$active_merge" -eq 0 ]]; then
    # Plain merge keyword — check whether any mention survives after removing
    # retrospective/non-PR-merge context lines (past tense, technical
    # reference, git branch-history sync, hook/script filenames containing
    # "merge"). A count-ratio comparison (plain vs retrospect line counts)
    # previously missed same-line co-occurrences whenever the JSON payload
    # put a retrospect phrase and the "merge" token on different structural
    # lines (e.g. "merge origin/next-fix" split across a multi-line question
    # object) — filtering out retrospect-matched lines FIRST, then checking
    # the remainder, is co-occurrence-independent and closes that gap.
    echo "$OPTIONS_BLOB" | grep -qE "$HG_ASK_MERGE_KEYWORDS" || return 0

    local non_retrospect_merge_lines
    non_retrospect_merge_lines=$(echo "$OPTIONS_BLOB" | grep -vE "$HG_ASK_RETROSPECT_MERGE" | grep -cE "$HG_ASK_MERGE_KEYWORDS")
    if [[ "$non_retrospect_merge_lines" -eq 0 ]]; then
      return 0
    fi
  fi

  echo "$OPTIONS_BLOB" | grep -qE '#[0-9]+|pull/[0-9]+' || return 0

  # release-please bot-PR allowlist (issue #36).
  # If EVERY PR referenced in the merge options is a bot-authored release PR,
  # bypass both attestation gates — there is nothing for a human reviewer to
  # inspect line-by-line on an automated version-bump PR.
  #
  # Allowlist match (PR qualifies if ANY clause holds):
  #   - author.login  in { github-actions[bot], release-please[bot], dependabot[bot], ... }
  #   - headRefName    starts with  release-please--   OR   dependabot/
  #
  # Fail closed: if gh is unavailable/unauthenticated, the repo cannot be
  # resolved, or any referenced PR lookup fails (404 / network), that PR is
  # treated as NOT allowlisted and the existing gates run. Never fail open.
  if command -v gh >/dev/null 2>&1; then
    local rp_repo rp_prs rp_all=1 rp_seen=0 rp_n rp_view rp_author rp_headref
    rp_repo="${GH_REPO:-$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null)}"
    rp_prs=$(echo "$OPTIONS_BLOB" \
      | grep -oE '#[0-9]+|pull/[0-9]+' \
      | grep -oE '[0-9]+' | sort -u)
    if [[ -n "$rp_repo" && -n "$rp_prs" ]]; then
      while IFS= read -r rp_n; do
        [[ -z "$rp_n" ]] && continue
        rp_seen=1
        rp_view=$(gh pr view "$rp_n" --json author,headRefName \
          -q '.author.login + "\t" + .headRefName' -R "$rp_repo" 2>/dev/null)
        if [[ -z "$rp_view" ]]; then
          rp_all=0; break          # lookup failure -> fail closed
        fi
        rp_author="${rp_view%%$'\t'*}"
        rp_headref="${rp_view#*$'\t'}"
        # gh pr view returns .author.login as "app/github-actions" for the
        # GitHub App variant; webhook/API payloads use "github-actions[bot]".
        # Match both forms (one-line additions for future bots).
        case "$rp_author" in
          "github-actions[bot]"|"release-please[bot]"|"app/github-actions"|"app/release-please"|"dependabot[bot]"|"app/dependabot"|"dependabot") continue ;;
        esac
        case "$rp_headref" in
          "release-please--"*|"dependabot/"*) continue ;;
        esac
        rp_all=0; break            # a non-bot PR is present -> require attestation
      done <<< "$rp_prs"
      if [[ "$rp_seen" -eq 1 && "$rp_all" -eq 1 ]]; then
        return 0                   # all referenced PRs are bot release PRs
      fi
    fi
  fi

  # Solo-infra-repo exemption (personal repos with no CI + no reviewers).
  # When EVERY referenced PR sits in a repo that has NO CI checks AND NO
  # requested reviewers / submitted reviews, there is no pipeline or reviewbot
  # for a /consolidate AI Review Summary to attest against — the two attestation
  # gates below are structurally unsatisfiable, so a merge ask gets endlessly
  # reworded. Exempt such asks. (Recurs on solo infra repos: no CI, no reviewers.)
  #
  # Fail closed: gh unavailable/unauthenticated, repo unresolved, or ANY per-PR
  # lookup failure -> NOT exempt (existing gates run). Never fail open. Any CI
  # check OR any requested-reviewer/review present -> NOT a solo-infra repo.
  if command -v gh >/dev/null 2>&1; then
    local si_repo si_prs si_all=1 si_seen=0 si_n si_rev si_checks
    si_repo="${GH_REPO:-$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null)}"
    si_prs=$(echo "$OPTIONS_BLOB" | grep -oE '#[0-9]+|pull/[0-9]+' | grep -oE '[0-9]+' | sort -u)
    if [[ -n "$si_repo" && -n "$si_prs" ]]; then
      while IFS= read -r si_n; do
        [[ -z "$si_n" ]] && continue
        si_seen=1
        si_rev=$(gh pr view "$si_n" --json reviewRequests,reviews \
          -q '((.reviewRequests|length)+(.reviews|length))' -R "$si_repo" 2>/dev/null)
        [[ -z "$si_rev" ]] && { si_all=0; break; }   # lookup failure -> fail closed
        [[ "$si_rev" != "0" ]] && { si_all=0; break; }  # reviewer/review present
        si_checks=$(gh pr checks "$si_n" -R "$si_repo" --json bucket -q 'length' 2>/dev/null)
        [[ -z "$si_checks" ]] && { si_all=0; break; }   # lookup failure -> fail closed
        [[ "$si_checks" != "0" ]] && { si_all=0; break; }  # CI present
      done <<< "$si_prs"
      if [[ "$si_seen" -eq 1 && "$si_all" -eq 1 ]]; then
        return 0                   # all referenced PRs: CI-less + reviewer-less repo
      fi
    fi
  fi

  # CI-gate-only accumulation-branch exemption.
  # When EVERY referenced PR sits on a base branch where reviews are structurally
  # disabled (a CI-gate-only accumulation branch — e.g. a two-tier staging model
  # whose real review gate is the later promotion PR), no AI Review Summary can
  # ever exist for it, so the two attestation gates below are unsatisfiable and a
  # merge ask gets endlessly reworded. Detect this generically via the reviewer
  # bot's own "reviews are disabled for this base branch" check line — no
  # hardcoded branch names (same signal consolidate/pr.md's CI-gate-only gate
  # keys on), so the exemption stays portable across repos.
  #
  # Fail closed: gh unavailable/unauthenticated, repo unresolved, or ANY per-PR
  # `gh pr checks` failure / missing signal -> NOT exempt (existing gates run).
  if command -v gh >/dev/null 2>&1; then
    local cg_repo cg_prs cg_all=1 cg_seen=0 cg_n cg_checks
    cg_repo="${GH_REPO:-$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null)}"
    cg_prs=$(echo "$OPTIONS_BLOB" | grep -oE '#[0-9]+|pull/[0-9]+' | grep -oE '[0-9]+' | sort -u)
    if [[ -n "$cg_repo" && -n "$cg_prs" ]]; then
      while IFS= read -r cg_n; do
        [[ -z "$cg_n" ]] && continue
        cg_seen=1
        cg_checks=$(gh pr checks "$cg_n" -R "$cg_repo" 2>/dev/null || true)
        [[ -z "$cg_checks" ]] && { cg_all=0; break; }   # lookup failure -> fail closed
        echo "$cg_checks" | grep -qiE 'reviews are disabled for this base branch' \
          || { cg_all=0; break; }                       # base not review-disabled
      done <<< "$cg_prs"
      if [[ "$cg_seen" -eq 1 && "$cg_all" -eq 1 ]]; then
        return 0                   # all referenced PRs sit on a review-disabled base
      fi
    fi
  fi

  # Gate 1: AI Review Summary attestation
  # Locale variants in data/hangul-patterns.regex (HG_ASK_SUMMARY_ATTESTATION).
  if ! echo "$OPTIONS_BLOB" | grep -qE "$HG_ASK_SUMMARY_ATTESTATION"; then
    cat >&2 <<'MSG'
DENIED: AskUserQuestion has merge option for a PR without AI Review Summary attestation.

Why blocked:
  - One or more options reference merge/Squash + PR #N
  - But no option text mentions "AI Review Summary ✅/posted" or quotes an issuecomment URL

Required action (pick one before retrying):
  1. Run /consolidate pr <N> first to post AI Review Summary, then re-issue the question
  2. If Summary is already posted, include "AI Review Summary posted" in the option description
  3. Replace the merge option with a non-merge action (e.g., "verify only", "hold")

Reference: failed-attempts.md "AI Review Summary missing on merge recommendation" (7+ recurrences).
MSG
    exit 2
  fi

  # Gate 2: Test Plan attestation
  # Locale variants in data/hangul-patterns.regex (HG_ASK_TESTPLAN_ATTESTATION).
  if ! echo "$OPTIONS_BLOB" | grep -qE "$HG_ASK_TESTPLAN_ATTESTATION"; then
    cat >&2 <<'MSG'
DENIED: AskUserQuestion has merge option for a PR without Test Plan attestation.

Why blocked:
  - One or more options reference merge/Squash + PR #N
  - AI Review Summary attestation is present ✅
  - But no option text mentions "Test Plan N/N ✅" or "Test Plan all [x]"

Required action (pick one before retrying):
  1. Verify Test Plan items first (Playwright, curl, manual test) and check [x] on PR body
  2. Include "Test Plan N/N ✅" in the option description after all items are checked
  3. Replace the merge option with "Test Plan verification" or "hold"

Reference: failed-attempts.md "Test Plan unchecked on merge recommendation" (5+ recurrences).
MSG
    exit 2
  fi
}

# ============================================================================
# Check 3: release-please / semantic-release / changesets close without verification
# ============================================================================
check_release_please_close() {
  [[ -z "$OPTIONS_BLOB" ]] && return 0
  echo "$OPTIONS_BLOB" | grep -qiE 'release-please|semantic-release|changesets' || return 0
  echo "$OPTIONS_BLOB" | grep -qiE "$HG_ASK_CLOSE_KEYWORDS" || return 0

  # Skip when close mentions are retrospective/deferred rather than active
  # proposals ("publish/close deferred", "cannot close ... without a merged PR",
  # or a discard-changes keyword). Mirror of the retrospective-merge guard in
  # check_merge_without_review: when deferred/negated close mentions dominate
  # (>= plain close mentions), there is no active close proposal to gate.
  local plain_close retro_close
  plain_close=$(echo "$OPTIONS_BLOB" | grep -ciE "$HG_ASK_CLOSE_KEYWORDS")
  retro_close=$(echo "$OPTIONS_BLOB" | grep -ciE "$HG_ASK_RETROSPECT_CLOSE")
  if [[ "$retro_close" -ge "$plain_close" ]]; then
    return 0
  fi

  echo "$OPTIONS_BLOB" | grep -qE '#[0-9]+|pull/[0-9]+' || return 0
  echo "$OPTIONS_BLOB" | grep -qiE "$HG_ASK_VERIFICATION_ATTESTATION" && return 0

  cat >&2 <<'MSG'
DENIED: AskUserQuestion recommends closing a release-please / semantic-release / changesets PR
without verification attestation.

Why blocked:
  - Options reference release-automation tool (release-please/semantic-release/changesets)
  - Options reference close action + PR number
  - But no option text shows verification attestation (gh pr view/diff result, pinned base, counter only, etc.)

Required action (pick one before retrying):
  1. Apply workflow/config fix → push → wait for next auto-generated PR
  2. Run `gh pr view <new-PR> --json title,body` or `gh pr diff <new-PR>` to verify
     intended behavior (pinned base, counter-only increment, etc.)
  3. Include verification result in the option description:
     "verified (PR #N base=0.4.9-beta.4, diff URL) → close"
  4. Then re-issue AskUserQuestion

Reference: ~/.agents/rules/release-automation.md 'auto-generated PR close recommendation prerequisites (HARD STOP)'.
failed-attempts.md: 'speculative release-please config option presentation' (3 recurrences, hook escalation).
MSG
  exit 2
}

# ============================================================================
# Check 4: Vendor name leak in question/options (not introduced by user)
# ============================================================================
check_vendor_leak() {
  local violations=""
  load_user_text

  # Workload context exception (Issue #109): If k8s/cluster workload context tokens are present, skip vendor leak check.
  # "Application" is checked case-SENSITIVE (exact ArgoCD CRD Kind casing) — a
  # case-insensitive match here also catches the ordinary English word
  # "application" anywhere in prose (e.g. "for this application's vector
  # search"), which silently disables the entire vendor-leak scan below.
  local workload_pattern_cs='\bApplication\b'
  local workload_pattern_ci='\b(workload|pod|namespace|Prune|selfHeal|StatefulSet|Deployment)\b'
  if [[ -n "${HG_ASK_WORKLOAD_CONTEXT_KO:-}" ]]; then
    workload_pattern_ci="(${workload_pattern_ci}|${HG_ASK_WORKLOAD_CONTEXT_KO})"
  fi
  if echo "$ASK_TEXT" | grep -qE "$workload_pattern_cs" || echo "$ASK_TEXT" | grep -qiE "$workload_pattern_ci"; then
    return 0
  fi

  for vendor in qdrant chroma weaviate pinecone milvus pgvector redis-search; do
    if echo "$ASK_TEXT" | grep -qiE "\b${vendor}\b|mcp__${vendor}([_-]|$)"; then
      if ! echo "$USER_TEXT" | grep -qiE "\b${vendor}\b"; then
        local hits
        hits=$(echo "$ASK_TEXT" | grep -oiE "\b${vendor}\b|mcp__${vendor}([_-]|$)" | sort -u | head -3 | tr '\n' ' ')
        violations="${violations}  - ${vendor}: ${hits}\n"
      fi
    fi
  done

  for cli in qdrant-find qdrant-store chroma-find chroma-store; do
    if echo "$ASK_TEXT" | grep -qiE "\b${cli}\b"; then
      if ! echo "$USER_TEXT" | grep -qiE "\b${cli}\b"; then
        local hits
        hits=$(echo "$ASK_TEXT" | grep -oiE "\b${cli}\b" | sort -u | head -3 | tr '\n' ' ')
        violations="${violations}  - ${cli}: ${hits}\n"
      fi
    fi
  done

  [[ -z "$violations" ]] && return 0

  {
    echo "DENIED: AskUserQuestion contains vendor-specific tool/service name not introduced by user."
    echo ""
    echo "Why blocked:"
    echo "  - skill-usage.md 'Author-facing media coverage extension'"
    echo "  - Vendor name in option label/description biases user choice before they pick a backend"
    echo "  - Recent user message did NOT introduce this vendor, so this is an assistant-side leak"
    echo ""
    echo "Vendor patterns found in question/options:"
    echo -e "$violations"
    echo "Required action (pick one before retrying):"
    echo "  1. Replace vendor name with abstract term:"
    echo "     - 'qdrant-find' / 'qdrant-store' → 'RAG semantic search' / 'RAG receiver store'"
    echo "     - 'qdrant' / 'pgvector' (backend name) → 'RAG backend' or 'vector store'"
    echo "     - 'mcp__<vendor>__*' → 'RAG store MCP tool'"
    echo "  2. If user explicitly asked about this vendor (e.g., 'pgvector vs qdrant comparison'),"
    echo "     rephrase user input to include the vendor name first, then retry."
    echo ""
    echo "Reference: ~/.agents/rules/skill-usage.md 'Author-facing media coverage extension'"
  } >&2
  exit 2
}

# ============================================================================
# Check 5: Supervisor session recommending Ralph-loop work
# ============================================================================
check_supervisor_loop_recommend() {
  [[ -z "$OPTIONS_BLOB" ]] && return 0
  if [[ -z "$PY" ]]; then
    echo "WARN: no working python interpreter found — supervisor-loop-recommend check skipped this call" >&2
    return 0
  fi

  # Quick trigger pattern check before loading transcript
  if ! "$PY" -c "
import re, sys
blob = sys.argv[1]
pat = re.compile(r'(?<![A-Za-z0-9_-])(consolidate|pr-review|/consolidate|/github-flow\s+merge|code-reviewer)(?![A-Za-z0-9_-])', re.IGNORECASE)
sys.exit(0 if pat.search(blob) else 1)
" "$OPTIONS_BLOB" 2>/dev/null; then
    return 0
  fi

  load_context_blob
  [[ -z "$CONTEXT_BLOB" ]] && return 0

  if ! "$PY" -c "
import re, sys
blob = sys.argv[1]
pat = re.compile(
    r'\"name\"\s*:\s*\"Skill\"[\s\S]{0,500}?\"skill\"\s*:\s*\"ralph\"[\s\S]{0,200}?supervise'
    r'|\"ralph\",\s*\"supervise\"'
    r'|/ralph\s+supervise'
    r'|ralph\s+supervise',
    re.IGNORECASE,
)
sys.exit(0 if pat.search(blob) else 1)
" "$CONTEXT_BLOB" 2>/dev/null; then
    return 0
  fi

  cat >&2 <<'MSG'
DENIED: AskUserQuestion in Ralph supervisor session recommends Ralph-loop work.

Why blocked:
  - Supervisor context detected (recent `Skill("ralph", "supervise")` invocation)
  - Option label/description contains Ralph-loop trigger keyword
    (consolidate / pr-review / /consolidate / /github-flow merge / code-reviewer)

Per agent-coord.md "supervise vs Ralph loop separation (HARD STOP)":
  - Supervisor session = report / analysis / user-decision support only
  - Ralph loop owns: consolidate, merge, code-review execution

Required action (pick one before retrying):
  1. Remove the trigger-keyword option(s); report the same content as TEXT instead
     (e.g., "PR #N has no AI Review Summary -- the next Ralph loop can run consolidate")
  2. Replace with supervisor-allowed options:
     BLOCKED triage / fix_plan.md cleanup / improvements.md update / start next Ralph loop
  3. Only if the user explicitly typed an override such as "handle this in the supervise session directly"
     earlier may you bypass this hook -- and you should still re-confirm via AskUserQuestion
     without the trigger keyword in the option.

Reference: failed-attempts.md "supervise vs Ralph loop" entries (4+ recurrences as of 2026-06-12)
MSG
  exit 2
}

# ============================================================================
# Check 6: Stateful infrastructure data-safety assertion guard
# ============================================================================
# Two sub-gates:
#   (A) Destructive volume/replica operations as options — outright deny.
#       User mandate: "prevent data loss on recurrence — never put 'recreate the PV' in the options".
#   (B) Data-safety claims (no data loss / auto-recovery / salvage) on stateful
#       resources WITHOUT state-verification attestation (kubectl get / replica
#       count / robustness / primary-source check) → deny.
#       Recurrence pattern of "asserting external-tool behavior" extended to stateful infra.
check_stateful_data_safety() {
  [[ -z "$OPTIONS_BLOB" ]] && return 0

  # Gate A: destructive volume/replica operation present in any option
  if echo "$OPTIONS_BLOB" | grep -qiE "$HG_ASK_DESTRUCTIVE_VOLUME_OP"; then
    cat >&2 <<'MSG'
DENIED: AskUserQuestion option proposes destructive operation on a stateful resource (PV/volume/PVC/replica/snapshot).

Why blocked:
  - One or more options contains a destructive verb (recreate / delete / wipe / reset / purge / fresh volume) applied to a stateful resource.
  - Destructive stateful operations risk irreversible data loss and MUST NOT be presented as casual user options.

Required action (pick one before retrying):
  1. Remove the destructive option entirely. Stateful recovery uses non-destructive paths first:
     - Replica salvage (clear .spec.failedAt) — preserves data on disk
     - Restore from snapshot/backup (if exists)
     - Manual disk inspection (SSH + check /var/lib/longhorn/replicas/.../volume.meta)
  2. If destruction is truly the only path, do NOT present it as an option. Instead:
     - Report the situation as text (no options)
     - Document the data-loss implication explicitly
     - Wait for the user to explicitly type the destructive command themselves
  3. The user mandate: "never put 'recreate the PV' in the options" — destructive PV/volume operations are forbidden as ask options.

Reference: failed-attempts.md "stateful destructive option in ask" + k3s.md "no data-loss-capable operation as an ask option"
MSG
    exit 2
  fi

  # Gate B: data-safety claim on stateful resource without state attestation
  if echo "$OPTIONS_BLOB" | grep -qiE "$HG_ASK_STATEFUL_RESOURCE" && \
     echo "$OPTIONS_BLOB" | grep -qiE "$HG_ASK_DATA_SAFETY_CLAIM"; then
    if ! echo "$OPTIONS_BLOB" | grep -qiE "$HG_ASK_STATE_ATTESTATION"; then
      cat >&2 <<'MSG'
DENIED: AskUserQuestion claims data safety on a stateful resource without primary-source state verification.

Why blocked:
  - Option references a stateful resource (longhorn / replica / PV / PVC / volume / snapshot / etcd / vault) AND
  - Option asserts data safety (no data loss / auto-recovery / salvage / safely delete) BUT
  - No option text quotes state verification (kubectl get replica/volume, spec.numberOfReplicas, status.robustness, replica count, primary-source check).

Why this matters:
  - "Auto-recovers from healthy replicas on node X" was asserted previously without checking that node X actually had replicas. Result: only 1 replica existed, on the failed node. Data was at risk before verification.
  - Stateful claims require primary-source proof in the same option, not assumptions about defaults (e.g., "longhorn usually has 3 replicas").

Required action (pick one before retrying):
  1. Run primary-source checks first, then include the result in the option description:
     - `kubectl -n <ns> get replica.longhorn.io -o jsonpath='{.items[*].spec.nodeID},{.items[*].status.currentState}'`
     - `kubectl -n <ns> get volume.longhorn.io <vol> -o jsonpath='{.spec.numberOfReplicas}|{.status.robustness}'`
     - `kubectl get pvc <pvc> -o jsonpath='{.status.phase}'`
  2. Quote the verified state in option description (e.g., "verified: 2 replicas, 1 healthy on a1-1, robustness=degraded").
  3. If verification is not possible, do NOT claim data safety. State the risk explicitly instead.

Reference: failed-attempts.md "stateful data-safety claim without verification" (4th recurrence of "asserting external-tool behavior") + k3s.md "stateful operations require primary-source verification"
MSG
      exit 2
    fi
  fi
}

# ============================================================================
# Check 7: PR-creation option without explicit draft marker
# ============================================================================
# Trigger: option proposes PR creation but description lacks 'draft' keyword.
# Reference: github-flow/pr.md:15 "Draft default governs upstream asks too (HARD STOP)"
# Failed-attempts entry: "next-suggestion ask option with 'create PR' — missing draft marker"
#   - 1st: github-flow/pr.md:15 rule established
#   - 2nd 2026-06-24: next/suggestion-patterns.md cross-ref added
#   - 3rd 2026-06-28: hook escalation (this check)
check_pr_creation_without_draft() {
  [[ -z "$OPTIONS_BLOB" ]] && return 0

  # PR-creation detection — split strong (imperative creation) vs weak (compound
  # workflow mention) signals to avoid gray-zone false positives. A weak signal
  # such as "worktree + PR" often only *describes* a branch-policy consequence
  # ("branch-policy applies (feat/fix worktree + PR)") rather than proposing a PR
  # be created — so it counts only when an imperative creation cue co-occurs.
  local pr_strong_pattern="gh pr create|create PR|create a PR|creates a PR|open a PR|opens a PR|raise a PR|submit a PR${HG_ASK_PR_STRONG_KO:+|$HG_ASK_PR_STRONG_KO}"
  local pr_weak_pattern='push.*\+.*PR|cherry-pick.*PR|worktree.*PR|branch.*\+.*PR'
  local pr_creation_cue='create|creates|open a PR|opens a PR|raise a PR|submit a PR|make a PR|new PR'

  local pr_proposes_creation=0
  if echo "$OPTIONS_BLOB" | grep -qiE "$pr_strong_pattern"; then
    pr_proposes_creation=1
  elif echo "$OPTIONS_BLOB" | grep -qiE "$pr_weak_pattern" \
       && echo "$OPTIONS_BLOB" | grep -qiE "$pr_creation_cue"; then
    pr_proposes_creation=1
  fi

  [[ "$pr_proposes_creation" -eq 0 ]] && return 0

  # Check if 'draft' keyword present in options (covers both creation paths and ready opt-out)
  if echo "$OPTIONS_BLOB" | grep -qiE "draft|--ready"; then
    return 0
  fi

  # Exception: user explicitly requested ready PR in recent turns
  load_user_text
  if echo "$USER_TEXT" | grep -qiE "ready PR|--ready|non-draft|non draft${HG_ASK_PR_READY_KO:+|$HG_ASK_PR_READY_KO}"; then
    return 0
  fi

  cat >&2 <<'MSG'
DENIED: AskUserQuestion option proposes PR creation without explicit 'draft' marker.

Why blocked:
  - One or more options contains PR creation verbs (gh pr create / create PR / cherry-pick + PR / worktree + PR) with a co-occurring creation cue, BUT
  - The option description does not include 'draft' or '--ready' keyword AND
  - No explicit user request for ready (non-draft) PR was detected in recent transcript.

Per github-flow/pr.md:15 "Draft default governs upstream asks too (HARD STOP)":
  - Every PR creation option must be labeled as "draft PR" by default
  - A ready (non-draft) PR must be a separate option (e.g., "push + ready PR --ready"), never folded into a generic "create PR" label
  - No explicit ready request → draft

Required action (pick one before retrying):
  1. Edit option label/description to include 'draft PR' explicitly (e.g., "Push + draft PR creation")
  2. If both draft and ready paths are valid, present them as separate options:
     - "Push + draft PR creation (default)"
     - "Push + ready PR creation (--ready, autonomous review trigger)"
  3. If the user explicitly requested a ready PR, paraphrase that in your text response before this AskUserQuestion call so the hook can detect it.

Reference: failed-attempts.md "next-suggestion ask option with 'create PR' — missing draft marker" (3rd recurrence 2026-06-28) + github-flow/pr.md:15
MSG
  exit 2
}

check_push_without_details() {
  # Push-recommendation detail check — options proposing git push must specify target remote/branch AND commit info (SHA or subject)
  # Locale-specific phrasing comes from data/hangul-patterns.regex (HG_ASK_PUSH_KO);
  # the English-only fallback is sufficient when the data file is absent.
  local push_pattern="git push|pushing|push to|Push"
  if [[ -n "$HG_ASK_PUSH_KO" ]]; then
    push_pattern="$push_pattern|$HG_ASK_PUSH_KO"
  fi
  if ! echo "$OPTIONS_BLOB" | grep -qiE "$push_pattern"; then
    return 0
  fi

  # Skip if the ask is not actually proposing a git push execution (e.g. asking whether to push or skip, or post-push verification mentions)
  if echo "$OPTIONS_BLOB" | grep -qiE "do not push|skip push|push skipped|no push"; then
    return 0
  fi

  # Skip meta-discussion of this very gate (fixing/describing the push-detail
  # requirement itself, not proposing an actual push) — same class of FP the
  # merge-gate's HG_ASK_RETROSPECT_MERGE already exempts via a bare "ask-guard"
  # self-reference. Without this, an option like "fix ask-guard.sh's Git Push
  # gate false positive" collaterally blocks the whole call, including any
  # co-occurring option that never mentions push at all.
  if echo "$OPTIONS_BLOB" | grep -qiE "push[- ]?(gate|detail)|ask-guard.*push|push.*ask-guard|push.*(false[- ]?positive|\bFP\b)"; then
    return 0
  fi

  local commit_pattern="commit|hash|sha|[0-9a-f]{7,40}"
  if [[ -n "$HG_ASK_COMMIT_KO" ]]; then
    commit_pattern="$commit_pattern|$HG_ASK_COMMIT_KO"
  fi

  # Per-option iteration: only block when an individual option that proposes push lacks details
  local option_line
  while IFS= read -r option_line; do
    [[ -z "$option_line" ]] && continue
    if echo "$option_line" | grep -qiE "$push_pattern"; then
      # Ignore meta-discussion or skip mentions in this specific option line
      if echo "$option_line" | grep -qiE "do not push|skip push|push skipped|no push|push[- ]?(gate|detail)|ask-guard.*push|push.*ask-guard|push.*(false[- ]?positive|\bFP\b)"; then
        continue
      fi

      local has_remote=0
      local has_commit_info=0

      if echo "$option_line" | grep -qiE "origin/|remote|branch|local|main|master|target:" || echo "$ASK_TEXT" | grep -qiE "origin/|remote|branch|local|main|master|target:"; then
        has_remote=1
      fi

      if echo "$option_line" | grep -qiE "$commit_pattern" || echo "$ASK_TEXT" | grep -qiE "$commit_pattern"; then
        has_commit_info=1
      fi

      if [[ "$has_remote" -eq 0 || "$has_commit_info" -eq 0 ]]; then
        cat >&2 <<'MSG'
DENIED: AskUserQuestion option proposes Git Push without explicit remote/branch and commit details.

Why blocked:
  - Option proposes a Git Push action, BUT
  - The question/option text lacks explicit target remote/branch details (e.g., origin/local, origin/main) OR commit details (SHA / commit subject).

Per git.md and GEMINI.md "Git Push Recommendation Detail Rule (HARD STOP)":
  - Whenever recommending or asking for Git Push execution, you MUST state the exact target remote, branch, and commit SHA/subject so the user can immediately evaluate the action.

Required action:
  - Run 'git remote -v' and 'git log -1' to inspect primary state.
  - Include explicit target remote/branch and commit SHA/subject in your AskUserQuestion question or option description text.
MSG
        exit 2
      fi
    fi
  done <<< "$OPTIONS_BLOB"

  return 0
}

# Execute checks in cost order
check_merge_without_review
check_release_please_close
check_vendor_leak
check_supervisor_loop_recommend
check_stateful_data_safety
check_pr_creation_without_draft
check_push_without_details

exit 0
