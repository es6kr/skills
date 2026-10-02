#!/usr/bin/env bash
# CI entry point for block-orca-ask-without-split-option.sh.
#
# The guard carries its fixtures in-file behind `--test` (4 block + 8 allow). The
# "Skill Tests" job sweeps skills/*/tests/*.sh and nothing sweeps bash `--test`
# flags, so without this wrapper the fixtures would exist and never run — the
# same shape of gap that let the gate this guard reinforces go stale.
set -euo pipefail
GUARD="$(cd "$(dirname "$0")/.." && pwd)/resources/block-orca-ask-without-split-option.sh"
bash "$GUARD" --test
