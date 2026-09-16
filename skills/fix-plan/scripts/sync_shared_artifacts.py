#!/usr/bin/env python3
"""
sync_shared_artifacts.py - Architecture & Plan Artifacts CollabMD Sync Automation

plan/architecture 산출물(plan-*.md, research-*.md 등)의 프론트매터에
collabmd_url과 output_dir을 자동으로 보강(upsert)하고,
.agents/docs/shared/ 디렉토리로 동기화한 후 정합성을 검증합니다.

Usage:
  python3 sync_shared_artifacts.py <file1.md> [<file2.md> ...] [--dest-dir <path>] [--dry-run]
"""

import os
import sys
import re
import argparse
import filecmp
import shutil
from typing import List, Dict, Tuple, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_COLLABMD_BASE = "https://collabmd.dgs.ai.kr/#file=daegunsoftdev-agents-docs/"
DEFAULT_SHARED_DIR = ".agents/docs/shared"


def parse_frontmatter(content: str) -> Tuple[Optional[str], str]:
    """
    내용에서 YAML 프론트매터 블록(--- ... ---)과 나머지 본문을 분리합니다.
    프론트매터가 없으면 (None, content)를 반환합니다.
    """
    if content.startswith("---\n"):
        end_idx = content.find("\n---\n", 4)
        if end_idx != -1:
            fm_text = content[4:end_idx]
            body = content[end_idx + 5:]
            return fm_text, body
        elif content.endswith("\n---"):
            fm_text = content[4:-4]
            return fm_text, ""
    return None, content


def upsert_frontmatter_fields(
    fm_text: Optional[str],
    collabmd_url: str,
    output_dir: str
) -> str:
    """
    프론트매터 텍스트에 collabmd_url과 output_dir을 upsert합니다.
    """
    if fm_text is None:
        return f"---\ncollabmd_url: {collabmd_url}\noutput_dir: {output_dir}\n---\n"

    lines = fm_text.splitlines()
    has_collabmd = False
    has_output_dir = False
    new_lines = []

    for line in lines:
        if re.match(r"^collabmd_url\s*:", line):
            new_lines.append(f"collabmd_url: {collabmd_url}")
            has_collabmd = True
        elif re.match(r"^output_dir\s*:", line):
            new_lines.append(f"output_dir: {output_dir}")
            has_output_dir = True
        else:
            new_lines.append(line)

    if not has_collabmd:
        new_lines.append(f"collabmd_url: {collabmd_url}")
    if not has_output_dir:
        new_lines.append(f"output_dir: {output_dir}")

    return "---\n" + "\n".join(new_lines) + "\n---\n"


def process_artifact(
    src_path: str,
    dest_dir: str,
    base_url: str = DEFAULT_COLLABMD_BASE,
    dry_run: bool = False
) -> Dict[str, str]:
    """
    단일 산출물 파일을 처리합니다:
    1. 프론트매터에 collabmd_url 및 output_dir upsert
    2. dest_dir로 복사
    3. filecmp 검증
    """
    filename = os.path.basename(src_path)
    collabmd_url = f"{base_url.rstrip('/')}/{filename}"
    result = {
        "file": filename,
        "src": src_path,
        "collabmd_url": collabmd_url,
        "fm_updated": "No",
        "copied": "No",
        "verified": "No",
        "status": "OK"
    }

    if not os.path.isfile(src_path):
        result["status"] = "ERROR (File not found)"
        return result

    try:
        with open(src_path, "r", encoding="utf-8") as f:
            original_content = f.read()

        fm_text, body = parse_frontmatter(original_content)
        new_fm = upsert_frontmatter_fields(fm_text, collabmd_url, dest_dir)
        new_content = new_fm + body

        if new_content != original_content:
            result["fm_updated"] = "Yes"
            if not dry_run:
                with open(src_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(new_content)
        else:
            result["fm_updated"] = "Already Up-to-date"

        dest_path = os.path.join(dest_dir, filename)

        if not dry_run:
            os.makedirs(dest_dir, exist_ok=True)
            # 동일 경로인 경우 복사 스킵
            if os.path.abspath(src_path) != os.path.abspath(dest_path):
                shutil.copy2(src_path, dest_path)
                result["copied"] = "Yes"
            else:
                result["copied"] = "Same Path (In-place)"

            # 정합성 검증
            if os.path.exists(dest_path) and filecmp.cmp(src_path, dest_path, shallow=False):
                result["verified"] = "PASS"
            else:
                result["verified"] = "FAIL (Mismatch)"
                result["status"] = "ERROR (Verification Failed)"
        else:
            result["copied"] = "DRY-RUN"
            result["verified"] = "DRY-RUN"

    except Exception as e:
        result["status"] = f"ERROR ({str(e)})"

    return result


def find_workspace_root(start_path: str = ".") -> str:
    """
    현재 위치에서 .agents 디렉토리를 포함하는 워크스페이스 루트를 찾습니다.
    """
    curr = os.path.abspath(start_path)
    while True:
        if os.path.isdir(os.path.join(curr, ".agents")):
            return curr
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    return os.path.abspath(start_path)


def main():
    parser = argparse.ArgumentParser(
        description="Sync architecture/plan artifacts to .agents/docs/shared/ with CollabMD URL."
    )
    parser.add_argument("files", nargs="+", help="Target markdown files to sync")
    parser.add_argument(
        "--dest-dir",
        default=None,
        help=f"Destination directory (default: <workspace_root>/{DEFAULT_SHARED_DIR})"
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_COLLABMD_BASE,
        help=f"CollabMD base URL prefix (default: {DEFAULT_COLLABMD_BASE})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform simulation without writing or copying"
    )

    args = parser.parse_args()

    if args.dest_dir is None:
        ws_root = find_workspace_root()
        dest_dir = os.path.join(ws_root, DEFAULT_SHARED_DIR)
    else:
        dest_dir = os.path.abspath(args.dest_dir)

    print(f"=== Artifacts CollabMD Sync ===")
    print(f"Destination: {dest_dir}")
    print(f"Base URL:    {args.base_url}")
    print(f"Dry-run:     {args.dry_run}")
    print(f"File Count:  {len(args.files)}\n")

    results = []
    for f in args.files:
        res = process_artifact(f, dest_dir, args.base_url, args.dry_run)
        results.append(res)

    # 마크다운 표 형식 출력
    print("| File | FM Updated | Copied | Verified | Status | CollabMD URL |")
    print("|---|---|---|---|---|---|")
    has_error = False
    for r in results:
        if "ERROR" in r["status"]:
            has_error = True
        print(f"| `{r['file']}` | {r['fm_updated']} | {r['copied']} | {r['verified']} | {r['status']} | [{r['file']}]({r['collabmd_url']}) |")

    sys.exit(1 if has_error else 0)


if __name__ == "__main__":
    main()
