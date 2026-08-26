#!/usr/bin/env bash
# Tests for warn-fixplan-item-schema.sh
#
# R1 is the regression under fix: editing ONLY an item's header line leaves the
# item's Why/How outside the edit window, and the anchor exemption (keyed on an
# exact old_string header match) cannot see it because the header text itself
# changed. The advisory then reports Why/How as missing while both exist on disk.
#
# T2-T10 are the nets that must keep passing: a genuinely incomplete item still
# has to be flagged, and the scope carve-outs ([x] / [BLOCKED] / non-tracker file
# / non-edit tool / insert-before-anchor) must stay silent.

HOOK="$(cd "$(dirname "$0")/../resources" && pwd)/warn-fixplan-item-schema.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Each case gets its own directory so the fixture can keep the literal name the
# hook's path filter accepts ("*/fix_plan.md"). Disambiguating by filename
# instead (fix_plan_t2.md) silently drops the case out of scope, which reads as
# a pass for every case that expects silence.
mkdir -p "$TMP"/t2 "$TMP"/t3 "$TMP"/t4 "$TMP"/t5 "$TMP"/t6 "$TMP"/t7 "$TMP"/t8 "$TMP"/t9 "$TMP"/t10

pass=0
fail=0
RC=0
ERR=""

run_hook() {
  ERR="$(printf '%s' "$1" | bash "$HOOK" 2>&1 >/dev/null)"
  RC=$?
}

mk_edit() { # file_path old_string new_string
  jq -n --arg fp "$1" --arg o "$2" --arg n "$3" \
    '{tool_name:"Edit", tool_input:{file_path:$fp, old_string:$o, new_string:$n}}'
}

mk_write() { # file_path content
  jq -n --arg fp "$1" --arg c "$2" \
    '{tool_name:"Write", tool_input:{file_path:$fp, content:$c}}'
}

check() { # name expected_rc
  if [ "$2" = "$RC" ]; then
    pass=$((pass + 1))
    printf 'ok   %s\n' "$1"
  else
    fail=$((fail + 1))
    printf 'FAIL %s (expected rc=%s, got rc=%s)\n' "$1" "$2" "$RC"
    printf '%s\n' "$ERR" | sed 's/^/       /'
  fi
}

# ---------------------------------------------------------------------------
# R1 — header-only edit on an item whose Why/How live below the edit window
# ---------------------------------------------------------------------------
FP="$TMP/fix_plan.md"
cat >"$FP" <<'EOF'
# fix_plan

## Progress

- [ ] Fix the login redirect loop on Safari
  - **Why**: Users bounce between /login and /callback after SSO.
  - **How to apply**: Add a state check in the callback handler; verify with an E2E run.

- [ ] Add retry to the export job
  - **Why**: Transient S3 timeouts fail the nightly export.
  - **How to apply**: Wrap the upload in a 3-attempt backoff; assert in unit tests.
EOF
run_hook "$(mk_edit "$FP" \
  '- [ ] Fix the login redirect loop' \
  '- [ ] Fix the login redirect loop on Safari')"
check "R1 header-only edit does not report existing Why/How as missing" 0

# ---------------------------------------------------------------------------
# T2 — a genuinely incomplete item is still flagged
# ---------------------------------------------------------------------------
FP="$TMP/t2/fix_plan.md"
cat >"$FP" <<'EOF'
# fix_plan

- [ ] Do a thing without rationale

- [ ] Complete item
  - **Why**: reason recorded.
  - **How to apply**: procedure recorded.
EOF
run_hook "$(mk_edit "$FP" '## Progress' '- [ ] Do a thing without rationale')"
check "T2 item missing Why/How is flagged" 2

# ---------------------------------------------------------------------------
# T3 — a complete item authored via Write stays silent
# ---------------------------------------------------------------------------
FP="$TMP/t3/fix_plan.md"
CONTENT='- [ ] Ship the audit log viewer
  - **Why**: Support cannot answer "who changed this" without shell access.
  - **How to apply**: Add a read-only view over the events table; cover with an integration test.'
printf '%s\n' "$CONTENT" >"$FP"
run_hook "$(mk_write "$FP" "$CONTENT")"
check "T3 complete item stays silent" 0

