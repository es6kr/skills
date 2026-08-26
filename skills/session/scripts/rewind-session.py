#!/usr/bin/env python3
"""
Direct Session Rewind Helper for Antigravity (IDE/CLI) & Claude Code.

Features:
  --list-sessions <engine> : Enumerate sessions with UUID, title, step/line count, mtime
  --list-checkpoints <engine> <uuid> : Enumerate user prompts, AskUserQuestion steps, and planner responses
  --antigravity-ide [--uuid <id>] [--step <idx>] [--preserve-ask] : Truncate Antigravity IDE SQLite DB & transcript.jsonl
  --antigravity-cli [--uuid <id>] [--step <idx>] [--preserve-ask] : Truncate Antigravity CLI SQLite DB & transcript.jsonl
  --claude-code [--uuid <id>] [--line <idx>] : Truncate Claude Code JSONL file
"""

import sys
import os
import json
import sqlite3
import argparse
import glob
from datetime import datetime

def list_antigravity_sessions(engine_dir):
    conv_dir = os.path.expanduser(os.path.join(engine_dir, "conversations"))
    summary_db = os.path.expanduser(os.path.join(engine_dir, "conversation_summaries.db"))

    if not os.path.exists(conv_dir):
        return []

    results = []
    titles = {}
    if os.path.exists(summary_db):
        try:
            conn = sqlite3.connect(summary_db)
            cursor = conn.cursor()
            cursor.execute("SELECT conversation_id, title FROM conversation_summaries")
            for cid, title in cursor.fetchall():
                titles[cid] = title
            conn.close()
        except Exception:
            pass

    for db_path in glob.glob(os.path.join(conv_dir, "*.db")):
        cid = os.path.splitext(os.path.basename(db_path))[0]
        mtime = datetime.fromtimestamp(os.path.getmtime(db_path)).strftime('%Y-%m-%d %H:%M:%S')
        title = titles.get(cid, "(No Title)")
        step_count = 0
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM steps")
            step_count = cursor.fetchone()[0]
            conn.close()
        except Exception:
            pass

        results.append({
            "uuid": cid,
            "title": title,
            "mtime": mtime,
            "steps": step_count,
            "path": db_path
        })

    results.sort(key=lambda x: x["mtime"], reverse=True)
    return results

def get_transcript_path(engine_dir, cid):
    return os.path.expanduser(os.path.join(engine_dir, "brain", cid, ".system_generated", "logs", "transcript.jsonl"))

def parse_ask_question_text(args_dict):
    if not isinstance(args_dict, dict):
        return ""
    q = args_dict.get("questions", "")
    if isinstance(q, str) and q.startswith("["):
        try:
            parsed = json.loads(q)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed[0].get("question", "")
        except Exception:
            pass
    elif isinstance(q, list) and len(q) > 0:
        return q[0].get("question", "")
    return args_dict.get("question", "")

