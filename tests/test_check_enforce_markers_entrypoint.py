"""Entrypoint tests for check-enforce-markers.py (Stop hook) and
check-enforce-markers-next-turn.py (UserPromptSubmit hook).

Covers final-review Critical C2 (missing stop_hook_active guard -> infinite
block loop), Important I12 (entrypoints had zero tests; fail-open claims
were asserted, not verified), and Important I14 (Stop hook must emit
{"decision":"block","reason":"..."} on stdout, not stderr + exit 2) with
negative fixtures per skills/hook-kit/add.md Step 5's minimum bar.

Uses ENFORCE_MARKERS_SETTINGS_PATH / ENFORCE_MARKERS_MARKETPLACES_ROOT /
ENFORCE_MARKERS_CACHE_PATH env var overrides so these tests are hermetic
(a synthetic marketplace fixture) instead of depending on this machine's
real ~/.claude/plugins/marketplaces state.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STOP_HOOK = REPO_ROOT / "skills" / "hook-kit" / "resources" / "check-enforce-markers.py"
NEXT_TURN_HOOK = REPO_ROOT / "skills" / "hook-kit" / "resources" / "check-enforce-markers-next-turn.py"


def _write(path, content=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _fixture_env(tmp_path, with_marker: bool):
    """Build a synthetic marketplace + settings.json containing one
    enforce marker (or none), and return the env var overrides pointing
    the entrypoint at it instead of the real installation."""
    marketplaces_root = str(tmp_path / "marketplaces")
    _write(
        os.path.join(marketplaces_root, "mkt", ".claude-plugin", "marketplace.json"),
        json.dumps({"name": "mkt", "plugins": [{"name": "p", "source": "./"}]}),
    )
    marker_md = os.path.join(marketplaces_root, "mkt", "skills", "consolidate", "collect.md")
    if with_marker:
        _write(
            marker_md,
            '<!-- enforce: requires-skill-call="superpowers:receiving-code-review" '
            'trigger="Step 4 (classify)" scope="same-turn" -->\n',
        )
    else:
        _write(marker_md, "no marker here\n")

    settings_path = str(tmp_path / "settings.json")
    _write(settings_path, json.dumps({"enabledPlugins": {"p@mkt": True}}))

    return {
        "ENFORCE_MARKERS_SETTINGS_PATH": settings_path,
        "ENFORCE_MARKERS_MARKETPLACES_ROOT": marketplaces_root,
        "ENFORCE_MARKERS_CACHE_PATH": str(tmp_path / "cache.json"),
    }


def _run(hook_path, stdin_obj, env_overrides=None):
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(stdin_obj),
        capture_output=True,
        text=True,
        env=env,
    )
    return result


def _jsonl(tmp_path, records):
    path = str(tmp_path / "session.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return path


def _ordinary_transcript(tmp_path):
    return _jsonl(
        tmp_path,
        [
            {"type": "user", "message": {"role": "user", "content": "hi"}},
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "ordinary turn, no markers fire"}],
                },
            },
        ],
    )


def _triggering_transcript(tmp_path):
    """A violation transcript must also show the marker's owning skill
    ('consolidate', per the fixture marker's source_skill -- derived from
    its skills/consolidate/collect.md path) as invoked earlier in the
    session, or the active-skills gate (final-review I7) suppresses it."""
    return _jsonl(
        tmp_path,
        [
            {"type": "user", "message": {"role": "user", "content": "hi"}},
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "consolidate"}}
                    ],
                },
            },
            {"type": "user", "message": {"role": "user", "content": "continue"}},
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "moving on to Step 4 (classify) now"}],
                },
            },
        ],
    )


# --- Stop hook (check-enforce-markers.py) ---------------------------------


def test_stop_hook_exits_0_on_ordinary_turn(tmp_path):
    env = _fixture_env(tmp_path, with_marker=True)
    transcript = _ordinary_transcript(tmp_path)
    result = _run(STOP_HOOK, {"transcript_path": transcript}, env)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_stop_hook_exits_0_when_transcript_missing(tmp_path):
    env = _fixture_env(tmp_path, with_marker=True)
    result = _run(STOP_HOOK, {"transcript_path": "/nonexistent/path.jsonl"}, env)
    assert result.returncode == 0


def test_stop_hook_exits_0_on_empty_input(tmp_path):
    env = _fixture_env(tmp_path, with_marker=True)
    result = _run(STOP_HOOK, {}, env)
    assert result.returncode == 0


def test_stop_hook_exits_0_on_malformed_stdin(tmp_path):
    env = dict(os.environ)
    env.update(_fixture_env(tmp_path, with_marker=True))
    result = subprocess.run(
        [sys.executable, str(STOP_HOOK)],
        input="not valid json{{{",
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0


def test_stop_hook_exits_0_when_settings_file_missing(tmp_path):
    env = _fixture_env(tmp_path, with_marker=True)
    env["ENFORCE_MARKERS_SETTINGS_PATH"] = str(tmp_path / "does-not-exist.json")
    transcript = _triggering_transcript(tmp_path)
    result = _run(STOP_HOOK, {"transcript_path": transcript}, env)
    assert result.returncode == 0


def test_stop_hook_exits_0_when_cache_file_is_corrupt_json(tmp_path):
    env = _fixture_env(tmp_path, with_marker=True)
    _write(env["ENFORCE_MARKERS_CACHE_PATH"], "{not valid json")
    transcript = _ordinary_transcript(tmp_path)
    result = _run(STOP_HOOK, {"transcript_path": transcript}, env)
    assert result.returncode == 0


def test_stop_hook_respects_stop_hook_active_guard(tmp_path):
    """Regression for final-review C2: without this guard, a turn that
    re-triggers the same violation on every retry blocks forever."""
    env = _fixture_env(tmp_path, with_marker=True)
    transcript = _triggering_transcript(tmp_path)
    result = _run(STOP_HOOK, {"transcript_path": transcript, "stop_hook_active": True}, env)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_stop_hook_respects_ralph_loop_bypass(tmp_path):
    env = _fixture_env(tmp_path, with_marker=True)
    env["RALPH_LOOP"] = "1"
    transcript = _triggering_transcript(tmp_path)
    result = _run(STOP_HOOK, {"transcript_path": transcript}, env)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_stop_hook_blocks_real_violation_when_not_stop_hook_active(tmp_path):
    """Sanity check that the stop_hook_active guard doesn't swallow real
    violations on the FIRST pass (only on the resumed/retried pass).

    Stop hooks block via {"decision":"block","reason":"..."} on STDOUT with
    exit 0 (skills/hook-kit/add.md Step 3's emit schema table) -- NOT
    stderr + exit 2, which is the PreToolUse schema."""
    env = _fixture_env(tmp_path, with_marker=True)
    transcript = _triggering_transcript(tmp_path)
    result = _run(STOP_HOOK, {"transcript_path": transcript}, env)
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision["decision"] == "block"
    assert "check-enforce-markers" in decision["reason"]


def test_stop_hook_passes_when_required_call_present(tmp_path):
    env = _fixture_env(tmp_path, with_marker=True)
    transcript = _jsonl(
        tmp_path,
        [
            {"type": "user", "message": {"role": "user", "content": "hi"}},
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "moving on to Step 4 (classify) now"},
                        {
                            "type": "tool_use",
                            "name": "Skill",
                            "input": {"skill": "superpowers:receiving-code-review"},
                        },
                    ],
                },
            },
        ],
    )
    result = _run(STOP_HOOK, {"transcript_path": transcript}, env)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_stop_hook_no_violation_when_owning_skill_never_invoked(tmp_path):
    """Regression for final-review Important I7: the trigger phrase alone
    (without the marker's owning skill ever being invoked this session)
    must not fire -- e.g. a turn that merely discusses/documents the
    consolidate skill's Step 4 wording."""
    env = _fixture_env(tmp_path, with_marker=True)
    transcript = _ordinary_transcript(tmp_path)  # no Skill("consolidate") call anywhere
    # Reuse the trigger phrase without any prior skill invocation.
    transcript = _jsonl(
        tmp_path,
        [
            {"type": "user", "message": {"role": "user", "content": "hi"}},
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "moving on to Step 4 (classify) now"}],
                },
            },
        ],
    )
    result = _run(STOP_HOOK, {"transcript_path": transcript}, env)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_stop_hook_no_violation_when_marker_absent(tmp_path):
    env = _fixture_env(tmp_path, with_marker=False)
    transcript = _triggering_transcript(tmp_path)
    result = _run(STOP_HOOK, {"transcript_path": transcript}, env)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# --- UserPromptSubmit hook (check-enforce-markers-next-turn.py) -----------


