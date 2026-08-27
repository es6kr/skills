"""Tests for hook-kit/resources/block-hook-registration-without-registry-read.js.

The guard is a PreToolUse Edit|Write hook. It must block hook-registration edits
(settings.json ``hooks`` content, any ``hooks/hooks.json``) when the session
transcript shows no read of ``hook-registry.yaml``, and stay silent otherwise.
Exercised via subprocess (the CLI/stdin contract is the public surface).
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent
GUARD = REPO_ROOT / "skills" / "hook-kit" / "resources" / "block-hook-registration-without-registry-read.js"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _run(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [NODE, str(GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )


def _transcript(tmp_path: pathlib.Path, body: str) -> str:
    p = tmp_path / "session.jsonl"
    p.write_text(body, encoding="utf-8")
    return str(p)


HOOKS_CONTENT = '{"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "x.sh"}]}]}}'


def test_hooks_json_write_without_registry_read_is_blocked(tmp_path):
    rc = _run({
        "tool_name": "Write",
        "tool_input": {"file_path": str(tmp_path / "hooks" / "hooks.json"), "content": HOOKS_CONTENT},
        "transcript_path": _transcript(tmp_path, '{"type":"user","message":"hello"}\n'),
    })
    assert rc.returncode == 2
    assert "hook-registry.yaml" in rc.stderr


def test_hooks_json_write_after_registry_read_passes(tmp_path):
    rc = _run({
        "tool_name": "Write",
        "tool_input": {"file_path": str(tmp_path / "hooks" / "hooks.json"), "content": HOOKS_CONTENT},
        "transcript_path": _transcript(
            tmp_path,
            '{"type":"assistant","tool_input":{"file_path":"skills/hook-kit/hook-registry.yaml"}}\n',
        ),
    })
    assert rc.returncode == 0


def test_settings_hooks_edit_without_registry_read_is_blocked(tmp_path):
    rc = _run({
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(tmp_path / ".claude" / "settings.json"),
            "old_string": '"matcher": "Bash",',
            "new_string": '"matcher": "Bash|PowerShell",',
        },
        "transcript_path": _transcript(tmp_path, "no registry here\n"),
    })
    assert rc.returncode == 2


def test_settings_non_hook_edit_is_ignored(tmp_path):
    rc = _run({
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(tmp_path / ".claude" / "settings.json"),
            "old_string": '"Bash(git *)",',
            "new_string": '"Bash(git *)",\n      "Bash(npm *)",',
        },
        "transcript_path": _transcript(tmp_path, "no registry here\n"),
    })
    assert rc.returncode == 0


def test_unrelated_file_is_ignored(tmp_path):
    rc = _run({
        "tool_name": "Write",
        "tool_input": {"file_path": str(tmp_path / "README.md"), "content": "hooks matcher command"},
        "transcript_path": _transcript(tmp_path, "no registry here\n"),
    })
    assert rc.returncode == 0


def test_explicit_override_token_passes(tmp_path):
    rc = _run({
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(tmp_path / ".claude-plugin" / "hooks.json"),
            "content": HOOKS_CONTENT + "\n// hook-registry-consulted",
        },
        "transcript_path": _transcript(tmp_path, "no registry here\n"),
    })
    assert rc.returncode == 0


def test_missing_transcript_fails_open(tmp_path):
    rc = _run({
        "tool_name": "Write",
        "tool_input": {"file_path": str(tmp_path / "hooks" / "hooks.json"), "content": HOOKS_CONTENT},
    })
    assert rc.returncode == 0
