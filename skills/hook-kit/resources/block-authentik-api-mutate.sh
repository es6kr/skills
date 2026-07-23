#!/usr/bin/env bash
# block-authentik-api-mutate.sh
# PreToolUse hook: Block mutating requests (POST/PUT/PATCH/DELETE) against the Authentik API
# Prevents direct API changes to terraform-managed resources (3rd recurrence prevention)
#
# Allowed: GET (read-only queries)
# Blocked: POST, PUT, PATCH, DELETE → flows, stages, providers, applications, brands

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
if [[ "$TOOL_NAME" != "Bash" && "$TOOL_NAME" != "PowerShell" ]]; then
  exit 0
fi

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
if [[ -z "$COMMAND" ]]; then
  exit 0
fi

# curl -X POST/PUT/PATCH/DELETE ... authentik ... api/v3/(flows|stages|providers|applications|brands)
if echo "$COMMAND" | grep -qiE 'curl\s.*-[xX]\s*(POST|PUT|PATCH|DELETE).*authentik.*api/v3/(flows|stages|providers|applications|brands)'; then
  echo "DENIED: Authentik API mutating request blocked."
  echo ""
  echo "Direct API changes to terraform-managed resources are forbidden."
  echo "Modify the .tf files in terraform-pam and proceed with terraform plan → apply."
  echo ""
  echo "iac.md rule: direct changes to terraform-managed resources are forbidden (HARD STOP)"
  exit 2
fi

exit 0
