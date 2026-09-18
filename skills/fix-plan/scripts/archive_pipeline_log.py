#!/usr/bin/env python3
"""archive_pipeline_log.py — Archive old Pipeline Execution Log entries from fix_plan.md.

Parses the '## Pipeline Execution Log' section, identifies entries to keep (most recent per role
+ dynamic cutoff), and archives older entries into docs/generated/fix_plan-pipeline-log-archive-*.md.

Usage:
    python3 archive_pipeline_log.py [--file <path>] [--keep-count N] [--keep-since YYYY-MM-DD] [--dry-run]

Options:
    --file              Path to fix_plan.md or checklist.md. Auto-detects if not given.
    --keep-count N      Keep the N most recent entries (overrides cutoff calculation).
    --keep-since DATE   Keep all entries on or after DATE (YYYY-MM-DD).
    --dry-run           Report what would be kept/archived without writing files.
"""

import sys
import os
import re
import argparse
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Archive old Pipeline Execution Log entries from fix_plan.md."
    )
    parser.add_argument(
        "--file",
        help="Path to fix_plan.md or checklist.md file.",
        default=None
    )
    parser.add_argument(
        "--keep-count",
        type=int,
        help="Keep the N most recent entries (overrides cutoff logic).",
        default=None
    )
    parser.add_argument(
        "--keep-since",
        help="Keep all entries on or after this date (YYYY-MM-DD).",
        default=None
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be archived without writing files."
    )
    return parser.parse_args()


def extract_pipeline_log_section(lines):
    """Extract the entire '## Pipeline Execution Log' section from lines.

    Returns: (start_line_idx, end_line_idx, log_lines)
        start_line_idx: 0-based index of '## Pipeline Execution Log' header
        end_line_idx: 0-based index of first line after the section (next ## header or EOF)
        log_lines: List of entry lines (bullets starting with '- **')
    """
    start_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "## Pipeline Execution Log":
            start_idx = i
            break

    if start_idx is None:
        return None, None, []

    # Find the end: next section header (^##) or end of file
    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        if lines[i].startswith("##"):
            end_idx = i
            break

    # Extract entry lines: bullets starting with "- **"
    log_lines = []
    for i in range(start_idx + 1, end_idx):
        line = lines[i]
        if line.startswith("- **"):
            log_lines.append(line)
        elif line.strip() == "":
            # Skip blank lines within section
            continue
        elif line.startswith("-"):
            # Other bullet lines (archival pointers, etc.) — include them if not an entry
            log_lines.append(line)

    return start_idx, end_idx, log_lines


def extract_entry_metadata(line):
    """Extract date and role from a pipeline log entry line.

    Entry format examples:
        - **Last pipeline run**: 2026-09-07 (role=impl, ...)
        - **Prior run**: 2026-09-04 (role=pm, ...)
        - **REPEAT 실행**: 2026-08-30 (role=deep, ...)
        - **Archived pipeline log (2026-08-11 ~ 2026-08-21, N entries)**: ...  (not an entry)

    Returns: (date_str, role, is_archive_pointer)
        date_str: "YYYY-MM-DD" or None if not parseable
        role: "pm", "deep", "impl", or None if not found
        is_archive_pointer: True if this is an archival pointer line (not a real entry)
    """
    # Check if this is an archival pointer (skip these, they're not real entries)
    if "Archived pipeline log" in line:
        return None, None, True

    # Extract date: find first YYYY-MM-DD pattern
    date_match = re.search(r"\b(202\d-\d{2}-\d{2})\b", line)
    date_str = date_match.group(1) if date_match else None

    # Extract role: look for (role=pm|deep|impl)
    role_match = re.search(r"\(role=(pm|deep|impl)", line)
    role = role_match.group(1) if role_match else None

    return date_str, role, False


def compute_cutoff_date(entries_metadata, keep_since=None):
    """Compute cutoff date to ensure at least one entry per role is kept.

    If keep_since is specified, use it as the cutoff.
    Otherwise, compute the earliest date such that every role's most-recent entry is kept.

    Args:
        entries_metadata: List of (date_str, role, is_archive_pointer)
        keep_since: Optional "YYYY-MM-DD" string to override computation

    Returns: cutoff_date_str (entries >= this date are kept)
    """
    if keep_since:
        return keep_since

    # Find latest entry per role
    latest_per_role = {}
    for date_str, role, is_archive in entries_metadata:
        if is_archive or role is None:
            continue
        if role not in latest_per_role or date_str > latest_per_role[role]:
            latest_per_role[role] = date_str

    if not latest_per_role:
        # No valid entries found; keep everything
        return None

    # Cutoff = the earliest of all latest_per_role dates
    cutoff = min(latest_per_role.values())
    return cutoff


