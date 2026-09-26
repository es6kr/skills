#!/usr/bin/env python3
"""
OpenClaw session manager - list, search, and summarize OpenClaw sessions.
Default OpenClaw root: ~/.openclaw
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any


def get_default_openclaw_root() -> Path:
    return Path.home() / ".openclaw"


def extract_message_text(content: Any) -> str:
    """Extract plain text from message content (list of blocks or string)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif item.get("type") == "toolCall":
                    name = item.get("name", "")
                    parts.append(f"[Tool: {name}]")
            elif isinstance(item, str):
                parts.append(item)
        return " ".join(parts).strip()
    return ""


def format_timestamp(ts: Any) -> str:
    """Format ISO timestamp or epoch millis into human-readable string."""
    if not ts:
        return ""
    if isinstance(ts, (int, float)):
        # Epoch millis or seconds
        if ts > 1e11:
            ts = ts / 1000.0
        try:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(ts)
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return ts
    return str(ts)


def is_primary_session_file(filename: str) -> bool:
    """Check if file is a primary session JSONL (not trajectory, reset, deleted, or bak)."""
    if not filename.endswith(".jsonl"):
        return False
    if filename.endswith(".trajectory.jsonl"):
        return False
    # Avoid reset/deleted/bak/migrated files
    for marker in (".reset.", ".deleted.", ".bak", ".migrated", ".pre-doctor"):
        if marker in filename:
            return False
    return True


def list_sessions(
    openclaw_root: Optional[Path] = None,
    agent: Optional[str] = None,
    limit: int = 0
) -> List[Dict[str, Any]]:
    """List sessions stored in OpenClaw agents directory."""
    root = Path(openclaw_root) if openclaw_root else get_default_openclaw_root()
    agents_dir = root / "agents"
    if not agents_dir.exists():
        return []

    sessions = []

    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue
        agent_name = agent_dir.name
        if agent and agent_name != agent:
            continue

        sessions_dir = agent_dir / "sessions"
        if not sessions_dir.exists() or not sessions_dir.is_dir():
            continue

        # Load active session metadata from sessions.json
        meta_file = sessions_dir / "sessions.json"
        active_session_map = {}
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8", errors="replace") as f:
                    meta_data = json.load(f)
                    if isinstance(meta_data, dict):
                        for key, val in meta_data.items():
                            if isinstance(val, dict):
                                sid = val.get("sessionId")
                                if sid:
                                    route = val.get("route", {})
                                    channel = route.get("channel") if isinstance(route, dict) else None
                                    active_session_map[sid] = {
                                        "key": key,
                                        "updatedAt": val.get("updatedAt"),
                                        "channel": channel,
                                        "route": route
                                    }
            except Exception:
                pass

        # Scan *.jsonl files
        for fpath in sessions_dir.glob("*.jsonl"):
            fname = fpath.name
            if not is_primary_session_file(fname):
                continue

            session_id = fname[:-6]  # remove .jsonl
            stat = fpath.stat()
            mtime_epoch = stat.st_mtime
            size_bytes = stat.st_size

            is_active = session_id in active_session_map
            active_info = active_session_map.get(session_id, {})
            channel = active_info.get("channel")

            # Extract first user message or prompt snippet as hint
            first_prompt = ""
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as sf:
                    for line in sf:
                        try:
                            obj = json.loads(line)
                            if obj.get("type") == "message" and obj.get("message", {}).get("role") == "user":
                                text = extract_message_text(obj.get("message", {}).get("content", ""))
                                if text:
                                    first_prompt = text[:120].replace("\n", " ")
                                    break
                        except Exception:
                            continue
            except Exception:
                pass

            sessions.append({
                "session_id": session_id,
                "agent_id": agent_name,
                "mtime": format_timestamp(mtime_epoch),
                "mtime_epoch": mtime_epoch,
                "size_bytes": size_bytes,
                "is_active": is_active,
                "channel": channel,
                "first_prompt": first_prompt,
                "path": str(fpath)
            })

    # Sort by mtime descending
    sessions.sort(key=lambda s: s["mtime_epoch"], reverse=True)

    if limit > 0:
        sessions = sessions[:limit]

    return sessions


