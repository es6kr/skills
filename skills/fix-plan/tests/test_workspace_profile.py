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

print("---")
print(f"pass={PASS} fail={FAIL}")
sys.exit(1 if FAIL else 0)