def split_keep_archive(lines, log_lines, entries_metadata, keep_count=None, keep_since=None):
    """Classify log entries into keep and archive lists.

    Returns: (keep_lines, archive_lines, kept_metadata, archived_metadata)
    """
    # Compute cutoff
    if keep_count is not None:
        # Separate real entries from archive pointer lines
        real_indices = [i for i, (_, _, is_archive) in enumerate(entries_metadata) if not is_archive]
        archive_pointer_indices = [i for i, (_, _, is_archive) in enumerate(entries_metadata) if is_archive]

        # Keep the N most recent real entries
        cutoff_idx = max(0, len(real_indices) - keep_count)
        kept_real_indices = set(real_indices[cutoff_idx:])

        # Archive pointers are always kept
        kept_indices = set(archive_pointer_indices) | kept_real_indices

        keep_lines = [log_lines[i] for i in range(len(log_lines)) if i in kept_indices]
        archive_lines = [log_lines[i] for i in range(len(log_lines)) if i not in kept_indices]
    else:
        cutoff = compute_cutoff_date(entries_metadata, keep_since)
        keep_lines = []
        archive_lines = []
        kept_indices = set()

        for i, line in enumerate(log_lines):
            date_str, role, is_archive = entries_metadata[i]

            # Always keep archival pointer lines
            if is_archive:
                keep_lines.append(line)
                kept_indices.add(i)
                continue

            # Keep if: date >= cutoff (or cutoff is None, or no date found)
            if cutoff is None or date_str is None or date_str >= cutoff:
                keep_lines.append(line)
                kept_indices.add(i)
            else:
                archive_lines.append(line)

    kept_metadata = [m for i, m in enumerate(entries_metadata) if i in kept_indices]
    archived_metadata = [m for i, m in enumerate(entries_metadata) if i not in kept_indices]

    return keep_lines, archive_lines, kept_metadata, archived_metadata


def extract_date_range(archived_metadata):
    """Extract min/max dates from archived entries.

    Returns: (min_date_str, max_date_str) or (None, None) if no valid dates.
    """
    dates = [date_str for date_str, role, is_archive in archived_metadata
             if not is_archive and date_str is not None]
    if not dates:
        return None, None
    return min(dates), max(dates)


def generate_archive_filename(fix_plan_path, min_date, max_date):
    """Generate archive filename path.

    If fix_plan.md is in .agents/ (or similar), create archive at workspace_root/docs/generated/.
    Otherwise create archive in the same parent directory as fix_plan.md.

    Args:
        fix_plan_path: Path to fix_plan.md
        min_date: "YYYY-MM-DD" string
        max_date: "YYYY-MM-DD" string

    Returns: (archive_path, relative_path_for_pointer)
        archive_path: Absolute Path object
        relative_path_for_pointer: Relative path string from fix_plan.md location to archive
    """
    fix_plan_dir = fix_plan_path.parent
    if fix_plan_dir.name in [".agents", ".claude"]:
        workspace_root = fix_plan_dir.parent
        archive_dir = workspace_root / "docs" / "generated"
    else:
        archive_dir = fix_plan_dir / "docs" / "generated"

    # Create archive in docs/generated under workspace root
    archive_dir.mkdir(parents=True, exist_ok=True)

    filename = f"fix_plan-pipeline-log-archive-{min_date}_{max_date}.md"
    archive_path = archive_dir / filename

    # Compute relative path from fix_plan.md location to archive
    try:
        relative_path = os.path.relpath(archive_path, fix_plan_dir)
    except ValueError:
        relative_path = str(archive_path)

    return archive_path, str(relative_path).replace("\\", "/")


def create_archive_file(archive_path, archived_lines, min_date, max_date):
    """Write archive file with header note and archived entries.

    Args:
        archive_path: Path to write archive file
        archived_lines: List of entry lines to archive
        min_date: Earliest date in archive
        max_date: Latest date in archive
    """
    header = f"""# Archived Pipeline Execution Log — {min_date} ~ {max_date}

This archive contains {len(archived_lines)} entries extracted from `.agents/fix_plan.md` on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.
See the live log in fix_plan.md for current entries and pointer location.

---

"""

    content = header + "\n".join(archived_lines) + "\n"
    archive_path.write_text(content, encoding="utf-8")


def generate_archive_pointer(min_date, max_date, archive_path_relative, count=None):
    """Generate a single pointer bullet to replace archived entries.

    Args:
        min_date: Earliest date in archive
        max_date: Latest date in archive
        archive_path_relative: Relative path from fix_plan.md location to archive file
        count: Number of entries archived

    Returns: Pointer line string
    """
    n = count if count is not None else "entries"
    return (f"- **Archived pipeline log ({min_date} ~ {max_date})**: "
            f"<{n} entries archived> → {archive_path_relative}")


