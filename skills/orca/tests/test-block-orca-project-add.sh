#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
GUARD="$ROOT/resources/block-orca-project-add.sh"

run_case() {
  local command=$1 expected=$2 output
  output=$(printf '{"tool_name":"Bash","tool_input":{"command":"%s"}}' "$command" | "$GUARD" 2>&1 || true)
  if [[ "$expected" == blocked ]]; then
    grep -q 'BLOCKED: Orca project/repository registration' <<<"$output"
  else
    [[ -z "$output" ]]
  fi
}

run_case 'orca repo add --path C:/repo --json' blocked
run_case 'orca project setup-existing-folder --project x --host local --path C:/ws' blocked
run_case 'orca project setup-clone --project x --host local --url https://example.test/x.git' blocked
run_case 'orca project setup-create --project x --host local' blocked
run_case 'FOO=bar orca project setup-existing-folder --project x --host local --path C:/ws' blocked
run_case 'ORCA_PROJECT_REGISTRATION_APPROVED=1 orca project setup-existing-folder --project x --host local --path C:/ws' allowed
run_case 'orca repo list --json' allowed
run_case 'orca project list --json' allowed
run_case 'orca terminal create --worktree name:ws --command claude' allowed
run_case 'orca worktree create --repo id:x --name plan' allowed
printf '9/9 passed\n'
