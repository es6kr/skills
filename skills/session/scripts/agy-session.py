#!/usr/bin/env python3
"""agy-session.py - Manage, copy, clone, and bind Antigravity (CLI / IDE) sessions.

Usage:
    python agy-session.py copy <source_uuid> <target_workspace> [--engine cli|ide] [--title <title>] [--dry-run]
    python agy-session.py bind <source_uuid> <target_workspace> [--engine cli|ide] [--mode append|replace] [--dry-run]
    python agy-session.py show <uuid> [--engine cli|ide]
    python agy-session.py list [--engine cli|ide] [--workspace <path>]

Examples:
    python agy-session.py copy 459b20cf-6e1a-40f3-865a-708a6fa75c1c dgs --engine cli
    python agy-session.py bind 459b20cf-6e1a-40f3-865a-708a6fa75c1c dgs --mode append
"""

import argparse
import datetime
import json
import os
import re
import shutil
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

KNOWN_WORKSPACES = {
    "dgs": r"C:/Users/DAEGUNSOFT/ghq/github.com/daegunsoftDev",
    "daegunsoftdev": r"C:/Users/DAEGUNSOFT/ghq/github.com/daegunsoftDev",
    "es6kr": r"C:/Users/DAEGUNSOFT/ghq/github.com/es6kr",
}


def normalize_workspace_path(ws: str) -> str:
    """Normalize workspace argument to forward-slash path."""
    lower = ws.lower().strip()
    if lower in KNOWN_WORKSPACES:
        return KNOWN_WORKSPACES[lower]
    p = Path(ws).resolve()
    return str(p).replace("\\", "/")


def workspace_to_uri(ws_path: str) -> str:
    """Convert normalized filesystem path to Antigravity workspace URI."""
    if ws_path.startswith("file:///"):
        return ws_path
    clean = ws_path.replace("\\", "/").lstrip("/")
    if len(clean) > 1 and clean[1] == ":":
        return f"file:///{clean[0].upper()}:{clean[2:]}"
    return f"file:///{clean}"


def get_runtime_root(engine: str) -> Path:
    """Get the base directory for antigravity-cli or antigravity-ide."""
    user_home = Path.home()
    if engine == "cli":
        return user_home / ".gemini" / "antigravity-cli"
    elif engine == "ide":
        return user_home / ".gemini" / "antigravity-ide"
    raise ValueError(f"Unknown engine: {engine}")


def get_db_path(runtime_root: Path) -> Path:
    return runtime_root / "conversation_summaries.db"


