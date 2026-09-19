"""Unit tests for skills/fix-plan/scripts/hook_integrity_check.py.

Regression class under test (PR #363 review, CodeRabbit Major):
  - The checker iterated the OUTER entries of the installed nested hooks.json
    schema ({event: [{matcher, hooks: [{type, command}]}]}), found no "command"
    key there, and silently skipped every registered hook -> audit reported
    nothing while claiming success.
  - Interpreter-prefixed commands ("python3 /path/hook.sh") resolved the
    interpreter token instead of the script operand, so the wrong path was
    existence-checked.

Run:
  python -m pytest tests/test_hook_integrity_check.py -v

CI (.github/workflows/test.yml) collects via `python -m pytest tests -v`, so this
file must live under tests/. The script under test stays in
skills/fix-plan/scripts/ and is loaded by path.
"""
import importlib.util
import json
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(REPO_ROOT, "skills", "fix-plan", "scripts", "hook_integrity_check.py")


def _load():
    spec = importlib.util.spec_from_file_location("hook_integrity_check", CANON)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


# --- iter_hook_commands: schema coverage ---

def test_iter_nested_schema_yields_every_command():
    hooks_data = {
        "hooks": {
            "PostToolUse": [
                {"matcher": "Read", "hooks": [
                    {"type": "command", "command": "/a/one.sh"},
                    {"type": "command", "command": "/a/two.sh"},
                ]},
                {"matcher": "Bash", "hooks": [
                    {"type": "command", "command": "python3 /a/three.sh"},
                ]},
            ],
        }
    }
    got = list(mod.iter_hook_commands(hooks_data))
    assert got == [
        ("PostToolUse", "/a/one.sh"),
        ("PostToolUse", "/a/two.sh"),
        ("PostToolUse", "python3 /a/three.sh"),
    ]


def test_iter_flat_schema_still_supported():
    hooks_data = {
        "hooks": {
            "Stop": ["/flat/one.sh", {"command": "/flat/two.sh"}, {"script": "/flat/three.sh"}],
        }
    }
    got = list(mod.iter_hook_commands(hooks_data))
    assert got == [
        ("Stop", "/flat/one.sh"),
        ("Stop", "/flat/two.sh"),
        ("Stop", "/flat/three.sh"),
    ]


# --- resolve_script_operand: interpreter/env-prefix skipping ---

def test_resolve_skips_interpreter_and_flags():
    assert mod.resolve_script_operand("python3 /p/hook.sh") == "/p/hook.sh"
    assert mod.resolve_script_operand("bash -euo /p/guard.sh") == "/p/guard.sh"
    assert mod.resolve_script_operand("node /p/check.js") == "/p/check.js"


def test_resolve_skips_env_assignment_prefix():
    assert mod.resolve_script_operand("FOO=1 python3 /p/hook.py") == "/p/hook.py"


def test_resolve_plain_path_unchanged():
    assert mod.resolve_script_operand('"/p/with space/hook.sh"') == "/p/with space/hook.sh"


def test_resolve_preserves_windows_backslashes(monkeypatch):
    # posix=True shlex.split treats backslash as an escape character, so a
    # Windows path silently loses every backslash (\U -> U, \A -> A, ...)
    # and the resolved path stops existing. Guards the fix for that.
    # Force the win32 branch explicitly so this test is deterministic
    # regardless of the platform actually running it (CI runs on Linux).
    monkeypatch.setattr(mod.sys, "platform", "win32")
    assert mod.resolve_script_operand(r"python3 C:\Users\me\hook.sh") == r"C:\Users\me\hook.sh"


def test_resolve_posix_path_unaffected_by_win32_branch(monkeypatch):
    # On win32, posix=False is used -- confirm ordinary POSIX paths and
    # interpreter/flag skipping still resolve correctly under that mode.
    monkeypatch.setattr(mod.sys, "platform", "win32")
    assert mod.resolve_script_operand("python3 /p/hook.sh") == "/p/hook.sh"
    assert mod.resolve_script_operand('"/p/with space/hook.sh"') == "/p/with space/hook.sh"


# --- check_hook_integrity: end-to-end on the installed schema ---

def test_installed_schema_is_audited(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # win32 expanduser

    present = tmp_path / "present-hook.sh"
    present.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    present.chmod(0o755)
    missing = tmp_path / "missing-hook.sh"

    cfg_dir = tmp_path / ".claude"
    cfg_dir.mkdir()
    (cfg_dir / "hooks.json").write_text(json.dumps({
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [
                    {"type": "command", "command": f"python3 {present}"},
                    {"type": "command", "command": str(missing)},
                ]},
            ],
        }
    }), encoding="utf-8")

    results = mod.check_hook_integrity(str(tmp_path))

    ok_files = [i["file"] for i in results["OK"]]
    missing_files = [i["file"] for i in results["MISSING"]]
    # The script operand (not the interpreter) is what got audited:
    assert str(present) in ok_files
    assert str(missing) in missing_files
    assert "python3" not in ok_files + missing_files


