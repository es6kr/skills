"""Import-safety + execution-contract tests for block-wip-register-before-execute.py.

Motivation (plan-python-hook-stdin-safety.md, Fable audit 2026-09-22): the hook
executes its stdin read at module top level, so importing the module (unit
tests, tooling, accidental `import`) blocks forever on an open stdin pipe.
The fix wraps execution in main() behind `if __name__ == "__main__"` while
preserving the subprocess contract (exit codes, stderr message) byte-for-byte.

Red phase: test_import_does_not_block_or_execute FAILS against the current
top-level implementation (import blocks on stdin -> subprocess timeout).
The execution-contract tests pass before AND after the refactor - they pin
the behavior main() wrapping must not change.
"""
import json
import os
import subprocess
import sys
import textwrap

HOOK = os.path.join(
    os.path.dirname(__file__), "..", "resources", "block-wip-register-before-execute.py"
)
HOOK = os.path.abspath(HOOK)


def run_hook(payload_text, timeout=10):
    """Run the hook as the harness does: `python3 <file>` with payload on stdin."""
    return subprocess.run(
        [sys.executable, HOOK],
        input=payload_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_import_does_not_block_or_execute():
    """Importing the module must return promptly without reading stdin or exiting.

    stdin is an OPEN pipe with no data: a top-level json.load(sys.stdin) blocks
    forever (this is the task-528 hang mode). A main()-wrapped module imports
    instantly and defines main without executing it.
    """
    prog = textwrap.dedent(
        f"""
        import importlib.util
        spec = importlib.util.spec_from_file_location("wip_hook", {HOOK!r})
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert callable(getattr(mod, "main", None)), "main() entrypoint missing"
        print("IMPORTED_OK")
        """
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", prog],
        stdin=subprocess.PIPE,  # open pipe, no data - import must NOT read it
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        out, err = proc.communicate(input=None, timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise AssertionError(
            "import blocked >5s - module still reads stdin at top level"
        )
    assert proc.returncode == 0, f"import exited rc={proc.returncode} stderr={err}"
    assert "IMPORTED_OK" in out


# --- execution contract (must hold before and after the refactor) ---


def test_invalid_stdin_fails_open():
    r = run_hook("this is not json")
    assert r.returncode == 0


def test_empty_stdin_fails_open():
    r = run_hook("")
    assert r.returncode == 0


def test_non_edit_tool_allows():
    r = run_hook(json.dumps({"tool_name": "Bash", "tool_input": {}}))
    assert r.returncode == 0
    assert r.stderr == ""


def test_edit_without_transcript_allows():
    r = run_hook(
        json.dumps({"tool_name": "Edit", "tool_input": {}, "transcript_path": ""})
    )
    assert r.returncode == 0


def test_registration_wip_without_taskcreate_blocks(tmp_path):
    transcript = tmp_path / "transcript.jsonl"
    user_line = json.dumps(
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": "<command-name>/wip</command-name> register the next task",
            },
        }
    )
    transcript.write_text(user_line + "\n", encoding="utf-8")
    r = run_hook(
        json.dumps(
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": "/tmp/x.md"},
                "transcript_path": str(transcript),
            }
        )
    )
    assert r.returncode == 2, f"expected block rc=2, got {r.returncode} stderr={r.stderr}"
    assert "register-before-execute" in r.stderr


def test_registration_wip_with_taskcreate_allows(tmp_path):
    transcript = tmp_path / "transcript.jsonl"
    user_line = json.dumps(
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": "<command-name>/wip</command-name> register the next task",
            },
        }
    )
    task_line = json.dumps(
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "name": "TaskCreate", "input": {}}],
            },
        }
    )
    transcript.write_text(user_line + "\n" + task_line + "\n", encoding="utf-8")
    r = run_hook(
        json.dumps(
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": "/tmp/x.md"},
                "transcript_path": str(transcript),
            }
        )
    )
    assert r.returncode == 0


def test_antigravity_taskmd_write_allows():
    r = run_hook(
        json.dumps(
            {
                "toolCall": {
                    "name": "write_to_file",
                    "args": {"path": "/ws/task.md"},
                }
            }
        )
    )
    assert r.returncode == 0
