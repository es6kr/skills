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
HG_ASK_ACTIVE_MERGE_EN="${HG_ASK_ACTIVE_MERGE_EN:-Squash and merge|squash and merge|squash merge|Squash merge|merge it|proceed with merge|do merge|Merge this}"
# Known limitation: bare \bmerge\b over-matches git branch-merge / conflict-resolution
# asks (e.g. "merge origin/main into next-fix"), non-PR "merge" nouns (e.g. "plan
# merge", "doc merge", "consolidation"), not just PR-merge recommendations.
# Mitigated by HG_ASK_RETROSPECT_MERGE below (includes "merge origin/", "conflict
# resolution", "resolve conflict", "plan merge", "consolidat*") — phrase such asks
# with those tokens to pass.
HG_ASK_MERGE_KEYWORDS="${HG_ASK_MERGE_KEYWORDS:-\bmerge\b|\bMerge\b|\bMERGE\b|\bSquash\b|\bsquash\b}"
HG_ASK_RETROSPECT_MERGE="${HG_ASK_RETROSPECT_MERGE:-merged|MERGED|after merge|post-merge|squash type|squash subject|squash commit|merge time|validation|verification|merge --abort|merge abort|conflict resolution|resolve conflict|resolving conflict|review ?anchor|merge origin/|plan merge|doc merge|docs? merge|consolidat[a-z]*}"
HG_ASK_SUMMARY_ATTESTATION="${HG_ASK_SUMMARY_ATTESTATION:-AI Review Summary.*(completed|posted|✅)|github\.com/.+/pull/[0-9]+#issuecomment-[0-9]+}"
HG_ASK_TESTPLAN_ATTESTATION="${HG_ASK_TESTPLAN_ATTESTATION:-Test Plan.*(all).*\[x\]|Test Plan [0-9]+/[0-9]+ ✅|Test Plan.*✅}"
HG_ASK_CLOSE_KEYWORDS="${HG_ASK_CLOSE_KEYWORDS:-close}"
HG_ASK_RETROSPECT_CLOSE="${HG_ASK_RETROSPECT_CLOSE:-close deferred|deferred[^.]{0,15}close|cannot close|not close|closeable|becomes close}"
HG_ASK_VERIFICATION_ATTESTATION="${HG_ASK_VERIFICATION_ATTESTATION:-gh pr (view|diff)|base=|pinned|counter only|verified|diff URL|issuecomment}"
HG_ASK_PR_STRONG_KO="${HG_ASK_PR_STRONG_KO:-}"
HG_ASK_PR_READY_KO="${HG_ASK_PR_READY_KO:-}"

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
    # Plain merge keyword — check whether all mentions are retrospective
    # (past tense / technical reference) vs forward-looking.
    # Retrospective uses ("merged already", "squash type", "squash subject")
    # describe historical or release-please cascade mechanics and are not
    # merge proposals. Skip the gate when retrospective uses dominate
    # (>= plain mentions).
    echo "$OPTIONS_BLOB" | grep -qE "$HG_ASK_MERGE_KEYWORDS" || return 0

    local retrospect_lines plain_lines
    plain_lines=$(echo "$OPTIONS_BLOB" | grep -cE "$HG_ASK_MERGE_KEYWORDS")
    retrospect_lines=$(echo "$OPTIONS_BLOB" | grep -cE "$HG_ASK_RETROSPECT_MERGE")
    if [[ "$retrospect_lines" -ge "$plain_lines" ]]; then
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
  #   - author.login  in { github-actions[bot], release-please[bot] }
  #   - headRefName    starts with  release-please--
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
          "release-please--"*"dependabot/"*) continue ;;
        esac
        rp_all=0; break            # a non-bot PR is present -> require attestation
      done <<< "$rp_prs"
      if [[ "$rp_seen" -eq 1 && "$rp_all" -eq 1 ]]; then
        return 0                   # all referenced PRs are bot release PRs
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

  # Workload context exception (Issue #109): If k8s/cluster workload context tokens are present, skip vendor leak check
  local workload_pattern='\b(Application|workload|pod|namespace|Prune|selfHeal|StatefulSet|Deployment)\b'
  if [[ -n "${HG_ASK_WORKLOAD_CONTEXT_KO:-}" ]]; then
    workload_pattern="(${workload_pattern}|${HG_ASK_WORKLOAD_CONTEXT_KO})"
  fi
  if echo "$ASK_TEXT" | grep -qiE "$workload_pattern"; then
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

# Execute checks in cost order
check_merge_without_review
check_release_please_close
check_vendor_leak
check_supervisor_loop_recommend
check_stateful_data_safety
check_pr_creation_without_draft

exit 0
