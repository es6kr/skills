#!/usr/bin/env bash
# dev-reflect: reflect a local dev source repo's plugin/skill changes into the
# registered Claude Code marketplace clone for local testing BEFORE commit/push.
#
# Usage:
#   dev-reflect.sh --source <repo-path> --marketplace <name> [--enable <plugin>] [--dry-run]
#
#   --source       Local dev source repo (must contain .claude-plugin/marketplace.json)
#   --marketplace  Target clone name under ~/.claude/plugins/marketplaces/<name>/
#   --enable       Optional plugin name to enable as "<plugin>@<marketplace>" in settings.json
#   --dry-run      Print actions without writing
#
# What it does:
#   1. Sync component dirs (skills/ agents/ commands/ hooks/ plugins/) source -> clone
#   2. Upsert source's marketplace.json plugin entries into the clone (by name; clone-only kept)
#   3. chmod +x synced hook scripts
#   4. Sync the same component dirs into each cached plugin's version dir under
#      ~/.claude/plugins/cache/<marketplace>/<plugin-name>/<version>/ (see Notes)
#   5. (optional) enable the plugin in settings.json (with backup)
#   6. Print the 4-step plugin-activation verification + reload reminder
#
# Notes:
#   - Additive sync (rsync --delete only when rsync is present). Removed source files
#     are NOT pruned from the clone unless rsync is available.
#   - Direct clone edits are a TEST shortcut. A later GitHub re-sync overwrites them.
#     Commit/push the source repo to make changes durable.
#   - Step 1-3 only touch the marketplace CLONE (~/.claude/plugins/marketplaces/<name>/).
#     An already-running session loads skills from the plugin CACHE
#     (~/.claude/plugins/cache/<name>/<plugin>/<version>/) instead, which the clone sync
#     never reaches — a change "reflected" by this script can still appear stale to that
#     session. Step 4 closes that gap by mirroring the same component dirs into every
#     already-cached plugin version dir. It intentionally skips plugin/version
#     combinations that have no existing cache dir (nothing to keep in sync there yet).

set -euo pipefail

SOURCE="" MARKETPLACE="" ENABLE="" DRYRUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --source) SOURCE="$2"; shift 2 ;;
    --marketplace) MARKETPLACE="$2"; shift 2 ;;
    --enable) ENABLE="$2"; shift 2 ;;
    --dry-run) DRYRUN=1; shift ;;
    *) echo "[dev-reflect] unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -n "$SOURCE" ] || { echo "[dev-reflect] --source required" >&2; exit 2; }
[ -n "$MARKETPLACE" ] || { echo "[dev-reflect] --marketplace required" >&2; exit 2; }

SRC_MP="$SOURCE/.claude-plugin/marketplace.json"
CLONE="$HOME/.claude/plugins/marketplaces/$MARKETPLACE"
if [ ! -d "$CLONE" ] && [ -n "${USERPROFILE:-}" ] && [ -d "$USERPROFILE/.claude/plugins/marketplaces/$MARKETPLACE" ]; then
  CLONE="$USERPROFILE/.claude/plugins/marketplaces/$MARKETPLACE"