# ---------------------------------------------------------------------------
# T4 — completed [x] items belong to the bloat hook
# ---------------------------------------------------------------------------
FP="$TMP/t4/fix_plan.md"
CONTENT='- [x] Ship the dashboard filter
  - Landed in the March release.'
printf '%s\n' "$CONTENT" >"$FP"
run_hook "$(mk_write "$FP" "$CONTENT")"
check "T4 completed [x] item stays silent" 0

# ---------------------------------------------------------------------------
# T5 — BLOCKED items carry a trigger, not Why/How
# ---------------------------------------------------------------------------
FP="$TMP/t5/fix_plan.md"
CONTENT='- [BLOCKED:P2:external] Rotate the staging credentials
  - **trigger: ops team confirms the rotation window**'
printf '%s\n' "$CONTENT" >"$FP"
run_hook "$(mk_write "$FP" "$CONTENT")"
check "T5 BLOCKED item stays silent" 0

# ---------------------------------------------------------------------------
# T6 — non-tracker files are out of scope
# ---------------------------------------------------------------------------
FP="$TMP/t6/notes.md"
CONTENT='- [ ] Do a thing without rationale'
printf '%s\n' "$CONTENT" >"$FP"
run_hook "$(mk_write "$FP" "$CONTENT")"
check "T6 non-tracker file is out of scope" 0

# ---------------------------------------------------------------------------
# T7 — inserting before an existing item must not flag the trailing anchor
# ---------------------------------------------------------------------------
FP="$TMP/t7/fix_plan.md"
cat >"$FP" <<'EOF'
# fix_plan

- [ ] Newly inserted item
  - **Why**: fresh motivation.
  - **How to apply**: fresh procedure.

- [ ] Pre-existing item
  - **Why**: older motivation.
  - **How to apply**: older procedure.
EOF
run_hook "$(mk_edit "$FP" \
  '- [ ] Pre-existing item' \
  '- [ ] Newly inserted item
  - **Why**: fresh motivation.
  - **How to apply**: fresh procedure.

- [ ] Pre-existing item')"
check "T7 insert-before-anchor stays silent" 0

# ---------------------------------------------------------------------------
# T8 — an over-budget body is still flagged
# ---------------------------------------------------------------------------
FP="$TMP/t8/fix_plan.md"
CONTENT='- [ ] Migrate the billing pipeline
  - **Why**: the legacy cron drifts from the ledger.
  - **How to apply**: staged cutover.
  - extra line 1
  - extra line 2
  - extra line 3
  - extra line 4
  - extra line 5
  - extra line 6'
printf '%s\n' "$CONTENT" >"$FP"
run_hook "$(mk_write "$FP" "$CONTENT")"
check "T8 over-budget item is flagged" 2

# ---------------------------------------------------------------------------
# T9 — the blank separator between items is not body content
# ---------------------------------------------------------------------------
FP="$TMP/t9/fix_plan.md"
cat >"$FP" <<'EOF'
- [ ] Trim the report generator
  - **Why**: the monthly PDF takes nine minutes to render.
  - **How to apply**: stream the rows instead of buffering.
  - note one
  - note two
  - note three

- [ ] Unrelated later item
  - **Why**: unrelated.
  - **How to apply**: unrelated.
EOF
run_hook "$(mk_edit "$FP" '- [ ] Trim the report generator' \
  '- [ ] Trim the report generator
  - **Why**: the monthly PDF takes nine minutes to render.
  - **How to apply**: stream the rows instead of buffering.
  - note one
  - note two
  - note three')"
check "T9 trailing blank separator is not counted against the budget" 0

# ---------------------------------------------------------------------------
# T10 — only Edit/Write/MultiEdit are inspected
# ---------------------------------------------------------------------------
FP="$TMP/t10/fix_plan.md"
printf '%s\n' '- [ ] Do a thing without rationale' >"$FP"
run_hook "$(jq -n --arg fp "$FP" '{tool_name:"Bash", tool_input:{file_path:$fp, content:"- [ ] Do a thing without rationale"}}')"
check "T10 non-edit tool is ignored" 0

printf '\n%s passed, %s failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
