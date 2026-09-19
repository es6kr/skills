#!/usr/bin/env bash
# Fixture-driven test for resolve-session-id.sh.
set -euo pipefail
cd "$(dirname "$0")"

TMP_TEST_DIR=$(mktemp -d "${TMPDIR:-/tmp}/orca-test-session-id.XXXXXX")
trap 'rm -rf "$TMP_TEST_DIR"' EXIT

PROJECT_DIR="$TMP_TEST_DIR/projects/-Users-test-project"
mkdir -p "$PROJECT_DIR"

UUID_TARGET="7ef7b2b8-71b7-4c4a-927b-140b4190875b"
UUID_OTHER_ACTIVE="b37cce56-8ae8-4135-a6e9-5d6433e78680"

# Target session JSONL contains prompt "/fix-plan --pm"
cat > "$PROJECT_DIR/$UUID_TARGET.jsonl" <<EOF
{"type":"user","message":{"role":"user","content":"/fix-plan --pm"},"created_at":"2026-09-14T14:20:00Z"}
{"type":"assistant","message":{"role":"assistant","content":"Starting PM workflow"},"created_at":"2026-09-14T14:20:01Z"}
EOF

# Other concurrent session JSONL contains prompt "/fix-plan --deep" and is modified later!
cat > "$PROJECT_DIR/$UUID_OTHER_ACTIVE.jsonl" <<EOF
{"type":"user","message":{"role":"user","content":"/fix-plan --deep"},"created_at":"2026-09-14T14:20:05Z"}
{"type":"assistant","message":{"role":"assistant","content":"Deep auditing"},"created_at":"2026-09-14T14:20:06Z"}
EOF

# Explicitly make the OTHER active session's mtime newer than the target
touch -t 202609141425 "$PROJECT_DIR/$UUID_OTHER_ACTIVE.jsonl"
touch -t 202609141420 "$PROJECT_DIR/$UUID_TARGET.jsonl"

fail=0
assert_eq() { # $1=label $2=expected $3=actual
  if [ "$2" = "$3" ]; then
    echo "PASS $1"
  else
    echo "FAIL $1: expected=[$2] actual=[$3]"
    fail=1
  fi
}

# --- Case 1: Resolve target session by payload (mtime race immunity) ---
# Notice: ls -t would return $UUID_OTHER_ACTIVE, but payload search MUST return $UUID_TARGET!
out=$(./resolve-session-id.sh --payload "/fix-plan --pm" --project-dir "$PROJECT_DIR")
assert_eq "Payload matching returns target UUID despite older mtime" "$UUID_TARGET" "$out"

# --- Case 2: Resolve other session by its distinct payload ---
out_other=$(./resolve-session-id.sh --payload "/fix-plan --deep" --project-dir "$PROJECT_DIR")
assert_eq "Payload matching returns other UUID" "$UUID_OTHER_ACTIVE" "$out_other"

# --- Case 3: JSON output mode ---
out_json=$(./resolve-session-id.sh --payload "/fix-plan --pm" --project-dir "$PROJECT_DIR" --json)
sessid=$(printf '%s' "$out_json" | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>console.log(JSON.parse(s).sessionId))')
sessid8=$(printf '%s' "$out_json" | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>console.log(JSON.parse(s).sessid8))')
assert_eq "JSON sessionId matches" "$UUID_TARGET" "$sessid"
assert_eq "JSON sessid8 matches" "7ef7b2b8" "$sessid8"

# --- Case 4: Missing payload returns non-zero error ---
if ./resolve-session-id.sh --payload "nonexistent-marker-12345" --project-dir "$PROJECT_DIR" >/dev/null 2>&1; then
  echo "FAIL nonexistent payload should exit non-zero"
  fail=1
else
  echo "PASS nonexistent payload exits non-zero"
fi

exit $fail
