#!/usr/bin/env bash
# Covers hook_registry_verify.py --fix.
#
# Three registrations, three fates:
#   live-guard.sh     on disk           -> survives untouched
#   ghost-guard.sh    committed, deleted -> deregistered and tombstoned
#   pending-guard.sh  never committed    -> left alone
#
# The last one is the whole reason the mode consults git. An absent script has
# two causes that look identical on disk: it was deleted, or it was never
# committed and the registration is ahead of an implementation living in someone
# else's working tree. Tombstoning the second case destroys a guard that works.
#
# Idempotency is the other reason this file exists: the states this mode repairs
# are re-introduced by outside forces (a concurrent rebase, a half-finished
# refactor), so a correction that only works once cannot be wired into an
# automatic execution point. See failed-attempts.md
# class=manual-repetition-instead-of-automating-from-schema.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFY="$SCRIPT_DIR/../scripts/hook_registry_verify.py"
PASS=0
FAIL=0

if ! python3 -c 'import yaml' 2>/dev/null; then
  echo "SKIP: PyYAML not importable — hook_registry_verify.py requires it"
  exit 0
fi

ok()   { PASS=$((PASS+1)); echo "PASS: $1"; }
bad()  { FAIL=$((FAIL+1)); echo "FAIL: $1"; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected '$3', got '$2')"; fi; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

SKILLS="$TMP/skills-mkt"
PLUGINS="$TMP/plugins-mkt"
mkdir -p "$SKILLS/skills/demo/resources" "$SKILLS/hooks" "$PLUGINS/hooks"

printf '#!/bin/bash\nexit 0\n' > "$SKILLS/skills/demo/resources/live-guard.sh"
printf '#!/bin/bash\nexit 0\n' > "$SKILLS/skills/demo/resources/ghost-guard.sh"
chmod +x "$SKILLS/skills/demo/resources/live-guard.sh" "$SKILLS/skills/demo/resources/ghost-guard.sh"

cat > "$SKILLS/hooks/hooks.json" <<'JSON'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/skills/demo/resources/live-guard.sh"
          },
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/skills/demo/resources/ghost-guard.sh"
          },
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/skills/demo/resources/pending-guard.sh"
          }
        ]
      }
    ]
  }
}
JSON
printf '{\n  "hooks": {}\n}\n' > "$PLUGINS/hooks/hooks.json"

# The mode reads git history to tell a deletion from a not-yet-committed file,
# so the fixture has to be a real repo.
git -C "$SKILLS" init -q
git -C "$SKILLS" config user.email test@example.com
git -C "$SKILLS" config user.name test
git -C "$SKILLS" add skills hooks
git -C "$SKILLS" commit -qm "test: fixture"
git -C "$SKILLS" rm -q skills/demo/resources/ghost-guard.sh
git -C "$SKILLS" commit -qm "test: delete ghost-guard"

run_verify() { python3 "$VERIFY" --repo-root "$SKILLS" --plugins-root "$PLUGINS" "$@" 2>&1; }

BOOT="$(run_verify --bootstrap)"
case "$BOOT" in
  *orphan=2*) ok "bootstrap sees both orphan registrations" ;;
  *) bad "bootstrap should report orphan=2 — got: $BOOT" ;;
esac

FIX1="$(run_verify --fix)"
case "$FIX1" in
  *deregister*ghost-guard.sh*) ok "fix deregisters the deleted script" ;;
  *) bad "fix should deregister ghost-guard.sh — got: $FIX1" ;;
esac
case "$FIX1" in
  *"tombstone ghost-guard"*) ok "fix tombstones the emptied entry" ;;
  *) bad "fix should tombstone ghost-guard — got: $FIX1" ;;
esac
case "$FIX1" in
  *"LEAVING ALONE"*pending-guard.sh*) ok "fix leaves a never-committed path alone" ;;
  *) bad "fix should leave pending-guard.sh alone — got: $FIX1" ;;
esac
case "$FIX1" in
  *"tombstone pending-guard"*) bad "fix must not tombstone a never-committed path" ;;
  *) ok "never-committed path is not tombstoned" ;;
esac

LIVE=$(python3 - "$SKILLS/hooks/hooks.json" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1]))
cmds = [
    h.get("command", "")
    for groups in doc.get("hooks", {}).values()
    for g in groups
    for h in g.get("hooks", [])
]
print(
    sum("live-guard.sh" in c for c in cmds),
    sum("ghost-guard.sh" in c for c in cmds),
    sum("pending-guard.sh" in c for c in cmds),
)
PY
)
check "live survives, deleted gone, never-committed kept" "$LIVE" "1 0 1"

TOMB=$(python3 - "$SKILLS/skills/hook-kit/hook-registry.yaml" <<'PY'
import sys, yaml
hooks = (yaml.safe_load(open(sys.argv[1])) or {}).get("hooks") or []
e = next((h for h in hooks if h.get("id") == "ghost-guard"), None)
print("missing" if e is None else f"{e.get('status')}/{bool((e.get('tombstone') or {}).get('date'))}/{bool(e.get('registrations'))}")
PY
)
check "tombstone carries status+date and no registrations" "$TOMB" "removed/True/False"

BEFORE_HASH=$(shasum "$SKILLS/skills/hook-kit/hook-registry.yaml" "$SKILLS/hooks/hooks.json" | shasum)
FIX2="$(run_verify --fix)"
case "$FIX2" in
  *"nothing to correct"*) ok "second fix run is a no-op" ;;
  *) bad "second run should report nothing to correct — got: $FIX2" ;;
esac
AFTER_HASH=$(shasum "$SKILLS/skills/hook-kit/hook-registry.yaml" "$SKILLS/hooks/hooks.json" | shasum)
check "second run leaves both files byte-identical" "$AFTER_HASH" "$BEFORE_HASH"

echo
echo "hook-registry --fix: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
