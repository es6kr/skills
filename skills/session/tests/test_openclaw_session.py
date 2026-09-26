import json
import subprocess
import sys
from pathlib import Path
import pytest

# Add skills/session/scripts to sys.path
scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

import openclaw_session


@pytest.fixture
def mock_openclaw_env(tmp_path):
    """Create a mock .openclaw directory structure with agents, sessions.json, and jsonl files."""
    openclaw_dir = tmp_path / ".openclaw"
    agents_dir = openclaw_dir / "agents"
    main_sessions = agents_dir / "main" / "sessions"
    pm_sessions = agents_dir / "es6kr-project-pm" / "sessions"

    main_sessions.mkdir(parents=True)
    pm_sessions.mkdir(parents=True)

    # Mock sessions.json in main
    main_sessions_meta = {
        "agent:main:main": {
            "sessionId": "11111111-1111-1111-1111-111111111111",
            "updatedAt": 1790400000000,
            "route": {"channel": "discord", "accountId": "default"}
        }
    }
    (main_sessions / "sessions.json").write_text(json.dumps(main_sessions_meta), encoding="utf-8")

    # Mock sessions.json in pm
    (pm_sessions / "sessions.json").write_text(json.dumps({}), encoding="utf-8")

    # Session 1: main agent (active)
    session1_id = "11111111-1111-1111-1111-111111111111"
    session1_lines = [
        {"type": "session", "id": session1_id, "timestamp": "2026-09-26T00:00:00.000Z", "cwd": "/work/main"},
        {"type": "message", "id": "m1", "timestamp": "2026-09-26T00:01:00.000Z", "message": {"role": "user", "content": "Deploy infra to staging"}},
        {"type": "message", "id": "m2", "timestamp": "2026-09-26T00:02:00.000Z", "message": {"role": "assistant", "content": "Starting deployment..."}}
    ]
    with open(main_sessions / f"{session1_id}.jsonl", "w", encoding="utf-8") as f:
        for line in session1_lines:
            f.write(json.dumps(line) + "\n")

    # Session 1 trajectory: record tool actions (bash commands)
    session1_traj = [
        {"traceSchema": "openclaw-trajectory", "type": "tool.call", "ts": "2026-09-26T00:01:10.000Z", "data": {"name": "bash", "arguments": {"command": "git status", "cwd": "/work/main"}}},
        {"traceSchema": "openclaw-trajectory", "type": "tool.result", "ts": "2026-09-26T00:01:11.000Z", "data": {"name": "bash", "result": {"status": "completed", "exitCode": 0}}},
        {"traceSchema": "openclaw-trajectory", "type": "tool.call", "ts": "2026-09-26T00:01:30.000Z", "data": {"name": "bash", "arguments": {"command": "git commit -m 'feat: init'", "cwd": "/work/main"}}},
        {"traceSchema": "openclaw-trajectory", "type": "tool.result", "ts": "2026-09-26T00:01:31.000Z", "data": {"name": "bash", "result": {"status": "completed", "exitCode": 0}}},
    ]
    with open(main_sessions / f"{session1_id}.trajectory.jsonl", "w", encoding="utf-8") as f:
        for tline in session1_traj:
            f.write(json.dumps(tline) + "\n")

    # Session 2: main agent (reset file and trajectory should be ignored in listing count)
    session2_id = "22222222-2222-2222-2222-222222222222"
    session2_lines = [
        {"type": "session", "id": session2_id, "timestamp": "2026-09-25T12:00:00.000Z", "cwd": "/work/main"},
        {"type": "message", "id": "m3", "timestamp": "2026-09-25T12:01:00.000Z", "message": {"role": "user", "content": "Check database migration logs"}},
        {"type": "message", "id": "m4", "timestamp": "2026-09-25T12:02:00.000Z", "message": {"role": "assistant", "content": [{"type": "text", "text": "Migration completed successfully"}]}}
    ]
    with open(main_sessions / f"{session2_id}.jsonl", "w", encoding="utf-8") as f:
        for line in session2_lines:
            f.write(json.dumps(line) + "\n")

    # Associated files that should not be listed as distinct primary sessions
    (main_sessions / f"{session2_id}.trajectory.jsonl").write_text('{"type":"tool.call"}\n', encoding="utf-8")
    (main_sessions / f"{session2_id}.jsonl.reset.2026-09-25").write_text('{"type":"reset"}\n', encoding="utf-8")

    # Session 3: pm agent
    session3_id = "33333333-3333-3333-3333-333333333333"
    session3_lines = [
        {"type": "session", "id": session3_id, "timestamp": "2026-09-24T08:00:00.000Z", "cwd": "/work/pm"},
        {"type": "message", "id": "m5", "timestamp": "2026-09-24T08:01:00.000Z", "message": {"role": "user", "content": "Plan Q4 roadmaps"}},
        {"type": "message", "id": "m6", "timestamp": "2026-09-24T08:02:00.000Z", "message": {"role": "assistant", "content": "Here is the Q4 plan."}}
    ]
    with open(pm_sessions / f"{session3_id}.jsonl", "w", encoding="utf-8") as f:
        for line in session3_lines:
            f.write(json.dumps(line) + "\n")

    return openclaw_dir