def main():
    args = parse_args()

    if args.keep_count is not None and args.keep_count < 0:
        print("ERROR: --keep-count must be non-negative.", file=sys.stderr)
        sys.exit(1)

    if args.keep_since is not None:
        try:
            datetime.strptime(args.keep_since, "%Y-%m-%d")
        except ValueError:
            print(
                f"ERROR: Invalid date format for --keep-since: {args.keep_since!r}. "
                "Expected YYYY-MM-DD.",
                file=sys.stderr
            )
            sys.exit(1)

    # Resolve target file
    if args.file:
        target_path = Path(args.file).resolve()
    else:
        # Try common defaults (matching cleanup.py logic)
        candidates = [
            Path.cwd() / ".agents" / "fix_plan.md",
            Path.cwd() / "fix_plan.md",
            Path.cwd() / "checklist.md",
        ]
        target_path = None
        for p in candidates:
            if p.exists():
                target_path = p
                break
        if target_path is None:
            print(
                "ERROR: Could not find fix_plan.md or checklist.md. "
                "Provide --file or run from a directory with one of these files.",
                file=sys.stderr
            )
            sys.exit(1)

    if not target_path.exists():
        print(f"ERROR: File not found: {target_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[Loading] {target_path}")
    lines = target_path.read_text(encoding="utf-8").splitlines(keepends=False)

    # Extract Pipeline Execution Log section
    start_idx, end_idx, log_lines = extract_pipeline_log_section(lines)
    if start_idx is None:
        print("ERROR: No '## Pipeline Execution Log' section found.", file=sys.stderr)
        sys.exit(1)

    print(f"[Found] {len(log_lines)} entries in Pipeline Execution Log")

    # Parse entry metadata
    entries_metadata = [extract_entry_metadata(line) for line in log_lines]

    # Split keep/archive
    keep_lines, archive_lines, kept_metadata, archived_metadata = split_keep_archive(
        lines, log_lines, entries_metadata,
        keep_count=args.keep_count,
        keep_since=args.keep_since
    )

    print(f"[Decision] Keep {len(keep_lines)}, Archive {len(archive_lines)}")

    if not archive_lines:
        print("No entries to archive. Exiting.")
        sys.exit(0)

    # Losslessness check
    original_set = set(log_lines)
    new_set = set(keep_lines) | set(archive_lines)
    if original_set != new_set:
        print(
            f"ERROR: Losslessness check failed. "
            f"Original {len(original_set)} entries, "
            f"but keep ({len(set(keep_lines))}) + archive ({len(set(archive_lines))}) = "
            f"{len(new_set)} unique entries.",
            file=sys.stderr
        )
        sys.exit(1)

    # Extract date range for archive
    min_date, max_date = extract_date_range(archived_metadata)
    if min_date is None:
        print(
            "WARNING: Could not extract valid dates from archived entries. "
            "Using current date and count as placeholder.",
            file=sys.stderr
        )
        min_date = max_date = datetime.now().strftime("%Y-%m-%d")

    # Determine archive file path
    archive_path, archive_path_relative = generate_archive_filename(target_path, min_date, max_date)

    print(f"[Archive] {min_date} ~ {max_date}, {len(archive_lines)} entries → {archive_path_relative}")

    if args.dry_run:
        print("\n[DRY-RUN] Would create:")
        print(f"  Archive: {archive_path}")
        print(f"  Entries: {len(archive_lines)}")
        print(f"\n[DRY-RUN] Would update fix_plan.md:")
        print(f"  Keep: {len(keep_lines)} entries")
        print(f"  Pointer: - **Archived pipeline log ({min_date} ~ {max_date})**:")
        print(f"          {len(archive_lines)} entries archived → {archive_path_relative}")
        sys.exit(0)

    # Create archive file
    create_archive_file(archive_path, archive_lines, min_date, max_date)
    print(f"[Created] {archive_path}")

    # Generate pointer and update fix_plan.md
    pointer = generate_archive_pointer(
        min_date, max_date, str(archive_path_relative), count=len(archive_lines)
    )

    # Rebuild the file: lines before log section + updated log section + lines after
    new_lines = (
        lines[:start_idx + 1] +  # Include header "## Pipeline Execution Log"
        [""] +  # Blank line after header
        keep_lines +
        [pointer] +
        [""] +  # Blank line before next section
        lines[end_idx:]
    )

    target_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"[Updated] {target_path.name}")
    print("\n[Summary]")
    print(f"  Archived: {len(archive_lines)} entries ({min_date} ~ {max_date})")
    print(f"  Kept:     {len(keep_lines)} entries")
    print(f"  Archive:  {archive_path_relative}")


if __name__ == "__main__":
    main()
