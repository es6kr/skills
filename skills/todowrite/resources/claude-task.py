#!/usr/bin/env python3
"""
Claude & Agent Task JSON CLI Manager (`claude-task`)
Standalone utility for inspecting, creating, and updating task JSON files
compatible with Claude Code's Task tool directory format (`~/.claude/tasks/<session-id>/`)
and standalone agent environments (`~/.agents/tasks/<session-id>/`).

Usage:
  claude-task [--session SESSION] [--dir DIR] [--env {claude,agent,auto}] list [--json]
  claude-task [--session SESSION] [--dir DIR] show <id> [--json]
  claude-task [--session SESSION] [--dir DIR] add -s SUBJECT [-d DESC] [-a FORM] [--status STATUS] [--blocks ID...] [--blocked-by ID...]
  claude-task [--session SESSION] [--dir DIR] update <id> [--status STATUS] [-s SUBJECT] [-d DESC] [-a FORM] [--add-block ID...] [--add-blocked-by ID...]
  claude-task [--session SESSION] [--dir DIR] delete <id>
  claude-task [--session SESSION] [--dir DIR] dir
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, Dict, Any, List

# Windows terminals (Git Bash/cmd) often default stdout/stderr to cp949/euc-kr,
# mangling Korean subject/description text. Force UTF-8 regardless of locale.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

CLAUDE_TASKS_BASE = Path.home() / ".claude" / "tasks"
AGENTS_TASKS_BASE = Path.home() / ".agents" / "tasks"

def is_claude_env() -> bool:
    """Detect if running in Claude Code session environment or if Claude session dir exists."""
    if os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CLAUDE_TASK_DIR"):
        return True
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT") or os.environ.get("CLAUDE_CODE") == "1":
        return True
    if os.environ.get("ANTIGRAVITY_AGENT") or os.environ.get("GEMINI_AGENT"):
        return False
    return False

def resolve_task_dir(
    custom_dir: Optional[str] = None,
    session_id: Optional[str] = None,
    env_type: Optional[str] = None
) -> Path:
    # 1. Explicit directory path
    if custom_dir:
        p = Path(custom_dir).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    env_dir = os.environ.get("CLAUDE_TASK_DIR") or os.environ.get("AGENT_TASK_DIR")
    if env_dir:
        p = Path(env_dir).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    # 2. Determine base search order
    target_env = env_type if env_type and env_type != "auto" else ("claude" if is_claude_env() else "agent")
    
    if target_env == "claude":
        search_bases = [CLAUDE_TASKS_BASE]
    else:
        search_bases = [AGENTS_TASKS_BASE]

    # 3. Explicit session ID
    s_id = session_id or os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("AGENT_SESSION_ID")
    if s_id:
        p = search_bases[0] / s_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    # 4. Find most recent active directory in target search base
    for target_base in search_bases:
        if target_base.exists():
            dirs = [d for d in target_base.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if dirs:
                dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
                return dirs[0]

    # 5. Default fallback
    fallback = search_bases[0] / "default"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback

def get_next_task_id(task_dir: Path) -> str:
    hw_file = task_dir / ".highwatermark"
    current_max = 0

    if hw_file.exists():
        try:
            content = hw_file.read_text().strip()
            if content.isdigit():
                current_max = int(content)
        except Exception:
            pass

    for f in task_dir.glob("*.json"):
        if f.stem.isdigit():
            val = int(f.stem)
            if val > current_max:
                current_max = val

    next_id = current_max + 1
    hw_file.write_text(str(next_id) + "\n")
    return str(next_id)

def load_task(task_dir: Path, task_id: str) -> Dict[str, Any]:
    task_file = task_dir / f"{task_id}.json"
    if not task_file.exists():
        print(f"Error: Task #{task_id} not found in {task_dir}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(task_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading Task #{task_id}: {e}", file=sys.stderr)
        sys.exit(1)

def save_task(task_dir: Path, task_data: Dict[str, Any]) -> None:
    task_id = task_data["id"]
    task_file = task_dir / f"{task_id}.json"
    with open(task_file, "w", encoding="utf-8") as f:
        json.dump(task_data, f, ensure_ascii=False, indent=2)

def cmd_list(args):
    task_dir = resolve_task_dir(args.dir, args.session, args.env)
    tasks = []

    for f in task_dir.glob("*.json"):
        if f.name.startswith("."):
            continue
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                tasks.append(data)
        except Exception:
            pass

    def sort_key(t):
        tid = t.get("id", "0")
        return int(tid) if tid.isdigit() else tid

    tasks.sort(key=sort_key)

    if args.json:
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
        return

    env_label = "Claude Tasks" if ".claude" in str(task_dir) else "Agent Tasks"
    print(f"[{env_label}] Task Directory: {task_dir} ({len(tasks)} tasks)\n")
    if not tasks:
        print("  (No tasks registered)")
        return

    for t in tasks:
        tid = t.get("id", "?")
        subj = t.get("subject", "")
        status = t.get("status", "pending")
        active = t.get("activeForm", "")
        blocked_by = t.get("blockedBy", [])

        status_icon = "[ ]"
        if status == "in_progress":
            status_icon = "[/]"
        elif status == "completed":
            status_icon = "[x]"

        block_str = f" (blocked by: {', '.join(blocked_by)})" if blocked_by else ""
        active_str = f" -> {active}" if active else ""
        print(f"  {status_icon} #{tid}: {subj}{active_str}{block_str}")

def cmd_show(args):
    task_dir = resolve_task_dir(args.dir, args.session, args.env)
    data = load_task(task_dir, args.id)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"Task #{data.get('id')}")
        print(f"Subject: {data.get('subject')}")
        print(f"Status: {data.get('status')}")
        print(f"ActiveForm: {data.get('activeForm')}")
        print(f"Description: {data.get('description')}")
        print(f"Blocks: {data.get('blocks', [])}")
        print(f"BlockedBy: {data.get('blockedBy', [])}")

def cmd_add(args):
    task_dir = resolve_task_dir(args.dir, args.session, args.env)
    task_id = get_next_task_id(task_dir)

    data = {
        "id": task_id,
        "subject": args.subject,
        "description": args.description or args.subject,
        "activeForm": args.active_form or f"{args.subject} 진행 중",
        "status": args.status,
        "blocks": args.blocks or [],
        "blockedBy": args.blocked_by or []
    }

    save_task(task_dir, data)
    env_label = "Claude Tasks" if ".claude" in str(task_dir) else "Agent Tasks"
    print(f"Created {env_label} #{task_id}: {args.subject} in {task_dir}")

def cmd_update(args):
    task_dir = resolve_task_dir(args.dir, args.session, args.env)
    data = load_task(task_dir, args.id)

    if args.status:
        data["status"] = args.status
    if args.subject:
        data["subject"] = args.subject
    if args.description is not None:
        data["description"] = args.description
    if args.active_form is not None:
        data["activeForm"] = args.active_form

    if args.add_block:
        blocks = set(data.get("blocks", []))
        blocks.update(args.add_block)
        data["blocks"] = sorted(list(blocks))

    if args.add_blocked_by:
        blocked_by = set(data.get("blockedBy", []))
        blocked_by.update(args.add_blocked_by)
        data["blockedBy"] = sorted(list(blocked_by))

    save_task(task_dir, data)
    print(f"Updated Task #{args.id} (Status: {data['status']})")

def cmd_delete(args):
    task_dir = resolve_task_dir(args.dir, args.session, args.env)
    task_file = task_dir / f"{args.id}.json"
    if task_file.exists():
        task_file.unlink()
        print(f"Deleted Task #{args.id} from {task_dir}")
    else:
        print(f"Task #{args.id} not found in {task_dir}", file=sys.stderr)
        sys.exit(1)

def cmd_dir(args):
    task_dir = resolve_task_dir(args.dir, args.session, args.env)
    print(task_dir)

def parse_args():
    # Global options parser
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument("--dir", help="Explicit task directory path")
    global_parser.add_argument("--session", help="Explicit session ID")
    global_parser.add_argument("--env", choices=["claude", "agent", "auto"], help="Environment target (claude ~/.claude/tasks or agent ~/.agents/tasks)")

    # Pre-parse global options from sys.argv
    global_args, remaining_argv = global_parser.parse_known_args()

    # Main parser
    parser = argparse.ArgumentParser(
        description="Claude & Agent Task JSON CLI Manager (`claude-task`)",
        parents=[global_parser]
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand")

    # list
    p_list = subparsers.add_parser("list", aliases=["ls"], parents=[global_parser], help="List tasks")
    p_list.add_argument("--json", action="store_true", help="Output raw JSON array")
    p_list.set_defaults(func=cmd_list)

    # show
    p_show = subparsers.add_parser("show", aliases=["get"], parents=[global_parser], help="Show task details")
    p_show.add_argument("id", help="Task ID")
    p_show.add_argument("--json", action="store_true", help="Output raw JSON")
    p_show.set_defaults(func=cmd_show)

    # add
    p_add = subparsers.add_parser("add", aliases=["create"], parents=[global_parser], help="Add a new task")
    p_add.add_argument("--subject", "-s", required=True, help="Task subject")
    p_add.add_argument("--description", "-d", help="Task description")
    p_add.add_argument("--active-form", "-a", help="Active form text")
    p_add.add_argument("--status", choices=["pending", "in_progress", "completed"], default="pending")
    p_add.add_argument("--blocks", nargs="*", help="Task IDs blocked by this task")
    p_add.add_argument("--blocked-by", nargs="*", help="Task IDs that block this task")
    p_add.set_defaults(func=cmd_add)

    # update
    p_up = subparsers.add_parser("update", aliases=["edit"], parents=[global_parser], help="Update existing task")
    p_up.add_argument("id", help="Task ID")
    p_up.add_argument("--status", choices=["pending", "in_progress", "completed"])
    p_up.add_argument("--subject", "-s")
    p_up.add_argument("--description", "-d")
    p_up.add_argument("--active-form", "-a")
    p_up.add_argument("--add-block", nargs="*")
    p_up.add_argument("--add-blocked-by", nargs="*")
    p_up.set_defaults(func=cmd_update)

    # delete
    p_del = subparsers.add_parser("delete", aliases=["rm"], parents=[global_parser], help="Delete task")
    p_del.add_argument("id", help="Task ID")
    p_del.set_defaults(func=cmd_delete)

    # dir
    p_dir = subparsers.add_parser("dir", parents=[global_parser], help="Show resolved task directory")
    p_dir.set_defaults(func=cmd_dir)

    parsed = parser.parse_args()
    
    # Merge global_args into parsed if subparser didn't override
    if not parsed.session and global_args.session:
        parsed.session = global_args.session
    if not parsed.dir and global_args.dir:
        parsed.dir = global_args.dir
    if not parsed.env and global_args.env:
        parsed.env = global_args.env

    return parsed

def main():
    args = parse_args()
    if not args.subcommand:
        print("Error: subcommand required", file=sys.stderr)
        sys.exit(1)
    args.func(args)

if __name__ == "__main__":
    main()
