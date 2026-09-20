#!/usr/bin/env python3
"""
Unit Test Suite for session:context (context-usage-inject.sh & context-usage-now.sh)
Validates Claude Code usage extraction, compact boundaries, and Antigravity <CONTEXT_SUMMARY> compaction support.
"""
import os
import sys
import json
import subprocess
import pathlib
import tempfile
import unittest

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent.parent / "resources"
INJECT_SH = str(SCRIPT_DIR / "context-usage-inject.sh")
NOW_SH = str(SCRIPT_DIR / "context-usage-now.sh")


class TestContextMeasure(unittest.TestCase):
    def test_claude_code_usage_extraction(self):
        """Verify normal Claude Code JSONL transcript usage extraction."""
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        f.write(json.dumps({"type": "user", "message": {"role": "user", "content": "hello"}}) + "\n")
        f.write(json.dumps({
            "type": "assistant",
            "message": {
                "role": "assistant",
                "model": "claude-3-7-sonnet",
                "content": [{"type": "text", "text": "world"}],
                "usage": {
                    "input_tokens": 10000,
                    "cache_creation_input_tokens": 5000,
                    "cache_read_input_tokens": 5000,
                    "output_tokens": 500
                }
            }
        }) + "\n")
        f.close()

        payload = json.dumps({"transcript_path": f.name})
        res = subprocess.run([INJECT_SH], input=payload, text=True, capture_output=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Context usage:", res.stdout)
        self.assertIn("20.0k / 200k tokens (10.0%)", res.stdout)
        os.remove(f.name)

    def test_claude_code_compact_boundary_reset(self):
        """Verify compact_boundary resets prior usage in Claude Code transcripts."""
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        f.write(json.dumps({
            "type": "assistant",
            "message": {
                "role": "assistant",
                "model": "claude-3-7-sonnet",
                "usage": {"input_tokens": 80000, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
            }
        }) + "\n")
        f.write(json.dumps({"type": "system", "subtype": "compact_boundary"}) + "\n")
        f.close()

        payload = json.dumps({"transcript_path": f.name})
        res = subprocess.run([INJECT_SH], input=payload, text=True, capture_output=True)
        self.assertEqual(res.returncode, 0)
        # Should be empty since no post-compact assistant turn has occurred yet
        self.assertEqual(res.stdout.strip(), "")
        os.remove(f.name)

    def test_antigravity_uncompacted_calculation(self):
        """Verify Antigravity JSONL calculation without compaction."""
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        f.write(json.dumps({"step_index": 0, "source": "USER_EXPLICIT", "type": "USER_INPUT", "content": "작업 시작"}) + "\n")
        f.write(json.dumps({"step_index": 1, "source": "MODEL", "type": "PLANNER_RESPONSE", "thinking": "reasoning...", "content": "진행 중"}) + "\n")
        f.close()

        payload = json.dumps({"transcript_path": f.name})
        res = subprocess.run([INJECT_SH], input=payload, text=True, capture_output=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Context usage:", res.stdout)
        self.assertIn("/ 1000k tokens", res.stdout)
        os.remove(f.name)

    def test_antigravity_context_summary_compaction_slicing(self):
        """Verify Antigravity <CONTEXT_SUMMARY> discards pre-compact steps and calculates active window."""
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        # Old pre-compact steps (e.g. 500k chars)
        for i in range(50):
            f.write(json.dumps({"step_index": i, "source": "MODEL", "type": "PLANNER_RESPONSE", "content": "X" * 10000}) + "\n")
        # Summary step
        f.write(json.dumps({
            "step_index": 50,
            "source": "USER_EXPLICIT",
            "type": "USER_INPUT",
            "content": "<CONTEXT_SUMMARY>\nOld turns summarized here\n</CONTEXT_SUMMARY>"
        }) + "\n")
        # New post-compact step
        f.write(json.dumps({
            "step_index": 51,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "content": "신규 작업 완료"
        }) + "\n")
        f.close()

        payload = json.dumps({"transcript_path": f.name})
        res = subprocess.run([INJECT_SH], input=payload, text=True, capture_output=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Context usage:", res.stdout)
        # Without 500k old chars, active tokens is small (< 1k)
        self.assertIn("/ 1000k tokens", res.stdout)
        os.remove(f.name)

    def test_context_usage_now_pull(self):
        """Verify context-usage-now.sh pull path."""
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        f.write(json.dumps({
            "step_index": 0,
            "source": "USER_EXPLICIT",
            "type": "USER_INPUT",
            "content": "<CONTEXT_SUMMARY>summary</CONTEXT_SUMMARY>"
        }) + "\n")
        f.close()

        res = subprocess.run(["bash", NOW_SH, f.name], text=True, capture_output=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Context usage:", res.stdout)
        os.remove(f.name)


class TestContextUsageNowFallbackScoping(unittest.TestCase):
    """No-argument invocation used to fall back to 'most recently modified
    jsonl under all of ~/.claude/projects' -- with many concurrent sessions
    across workspaces/machines (Syncthing-synced project dirs included) that
    silently reports a completely unrelated session's usage as the caller's
    own. The fallback must be scoped to the calling workspace's own project
    dir (derived from cwd the same way Claude Code names it) before it ever
    considers files outside that dir."""

    def _write_transcript(self, path, input_tokens):
        with open(path, "w") as f:
            f.write(json.dumps({
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "model": "claude-3-7-sonnet",
                    "usage": {
                        "input_tokens": input_tokens,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                    },
                },
            }) + "\n")

    def test_scopes_fallback_to_calling_workspace_over_newer_decoy(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as workspace:
            # bash resolves $PWD to the physical path (e.g. macOS
            # /var/folders/... -> /private/var/folders/...), so the project
            # key must be derived from the same realpath the script will see.
            workspace = os.path.realpath(workspace)
            projects_dir = pathlib.Path(home) / ".claude" / "projects"
            project_key = workspace.replace("/", "-").replace(".", "-")
            own_dir = projects_dir / project_key
            own_dir.mkdir(parents=True)
            own_jsonl = own_dir / "own-session.jsonl"
            self._write_transcript(own_jsonl, 1000)  # 0.5% of a 200k window

            # A decoy from a *different* workspace, touched more recently --
            # this is what used to win the unscoped global mtime race.
            decoy_dir = projects_dir / "-some-other-workspace"
            decoy_dir.mkdir(parents=True)
            decoy_jsonl = decoy_dir / "decoy-session.jsonl"
            self._write_transcript(decoy_jsonl, 90000)  # 45% of a 200k window
            future = pathlib.Path(str(own_jsonl)).stat().st_mtime + 3600
            os.utime(decoy_jsonl, (future, future))

            env = dict(os.environ)
            env["HOME"] = home
            env.pop("ANTIGRAVITY_AGENT", None)
            env.pop("ANTIGRAVITY_CONVERSATION_ID", None)
            env.pop("ANTIGRAVITY_CONVERSATION_ID", None)
            res = subprocess.run(
                ["bash", NOW_SH], cwd=workspace, env=env, text=True, capture_output=True
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            # Must reflect own-session.jsonl (0.5%), not the newer decoy (45%).
            self.assertIn("(0.5%)", res.stdout)
            self.assertNotIn("(45.0%)", res.stdout)

    def test_claude_code_workspace_match_outranks_antigravity_dir_existence(self):
        """On any machine where Antigravity has ever run, $HOME/.gemini/antigravity-cli/brain
        exists unconditionally -- that mere existence check used to steal
        precedence away from Claude Code on every bare invocation, regardless
        of which harness actually called this script. A workspace-scoped
        Claude Code match must win over it."""
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as workspace:
            workspace = os.path.realpath(workspace)
            projects_dir = pathlib.Path(home) / ".claude" / "projects"
            project_key = workspace.replace("/", "-").replace(".", "-")
            own_dir = projects_dir / project_key
            own_dir.mkdir(parents=True)
            own_jsonl = own_dir / "own-session.jsonl"
            self._write_transcript(own_jsonl, 1000)  # 0.5% of a 200k window

            # Antigravity has "been used" on this machine -- the dir exists --
            # but this invocation is not an Antigravity call.
            brain_dir = pathlib.Path(home) / ".gemini" / "antigravity-cli" / "brain" / "some-agent" / "logs"
            brain_dir.mkdir(parents=True)
            antigravity_transcript = brain_dir / "transcript.jsonl"
            with open(antigravity_transcript, "w") as f:
                f.write(json.dumps({
                    "step_index": 0, "source": "MODEL", "type": "PLANNER_RESPONSE",
                    "content": "X" * 400000,  # large -> would read as a big percentage
                }) + "\n")

            env = dict(os.environ)
            env["HOME"] = home
            env.pop("ANTIGRAVITY_AGENT", None)
            env.pop("ANTIGRAVITY_CONVERSATION_ID", None)
            res = subprocess.run(
                ["bash", NOW_SH], cwd=workspace, env=env, text=True, capture_output=True
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("(0.5%)", res.stdout)
            self.assertIn("/ 200k tokens", res.stdout)

    def test_falls_back_to_global_search_when_workspace_dir_absent(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as workspace:
            projects_dir = pathlib.Path(home) / ".claude" / "projects"
            only_dir = projects_dir / "-some-other-workspace"
            only_dir.mkdir(parents=True)
            only_jsonl = only_dir / "only-session.jsonl"
            self._write_transcript(only_jsonl, 2000)

            env = dict(os.environ)
            env["HOME"] = home
            # `workspace` itself has no matching entry under projects_dir.
            res = subprocess.run(
                ["bash", NOW_SH], cwd=workspace, env=env, text=True, capture_output=True
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("Context usage:", res.stdout)


if __name__ == "__main__":
    unittest.main()