fi
if [ ! -d "$CLONE" ]; then
  for _cand in /mnt/c/Users/*/.claude/plugins/marketplaces/"$MARKETPLACE"; do
    if [ -d "$_cand" ]; then
      CLONE="$_cand"
      break
    fi
  done
fi
CLONE_MP="$CLONE/.claude-plugin/marketplace.json"

[ -f "$SRC_MP" ]   || { echo "[dev-reflect] not a marketplace source (no $SRC_MP)" >&2; exit 1; }
[ -d "$CLONE" ]    || { echo "[dev-reflect] marketplace clone not found: $CLONE" >&2; exit 1; }
[ -f "$CLONE_MP" ] || { echo "[dev-reflect] clone has no marketplace.json: $CLONE_MP" >&2; exit 1; }
command -v jq >/dev/null || { echo "[dev-reflect] jq required" >&2; exit 1; }

# Executes its arguments directly (never eval) so that untrusted values (e.g.
# PLUGIN_NAME sourced from --source's own marketplace.json) can never be
# re-parsed as shell syntax, regardless of what characters they contain.
run() { if [ "$DRYRUN" = 1 ]; then echo "DRY: $*"; else "$@"; fi; }

# 1. Sync component dirs
HAVE_RSYNC=0; command -v rsync >/dev/null && HAVE_RSYNC=1
for dir in skills agents commands hooks plugins; do
  [ -d "$SOURCE/$dir" ] || continue
  if [ "$HAVE_RSYNC" = 1 ]; then
    run rsync -a --delete "$SOURCE/$dir/" "$CLONE/$dir/"
  else
    run mkdir -p "$CLONE/$dir"
    run command cp -r "$SOURCE/$dir/." "$CLONE/$dir/"
  fi
  echo "[dev-reflect] synced $dir/"
done

# 2. Upsert source plugin entries into clone marketplace.json (clone-only entries kept)
if [ "$DRYRUN" = 1 ]; then
  echo "DRY: upsert plugins from $SRC_MP into $CLONE_MP"
else
  TMP="$(mktemp)"
  jq --slurpfile s <(jq '.plugins' "$SRC_MP") '
    ($s[0]) as $src
    | ($src | map(.name)) as $names
    | .plugins = ([.plugins[] | select(.name as $n | ($names | index($n) | not))] + $src)
  ' "$CLONE_MP" > "$TMP"
  jq empty "$TMP"
  command cp "$TMP" "$CLONE_MP"; rm -f "$TMP"
  echo "[dev-reflect] marketplace.json plugins upserted"
fi

# 3. chmod +x synced hook scripts
if [ "$DRYRUN" != 1 ]; then
  find "$CLONE/skills" "$CLONE/hooks" "$CLONE/plugins" -type f -name '*.sh' 2>/dev/null \
    -exec chmod +x {} \; || true
fi

# 4. Sync into already-cached plugin version dirs (marketplace clone alone is not
#    what an active session loads from — see the Notes block above)
while IFS= read -r PLUGIN_NAME; do
  [ -n "$PLUGIN_NAME" ] || continue
  PLUGIN_CACHE_BASE="$HOME/.claude/plugins/cache/$MARKETPLACE/$PLUGIN_NAME"
  [ -d "$PLUGIN_CACHE_BASE" ] || continue
  for CACHE_DIR in "$PLUGIN_CACHE_BASE"/*; do
    [ -d "$CACHE_DIR" ] || continue
    for dir in skills agents commands hooks plugins; do
      [ -d "$SOURCE/$dir" ] || continue
      if [ "$HAVE_RSYNC" = 1 ]; then
        run rsync -a --delete "$SOURCE/$dir/" "$CACHE_DIR/$dir/"
      else
        run mkdir -p "$CACHE_DIR/$dir"
        run command cp -r "$SOURCE/$dir/." "$CACHE_DIR/$dir/"
      fi
    done
    if [ "$DRYRUN" != 1 ]; then
      find "$CACHE_DIR/skills" "$CACHE_DIR/hooks" "$CACHE_DIR/plugins" -type f -name '*.sh' 2>/dev/null \
        -exec chmod +x {} \; || true
    fi
    echo "[dev-reflect] synced plugin cache: $CACHE_DIR"
  done
done <<< "$(jq -r '.plugins[].name' "$SRC_MP")"

# 5. Optional: enable plugin in settings.json
if [ -n "$ENABLE" ]; then
  S="$HOME/.claude/settings.json"
  KEY="$ENABLE@$MARKETPLACE"
  if [ "$DRYRUN" = 1 ]; then
    echo "DRY: enable $KEY in $S (with backup)"
  else
    command cp "$S" "$S.bak-dev-reflect"
    TMP="$(mktemp)"
    jq --arg k "$KEY" '.enabledPlugins[$k] = true' "$S" > "$TMP"
    jq empty "$TMP"
    command cp "$TMP" "$S"; rm -f "$TMP"
    echo "[dev-reflect] enabled $KEY (backup: settings.json.bak-dev-reflect)"
  fi
fi

# 6. Verification report
cat <<EOF

[dev-reflect] Reflected to clone: $CLONE
Plugin activation verification:
  1) marketplace registered ........ $MARKETPLACE (extraKnownMarketplaces)
  2) component files in clone ...... synced above
  3) enabledPlugins ................ $( [ -n "$ENABLE" ] && echo "$ENABLE@$MARKETPLACE=true (this run)" || echo "not changed (pass --enable to set)" )
  4) Skill tool detection .......... NEXT SESSION (plugins load at session start)

=> Restart Claude Code / start a new session, then verify the skill is detected.
   This edits the clone only (test shortcut). Commit/push the source repo to persist.
EOF