def test_list_openclaw_sessions(mock_openclaw_env):
    """Test listing all openclaw sessions across agents."""
    sessions = openclaw_session.list_sessions(openclaw_root=mock_openclaw_env)

    # Should find 3 sessions (session1, session2, session3)
    session_ids = [s["session_id"] for s in sessions]
    assert "11111111-1111-1111-1111-111111111111" in session_ids
    assert "22222222-2222-2222-2222-222222222222" in session_ids
    assert "33333333-3333-3333-3333-333333333333" in session_ids
    assert len(sessions) == 3

    # Check active status and channel for session 1
    s1 = next(s for s in sessions if s["session_id"] == "11111111-1111-1111-1111-111111111111")
    assert s1["is_active"] is True
    assert s1["channel"] == "discord"
    assert s1["agent_id"] == "main"

    # Check agent filter
    pm_only = openclaw_session.list_sessions(openclaw_root=mock_openclaw_env, agent="es6kr-project-pm")
    assert len(pm_only) == 1
    assert pm_only[0]["session_id"] == "33333333-3333-3333-3333-333333333333"


def test_search_openclaw_sessions(mock_openclaw_env):
    """Test searching openclaw sessions by keyword."""
    # Search 'staging'
    results = openclaw_session.search_sessions(openclaw_root=mock_openclaw_env, keyword="staging")
    assert len(results) == 1
    assert results[0]["session_id"] == "11111111-1111-1111-1111-111111111111"
    assert results[0]["role"] == "user"
    assert "staging" in results[0]["content"].lower()

    # Search 'migration' (found in assistant text block)
    results_mig = openclaw_session.search_sessions(openclaw_root=mock_openclaw_env, keyword="migration")
    assert len(results_mig) >= 1
    assert any(r["session_id"] == "22222222-2222-2222-2222-222222222222" for r in results_mig)

    # Search non-existent keyword
    assert len(openclaw_session.search_sessions(openclaw_root=mock_openclaw_env, keyword="nonexistent12345")) == 0


def test_summarize_openclaw_session(mock_openclaw_env):
    """Test summarizing an openclaw session."""
    summary = openclaw_session.summarize_session(
        session_id="11111111-1111-1111-1111-111111111111",
        openclaw_root=mock_openclaw_env
    )

    assert summary["session_id"] == "11111111-1111-1111-1111-111111111111"
    assert summary["agent_id"] == "main"
    assert len(summary["messages"]) == 2
    assert summary["messages"][0]["role"] == "user"
    assert summary["messages"][0]["text"] == "Deploy infra to staging"
    assert summary["messages"][1]["role"] == "assistant"
    assert summary["messages"][1]["text"] == "Starting deployment..."


def test_cli_execution(mock_openclaw_env):
    """Test CLI commands work as expected."""
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "openclaw_session.py"

    # List command
    res_list = subprocess.run(
        [sys.executable, str(script_path), "list", "--root", str(mock_openclaw_env), "--json"],
        capture_output=True,
        text=True,
        check=True
    )
    data = json.loads(res_list.stdout)
    assert len(data) == 3

    # Search command
    res_search = subprocess.run(
        [sys.executable, str(script_path), "search", "Q4", "--root", str(mock_openclaw_env), "--json"],
        capture_output=True,
        text=True,
        check=True
    )
    search_data = json.loads(res_search.stdout)
    assert len(search_data) == 2

    # Inspect command
    res_inspect = subprocess.run(
        [sys.executable, str(script_path), "inspect", "11111111-1111-1111-1111-111111111111", "--root", str(mock_openclaw_env), "--json"],
        capture_output=True,
        text=True,
        check=True
    )
    inspect_data = json.loads(res_inspect.stdout)
    assert len(inspect_data["tool_actions"]) == 2
    assert inspect_data["last_action"]["command"] == "git commit -m 'feat: init'"


def test_inspect_openclaw_session_with_actions(mock_openclaw_env):
    """Test inspecting an openclaw session to check completed actions/tools for resumption."""
    inspection = openclaw_session.inspect_session(
        session_id="11111111-1111-1111-1111-111111111111",
        openclaw_root=mock_openclaw_env
    )
    assert inspection["session_id"] == "11111111-1111-1111-1111-111111111111"
    assert inspection["agent_id"] == "main"
    assert len(inspection["tool_actions"]) == 2
    assert inspection["tool_actions"][0]["name"] == "bash"
    assert inspection["tool_actions"][0]["command"] == "git status"
    assert inspection["tool_actions"][1]["command"] == "git commit -m 'feat: init'"
    assert inspection["last_action"]["command"] == "git commit -m 'feat: init'"

