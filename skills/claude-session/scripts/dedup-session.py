#!/usr/bin/env python3
"""Remove duplicate messages from a session JSONL file

Usage:
    python dedup-session.py <session_file>
    python dedup-session.py <session_file> --dry-run
"""

import json
import hashlib
import sys
from pathlib import Path


def strip_lone_surrogates(s: str) -> str:
    """Drop lone UTF-16 surrogate code points (U+D800..U+DFFF).

    json.loads of an escaped \\uXXXX lone surrogate yields a str char in this
    range; json.dumps(ensure_ascii=False) then keeps it, and writing to a utf-8
    stream raises UnicodeEncodeError ('surrogates not allowed'). Astral chars are
    single code points in Python str, so any char in this range is corruption —
    safe to drop, leaving valid utf-8 output (Korean etc. preserved).
    """
    if not any(0xD800 <= ord(c) <= 0xDFFF for c in s):
        return s
    return ''.join(c for c in s if not 0xD800 <= ord(c) <= 0xDFFF)


def get_content_richness(data: dict) -> int:
    """Calculate content richness score for a message (higher is better)"""
    if not data:
        return 0

    msg_type = data.get('type', '')
    if msg_type not in ('assistant', 'user'):
        return len(json.dumps(data))

    content = data.get('message', {}).get('content', [])
    if not isinstance(content, list):
        return 0

    score = 0
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get('type', '')
        # High score for tool_use/tool_result
        if item_type in ('tool_use', 'tool_result'):
            score += 1000
        # Score text content by length
        elif item_type == 'text':
            score += len(item.get('text', ''))
        # Low score for thinking (not valuable without other content)
        elif item_type == 'thinking':
            score += 1

    return score


def get_dedup_key(data: dict) -> str:
    """Generate key for duplicate detection

    Messages with the same message.id are treated as the same message regardless of streaming stage:
    - Intermediate streaming results (text only) and final results (with tool_use) share the same key
    - get_content_richness() selects the richest version
    """
    msg_type = data.get('type', '')

    # assistant/user messages: keyed by message.id only
    if msg_type in ('assistant', 'user'):
        msg = data.get('message', {})
        if isinstance(msg, dict) and msg.get('id'):
            return f"msg:{msg['id']}"

    # progress: keyed by tool_use_id + content hash
    if msg_type == 'progress':
        tool_use_id = data.get('tool_use_id', '')
        content = json.dumps(data.get('content', {}), sort_keys=True)
        content_hash = hashlib.md5(content.encode()).hexdigest()[:16]
        return f"progress:{tool_use_id}:{content_hash}"

    # others: keyed by uuid
    uuid = data.get('uuid')
    if uuid:
        return f"uuid:{uuid}"

    return f"line:{json.dumps(data, sort_keys=True)}"