def list_antigravity_checkpoints(engine_dir, cid):
    t_path = get_transcript_path(engine_dir, cid)
    checkpoints = []

    if os.path.exists(t_path):
        try:
            with open(t_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    step_idx = data.get("step_index", 0)
                    step_type = data.get("type", "")
                    
                    if step_type == "USER_INPUT":
                        content = data.get("content", {})
                        text = content.get("text", "") if isinstance(content, dict) else str(content)
                        summary = text[:80].replace("\n", " ")
                        checkpoints.append({
                            "step_index": step_idx,
                            "type": "USER_INPUT",
                            "is_ask": False,
                            "label": f"[USER PROMPT] Step {step_idx}: {summary}",
                            "summary": summary
                        })
                    elif step_type == "PLANNER_RESPONSE":
                        tool_calls = data.get("tool_calls", [])
                        for tc in tool_calls:
                            tname = tc.get("name", "") or tc.get("tool_name", "")
                            if tname in ("ask_question", "AskUserQuestion"):
                                args = tc.get("args", {}) or tc.get("arguments", {})
                                q_text = parse_ask_question_text(args)
                                summary = q_text[:80].replace("\n", " ")
                                checkpoints.append({
                                    "step_index": step_idx,
                                    "type": "ASK_QUESTION",
                                    "is_ask": True,
                                    "label": f"[ASK QUESTION] Step {step_idx}: {summary}",
                                    "summary": summary
                                })
                                break
        except Exception as e:
            print(f"Warning: Error reading transcript.jsonl: {e}", file=sys.stderr)

    return checkpoints

def rewind_antigravity_db(db_path, cutoff_step, cid=None, summary_db_path=None, preserve_ask=True, transcript_path=None):
    if not os.path.exists(db_path):
        print(f"Error: DB file not found: {db_path}", file=sys.stderr)
        return False

    effective_cutoff = cutoff_step
    if not preserve_ask and transcript_path and os.path.exists(transcript_path):
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if data.get("step_index", 0) == cutoff_step:
                        tool_calls = data.get("tool_calls", [])
                        for tc in tool_calls:
                            tname = tc.get("name", "") or tc.get("tool_name", "")
                            if tname in ("ask_question", "AskUserQuestion"):
                                effective_cutoff = max(0, cutoff_step - 1)
                                break
                        break
        except Exception:
            pass

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM steps WHERE idx > ?", (effective_cutoff,))
    delete_count = cursor.fetchone()[0]

    # Backup DB
    backup_db = db_path + ".bak"
    import shutil
    shutil.copy2(db_path, backup_db)

    cursor.execute("DELETE FROM steps WHERE idx > ?", (effective_cutoff,))
    conn.commit()
    conn.close()

    # Truncate transcript.jsonl & transcript_full.jsonl if present
    if transcript_path and os.path.exists(transcript_path):
        try:
            backup_t = transcript_path + ".bak"
            shutil.copy2(transcript_path, backup_t)
            new_lines = []
            with open(transcript_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if data.get("step_index", 0) <= effective_cutoff:
                        new_lines.append(line.strip())

            tf_path = os.path.join(os.path.dirname(transcript_path), "transcript_full.jsonl")
            if os.path.exists(tf_path):
                shutil.copy2(tf_path, tf_path + ".bak")
                tf_lines = [l.strip() for l in open(tf_path, encoding="utf-8") if l.strip()]
                valid_tf = [l for l in tf_lines if json.loads(l).get("step_index", 0) <= effective_cutoff]
                with open(tf_path + ".tmp", "w", encoding="utf-8") as f_tf:
                    f_tf.write("\n".join(valid_tf) + "\n")
                os.replace(tf_path + ".tmp", tf_path)
            tmp_t = transcript_path + ".tmp"
            with open(tmp_t, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_lines) + '\n')
            os.replace(tmp_t, transcript_path)
            print(f"Successfully truncated transcript {transcript_path} and transcript_full.jsonl to step <= {effective_cutoff}")
        except Exception as e:
            print(f"Warning: Failed to truncate transcripts: {e}", file=sys.stderr)

    if summary_db_path and os.path.exists(summary_db_path) and cid:
        try:
            s_conn = sqlite3.connect(summary_db_path)
            s_cursor = s_conn.cursor()
            s_cursor.execute(
                "UPDATE conversation_summaries SET step_count=(SELECT COUNT(*) FROM steps WHERE conversation_id=?) WHERE conversation_id=?",
                (cid, cid)
            )
            s_conn.commit()
            s_conn.close()
        except Exception as e:
            print(f"Warning: Failed to update summary DB: {e}", file=sys.stderr)

    print(f"Successfully truncated DB {db_path} to idx <= {cutoff_step} (Deleted {delete_count} steps). Backup saved to {backup_db}")
    return True

def find_claude_session_file(uuid_or_path):
    if os.path.exists(uuid_or_path):
        return os.path.abspath(uuid_or_path)
    projects_dir = os.path.expanduser("~/.claude/projects")
    if not os.path.exists(projects_dir):
        return None
    for root, dirs, files in os.walk(projects_dir):
        if ".bak" in root:
            continue
        for f in files:
            if f == f"{uuid_or_path}.jsonl" or f == uuid_or_path:
                return os.path.join(root, f)
    return None

def list_claude_sessions():
    projects_dir = os.path.expanduser("~/.claude/projects")
    if not os.path.exists(projects_dir):
        return []
    results = []
    for root, dirs, files in os.walk(projects_dir):
        if ".bak" in root:
            continue
        for f in files:
            if f.endswith(".jsonl"):
                full_path = os.path.join(root, f)
                cid = os.path.splitext(f)[0]
                mtime = datetime.fromtimestamp(os.path.getmtime(full_path)).strftime('%Y-%m-%d %H:%M:%S')
                line_count = 0
                title = "(No Title)"
                try:
                    with open(full_path, "r", encoding="utf-8") as s_file:
                        for idx, line in enumerate(s_file):
                            line_count += 1
                            if idx < 5 and title == "(No Title)" and line.strip():
                                try:
                                    data = json.loads(line)
                                    if "custom-title" in data:
                                        title = data["custom-title"]
                                    elif data.get("type") == "user":
                                        msg = data.get("message", {})
                                        content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
                                        if isinstance(content, list):
                                            content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
                                        text = content if isinstance(content, str) else str(content)
                                        if text:
                                            title = text[:60].replace("\n", " ")
                                except Exception:
                                    pass
                except Exception:
                    pass
                results.append({
                    "uuid": cid,
                    "title": title,
                    "mtime": mtime,
                    "lines": line_count,
                    "path": full_path
                })
    results.sort(key=lambda x: x["mtime"], reverse=True)
    return results

def rewind_claude_session(uuid_or_path, keep_lines):
    session_file = find_claude_session_file(uuid_or_path)
    if not session_file or not os.path.exists(session_file):
        print(f"Error: Claude Code session file not found for UUID: {uuid_or_path}", file=sys.stderr)
        return False
    if keep_lines < 0:
        print(f"Error: keep_lines must be non-negative (got {keep_lines})", file=sys.stderr)
        return False

    backup_path = session_file + ".bak"
    import shutil
    shutil.copy2(session_file, backup_path)

    retained_lines = []
    total_lines = 0
    with open(session_file, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            total_lines += 1
            if idx < keep_lines:
                retained_lines.append(line.rstrip("\r\n"))

    tmp_path = session_file + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        if retained_lines:
            f.write("\n".join(retained_lines) + "\n")
    os.replace(tmp_path, session_file)

    deleted_lines = max(0, total_lines - len(retained_lines))
    print(f"Successfully truncated Claude Code session {session_file} to {len(retained_lines)} lines (Deleted {deleted_lines} lines). Backup saved to {backup_path}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Direct Session Rewind Engine")
    parser.add_argument("--list-sessions", choices=["antigravity-ide", "antigravity-cli", "claude-code"], help="List sessions for engine")
    parser.add_argument("--list-checkpoints", choices=["antigravity-ide", "antigravity-cli"], help="List checkpoints for session UUID")
    parser.add_argument("--antigravity-ide", action="store_true", help="Target Antigravity IDE")
    parser.add_argument("--antigravity-cli", action="store_true", help="Target Antigravity CLI")
    parser.add_argument("--claude-code", action="store_true", help="Target Claude Code")
    parser.add_argument("--uuid", help="Session UUID")
    parser.add_argument("--step", type=int, help="Target step_index to truncate steps after (for Antigravity)")
    parser.add_argument("--line", type=int, help="Target line index to truncate lines after (for Claude Code)")
    parser.add_argument("--preserve-ask", action="store_true", help="Preserve the AskUserQuestion step itself when rewinding to an Ask response")

    args = parser.parse_args()

    if args.list_sessions:
        engine = args.list_sessions
        if engine == "antigravity-ide":
            sessions = list_antigravity_sessions("~/.gemini/antigravity-ide")
        elif engine == "antigravity-cli":
            sessions = list_antigravity_sessions("~/.gemini/antigravity-cli")
        elif engine == "claude-code":
            sessions = list_claude_sessions()
        else:
            sessions = []
        
        print(json.dumps(sessions, ensure_ascii=False, indent=2))
        sys.exit(0)

    if args.list_checkpoints:
        if not args.uuid:
            print("Error: --uuid is required for --list-checkpoints", file=sys.stderr)
            sys.exit(1)
        engine_dir = "~/.gemini/antigravity-ide" if args.list_checkpoints == "antigravity-ide" else "~/.gemini/antigravity-cli"
        checkpoints = list_antigravity_checkpoints(engine_dir, args.uuid)
        print(json.dumps(checkpoints, ensure_ascii=False, indent=2))
        sys.exit(0)

    if args.antigravity_ide or args.antigravity_cli:
        engine_dir = "~/.gemini/antigravity-ide" if args.antigravity_ide else "~/.gemini/antigravity-cli"
        if not args.uuid or args.step is None:
            print("Error: --uuid and --step are required for DB truncation.", file=sys.stderr)
            sys.exit(1)
        
        db_path = os.path.expanduser(os.path.join(engine_dir, "conversations", f"{args.uuid}.db"))
        summary_db = os.path.expanduser(os.path.join(engine_dir, "conversation_summaries.db"))
        transcript_path = get_transcript_path(engine_dir, args.uuid)
        success = rewind_antigravity_db(db_path, args.step, cid=args.uuid, summary_db_path=summary_db, preserve_ask=args.preserve_ask, transcript_path=transcript_path)
        sys.exit(0 if success else 1)

    if args.claude_code:
        if not args.uuid or args.line is None:
            print("Error: --uuid and --line are required for Claude Code session truncation.", file=sys.stderr)
            sys.exit(1)
        success = rewind_claude_session(args.uuid, args.line)
        sys.exit(0 if success else 1)

    parser.print_help(file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()

