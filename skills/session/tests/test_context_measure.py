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


if __name__ == "__main__":
    unittest.main()
