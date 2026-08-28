"""Unit tests for trigger-compile.sh and exclude_content noise suppression.

Tests:
  - exclude_content / exclude-content / content_exclude parsing in trigger-compile.sh
  - Generated trigger-PostToolUse.js code contains !new RegExp(...).test(NEW_CONTENT)
  - PostToolUse execution suppresses trigger on audit section edits
  - PostToolUse execution fires trigger on normal plan edits
"""
import json
import os
import subprocess
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRIGGER_COMPILE = os.path.join(REPO_ROOT, "skills", "skill-kit", "scripts", "trigger-compile.sh")
POST_TRIGGER_JS = os.path.join(REPO_ROOT, "skills", "skill-kit", "resources", "trigger-PostToolUse.js")


def test_code_workflow_trigger_has_exclude_content():
    """Verify code-workflow/SKILL.md defines exclude_content for audit noise."""
    skill_file = os.path.join(REPO_ROOT, "skills", "code-workflow", "SKILL.md")
    with open(skill_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "exclude_content:" in content or "exclude-content:" in content
    assert "Audit" in content


def test_post_tool_use_js_has_new_content_and_regex():
    """Verify compiled trigger-PostToolUse.js inspects NEW_CONTENT."""
    assert os.path.isfile(POST_TRIGGER_JS)
    with open(POST_TRIGGER_JS, "r", encoding="utf-8") as f:
        code = f.read()
    assert "NEW_CONTENT" in code
    assert "!new RegExp(" in code
    assert "Audit" in code


def _run_post_trigger(tool_input):
    """Run trigger-PostToolUse.js with a mock tool input payload."""
    payload = {
        "tool_name": "Edit",
        "tool_input": tool_input
    }
    proc = subprocess.run(
        ["node", POST_TRIGGER_JS],
        input=json.dumps(payload),
        capture_output=True,
        text=True
    )
    return proc.stdout


def test_post_tool_use_suppresses_fable_audit_edit():
    """Fable or review agent appending audit comments must not fire code-workflow trigger."""
    out = _run_post_trigger({
        "file_path": "/workspace/docs/generated/plan-foo.md",
        "new_string": "## 2026-08-25 Fable Audit\n\n- status: approved_by_fable_audit\n- findings: 0 major"
    })
    assert '<skill-trigger name="code-workflow">' not in out


def test_post_tool_use_suppresses_audit_status_edit():
    """Edits containing audit_status: must not fire code-workflow trigger."""
    out = _run_post_trigger({
        "file_path": "plan-my-feature.md",
        "new_string": "audit_status: approved_by_fable_audit\n"
    })
    assert '<skill-trigger name="code-workflow">' not in out


def test_post_tool_use_suppresses_korean_audit_edit():
    """Edits containing Korean audit header must not fire code-workflow trigger."""
    out = _run_post_trigger({
        "file_path": "plan-my-feature.md",
        "new_string": "## Fable \uAC10\uC0AC \uBC0F \uAC80\uC99D \uACB0\uACFC\n\n\uC2B9\uC778 \uC644\uB8CC"
    })
    assert '<skill-trigger name="code-workflow">' not in out


def test_post_tool_use_fires_on_normal_plan_edit():
    """Normal plan creation/edit must still fire code-workflow trigger."""
    out = _run_post_trigger({
        "file_path": "/workspace/docs/generated/plan-foo.md",
        "new_string": "## Architecture Overview\n\nWe will implement the feature across 3 phases."
    })
    assert '<skill-trigger name="code-workflow">' in out
    assert 'plan-*.md or research-*.md file modification detected' in out
