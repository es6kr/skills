"""Unit tests for verify-hooks-json.py (synthetic fixtures only, independent of
repo content).

Two failure classes under test:
  - Duplicate registration: the same (event, matcher, script-basename) registered
    2+ times -> fires twice on every trigger
  - Ghost registration: a registered path has no file behind it -> the hook dies
    with exit 127, which the harness cannot distinguish from "ran, no objection",
    so the guard stays listed while enforcing nothing

Run:
  python -m pytest tests/test_verify_hooks_json.py -v

CI (.github/workflows/test.yml) collects via `python -m pytest tests -v`, so this
file must live under tests/. The script under test stays in scripts/ and is loaded
by path.

Ported from es6kr/claude-plugins (PR #23, merged) — translated from the original
Korean docstrings/comments since this repo is PUBLIC and English-only.
"""
import importlib.util
import json
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(REPO_ROOT, "scripts", "verify-hooks-json.py")


def _load():
    spec = importlib.util.spec_from_file_location("verify_hooks_json", CANON)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


def _write_plugin(tmp_path, commands, scripts_to_create=()):
    """Create <plugin-root>/hooks/hooks.json and return its path."""
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": c} for c in commands]}
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(payload), encoding="utf-8")
    for rel in scripts_to_create:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    return hooks_dir / "hooks.json"


# --- ghost registration ---

def test_ghost_registration_is_reported(tmp_path):
    """A registered path with no file behind it is flagged as a ghost."""
    fp = _write_plugin(tmp_path, ['bash "${CLAUDE_PLUGIN_ROOT}/skills/a/resources/gone.sh"'])
    errors, checked, skipped = mod.check_hooks_file(fp)
    assert checked == 1 and skipped == 0
    assert len(errors) == 1
    assert "Ghost hook registration" in errors[0]
    assert "skills/a/resources/gone.sh" in errors[0]


def test_existing_script_passes(tmp_path):
    """A registered path that exists on disk passes."""
    rel = "skills/a/resources/present.sh"
    fp = _write_plugin(tmp_path, ['bash "${CLAUDE_PLUGIN_ROOT}/' + rel + '"'], [rel])
    errors, checked, skipped = mod.check_hooks_file(fp)
    assert errors == [] and checked == 1 and skipped == 0


def test_relocated_script_is_caught(tmp_path):
    """The real-world regression: a script was moved but its registration wasn't."""
    fp = _write_plugin(
        tmp_path,
        ['bash "${CLAUDE_PLUGIN_ROOT}/skills/hook-kit/resources/moved.sh"'],
        ["skills/cleanup/resources/moved.sh"],  # actual location is the relocated one
    )
    errors, _, _ = mod.check_hooks_file(fp)
    assert len(errors) == 1 and "Ghost hook registration" in errors[0]


# --- path-extraction shapes ---

def test_path_extraction_handles_command_shapes():
    """Recognizes quoted/unquoted, with/without interpreter, with/without braces."""
    cases = [
        ('bash "${CLAUDE_PLUGIN_ROOT}/a/b.sh"', ["a/b.sh"]),
        ("${CLAUDE_PLUGIN_ROOT}/a/b.sh", ["a/b.sh"]),
        ("$CLAUDE_PLUGIN_ROOT/a/b.sh", ["a/b.sh"]),
        ('node "${CLAUDE_PLUGIN_ROOT}/a/b.js" Read', ["a/b.js"]),
        ("echo hello", []),
    ]
    for cmd, expected in cases:
        assert mod.extract_plugin_root_paths(cmd) == expected, cmd


def test_path_extraction_does_not_produce_false_ghosts():
    """Getting the path terminator wrong produces a path that doesn't exist -> a
    false positive (CI failing on a legitimate change).

    A false positive is worse than a miss — it blocks normal work. Whitespace
    inside quotes must stay one unit; a shell metacharacter outside quotes must
    terminate the path.
    """
    cases = [
        # space inside quotes: truncating it yields a nonexistent path
        ('bash "${CLAUDE_PLUGIN_ROOT}/a/my guard.sh"', ["a/my guard.sh"]),
        ("bash '${CLAUDE_PLUGIN_ROOT}/a/my guard.sh'", ["a/my guard.sh"]),
        # shell metacharacter outside quotes: including it yields a nonexistent path
        ("${CLAUDE_PLUGIN_ROOT}/a/g.sh;", ["a/g.sh"]),
        ("${CLAUDE_PLUGIN_ROOT}/a/g.sh)", ["a/g.sh"]),
        ('bash "${CLAUDE_PLUGIN_ROOT}/a/g.sh" && echo ok', ["a/g.sh"]),
        ("bash ${CLAUDE_PLUGIN_ROOT}/a/g.sh | tee /tmp/x", ["a/g.sh"]),
        ('(bash "${CLAUDE_PLUGIN_ROOT}/a/g.sh")', ["a/g.sh"]),
        # two references in one command
        (
            "${CLAUDE_PLUGIN_ROOT}/a/one.sh && ${CLAUDE_PLUGIN_ROOT}/a/two.sh",
            ["a/one.sh", "a/two.sh"],
        ),
    ]
    for cmd, expected in cases:
        assert mod.extract_plugin_root_paths(cmd) == expected, cmd


