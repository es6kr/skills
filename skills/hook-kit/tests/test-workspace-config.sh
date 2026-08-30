#!/usr/bin/env bash
# Tests for workspace-config.sh — the shared workspace config resolver.
#
# Run: bash ~/.agents/skills/hook-kit/tests/test-workspace-config.sh
#
# Contract under test:
#   workspace-config.sh --export [target_path]
#     -> emits eval-able `WSCFG_<ROLE>_<FIELD>=<value>` lines on stdout
#
# Resolution order: AGENT_WORKSPACE_PROFILE env > profile match on path
# components > "default". A missing/unparseable config must degrade to
# kind=none (skip), never to a hard failure — hooks source this on every
# invocation and a crash here would break every session.

set -uo pipefail

SHIM="$(cd "$(dirname "$0")/../resources" && pwd)/workspace-config.sh"
FIXTURE="$(mktemp -d)"
trap 'rm -rf "$FIXTURE"' EXIT

pass=0
fail=0

check() { # name expected actual
  if [ "$2" = "$3" ]; then
    pass=$((pass + 1)); printf 'PASS  %s\n' "$1"
  else
    fail=$((fail + 1)); printf 'FAIL  %s\n        expected=[%s]\n        actual  =[%s]\n' "$1" "$2" "$3"
  fi
}

# Clear every WSCFG_* var so a stale value from a previous case cannot
# masquerade as a pass. Must use `compgen -v`, not `env`: the shim emits
# plain assignments (not `export`), so `env` does not list them and the
# stale value survives into the next case as a false pass.
reset_env() {
  local name
  for name in $(compgen -v | grep '^WSCFG_' || true); do
    unset "$name"
  done
}

load() { # target_path
  reset_env
  eval "$("$SHIM" --export "$1" 2>/dev/null)" || true
}

cat > "$FIXTURE/config.json" <<'JSON'
{
  "version": 2,
  "defaults": {
    "checklist": { "kind": "file", "path": ".agents/fix_plan.md" },
    "backlog":   { "kind": "none" },
    "rag":       { "kind": "none" },
    "wiki":      { "kind": "none" }
  },
  "profiles": {
    "wsA": {
      "match": { "path_components": ["wsA"] },
      "roles": {
        "rag": {
          "kind": "qdrant",
          "endpoint": "http://example.invalid:6333",
          "mcp_prefix": "mcp__qdrant__",
          "collections": { "wiki": "a-wiki", "task": "a-task" }
        },
        "wiki": { "kind": "skill", "skill": "x:wiki", "topic": "query" },
        "artifacts": { "kind": "dir", "path": "docs/plans" },
        "staging": { "kind": "branch", "next_fix": "next-fix", "next_feat": "next-feat", "main": "main" }
      }
    },
    "wsB": {
      "match": { "path_components": ["wsB"] },
      "roles": {
        "wiki": { "kind": "mcp", "tool_prefix": "mcp__kordoc__" }
      }
    }
  }
}
JSON

export AGENT_WORKSPACE_CONFIG="$FIXTURE/config.json"

# --- Profile detection -------------------------------------------------
load "/tmp/wsA/repo"
check "T1  profile matched by path component"   "wsA"                    "${WSCFG_PROFILE:-}"

# --- role -> kind indirection ------------------------------------------
check "T2  rag kind from profile"               "qdrant"                 "${WSCFG_RAG_KIND:-}"
check "T3  rag mcp_prefix exported"             "mcp__qdrant__"          "${WSCFG_RAG_MCP_PREFIX:-}"
check "T4  collections flattened per key"       "a-wiki"                 "${WSCFG_RAG_COLLECTION_WIKI:-}"

# --- wiki supports 3 kinds (git / skill / mcp) -------------------------
check "T5  wiki kind=skill (not git)"           "skill"                  "${WSCFG_WIKI_KIND:-}"
check "T6  wiki skill id exported"              "x:wiki"                 "${WSCFG_WIKI_SKILL:-}"

load "/tmp/wsB/repo"
check "T7  wiki kind=mcp with tool_prefix"      "mcp__kordoc__"          "${WSCFG_WIKI_TOOL_PREFIX:-}"

# --- No match must NOT leak another workspace's receivers --------------
load "/tmp/unrelated/repo"
check "T8  unmatched path -> default profile"   "default"                "${WSCFG_PROFILE:-}"
check "T9  default rag kind is none"            "none"                   "${WSCFG_RAG_KIND:-}"

# --- defaults inheritance ----------------------------------------------
# wsA defines no checklist role; it must inherit from defaults rather than
# vanishing (consumers rely on the checklist path always resolving).
reset_env
export AGENT_WORKSPACE_PROFILE=wsA
eval "$("$SHIM" --export "/tmp" 2>/dev/null)" || true
check "T10 role absent in profile inherits default" ".agents/fix_plan.md" "${WSCFG_CHECKLIST_PATH:-}"
unset AGENT_WORKSPACE_PROFILE

# --- Degradation: a broken/missing config must not block ---------------
export AGENT_WORKSPACE_CONFIG="$FIXTURE/does-not-exist.json"
load "/tmp/wsA/repo"
check "T11 missing config degrades to none"     "none"                   "${WSCFG_RAG_KIND:-}"

printf 'not json at all' > "$FIXTURE/broken.json"
export AGENT_WORKSPACE_CONFIG="$FIXTURE/broken.json"
load "/tmp/wsA/repo"
check "T12 unparseable config degrades to none" "none"                   "${WSCFG_RAG_KIND:-}"

