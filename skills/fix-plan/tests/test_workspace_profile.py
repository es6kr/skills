#!/usr/bin/env python3
"""Tests for workspace_profile.detect_workspace path matching.

Regression under test: `cwd_match` tokens are written as path fragments
("ghq/github.com/<org>"), but the matcher compared them against single path
components. No multi-segment token could ever match, so every workspace fell
through to "default" — meaning localhost endpoints and the wrong collections
for every consumer, silently.

The fix must stay segment-exact so a token still cannot match a longer
component that merely contains it.

Run: python3 skills/fix-plan/tests/test_workspace_profile.py
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import workspace_profile  # noqa: E402

PASS = 0
FAIL = 0


def check(name, expected, actual):
    global PASS, FAIL
    if expected == actual:
        PASS += 1
        print(f"PASS  {name}")
    else:
        FAIL += 1
        print(f"FAIL  {name}\n        expected=[{expected}]\n        actual  =[{actual}]")


CONFIG = {
    "profiles": {
        "wsMulti": {
            "cwd_match": ["ghq/github.com/wsMulti", "WSMULTI"],
            "qdrant_url": "http://example.invalid:30333",
            "workspace_name": "wsMulti",
        },
        "wsSingle": {
            "cwd_match": ["wsSingle"],
            "workspace_name": "wsSingle",
        },
    }
}

tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
json.dump(CONFIG, tmp)
tmp.close()
workspace_profile.CONFIG_FILE = Path(tmp.name)
# Point the v2 location at a path that cannot exist so the v1 cases below are
# not silently served by whatever real v2 config happens to be on this machine.
setattr(workspace_profile, "CONFIG_FILE_V2", Path(tmp.name + ".absent-v2"))

check(
    "T1 multi-segment cwd_match matches",
    "wsMulti",
    workspace_profile.detect_workspace("/Users/x/ghq/github.com/wsMulti/repo"),
)
check(
    "T2 single-component token still matches",
    "wsSingle",
    workspace_profile.detect_workspace("/Users/x/ghq/github.com/wsSingle/repo"),
)
check(
    "T3 substring-only component does not match",
    "default",
    workspace_profile.detect_workspace("/Users/x/ghq/github.com/not-wsSingle-scratch"),
)
check(
    "T4 unrelated path falls back to default",
    "default",
    workspace_profile.detect_workspace("/Users/x/somewhere/else"),
)
check(
    "T5 matched profile resolves real endpoint (not the localhost default)",
    "http://example.invalid:30333",
    workspace_profile.get_profile(
        target_path="/Users/x/ghq/github.com/wsMulti/repo"
    )["qdrant_url"],
)

# --- v2 schema (roles + kind) -----------------------------------------
# The v2 config names roles rather than vendors, so a vendor swap is a
# one-line edit. Consumers here still read the flat vendor-named keys, so
# v2 must be translated back down to them — otherwise adopting v2 silently
# hands every consumer the placeholder defaults.
CONFIG_V2 = {
    "version": 2,
    "defaults": {
        "backlog": {"kind": "none"},
        "checklist": {"kind": "file", "path": ".agents/fix_plan.md"},
        "rag": {"kind": "none"},
        "wiki": {"kind": "none"},
    },
    "profiles": {
        "wsV2": {
            "match": {"path_components": ["ghq/github.com/wsV2"]},
            "roles": {
                "backlog": {
                    "kind": "plane",
                    "endpoint": "https://plane.v2.invalid",
                    "project": "proj-v2",
                    "token_env": "V2_TOKEN",
                },
                "checklist": {"kind": "file", "path": ".agents/fix_plan.md"},
                "rag": {
                    "kind": "qdrant",
                    "endpoint": "http://v2.invalid:30333",
                    "collections": {
                        "memory": "v2-memory",
                        "task": "v2-task",
                        "wiki": "v2-wiki",
                    },
                },
                "wiki": {"kind": "git", "path": "/tmp/wsV2/llm-wiki"},
            },
        },
        "wsV2NoRag": {
            "match": {"path_components": ["wsV2NoRag"]},
            "roles": {"rag": {"kind": "none"}},
        },
    },
}

tmp2 = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
json.dump(CONFIG_V2, tmp2)
tmp2.close()
setattr(workspace_profile, "CONFIG_FILE_V2", Path(tmp2.name))

V2_PATH = "/Users/x/ghq/github.com/wsV2/repo"
check(
    "T6  v2 config takes precedence over v1",
    "wsV2",
    workspace_profile.detect_workspace(V2_PATH),
)
p = workspace_profile.get_profile(target_path=V2_PATH)
check("T7  v2 rag endpoint -> qdrant_url",        "http://v2.invalid:30333", p["qdrant_url"])
check("T8  v2 collections -> flat keys",          "v2-wiki",                 p["qdrant_wiki_collection"])
check("T9  v2 backlog -> plane_host",             "https://plane.v2.invalid", p["plane_host"])
check("T10 v2 backlog token_env -> plane_token_env", "V2_TOKEN",             p["plane_token_env"])
check("T11 v2 wiki path -> llm_wiki_path",        "/tmp/wsV2/llm-wiki",      p["llm_wiki_path"])
check("T12 v2 checklist path -> tracker_root",    ".agents",                 p["tracker_root"])

# DEFAULT_PROFILE already carries workspace_name="default", so a setdefault
# cannot correct it. v1 configs hid this by naming workspace_name explicitly
# in every profile; a translated v2 profile must supply it too, or the report
# claims "default" while serving a matched profile's real endpoints.
check("T15 v2 profile reports its own workspace_name", "wsV2", p["workspace_name"])

# kind "none" must not fabricate an endpoint — it means "not configured".
pn = workspace_profile.get_profile(target_path="/Users/x/wsV2NoRag/repo")
check("T13 v2 kind=none leaves qdrant_url unset", "",                        pn["qdrant_url"])

# v1 remains readable when no v2 file is present (migration window).
setattr(workspace_profile, "CONFIG_FILE_V2", Path(tmp2.name + ".absent"))
check(
    "T14 falls back to v1 when v2 absent",
    "wsMulti",
    workspace_profile.detect_workspace("/Users/x/ghq/github.com/wsMulti/repo"),
)

print("---")
print(f"pass={PASS} fail={FAIL}")
sys.exit(1 if FAIL else 0)
