#!/usr/bin/env bash
# Stop hook: consolidated session-end RAG check (store + find anti-patterns).
#
# Consolidates check-session-rag-store.sh + check-session-rag-find.sh into a
# single transcript scan that extracts all metrics at once. Both anti-patterns
# are evaluated independently; if either trips, exit 2 with a combined message.
#
# Anti-pattern 1 — findings-without-store:
#   The session produced findings (task completions, skill/rule/hook edits,
#   audit/discovery signals) but never called a RAG-store tool. Findings should
#   be persisted to RAG before ending the session.
#   Override: user says "no RAG store needed" or "skip qdrant store".
#
# Anti-pattern 2 — store-without-find:
#   The session called RAG-store tools but never called RAG-find tools. Data
#   accumulates without being consulted — defeats the loop's learning purpose.
#   Override: user message contains the literal token 'skip-find-check'.
#
# Vendor-agnostic detection:
#   STORE tool match: ^mcp__<vendor>__.*-store$ (qdrant-store, chroma-store, ...)
#   FIND  tool match: ^mcp__<vendor>__.*-find$  (qdrant-find,  chroma-find, ...)
#
# Exit codes:
#   0 = allow stop (no anti-pattern triggered, or override active)
#   2 = block stop + inject reminder via stderr (LLM reads stderr on exit 2)

set -uo pipefail

# Ralph autonomous loop (RALPH_LOOP=1) has no interactive user to supply the
# "no RAG store needed" override, so this Stop hook's exit-2 block would stall
# the loop every turn until the circuit breaker trips. Headless loops manage RAG
# persistence via their own wrapper, so pass unconditionally here.
if [[ "${RALPH_LOOP:-}" == "1" ]]; then exit 0; fi

# Load locale-specific regex patterns from data/. The file is git-ignored so
# the public repo never sees Korean characters. When absent, the audit signal
# pattern falls back to an English-only regex.
HG_DATA_FILE="$(dirname "$0")/../data/hangul-patterns.regex"
if [ -f "$HG_DATA_FILE" ]; then
  # shellcheck source=/dev/null
  . "$HG_DATA_FILE"
fi
HG_RAG_AUDIT_SIGNAL="${HG_RAG_AUDIT_SIGNAL:-audit|discovery|decision|deployment|fa-prune|self-improving|retrospect}"
export HG_RAG_AUDIT_SIGNAL

input="$(cat)"
[ -z "$input" ] && exit 0

transcript="$(printf '%s' "$input" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('transcript_path', ''))
except Exception:
    pass
" 2>/dev/null)"

[ -z "$transcript" ] && exit 0
[ ! -f "$transcript" ] && exit 0

# Single transcript scan extracting all metrics for both checks
metrics="$(python3 - "$transcript" <<'PYEOF'
import json, os, re, sys

path = sys.argv[1]
store_re = re.compile(r"^mcp__[A-Za-z0-9_-]+__.*-store$")
find_re  = re.compile(r"^mcp__[A-Za-z0-9_-]+__.*-find$")
audit_re = re.compile(
    os.environ.get("HG_RAG_AUDIT_SIGNAL", r"audit|discovery|decision|deployment|fa-prune|self-improving|retrospect"),
    re.IGNORECASE,
)
skill_path_re = re.compile(r"/(skills|rules|hooks)/.*\.(md|sh|py|js|ts)$")

store_count = 0
find_count = 0
task_completed = 0
skill_or_rule_edits = 0
audit_signal = 0
find_skip = False
store_skip = False

with open(path, encoding="utf-8", errors="ignore") as fh:
    for line in fh:
        try:
            ent = json.loads(line)
        except Exception:
            continue
        msg = ent.get("message") or {}
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "tool_use":
                    tname = block.get("name", "")
                    tinput = block.get("input", {}) or {}
                    if store_re.match(tname):
                        store_count += 1
                    elif find_re.match(tname):
                        find_count += 1
                    elif tname == "TaskUpdate" and tinput.get("status") == "completed":
                        task_completed += 1
                    elif tname in {"Edit", "Write"}:
                        fp = tinput.get("file_path", "")
                        if skill_path_re.search(fp):
                            skill_or_rule_edits += 1
        if msg.get("role") == "user":
            txt = ""
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        txt += block.get("text", "")
            elif isinstance(content, str):
                txt = content
            if txt:
                if "skip-find-check" in txt:
                    find_skip = True
                if "no RAG store needed" in txt or "skip qdrant store" in txt:
                    store_skip = True
                if audit_re.search(txt):
                    audit_signal += 1

print(f"{store_count}|{find_count}|{task_completed}|{skill_or_rule_edits}|{audit_signal}|{1 if find_skip else 0}|{1 if store_skip else 0}")
PYEOF
)"

IFS='|' read -r store_count find_count task_completed skill_or_rule_edits audit_signal find_skip store_skip <<<"$metrics"
store_count="${store_count:-0}"
find_count="${find_count:-0}"
task_completed="${task_completed:-0}"
skill_or_rule_edits="${skill_or_rule_edits:-0}"
audit_signal="${audit_signal:-0}"
find_skip="${find_skip:-0}"
store_skip="${store_skip:-0}"

findings=$((task_completed + skill_or_rule_edits + audit_signal))

# Evaluate Anti-pattern 1: findings-without-store
ap1_trip=0
if [ "$store_skip" != "1" ] && [ "$store_count" -eq 0 ] && [ "$findings" -gt 0 ]; then
    ap1_trip=1
fi

# Evaluate Anti-pattern 2: store-without-find
ap2_trip=0
if [ "$find_skip" != "1" ] && [ "$store_count" -gt 0 ] && [ "$find_count" -eq 0 ]; then
    ap2_trip=1
fi

# All clear → allow stop
if [ "$ap1_trip" -eq 0 ] && [ "$ap2_trip" -eq 0 ]; then
    exit 0
fi

# Compose combined stderr message for any tripped anti-pattern
{
    if [ "$ap1_trip" -eq 1 ]; then
        cat <<EOF
Session-end RAG store check: this session has $findings finding-signal(s) but $store_count RAG-store call(s).

Signals detected:
  - Task completions: $task_completed
  - Skill/rule/hook edits: $skill_or_rule_edits
  - Audit/discovery prompts: $audit_signal
  - RAG-store calls: $store_count

Per skill-usage.md "session-end RAG store requirement": store key findings to a RAG receiver before ending the session. Use the appropriate <vendor>-store MCP tool (1 call per finding, with metadata keys: type, project, date, category).

To skip this check intentionally, the user must explicitly say "no RAG store needed" or "skip qdrant store".

EOF
    fi
    if [ "$ap2_trip" -eq 1 ]; then
        cat <<EOF
Session-end RAG find check: session has $store_count RAG-store call(s) but $find_count RAG-find call(s).

Anti-pattern: data accumulates without being consulted. The RAG loop's value is store + find together. Stores alone build a write-only archive.

Counts:
  - RAG-store calls: $store_count
  - RAG-find calls:  $find_count

Per skill-usage.md "session-end RAG store requirement" pairs with read-side rules in fix.md Step 1 / retrospect.md Step 1.5: every store should have a corresponding find earlier in the session (or be answering a find from a prior session).

To skip this check intentionally (e.g., one-shot ingestion job), include the literal token 'skip-find-check' in a user message before ending the session.
EOF
    fi
} >&2
exit 2
