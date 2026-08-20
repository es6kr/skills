#!/usr/bin/env bash
# workspace-config.sh — shared workspace config resolver.
#
# Single entry point for every hook/script that needs to know which
# receivers (checklist / backlog / rag / wiki) the current workspace is
# wired to. Consumers do not parse the config themselves:
#
#     eval "$(workspace-config.sh --export)"
#     [ "${WSCFG_RAG_KIND:-none}" = "none" ] && exit 0   # receiver absent -> skip
#
# Roles carry a `kind` discriminator so the vendor can change without any
# consumer edit, and `kind: "none"` makes "not configured" a first-class
# state. That distinction is the point: without it a guard cannot tell an
# unconfigured workspace from a negligent session, and blocks on both.
#
# Config resolution:
#   $AGENT_WORKSPACE_CONFIG        (explicit; no fallback if it is missing)
#   ~/.config/agent-workspace/config.json    (v2)
#   ~/.config/plane-backlog/config.json      (v1, translated on the fly)
#
# Profile resolution:
#   $AGENT_WORKSPACE_PROFILE > match.path_components (v2) / cwd_match (v1)
#   > "default".  An unmatched path resolves to "default", never to an
#   arbitrary configured profile — silently targeting another workspace's
#   token or collection is worse than resolving nothing.
#
# Failure policy: this runs on every hook invocation, so it degrades rather
# than fails. Missing file, malformed JSON, or no usable interpreter all
# emit all-"none" roles and exit 0.

set -uo pipefail

MODE="--export"
TARGET=""
for arg in "$@"; do
  case "$arg" in
    --export|--json) MODE="$arg" ;;
    -h|--help)
      sed -n '2,32p' "$0"
      exit 0
      ;;
    *) TARGET="$arg" ;;
  esac
done
[ -n "$TARGET" ] || TARGET="$PWD"

# Roles a consumer may rely on existing, whatever the config says.
emit_safe_defaults() {
  echo "WSCFG_PROFILE=default"
  for role in CHECKLIST BACKLOG RAG WIKI; do
    echo "WSCFG_${role}_KIND=none"
  done
}

# Windows ships a python3 stub that exits 49 instead of running, so probe
# for an interpreter that actually executes rather than trusting the name.
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import json,sys' >/dev/null 2>&1; then
    PY="$cand"
    break
  fi
done
if [ -z "$PY" ]; then
  emit_safe_defaults
  exit 0
fi

if [ -n "${AGENT_WORKSPACE_CONFIG:-}" ]; then
  CONFIG="$AGENT_WORKSPACE_CONFIG"
else
  CONFIG="$HOME/.config/agent-workspace/config.json"
  [ -f "$CONFIG" ] || CONFIG="$HOME/.config/plane-backlog/config.json"
fi

OUT="$("$PY" - "$CONFIG" "$TARGET" "$MODE" <<'PYEOF' 2>/dev/null
import json, os, re, shlex, sys
from pathlib import Path

cfg_path, target, mode = sys.argv[1], sys.argv[2], sys.argv[3]

ROLES = ("checklist", "backlog", "rag", "wiki")
BUILTIN_DEFAULTS = {
    "checklist": {"kind": "file", "path": ".agents/fix_plan.md"},
    "backlog": {"kind": "none"},
    "rag": {"kind": "none"},
    "wiki": {"kind": "none"},
}
# Scalar fields promoted to WSCFG_<ROLE>_<FIELD>. Anything else in a role
# spec is ignored rather than guessed at.
FIELDS = ("endpoint", "path", "token_env", "project",
          "mcp_prefix", "skill", "topic", "tool_prefix")


def bail():
    print("WSCFG_PROFILE=default")
    for r in ROLES:
        print("WSCFG_%s_KIND=none" % r.upper())
    sys.exit(0)


try:
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    if not isinstance(cfg, dict):
        bail()
except Exception:
    bail()

profiles = cfg.get("profiles") or {}
if not isinstance(profiles, dict):
    bail()


