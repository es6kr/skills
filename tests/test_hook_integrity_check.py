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
