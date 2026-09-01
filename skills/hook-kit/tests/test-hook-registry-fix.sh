#!/usr/bin/env bash
# Covers hook_registry_verify.py --fix: it must deregister orphan registrations,
# tombstone the entries left with nothing, leave live registrations untouched,
# and be a no-op on a second run.
#
# Idempotency is the point of the mode, not a nicety: the states it repairs get
# re-introduced by outside forces (a concurrent rebase, a half-finished
# refactor), so a correction that only works once has an expected lifetime close
# to zero. See failed-attempts.md class=manual-repetition-instead-of-automating-from-schema.

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
chmod +x "$SKILLS/skills/demo/resources/live-guard.sh"

# ghost-guard.sh is deliberately NOT created — that is the orphan under test.
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
          }
        ]
      }
    ]
  }
}
JSON
printf '{\n  "hooks": {}\n}\n' > "$PLUGINS/hooks/hooks.json"

run_verify() { python3 "$VERIFY" --repo-root "$SKILLS" --plugins-root "$PLUGINS" "$@" 2>&1; }

BOOT="$(run_verify --bootstrap)"
case "$BOOT" in
  *orphan=1*) ok "bootstrap sees the orphan registration" ;;
  *) bad "bootstrap should report orphan=1 — got: $BOOT" ;;
esac

FIX1="$(run_verify --fix)"
case "$FIX1" in
  *"deregister"*ghost-guard.sh*) ok "fix deregisters the orphan" ;;
  *) bad "fix should deregister ghost-guard.sh — got: $FIX1" ;;
esac
case "$FIX1" in
  *"tombstone ghost-guard"*) ok "fix tombstones the emptied entry" ;;
  *) bad "fix should tombstone ghost-guard — got: $FIX1" ;;
esac
case "$FIX1" in
  *"no findings"*) ok "registry validates clean after fix" ;;
  *) bad "registry should validate clean after fix — got: $FIX1" ;;
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
print(sum("live-guard.sh" in c for c in cmds), sum("ghost-guard.sh" in c for c in cmds))
PY
)
check "live registration survives, ghost is gone" "$LIVE" "1 0"

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