# --- Review-feedback regression tests (PR #451 consolidate) -----------------


def test_falls_back_to_home_config_when_workspace_has_none(tmp_path, monkeypatch):
    """Row 10: resolving hooks.json under `root` only made the checker
    early-return a false MISSING for any workspace without its own config,
    silently skipping every downstream check."""
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    hook = home / "global-hook.sh"
    hook.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    hook.chmod(0o755)
    (home / ".claude" / "hooks.json").write_text(json.dumps({
        "hooks": {"PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": str(hook)}]},
        ]}
    }), encoding="utf-8")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    workspace = tmp_path / "workspace"   # deliberately carries no hooks.json
    workspace.mkdir()

    results = mod.check_hook_integrity(str(workspace))

    missing_files = [i["file"] for i in results["MISSING"]]
    assert "hooks.json" not in missing_files, (
        "workspace without a local hooks.json must fall back to the home config, "
        f"got MISSING={results['MISSING']}"
    )
    assert str(hook) in [i["file"] for i in results["OK"]]


def test_workspace_config_takes_precedence_over_home(tmp_path, monkeypatch):
    """The root parameter must still win when the workspace does have a config."""
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    home_hook = home / "home-hook.sh"
    home_hook.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    (home / ".claude" / "hooks.json").write_text(json.dumps({
        "hooks": {"PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": str(home_hook)}]},
        ]}
    }), encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    workspace = tmp_path / "workspace"
    (workspace / ".claude").mkdir(parents=True)
    ws_hook = workspace / "ws-hook.sh"
    ws_hook.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    ws_hook.chmod(0o755)
    (workspace / ".claude" / "hooks.json").write_text(json.dumps({
        "hooks": {"PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": str(ws_hook)}]},
        ]}
    }), encoding="utf-8")

    results = mod.check_hook_integrity(str(workspace))
    audited = [i["file"] for i in results["OK"] + results["MISSING"] + results["STALE-PERM"]]
    assert str(ws_hook) in audited
    assert str(home_hook) not in audited


def test_missing_config_message_names_the_searched_scopes(tmp_path, monkeypatch):
    """Row 5: the operator-facing reason said "Global" even when the searched
    path was workspace-local. It must describe what was actually searched."""
    empty_home = tmp_path / "empty-home"
    empty_home.mkdir()
    monkeypatch.setenv("HOME", str(empty_home))
    monkeypatch.setenv("USERPROFILE", str(empty_home))

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    results = mod.check_hook_integrity(str(workspace))
    reasons = [i["reason"] for i in results["MISSING"] if i["file"] == "hooks.json"]
    assert reasons, "a genuinely absent config should still be reported"
    assert str(workspace) in reasons[0]
    assert "Global hooks.json config not found" != reasons[0]


# --- Reverse axis: source hooks.json registered, installed cache missing it --
#
# Regression class under test (fix_plan.md daegunsoftDev/.agents, 2026-08-29
# registration): the forward checks above only see ONE hooks.json (workspace
# or home config) and only ask "does the registered script exist on disk".
# They cannot see the actual 2026-08 incident: a marketplace SOURCE
# plugins/<p>/hooks/hooks.json gained a new Stop/UserPromptSubmit
# registration, but the INSTALLED CACHE hooks.json under
# ~/.claude/plugins/cache/<mp>/<p>/<version>/ was never resynced, so that
# registration was simultaneously absent from BOTH "registered" and "file
# exists" -- ghost detection (which requires a registration to exist first)
# never fires. These tests define the new reverse axis: diff a marketplace's
# source hooks.json registrations against its installed cache counterpart.


def _write_hooks_json(path, hooks_data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(hooks_data), encoding="utf-8")


def test_iter_marketplace_hooks_files_detects_layout1_root(tmp_path):
    """Layout 1: single-plugin marketplace with a root hooks/hooks.json."""
    mp = tmp_path / "marketplaces" / "solo-mp"
    _write_hooks_json(mp / "hooks" / "hooks.json", {"hooks": {}})

    found = list(mod._iter_marketplace_hooks_files(str(tmp_path / "marketplaces")))

    assert found == [("solo-mp", None, str(mp / "hooks" / "hooks.json"))]


def test_iter_marketplace_hooks_files_detects_layout2_nested(tmp_path):
    """Layout 2: multi-plugin marketplace, hooks.json nested per plugin."""
    mp = tmp_path / "marketplaces" / "multi-mp"
    _write_hooks_json(mp / "plugins" / "ask-user" / "hooks" / "hooks.json", {"hooks": {}})
    _write_hooks_json(mp / "plugins" / "other" / "hooks" / "hooks.json", {"hooks": {}})

    found = list(mod._iter_marketplace_hooks_files(str(tmp_path / "marketplaces")))

    assert sorted(found) == sorted([
        ("multi-mp", "ask-user", str(mp / "plugins" / "ask-user" / "hooks" / "hooks.json")),
        ("multi-mp", "other", str(mp / "plugins" / "other" / "hooks" / "hooks.json")),
    ])