def dedup_session(session_file: Path, dry_run: bool = False) -> dict:
    """Remove duplicates from session file and repair chain

    Strategy: dedup -> topology-preserving chain repair
    1. Load all messages
    2. Keep only the richest copy in each duplicate group (regardless of references)
    3. Preserve each surviving message's real parentUuid; only redirect pointers that
       referenced a dropped duplicate to the surviving copy, and null-root pointers
       whose target is truly gone. Never re-link to the previous file-order message
       (that would splice unrelated history across compact/resume boundaries).

    Returns:
        dict: {
            'original_lines': int,
            'unique_lines': int,
            'duplicates_by_type': dict,
            'fixed_chains': int,
            'output_file': str (only when dry_run=False)
        }
    """
    # Pass 1: load all messages
    messages = []

    with open(session_file, 'r', encoding='utf-8', errors='surrogatepass') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                messages.append((line, data))
            except json.JSONDecodeError:
                messages.append((line, None))

    # Pass 2: group by duplicate key (dedup_key -> [(line, data), ...])
    dedup_groups = {}
    for line, data in messages:
        if data is None:
            key = f"raw:{line}"
        else:
            key = get_dedup_key(data)

        if key not in dedup_groups:
            dedup_groups[key] = []
        dedup_groups[key].append((line, data))

    # Pass 3: select richest message from each group (prefer tool_use, then content length)
    best_messages = {}  # key -> (line, data)
    for key, group in dedup_groups.items():
        # Sort by richness score, pick the highest
        best = max(group, key=lambda x: get_content_richness(x[1]))
        best_messages[key] = best

    # Build two maps used by the topology-preserving chain repair (Pass 6):
    #   uuid_remap:  every uuid seen in a dedup group -> the kept (best) copy's uuid.
    #                Syncthing conflicts (and streaming fragments) record the same
    #                message.id under DIFFERENT uuids; only the richest copy survives,
    #                so a parentUuid pointing at a dropped copy must redirect to it.
    #   orig_parent: uuid -> its ORIGINAL parentUuid (first occurrence). Lets us walk
    #                out of a message's own streaming group: a kept copy's parent is
    #                often an earlier fragment OF THE SAME TURN, and remapping that to
    #                the kept uuid would make the message its own parent (self-loop).
    #                We follow orig_parent until we exit the group.
    uuid_remap = {}
    orig_parent = {}
    for key, group in dedup_groups.items():
        best_data = best_messages[key][1]
        kept_uuid = best_data.get('uuid') if best_data else None
        if not kept_uuid:
            continue
        for _, gdata in group:
            if gdata and gdata.get('uuid'):
                uuid_remap[gdata['uuid']] = kept_uuid
    for _, data in messages:
        if data and data.get('uuid') and data['uuid'] not in orig_parent:
            orig_parent[data['uuid']] = data.get('parentUuid')

    # Preserve original order while building unique_lines (use best message)
    unique_lines = []
    unique_data = []
    duplicates_by_type = {}
    seen_keys = set()

    for line, data in messages:
        if data is None:
            key = f"raw:{line}"
        else:
            key = get_dedup_key(data)

        if key not in seen_keys:
            # Use best message at the first occurrence position
            best_line, best_data = best_messages[key]
            unique_lines.append(best_line)
            unique_data.append(best_data)
            seen_keys.add(key)
        else:
            # Count removed duplicates
            msg_type = data.get('type', 'unknown') if data else 'unknown'
            duplicates_by_type[msg_type] = duplicates_by_type.get(msg_type, 0) + 1

    # Pass 4: collect all tool_use ids from remaining messages
    remaining_tool_use_ids = set()
    for data in unique_data:
        if data and data.get('type') == 'assistant':
            content = data.get('message', {}).get('content', [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'tool_use':
                        remaining_tool_use_ids.add(item.get('id'))

    # Pass 5: remove orphan tool_results (tool_use_id not in remaining tool_use ids)
    orphan_removed = 0
    filtered_lines = []
    filtered_data = []
    for line, data in zip(unique_lines, unique_data):
        if data and data.get('type') == 'user':
            content = data.get('message', {}).get('content', [])
            if isinstance(content, list):
                # Check if this is a user message with tool_results
                tool_results = [item for item in content if isinstance(item, dict) and item.get('type') == 'tool_result']
                if tool_results:
                    # Check if all tool_results are orphans
                    all_orphan = all(
                        item.get('tool_use_id') not in remaining_tool_use_ids
                        for item in tool_results
                    )
                    if all_orphan:
                        # Remove only orphan tool_results, keep other content (text, etc.)
                        non_orphan_content = [
                            item for item in data.get('message', {}).get('content', [])
                            if item.get('type') != 'tool_result'
                            or item.get('tool_use_id') in remaining_tool_use_ids
                        ]
                        if non_orphan_content:
                            data['message']['content'] = non_orphan_content
                            filtered_lines.append(json.dumps(data))
                            filtered_data.append(data)
                        else:
                            orphan_removed += 1
                        duplicates_by_type['user (orphan tool_result)'] = duplicates_by_type.get('user (orphan tool_result)', 0) + 1
                        continue
        filtered_lines.append(line)
        filtered_data.append(data)

    unique_lines = filtered_lines
    unique_data = filtered_data

    # Pass 6: repair the chain WITHOUT destroying its topology.
    #
    # File order != logical chain order. Claude Code sessions interleave sidechains
    # (subagents), compact/resume boundaries, and branch points, so a message's true
    # parent (parentUuid) very often differs from the previous file-order message.
    # The old "force every message to point at the previous line" strategy spliced
    # unrelated history into one linear mega-chain: it changed the effective leaf/root
    # and re-attached pre-compact history onto post-compact history, inflating the
    # active context ("context merges across the compact boundary"). Measured on a real
    # 30k-line session it rewrote 6056 parentUuids, 3265 of which still had a valid
    # surviving parent, and grew the leaf's active chain from ~77 to 10343 hops.
    #
    # Correct, topology-preserving handling per message:
    #   - parentUuid == null                     -> keep (chain ROOT / compact boundary)
    #   - parentUuid points to a surviving uuid   -> keep exactly (valid parent)
    #   - parentUuid points to a dropped duplicate -> remap to the surviving copy
    #   - parentUuid truly gone (no remap)         -> set null (new root); NEVER bridge
    #     to an unrelated file-order-previous message
    kept_uuids = set()
    for data in unique_data:
        if data and data.get('uuid'):
            kept_uuids.add(data['uuid'])

    def resolve_parent(parent, own_uuid):
        """Resolve a parentUuid to the nearest SURVIVING ancestor that is not the
        message itself. Walks uuid_remap (dropped copy -> kept copy) and, when that
        lands on the message's own turn (a streaming fragment of the same message.id),
        follows orig_parent out of the group. Returns None when the ancestry is lost."""
        seen = set()
        cur = parent
        while cur is not None:
            if cur in seen:                 # cycle guard
                return None
            seen.add(cur)
            kept = uuid_remap.get(cur, cur)  # surviving copy of this uuid
            if kept in kept_uuids and kept != own_uuid:
                return kept                  # a real, distinct, surviving ancestor
            # Either 'cur' has no surviving copy, or it collapses onto own_uuid
            # (an earlier fragment of this same turn). Step to its original parent.
            cur = orig_parent.get(cur)
        return None

    fixed_chains = 0
    final_lines = []
    # Null-rooted repairs: a non-null parentUuid that resolve_parent could not map to
    # any surviving ancestor (ancestry truly lost — see resolve_parent docstring).
    # Tracked with line/uuid so the caller can disclose exactly WHERE history
    # connectivity was severed, instead of only reporting an aggregate count (a repair
    # landing on a user-visible message, e.g. a compact-boundary marker, means real
    # data is missing from the file — not a defect this repair introduced, but a fact
    # worth surfacing rather than folding into a blanket "Validation: PASS").
    null_roots = []

    for i, (line, data) in enumerate(zip(unique_lines, unique_data)):
        if data is None or not data.get('uuid'):
            # Messages without uuid (e.g. file-history-snapshot) are kept as-is
            final_lines.append(line)
            continue

        own_uuid = data.get('uuid')
        current_parent = data.get('parentUuid')

        if current_parent is None:
            # Root / compact boundary — preserve.
            new_parent = None
        elif current_parent in kept_uuids and current_parent != own_uuid:
            # Valid parent survives — preserve exactly.
            new_parent = current_parent
        else:
            # Parent was deduplicated, collapses onto self, or is gone -> resolve to
            # the nearest distinct surviving ancestor, or null (never bridge to an
            # unrelated file-order-previous line, which would merge contexts).
            new_parent = resolve_parent(current_parent, own_uuid)

        # The very first surviving message is always a root.
        if i == 0:
            new_parent = None

        if new_parent != current_parent:
            if new_parent is None and current_parent is not None:
                null_roots.append({'uuid': own_uuid, 'line': i + 1, 'old_parent': current_parent})
            data = dict(data)
            data['parentUuid'] = new_parent
            final_lines.append(json.dumps(data, ensure_ascii=False))
            fixed_chains += 1
        else:
            final_lines.append(line)

    result = {
        'original_lines': len(messages),
        'unique_lines': len(final_lines),
        'duplicates_by_type': duplicates_by_type,
        'fixed_chains': fixed_chains,
        'null_roots': null_roots,
    }

    if not dry_run:
        # Generate .dedup output filename correctly even for .jsonl.bak etc.
        output_file = Path(str(session_file) + '.dedup')
        with open(output_file, 'w', encoding='utf-8') as f:
            for line in final_lines:
                # json.dumps(ensure_ascii=False) may emit lone surrogates from
                # corrupted source escapes — strip them so utf-8 write never crashes.
                f.write(strip_lone_surrogates(line) + '\n')
        result['output_file'] = str(output_file)

    return result


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    session_file = Path(sys.argv[1])
    dry_run = '--dry-run' in sys.argv

    if not session_file.exists():
        print(f"Error: {session_file} not found")
        sys.exit(1)

    result = dedup_session(session_file, dry_run)

    print(f"Original lines: {result['original_lines']}")
    print(f"Resulting lines: {result['unique_lines']}")
    print(f"Duplicates removed: {result['original_lines'] - result['unique_lines']}")

    if result.get('fixed_chains', 0) > 0:
        print(f"Chains repaired: {result['fixed_chains']}")

    if result['duplicates_by_type']:
        print("\nRemoved by type:")
        for t, c in sorted(result['duplicates_by_type'].items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")

    if result.get('null_roots'):
        print(f"\n[WARN] {len(result['null_roots'])} chain repair(s) had NO recoverable ancestor "
              f"(history above these lines is genuinely missing from this file, not caused by this "
              f"repair — inspect before declaring the session fully repaired):")
        for nr in result['null_roots']:
            print(f"  line {nr['line']}: uuid={nr['uuid'][:8]} (was parent={nr['old_parent'][:8]}, not found in file)")

    if not dry_run and 'output_file' in result:
        print(f"\nSaved: {result['output_file']}")


if __name__ == '__main__':
    main()