def search_sessions(
    openclaw_root: Optional[Path] = None,
    keyword: str = "",
    agent: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Search for keyword in OpenClaw session transcripts."""
    root = Path(openclaw_root) if openclaw_root else get_default_openclaw_root()
    agents_dir = root / "agents"
    if not agents_dir.exists():
        return []

    results = []
    kw_lower = keyword.lower()

    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue
        agent_name = agent_dir.name
        if agent and agent_name != agent:
            continue

        sessions_dir = agent_dir / "sessions"
        if not sessions_dir.exists():
            continue

        for fpath in sessions_dir.glob("*.jsonl"):
            if not is_primary_session_file(fpath.name):
                continue
            session_id = fpath.name[:-6]

            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as sf:
                    for line_idx, line in enumerate(sf, 1):
                        if kw_lower not in line.lower():
                            continue
                        try:
                            obj = json.loads(line)
                            msg_type = obj.get("type")
                            if msg_type == "message":
                                msg = obj.get("message", {})
                                role = msg.get("role", "unknown")
                                content_text = extract_message_text(msg.get("content", ""))
                                if kw_lower in content_text.lower():
                                    ts = obj.get("timestamp") or msg.get("timestamp")
                                    results.append({
                                        "session_id": session_id,
                                        "agent_id": agent_name,
                                        "line_num": line_idx,
                                        "role": role,
                                        "timestamp": format_timestamp(ts),
                                        "content": content_text[:300].replace("\n", " "),
                                        "path": str(fpath)
                                    })
                        except Exception:
                            continue
            except Exception:
                continue

    return results


def summarize_session(
    session_id: str,
    openclaw_root: Optional[Path] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """Extract and summarize dialogue history of a specific OpenClaw session."""
    root = Path(openclaw_root) if openclaw_root else get_default_openclaw_root()
    agents_dir = root / "agents"
    target_file = None
    target_agent = None

    # Search for session file across all agents
    if agents_dir.exists():
        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue
            candidate = agent_dir / "sessions" / f"{session_id}.jsonl"
            if candidate.exists():
                target_file = candidate
                target_agent = agent_dir.name
                break

    if not target_file or not target_file.exists():
        raise FileNotFoundError(f"OpenClaw session file not found for ID: {session_id}")

    messages = []
    session_meta = {}

    with open(target_file, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if len(messages) >= limit:
                break
            try:
                obj = json.loads(line)
                obj_type = obj.get("type")
                if obj_type == "session":
                    session_meta = {
                        "id": obj.get("id"),
                        "version": obj.get("version"),
                        "timestamp": format_timestamp(obj.get("timestamp")),
                        "cwd": obj.get("cwd")
                    }
                elif obj_type == "message":
                    msg = obj.get("message", {})
                    role = msg.get("role")
                    if role in ("user", "assistant"):
                        content_raw = msg.get("content", "")
                        text = extract_message_text(content_raw)
                        ts = obj.get("timestamp") or msg.get("timestamp")
                        messages.append({
                            "role": role,
                            "timestamp": format_timestamp(ts),
                            "text": text
                        })
            except Exception:
                continue

    return {
        "session_id": session_id,
        "agent_id": target_agent,
        "meta": session_meta,
        "messages": messages,
        "total_messages_returned": len(messages),
        "path": str(target_file)
    }


def main():
    parser = argparse.ArgumentParser(description="OpenClaw session manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List OpenClaw sessions")
    p_list.add_argument("--root", type=str, default=None, help="OpenClaw root directory")
    p_list.add_argument("--agent", type=str, default=None, help="Filter by agent ID")
    p_list.add_argument("--limit", type=int, default=0, help="Limit number of sessions")
    p_list.add_argument("--json", action="store_true", help="Output as JSON")

    # search
    p_search = subparsers.add_parser("search", help="Search in OpenClaw sessions")
    p_search.add_argument("keyword", type=str, help="Search keyword")
    p_search.add_argument("--root", type=str, default=None, help="OpenClaw root directory")
    p_search.add_argument("--agent", type=str, default=None, help="Filter by agent ID")
    p_search.add_argument("--json", action="store_true", help="Output as JSON")

    # summarize
    p_sum = subparsers.add_parser("summarize", help="Summarize an OpenClaw session")
    p_sum.add_argument("session_id", type=str, help="Session UUID")
    p_sum.add_argument("--root", type=str, default=None, help="OpenClaw root directory")
    p_sum.add_argument("--limit", type=int, default=50, help="Max messages to extract")
    p_sum.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    openclaw_root = Path(args.root) if args.root else None

    if args.command == "list":
        sessions = list_sessions(openclaw_root=openclaw_root, agent=args.agent, limit=args.limit)
        if args.json:
            print(json.dumps(sessions, indent=2, ensure_ascii=False))
        else:
            print("| Session UUID | Agent | Channel | Active | mtime | Size (bytes) | First Prompt |")
            print("|--------------|-------|---------|--------|-------|--------------|--------------|")
            for s in sessions:
                active_str = "✓ active" if s["is_active"] else ""
                channel_str = s["channel"] or "-"
                prompt_str = (s["first_prompt"][:50] + "...") if len(s["first_prompt"]) > 50 else (s["first_prompt"] or "-")
                print(f"| `{s['session_id']}` | {s['agent_id']} | {channel_str} | {active_str} | {s['mtime']} | {s['size_bytes']} | {prompt_str} |")
            print(f"\nTotal: {len(sessions)} sessions")

    elif args.command == "search":
        results = search_sessions(openclaw_root=openclaw_root, keyword=args.keyword, agent=args.agent)
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            print(f"Search results for '{args.keyword}': {len(results)} matches\n")
            for r in results:
                print(f"- [`{r['session_id']}`] ({r['agent_id']} | {r['role']} | {r['timestamp']}):")
                print(f"  {r['content']}")

    elif args.command == "summarize":
        try:
            summary = summarize_session(session_id=args.session_id, openclaw_root=openclaw_root, limit=args.limit)
            if args.json:
                print(json.dumps(summary, indent=2, ensure_ascii=False))
            else:
                print(f"## OpenClaw Session: {summary['session_id']}")
                print(f"- **Agent**: {summary['agent_id']}")
                print(f"- **Path**: `{summary['path']}`\n")
                print("### Conversation History")
                for m in summary["messages"]:
                    ts_prefix = f" [{m['timestamp']}]" if m['timestamp'] else ""
                    print(f"**{m['role']}{ts_prefix}**:")
                    print(f"{m['text']}\n")
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
