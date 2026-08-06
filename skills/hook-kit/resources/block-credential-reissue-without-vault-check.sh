#!/usr/bin/env bash
# PreToolUse:AskUserQuestion — block a credential/token (re)issuance ask when no
# secret-store check happened earlier in this session.
#
# Background: failed-attempts.md class `credential-absent-verdict-without-secret-store`
# (3rd occurrence, 2026-08-05) — an env var reading MISSING (e.g. DGS_PLANE_API_KEY)
# was treated as "token never issued / lost" without checking the shared es6kr
# Vault (`vault kv list secret/`) or the local `data/secrets/*.txt` cache first.
# Two prior occurrences got rule-level guards (web-browser/credential-issue.md,
# es6kr/vault.md self-check) that didn't cover this ask shape (a Plane API token
# missing outside the browser-credential-issue flow). Per escalation policy
# (1st=rule / 2nd=hook review / 3rd=hook required), this hook enforces it
# deterministically.

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
[[ "$TOOL_NAME" == "AskUserQuestion" ]] || exit 0

TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)

# Locale patterns (git-ignored data file; English-only fallback below).
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [[ -f "$HG_DATA_FILE" ]]; then . "$HG_DATA_FILE"; fi
DIRECTIVE="${HG_MD_DIRECTIVE_KO:-issue|reissue|generate}"
CONTEXT="${HG_MD_BROWSER_CTX:-token|Token|API key|credential}"

# Collect all question/option text from this AskUserQuestion call.
ASK_TEXT=$(echo "$INPUT" | jq -r '
  [.tool_input.questions[]? |
    (.question // ""),
    (.options[]? | (.label // "") + " " + (.description // ""))
  ] | join(" ")
' 2>/dev/null)

[[ -n "$ASK_TEXT" ]] || exit 0

# Must mention BOTH a reissue/generate directive AND a token/credential context
# word — narrows to "propose issuing a new credential", not any mention of
# "token" (e.g. context-usage token counts) or a bare directive word alone.
echo "$ASK_TEXT" | grep -qiE "$DIRECTIVE" || exit 0
echo "$ASK_TEXT" | grep -qiE "$CONTEXT" || exit 0

# Evidence a secret-store check already happened this session: a Bash tool_use
# whose command matches `vault kv (list|get)` or greps data/secrets/.
HAS_VAULT_CHECK=0
if [[ -n "$TRANSCRIPT_PATH" && -f "$TRANSCRIPT_PATH" ]]; then
  if jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use") | (.input.command? // "")' "$TRANSCRIPT_PATH" 2>/dev/null \
       | grep -qE 'vault kv (list|get)|data/secrets/' 2>/dev/null; then
    HAS_VAULT_CHECK=1
  fi
fi

[[ "$HAS_VAULT_CHECK" -eq 1 ]] && exit 0

cat >&2 <<'EOF'
[hook:block-credential-reissue-without-vault-check] BLOCKED (exit 2)

This AskUserQuestion proposes issuing/reissuing an external-service token or
API key, but no secret-store check (`vault kv list/get` or `data/secrets/*.txt`
grep) has run yet in this session's transcript.

An env var reading MISSING is not proof the credential was never issued —
check first (3rd recurrence of this exact miss, failed-attempts.md
"credential-absent-verdict-without-secret-store"):
  1. `data/secrets/*.txt` in the owning skill's directory (Glob/Grep)
  2. `vault kv list secret/` on the shared Vault (also stores other
     workspaces' secrets, not just this repo's own)

Only ask the user to (re)issue after both come back empty.
EOF
exit 2