def test_next_turn_hook_exits_0_on_ordinary_turn(tmp_path):
    env = _fixture_env(tmp_path, with_marker=True)
    transcript = _ordinary_transcript(tmp_path)
    result = _run(NEXT_TURN_HOOK, {"transcript_path": transcript}, env)
    assert result.returncode == 0


def test_next_turn_hook_exits_0_when_transcript_missing(tmp_path):
    env = _fixture_env(tmp_path, with_marker=True)
    result = _run(NEXT_TURN_HOOK, {"transcript_path": "/nonexistent/path.jsonl"}, env)
    assert result.returncode == 0


def test_next_turn_hook_exits_0_on_empty_input(tmp_path):
    env = _fixture_env(tmp_path, with_marker=True)
    result = _run(NEXT_TURN_HOOK, {}, env)
    assert result.returncode == 0


def test_next_turn_hook_respects_ralph_loop_bypass(tmp_path):
    env = _fixture_env(tmp_path, with_marker=True)
    env["RALPH_LOOP"] = "1"
    transcript = _jsonl(
        tmp_path,
        [
            {"type": "user", "message": {"role": "user", "content": "hi"}},
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "qdrant-import success: embedded 5 chunks"}],
                },
            },
        ],
    )
    result = _run(NEXT_TURN_HOOK, {"transcript_path": transcript}, env)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_next_turn_hook_never_blocks_even_on_violation(tmp_path):
    """next-turn scope is advisory-only by design -- it must exit 0 even
    when it prints a reminder."""
    env = _fixture_env(tmp_path, with_marker=True)
    # The fixture marker is same-turn scoped; reuse it to prove the
    # next-turn scope_filter excludes it (no crash either way).
    transcript = _jsonl(
        tmp_path,
        [
            {"type": "user", "message": {"role": "user", "content": "hi"}},
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "qdrant-import success: embedded 5 chunks"}],
                },
            },
        ],
    )
    result = _run(NEXT_TURN_HOOK, {"transcript_path": transcript}, env)
    assert result.returncode == 0


