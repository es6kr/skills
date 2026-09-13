#!/usr/bin/env bash
# CI wrapper for block-commit-tag-change-without-package-count.sh's --test mode.
#
# The script has always shipped a 14+-case built-in self-test, but nothing in
# .github/workflows/test.yml invoked it -- consolidate PR es6kr/skills#470
# found 3 empirically-reproducible bugs in this exact guard that its own test
# suite didn't catch, and none of them would have been caught by CI even if
# the suite had covered them, since the suite was never wired in.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$SCRIPT_DIR/../resources/block-commit-tag-change-without-package-count.sh"

bash "$GUARD" --test
exit $?