def test_find_cache_hooks_json_picks_highest_version(tmp_path):
    cache = tmp_path / "cache"
    _write_hooks_json(cache / "dgs" / "ask-user" / "0.1.0" / "hooks" / "hooks.json", {"hooks": {}})
    _write_hooks_json(cache / "dgs" / "ask-user" / "0.2.0" / "hooks" / "hooks.json", {"hooks": {}})

    resolved = mod._find_cache_hooks_json(str(cache), "dgs", "ask-user")

    assert resolved == str(cache / "dgs" / "ask-user" / "0.2.0" / "hooks" / "hooks.json")


def test_find_cache_hooks_json_none_when_plugin_never_installed(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()

    resolved = mod._find_cache_hooks_json(str(cache), "dgs", "never-installed")

    assert resolved is None


def test_hook_registration_keys_extracts_nested_schema():
    hooks_data = {
        "hooks": {
            "Stop": [
                {"matcher": "", "hooks": [
                    {"type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/hooks/next-trigger.sh\""},
                ]},
            ],
            "PreToolUse": [
                {"matcher": "AskUserQuestion", "hooks": [
                    {"type": "command", "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/ask-guard.sh\""},
                ]},
            ],
        }
    }
    keys = mod._hook_registration_keys_from_data(hooks_data)

    assert keys == {
        ("Stop", "", "next-trigger.sh"),
        ("PreToolUse", "AskUserQuestion", "ask-guard.sh"),
    }


def test_check_source_cache_sync_flags_registration_missing_from_cache(tmp_path):
    """The exact 2026-08-29 incident, reproduced: source gains a new Stop
    registration (block-ask-without-preflight-check.js); the cache install
    still only has the old registration set. This must be reported as
    unsynced -- not silently invisible like the forward ghost check."""
    marketplaces = tmp_path / "marketplaces"
    cache = tmp_path / "cache"

    _write_hooks_json(
        marketplaces / "dgs-skills" / "plugins" / "ask-user" / "hooks" / "hooks.json",
        {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "AskUserQuestion", "hooks": [
                        {"type": "command", "command": "node \"${CLAUDE_PLUGIN_ROOT}/hooks/block-ask-without-preflight-check.js\""},
                        {"type": "command", "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/ask-guard.sh\""},
                    ]},
                ],
            }
        },
    )
    # Cache install predates the block-ask-without-preflight-check.js addition.
    _write_hooks_json(
        cache / "dgs-skills" / "ask-user" / "0.1.0" / "hooks" / "hooks.json",
        {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "AskUserQuestion", "hooks": [
                        {"type": "command", "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/ask-guard.sh\""},
                    ]},
                ],
            }
        },
    )

    unsynced = mod.check_source_cache_sync(str(marketplaces), str(cache))

    assert len(unsynced) == 1
    entry = unsynced[0]
    assert entry["marketplace"] == "dgs-skills"
    assert entry["plugin"] == "ask-user"
    assert entry["event"] == "PreToolUse"
    assert entry["matcher"] == "AskUserQuestion"
    assert entry["script"] == "block-ask-without-preflight-check.js"


def test_check_source_cache_sync_clean_when_registrations_match(tmp_path):
    marketplaces = tmp_path / "marketplaces"
    cache = tmp_path / "cache"
    hooks_data = {
        "hooks": {
            "Stop": [
                {"hooks": [{"type": "command", "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/next-trigger.sh\""}]},
            ],
        }
    }
    _write_hooks_json(marketplaces / "dgs-skills" / "plugins" / "ask-user" / "hooks" / "hooks.json", hooks_data)
    _write_hooks_json(cache / "dgs-skills" / "ask-user" / "0.1.0" / "hooks" / "hooks.json", hooks_data)

    unsynced = mod.check_source_cache_sync(str(marketplaces), str(cache))

    assert unsynced == []


def test_check_source_cache_sync_reports_when_plugin_never_installed(tmp_path):
    """Source registers hooks for a plugin with no cache install at all --
    the whole registration set is unsynced, not silently skipped."""
    marketplaces = tmp_path / "marketplaces"
    cache = tmp_path / "cache"
    cache.mkdir()
    _write_hooks_json(
        marketplaces / "solo-mp" / "hooks" / "hooks.json",
        {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "/x/never-installed.sh"}]}]}},
    )

    unsynced = mod.check_source_cache_sync(str(marketplaces), str(cache))

    assert len(unsynced) == 1
    assert unsynced[0]["cache"] == "(no cache install found)"
    assert unsynced[0]["script"] == "never-installed.sh"