"$SHIM" --export "/tmp/wsA/repo" >/dev/null 2>&1
check "T13 broken config still exits 0"         "0"                      "$?"

# --- v1 config translation --------------------------------------------
# The live v1 config writes cwd_match as multi-segment strings
# ("ghq/github.com/es6kr"). A matcher that only compares single path
# components can never match those, which silently resolved every
# workspace to "default" (localhost qdrant, empty plane host).
cat > "$FIXTURE/v1.json" <<'JSON'
{
  "profiles": {
    "wsLegacy": {
      "cwd_match": ["ghq/github.com/wsLegacy", "WSLEGACY"],
      "default_project": "proj-1",
      "llm_wiki_path": "/tmp/wsLegacy/llm-wiki",
      "plane_host": "https://plane.example.invalid",
      "plane_token_env": "WSLEGACY_TOKEN",
      "qdrant_memory_collection": "claude-memory",
      "qdrant_url": "http://example.invalid:30333",
      "qdrant_wiki_collection": "legacy-wiki",
      "workspace_name": "wsLegacy"
    }
  }
}
JSON
export AGENT_WORKSPACE_CONFIG="$FIXTURE/v1.json"

load "/tmp/ghq/github.com/wsLegacy/repo"
check "T14 multi-segment cwd_match matches"     "wsLegacy"               "${WSCFG_PROFILE:-}"
check "T15 v1 qdrant_url -> rag endpoint"       "http://example.invalid:30333" "${WSCFG_RAG_ENDPOINT:-}"
check "T16 v1 collections translated"           "legacy-wiki"            "${WSCFG_RAG_COLLECTION_WIKI:-}"
check "T17 v1 plane_host -> backlog kind"       "plane"                  "${WSCFG_BACKLOG_KIND:-}"
check "T18 v1 llm_wiki_path -> wiki kind=git"   "git"                    "${WSCFG_WIKI_KIND:-}"

# A multi-segment token must match contiguous segments only — a token must
# not match a longer component that merely contains it.
load "/tmp/ghq/github.com/not-wsLegacy-scratch/repo"
check "T19 substring-only path does not match"  "default"                "${WSCFG_PROFILE:-}"

# --- v2 profile with no `roles` key inherits top-level defaults ---------
# Regression: v2 used to be detected per-profile via `roles` presence. A v2
# profile that defines only `match` and relies on top-level `defaults` was
# misread as v1, and v1_to_roles overwrote its configured checklist path with
# the `.agents/fix_plan.md` v1 fallback. version==2 must win regardless.
cat > "$FIXTURE/v2-noroles.json" <<'JSON'
{
  "version": 2,
  "defaults": {
    "checklist": { "kind": "file", "path": ".custom/tracker.md" },
    "rag": { "kind": "qdrant", "endpoint": "http://example.invalid:6333", "mcp_prefix": "mcp__qdrant__" }
  },
  "profiles": {
    "wsBare": { "match": { "path_components": ["wsBare"] } }
  }
}
JSON
export AGENT_WORKSPACE_CONFIG="$FIXTURE/v2-noroles.json"
load "/tmp/wsBare/repo"
check "T20 no-roles v2 profile resolves"        "wsBare"                 "${WSCFG_PROFILE:-}"
check "T21 no-roles v2 keeps default checklist" ".custom/tracker.md"     "${WSCFG_CHECKLIST_PATH:-}"
check "T22 no-roles v2 keeps default rag kind"  "qdrant"                 "${WSCFG_RAG_KIND:-}"

# --- artifacts role: where generated research/plan documents land -------
# The authoring skill used to hardcode one repository's outputs directory, so
# every workspace was dragged through that repository's commit conventions.
# Which directory receives generated documents is a per-workspace setting, so
# it belongs in the schema alongside the other receivers — and replacing one
# hardcoded path with a different hardcoded path would not have fixed that.
export AGENT_WORKSPACE_CONFIG="$FIXTURE/config.json"
load "/tmp/wsA/repo"
check "T23 artifacts kind from profile"         "dir"                    "${WSCFG_ARTIFACTS_KIND:-}"
check "T24 artifacts path from profile"         "docs/plans"             "${WSCFG_ARTIFACTS_PATH:-}"

# A workspace that says nothing about artifacts still needs a destination,
# otherwise the consumer is back to inventing one.
load "/tmp/wsB/repo"
check "T25 unset artifacts inherits default"    ".agents/docs/generated" "${WSCFG_ARTIFACTS_PATH:-}"

export AGENT_WORKSPACE_CONFIG="$FIXTURE/v1.json"
load "/tmp/ghq/github.com/wsLegacy/repo"
check "T26 v1 profile also gets a default"      ".agents/docs/generated" "${WSCFG_ARTIFACTS_PATH:-}"

# --- staging role: release branch staging routing ----------------------
export AGENT_WORKSPACE_CONFIG="$FIXTURE/config.json"
load "/tmp/wsA/repo"
check "T27 staging kind from profile"           "branch"                 "${WSCFG_STAGING_KIND:-}"
check "T28 staging next_fix from profile"       "next-fix"               "${WSCFG_STAGING_NEXT_FIX:-}"
check "T29 staging next_feat from profile"      "next-feat"              "${WSCFG_STAGING_NEXT_FEAT:-}"
check "T30 staging main from profile"           "main"                   "${WSCFG_STAGING_MAIN:-}"

load "/tmp/wsB/repo"
check "T31 unset staging degrades to none"      "none"                   "${WSCFG_STAGING_KIND:-}"
printf -- '---\npass=%d fail=%d\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
