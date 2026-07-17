#!/usr/bin/env bash
# gh wrapper that pins the acting account via per-invocation token injection.
#
# Workaround for the macOS gh CLI bug where `gh auth switch --user <account>`
# reports success but subsequent `gh api user` still returns the previous
# account within the same session. Injecting GH_TOKEN per invocation makes the
# acting account deterministic without mutating global gh auth state.
#
# Usage: gh-as.sh <account> <gh args...>
#   e.g. gh-as.sh alice pr view 42 -R owner/repo
#
# See github-flow/identity-auth.md for the owner→account mapping policy.
set -euo pipefail
ACCOUNT="${1:?usage: gh-as.sh <account> <gh-args...>}"
shift
GH_TOKEN="$(gh auth token --user "$ACCOUNT")" exec gh "$@"
