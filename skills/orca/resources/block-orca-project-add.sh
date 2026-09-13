#!/usr/bin/env bash
# block-orca-project-add.sh (PreToolUse:Bash)
#
# Orca's durable project/repository registry must not be expanded by an agent.
# New work is launched only from already-registered workspace roots and panes.
set -euo pipefail

input=$(cat)
command=$(printf '%s' "$input" | python -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit(0)
print((data.get("tool_input") or {}).get("command") or data.get("command") or "")
' 2>/dev/null)

[ -z "$command" ] && exit 0

# Ignore command names inside quoted literals; an echoed example is not a call.
sanitized=$(printf '%s' "$command" | sed -E "s/'[^']*'//g; s/\"[^\"]*\"//g")
# Match direct Orca CLI invocations even when ordinary environment variables
# prefix the command. Only the explicit approval marker bypasses this guard.
project_add_re='(^|[;&|][[:space:]]*)([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]+[[:space:]]+)*orca[[:space:]]+(repo[[:space:]]+add|project[[:space:]]+setup-(existing-folder|clone|create))\b'
printf '%s' "$sanitized" | grep -qE "$project_add_re" || exit 0

# This marker is set only when the user explicitly requests root-folder
# registration for the current Orca session. Arbitrary environment prefixes do
# not bypass the guard.
printf '%s' "$sanitized" | grep -qE '(^|[;&|][[:space:]]*)ORCA_PROJECT_REGISTRATION_APPROVED=1([[:space:]]|$)' && exit 0

cat >&2 <<'EOF'
============================================================
⛔ [Safety Hook] BLOCKED: Orca project/repository registration.

Do not run `orca repo add` or `orca project setup-existing-folder|setup-clone|setup-create`.
Reuse an already-registered workspace root and its existing terminals/panes.
Read-only `orca repo list` and `orca project list` remain allowed.
============================================================
EOF
exit 2