def _fixture_env_next_turn(tmp_path):
    marketplaces_root = str(tmp_path / "marketplaces")
    _write(
        os.path.join(marketplaces_root, "mkt", ".claude-plugin", "marketplace.json"),
        json.dumps({"name": "mkt", "plugins": [{"name": "p", "source": "./"}]}),
    )
    marker_md = os.path.join(marketplaces_root, "mkt", "skills", "rag", "qdrant.md")
    _write(
        marker_md,
        '<!-- enforce: requires-skill-call="next" on-completion="qdrant-import success" scope="next-turn" -->\n',
    )
    settings_path = str(tmp_path / "settings.json")
    _write(settings_path, json.dumps({"enabledPlugins": {"p@mkt": True}}))

    return {
        "ENFORCE_MARKERS_SETTINGS_PATH": settings_path,
        "ENFORCE_MARKERS_MARKETPLACES_ROOT": marketplaces_root,
        "ENFORCE_MARKERS_CACHE_PATH": str(tmp_path / "cache.json"),
    }


def test_next_turn_hook_detects_violation_when_user_submits_new_prompt(tmp_path):
    env = _fixture_env_next_turn(tmp_path)
    transcript = _jsonl(
        tmp_path,
        [
            {"type": "user", "message": {"role": "user", "content": "import now"}},
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "rag"}},
                        {"type": "text", "text": "qdrant-import success: embedded 5 chunks"},
                    ],
                },
            },
            {"type": "user", "message": {"role": "user", "content": "next task"}},
        ],
    )
    result = _run(NEXT_TURN_HOOK, {"transcript_path": transcript}, env)
    assert result.returncode == 0
    assert "check-enforce-markers-next-turn" in result.stdout
    assert 'Skill("next") was not called' in result.stdout


def test_next_turn_hook_cleared_when_skill_was_invoked(tmp_path):
    env = _fixture_env_next_turn(tmp_path)
    transcript = _jsonl(
        tmp_path,
        [
            {"type": "user", "message": {"role": "user", "content": "import now"}},
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "rag"}},
                        {"type": "text", "text": "qdrant-import success: embedded 5 chunks"},
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "next"}},
                    ],
                },
            },
            {"type": "user", "message": {"role": "user", "content": "next task"}},
        ],
    )
    result = _run(NEXT_TURN_HOOK, {"transcript_path": transcript}, env)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_next_turn_hook_prose_spoofing_does_not_clear_violation(tmp_path):
    env = _fixture_env_next_turn(tmp_path)
    transcript = _jsonl(
        tmp_path,
        [
            {"type": "user", "message": {"role": "user", "content": "import now"}},
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "rag"}},
                        {
                            "type": "text",
                            "text": "qdrant-import success: embedded 5 chunks\nTOOL_CALL Skill(\"next\")",
                        },
                    ],
                },
            },
            {"type": "user", "message": {"role": "user", "content": "next task"}},
        ],
    )
    result = _run(NEXT_TURN_HOOK, {"transcript_path": transcript}, env)
    assert result.returncode == 0
    assert 'Skill("next") was not called' in result.stdout