def v1_to_roles(p):
    """Translate a v1 (flat, vendor-named keys) profile into v2 roles.

    Keeps the old config usable during migration instead of forcing a
    big-bang cutover. A blank endpoint means the role is unconfigured,
    which is exactly kind: none.
    """
    roles = {}
    tracker = p.get("tracker_root") or ".agents"
    roles["checklist"] = {"kind": "file", "path": "%s/fix_plan.md" % tracker.rstrip("/")}

    if p.get("plane_host"):
        roles["backlog"] = {
            "kind": "plane",
            "endpoint": p["plane_host"],
            "token_env": p.get("plane_token_env", "PLANE_API_KEY"),
            "project": p.get("default_project", ""),
        }
    if p.get("qdrant_url"):
        collections = {}
        for key in ("memory", "task", "wiki"):
            val = p.get("qdrant_%s_collection" % key)
            if val:
                collections[key] = val
        roles["rag"] = {
            "kind": "qdrant",
            "endpoint": p["qdrant_url"],
            "mcp_prefix": "mcp__qdrant__",
            "collections": collections,
        }
    if p.get("llm_wiki_path"):
        roles["wiki"] = {"kind": "git", "path": p["llm_wiki_path"]}
    return roles


def match_tokens(name, prof):
    """v2 `match.path_components`, falling back to v1 `cwd_match`."""
    match = prof.get("match")
    if isinstance(match, dict) and match.get("path_components"):
        return match["path_components"]
    return prof.get("cwd_match") or [name]


def token_matches(token, parts):
    """Match a cwd token against a contiguous run of path segments.

    Tokens come in two shapes: a single component ("es6kr") and a path
    fragment ("ghq/github.com/es6kr"). Splitting on "/" and comparing
    segment sequences handles both, and because each segment is compared
    for equality a token still cannot match a longer component that merely
    contains it ("not-es6kr-scratch").

    A component-only matcher silently failed every multi-segment token in
    the live config, resolving all workspaces to "default" — i.e. localhost
    endpoints and the wrong collections. Keep this sequence-aware.
    """
    seq = [s for s in str(token).split("/") if s]
    if not seq:
        return False
    n = len(seq)
    return any(list(parts[i:i + n]) == seq for i in range(len(parts) - n + 1))


name = os.environ.get("AGENT_WORKSPACE_PROFILE")
if name not in profiles:
    parts = Path(target).resolve().parts
    name = "default"
    for pname, prof in profiles.items():
        if not isinstance(prof, dict):
            continue
        if any(token_matches(tok, parts) for tok in match_tokens(pname, prof)):
            name = pname
            break

profile = profiles.get(name) or {}
roles = dict(cfg.get("defaults") or BUILTIN_DEFAULTS)
if isinstance(profile, dict):
    if isinstance(profile.get("roles"), dict):
        roles.update(profile["roles"])
    else:
        roles.update(v1_to_roles(profile))
for role, spec in BUILTIN_DEFAULTS.items():
    roles.setdefault(role, spec)

if mode == "--json":
    print(json.dumps({"profile": name, "roles": roles}, indent=2, ensure_ascii=False))
    sys.exit(0)

SAFE = re.compile(r"[^A-Z0-9_]")


def emit(key, value):
    print("WSCFG_%s=%s" % (SAFE.sub("_", key.upper()), shlex.quote(str(value))))


emit("PROFILE", name)
for role, spec in roles.items():
    if not isinstance(spec, dict):
        continue
    emit("%s_KIND" % role, spec.get("kind", "none"))
    for field in FIELDS:
        if spec.get(field):
            emit("%s_%s" % (role, field), spec[field])
    for cname, cval in (spec.get("collections") or {}).items():
        emit("%s_COLLECTION_%s" % (role, cname), cval)
PYEOF
)"

if [ -z "$OUT" ]; then
  emit_safe_defaults
  exit 0
fi

printf '%s\n' "$OUT"
exit 0