def show_session(engine: str, sess_id: str):
    root = get_runtime_root(engine)
    db_file = get_db_path(root)
    if not db_file.exists():
        print(f"[ERROR] Database not found: {db_file}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute(
        "SELECT conversation_id, title, workspace_uris, project_id, last_modified_time, step_count FROM conversation_summaries WHERE conversation_id = ? OR conversation_id LIKE ?",
        (sess_id, f"{sess_id}%"),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        print(f"[ERROR] Session {sess_id} not found in {db_file}", file=sys.stderr)
        sys.exit(1)

    cid, title, ws_uris, pid, mtime, steps = row
    brain_dir = root / "brain" / cid
    conv_db = root / "conversations" / f"{cid}.db"

    print("=== Antigravity Session Details ===")
    print(f"Engine:             {engine}")
    print(f"Conversation ID:    {cid}")
    print(f"Title:              {title}")
    print(f"Workspaces:         {ws_uris}")
    print(f"Project ID:         {pid}")
    print(f"Last Modified:      {mtime}")
    print(f"Step Count:         {steps}")
    print(f"Brain Directory:    {brain_dir} (exists: {brain_dir.exists()})")
    print(f"Conversation DB:    {conv_db} (exists: {conv_db.exists()})")


def patch_raw_summary_blob(
    blob: Optional[bytes],
    old_uuid: str,
    new_uuid: str,
    old_uri: Optional[str],
    new_uri: Optional[str],
) -> Optional[bytes]:
    """Patch UUID and workspace URI inside protobuf blob if present."""
    if not blob:
        return blob

    data = blob
    if old_uuid.encode("ascii") in data:
        data = data.replace(old_uuid.encode("ascii"), new_uuid.encode("ascii"))

    if old_uri and new_uri:
        old_bytes = old_uri.encode("utf-8")
        new_bytes = new_uri.encode("utf-8")
        old_pattern = bytes([len(old_bytes)]) + old_bytes
        new_pattern = bytes([len(new_bytes)]) + new_bytes
        if old_pattern in data:
            data = data.replace(old_pattern, new_pattern)

    return data


def patch_conversation_db(db_path: Path, old_uuid: str, new_uuid: str):
    """Patch cascade_id and internal 36-byte UUID protobuf blobs in the cloned session DB."""
    if not db_path.exists():
        return
    old_bytes = old_uuid.encode("ascii")
    new_bytes = new_uuid.encode("ascii")
    try:
        cconn = sqlite3.connect(db_path)
        ccur = cconn.cursor()

        # Update trajectory_meta cascade_id
        ccur.execute(
            "UPDATE trajectory_meta SET cascade_id = ? WHERE cascade_id = ?",
            (new_uuid, old_uuid),
        )

        # Update steps metadata and step_payload
        ccur.execute(
            "SELECT idx, metadata, step_payload FROM steps WHERE metadata LIKE ? OR step_payload LIKE ?",
            (b"%" + old_bytes + b"%", b"%" + old_bytes + b"%"),
        )
        for s_idx, meta, payload in ccur.fetchall():
            new_meta = meta.replace(old_bytes, new_bytes) if meta else meta
            new_payload = payload.replace(old_bytes, new_bytes) if payload else payload
            ccur.execute(
                "UPDATE steps SET metadata = ?, step_payload = ? WHERE idx = ?",
                (new_meta, new_payload, s_idx),
            )

        # Update gen_metadata data
        ccur.execute(
            "SELECT idx, data FROM gen_metadata WHERE data LIKE ?",
            (b"%" + old_bytes + b"%",),
        )
        for g_idx, data in ccur.fetchall():
            new_data = data.replace(old_bytes, new_bytes) if data else data
            ccur.execute(
                "UPDATE gen_metadata SET data = ? WHERE idx = ?",
                (new_data, g_idx),
            )

        # Update executor_metadata and parent_references if present
        for tbl in ["executor_metadata", "parent_references"]:
            try:
                ccur.execute(
                    f"SELECT idx, data FROM {tbl} WHERE data LIKE ?",
                    (b"%" + old_bytes + b"%",),
                )
                for t_idx, data in ccur.fetchall():
                    new_data = data.replace(old_bytes, new_bytes) if data else data
                    ccur.execute(
                        f"UPDATE {tbl} SET data = ? WHERE idx = ?",
                        (new_data, t_idx),
                    )
            except Exception:
                pass

        cconn.commit()
        cconn.close()
        print(f"[*] Patched cascade_id and protobuf UUIDs in {db_path.name}")
    except Exception as e:
        print(f"[WARN] Failed patching conversation DB {db_path.name}: {e}")


def copy_session(
    engine: str,
    source_uuid: str,
    target_ws: str,
    custom_title: Optional[str] = None,
    dry_run: bool = False,
) -> str:
    root = get_runtime_root(engine)
    db_file = get_db_path(root)
    if not db_file.exists():
        print(f"[ERROR] Database not found: {db_file}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM conversation_summaries WHERE conversation_id = ? OR conversation_id LIKE ?",
        (source_uuid, f"{source_uuid}%"),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        print(f"[ERROR] Source session {source_uuid} not found in database", file=sys.stderr)
        sys.exit(1)

    col_names = [d[0] for d in cur.description]
    row_dict = dict(zip(col_names, row))
    actual_source_uuid = row_dict["conversation_id"]

    new_uuid = str(uuid.uuid4())
    norm_ws = normalize_workspace_path(target_ws)
    target_uri = workspace_to_uri(norm_ws)

    orig_ws_uris = row_dict.get("workspace_uris", "[]")
    first_orig_uri = None
    try:
        parsed_orig = json.loads(orig_ws_uris)
        if isinstance(parsed_orig, list) and len(parsed_orig) > 0:
            first_orig_uri = parsed_orig[0]
    except Exception:
        pass

    target_title = custom_title if custom_title else row_dict.get("title", "")
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    print(f"[*] Source Session:     {actual_source_uuid}")
    print(f"[*] Cloned Session ID:  {new_uuid}")
    print(f"[*] Target Workspace:   {norm_ws} ({target_uri})")
    print(f"[*] Session Title:      {target_title}")

    if dry_run:
        print("[DRY-RUN] No changes committed to disk or database.")
        conn.close()
        return new_uuid

    # 1. Copy Brain Directory
    src_brain = root / "brain" / actual_source_uuid
    dst_brain = root / "brain" / new_uuid
    if src_brain.exists():
        print(f"[*] Copying brain directory: {src_brain} -> {dst_brain}")
        shutil.copytree(src_brain, dst_brain)

        # Update transcript references in destination
        logs_dir = dst_brain / ".system_generated" / "logs"
        if logs_dir.exists():
            for fname in ["transcript.jsonl", "transcript_full.jsonl"]:
                tfile = logs_dir / fname
                if tfile.exists():
                    try:
                        content = tfile.read_text(encoding="utf-8")
                        content = content.replace(actual_source_uuid, new_uuid)
                        tfile.write_text(content, encoding="utf-8")
                    except Exception as e:
                        print(f"[WARN] Failed rewriting {fname}: {e}")
    else:
        print(f"[WARN] Source brain directory not found: {src_brain}")

    # 2. Copy Conversation SQLite DB
    src_conv_db = root / "conversations" / f"{actual_source_uuid}.db"
    dst_conv_db = root / "conversations" / f"{new_uuid}.db"
    if src_conv_db.exists():
        print(f"[*] Copying conversation DB: {src_conv_db} -> {dst_conv_db}")
        shutil.copy2(src_conv_db, dst_conv_db)
        patch_conversation_db(dst_conv_db, actual_source_uuid, new_uuid)

    # 3. Insert Row into conversation_summaries.db
    new_row = dict(row_dict)
    new_row["conversation_id"] = new_uuid
    new_row["workspace_uris"] = json.dumps([target_uri])
    if target_title:
        new_row["title"] = target_title
    new_row["last_modified_time"] = now_str
    new_row["last_user_input_time"] = now_str

    if "raw_summary" in new_row and new_row["raw_summary"]:
        new_row["raw_summary"] = patch_raw_summary_blob(
            new_row["raw_summary"],
            actual_source_uuid,
            new_uuid,
            first_orig_uri,
            target_uri,
        )

    cols = list(new_row.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_str = ", ".join(cols)
    vals = [new_row[c] for c in cols]

    cur.execute(
        f"INSERT INTO conversation_summaries ({col_str}) VALUES ({placeholders})",
        vals,
    )
    conn.commit()
    conn.close()

    print(f"[SUCCESS] Successfully cloned session to {new_uuid} in workspace {target_uri}")
    return new_uuid


def bind_session(
    engine: str,
    source_uuid: str,
    target_ws: str,
    mode: str = "append",
    dry_run: bool = False,
):
    root = get_runtime_root(engine)
    db_file = get_db_path(root)
    if not db_file.exists():
        print(f"[ERROR] Database not found: {db_file}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute(
        "SELECT conversation_id, workspace_uris, raw_summary FROM conversation_summaries WHERE conversation_id = ? OR conversation_id LIKE ?",
        (source_uuid, f"{source_uuid}%"),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        print(f"[ERROR] Session {source_uuid} not found in database", file=sys.stderr)
        sys.exit(1)

    actual_uuid, orig_ws_uris, raw_blob = row
    norm_ws = normalize_workspace_path(target_ws)
    target_uri = workspace_to_uri(norm_ws)

    ws_list: List[str] = []
    try:
        ws_list = json.loads(orig_ws_uris)
        if not isinstance(ws_list, list):
            ws_list = [orig_ws_uris] if orig_ws_uris else []
    except Exception:
        ws_list = [orig_ws_uris] if orig_ws_uris else []

    if mode == "append":
        if target_uri not in ws_list:
            ws_list.append(target_uri)
    elif mode == "replace":
        ws_list = [target_uri]

    new_ws_json = json.dumps(ws_list)
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    print(f"[*] Session ID:         {actual_uuid}")
    print(f"[*] Current Workspaces: {orig_ws_uris}")
    print(f"[*] New Workspaces:     {new_ws_json} (mode: {mode})")

    if dry_run:
        print("[DRY-RUN] No changes committed.")
        conn.close()
        return

    cur.execute(
        "UPDATE conversation_summaries SET workspace_uris = ?, last_modified_time = ? WHERE conversation_id = ?",
        (new_ws_json, now_str, actual_uuid),
    )
    conn.commit()
    conn.close()
    print(f"[SUCCESS] Updated workspace bindings for {actual_uuid}")


def main():
    parser = argparse.ArgumentParser(description="Antigravity session management utility")
    parser.add_argument("--engine", choices=["cli", "ide"], default="cli", help="Antigravity engine (cli or ide)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # show
    p_show = subparsers.add_parser("show", help="Show session details")
    p_show.add_argument("uuid", help="Session UUID or prefix")

    # copy
    p_copy = subparsers.add_parser("copy", help="Clone session to a new UUID with target workspace")
    p_copy.add_argument("source_uuid", help="Source session UUID or prefix")
    p_copy.add_argument("target_workspace", help="Target workspace path or alias (e.g. dgs, es6kr)")
    p_copy.add_argument("--title", default=None, help="Optional title for cloned session")
    p_copy.add_argument("--dry-run", action="store_true", help="Preview copy operation")

    # bind
    p_bind = subparsers.add_parser("bind", help="Bind existing session to another workspace")
    p_bind.add_argument("source_uuid", help="Session UUID or prefix")
    p_bind.add_argument("target_workspace", help="Target workspace path or alias")
    p_bind.add_argument("--mode", choices=["append", "replace"], default="append", help="Append to or replace workspaces")
    p_bind.add_argument("--dry-run", action="store_true", help="Preview bind operation")

    args = parser.parse_args()

    if args.command == "show":
        show_session(args.engine, args.uuid)
    elif args.command == "copy":
        copy_session(args.engine, args.source_uuid, args.target_workspace, args.title, args.dry_run)
    elif args.command == "bind":
        bind_session(args.engine, args.source_uuid, args.target_workspace, args.mode, args.dry_run)


if __name__ == "__main__":
    main()