def test_quoted_path_with_space_resolves_instead_of_false_ghost(tmp_path):
    """A path containing a space still passes when it exists (end-to-end false-positive regression guard)."""
    rel = "skills/a/resources/my guard.sh"
    fp = _write_plugin(tmp_path, ['bash "${CLAUDE_PLUGIN_ROOT}/' + rel + '"'], [rel])
    errors, checked, skipped = mod.check_hooks_file(fp)
    assert errors == [] and checked == 1 and skipped == 0


def test_unresolvable_command_is_skipped_not_failed(tmp_path):
    """An inline command with no CLAUDE_PLUGIN_ROOT reference is a skip, not an error."""
    fp = _write_plugin(tmp_path, ["echo inline-guard"])
    errors, checked, skipped = mod.check_hooks_file(fp)
    assert errors == [] and checked == 0 and skipped == 1


def test_plugin_root_is_grandparent_of_hooks_json(tmp_path):
    """${CLAUDE_PLUGIN_ROOT} = the grandparent directory of <plugin-root>/hooks/hooks.json."""
    fp = tmp_path / "plugins" / "code-quality" / "hooks" / "hooks.json"
    assert mod.plugin_root_for(fp) == tmp_path / "plugins" / "code-quality"


# --- duplicate registration (existing-behavior regression guard) ---

def test_duplicate_registration_is_reported(tmp_path):
    """The same (event, matcher, basename) registered twice is flagged as a duplicate."""
    rel = "skills/a/resources/dup.sh"
    cmd = 'bash "${CLAUDE_PLUGIN_ROOT}/' + rel + '"'
    fp = _write_plugin(tmp_path, [cmd, cmd], [rel])
    errors, _, _ = mod.check_hooks_file(fp)
    assert len(errors) == 1
    assert "Duplicate hook registration" in errors[0]


def test_duplicate_inline_command_is_reported(tmp_path):
    """An inline command with no script token is still a duplicate when registered twice.

    Exercises the extract_script_basename fallback that uses the whole command
    string as the dedup key.
    """
    fp = _write_plugin(tmp_path, ["echo inline-guard", "echo inline-guard"])
    errors, checked, skipped = mod.check_hooks_file(fp)
    assert checked == 0 and skipped == 2
    assert len(errors) == 1 and "Duplicate hook registration" in errors[0]


def test_distinct_inline_commands_are_not_duplicates(tmp_path):
    """Two different inline commands are not duplicates (the fallback key differs per command)."""
    fp = _write_plugin(tmp_path, ["echo one", "echo two"])
    errors, _, _ = mod.check_hooks_file(fp)
    assert errors == []


def test_duplicate_and_ghost_reported_together(tmp_path):
    """The two classes are independent — both can be reported for one file."""
    cmd = 'bash "${CLAUDE_PLUGIN_ROOT}/skills/a/resources/gone.sh"'
    fp = _write_plugin(tmp_path, [cmd, cmd])
    errors, _, _ = mod.check_hooks_file(fp)
    assert sum("Duplicate hook registration" in e for e in errors) == 1  # only the 2nd registration is a duplicate
    assert sum("Ghost hook registration" in e for e in errors) == 2      # both registrations are ghosts
    assert len(errors) == 3


def test_malformed_json_is_reported(tmp_path):
    """A JSON parse failure is not silently swallowed."""
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir(parents=True)
    fp = hooks_dir / "hooks.json"
    fp.write_text("{ not json", encoding="utf-8")
    errors, checked, skipped = mod.check_hooks_file(fp)
    assert len(errors) == 1 and "Failed to parse JSON" in errors[0]
