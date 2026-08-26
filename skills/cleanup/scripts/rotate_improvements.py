#!/usr/bin/env python3
"""Rotate resolved items from improvements ledger to archive."""

import os
import re
from typing import Dict, List, Tuple

RESOLVED_PREFIXES = ('[APPLIED', '[IMPLEMENTED', '[NO-ACTION', '[DONE')


def is_resolved_tag(tag: str) -> bool:
    """Check if a tag string indicates a resolved item."""
    tag = tag.strip()
    if not tag:
        return False
    return any(tag.startswith(p) for p in RESOLVED_PREFIXES)


def parse_improvements(content: str) -> Tuple[List[str], List[str]]:
    """Parse improvements content into active and resolved item blocks."""
    lines = content.splitlines(keepends=True)
    items: List[Tuple[str, bool]] = []
    
    current_item_lines: List[str] = []
    current_is_resolved = False
    in_items = False
    
    for line in lines:
        if line.startswith("### "):
            in_items = True
            if current_item_lines:
                items.append(("".join(current_item_lines), current_is_resolved))
                current_item_lines = []
                current_is_resolved = False
            current_item_lines.append(line)
        elif in_items:
            current_item_lines.append(line)
            tag_match = re.search(r'-\s+\*\*Tag\*\*:\s*(.+)', line)
            if tag_match:
                tag = tag_match.group(1).strip()
                if is_resolved_tag(tag):
                    current_is_resolved = True
            
    if current_item_lines:
        items.append(("".join(current_item_lines), current_is_resolved))
        
    active = [item_text for item_text, resolved in items if not resolved]
    resolved = [item_text for item_text, resolved in items if resolved]
    return active, resolved


def rotate_file(src_path: str, archive_path: str, dry_run: bool = False) -> Dict[str, int]:
    """Rotate resolved items from src_path to archive_path."""
    if not os.path.exists(src_path):
        return {"active_count": 0, "resolved_count": 0}
        
    with open(src_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    lines = content.splitlines(keepends=True)
    header_lines: List[str] = []
    topic_sections: List[Tuple[str, List[Tuple[str, bool]]]] = []
    
    current_topic = ""
    current_items: List[Tuple[str, bool]] = []
    current_item_lines: List[str] = []
    current_is_resolved = False
    in_topics = False
    
    for line in lines:
        if line.startswith("## "):
            in_topics = True
            if current_item_lines:
                current_items.append(("".join(current_item_lines), current_is_resolved))
                current_item_lines = []
                current_is_resolved = False
            if current_topic or current_items:
                topic_sections.append((current_topic, current_items))
                current_items = []
            current_topic = line
        elif line.startswith("### "):
            if current_item_lines:
                current_items.append(("".join(current_item_lines), current_is_resolved))
                current_item_lines = []
                current_is_resolved = False
            current_item_lines.append(line)
        elif current_item_lines:
            current_item_lines.append(line)
            tag_match = re.search(r'-\s+\*\*Tag\*\*:\s*(.+)', line)
            if tag_match:
                tag = tag_match.group(1).strip()
                if is_resolved_tag(tag):
                    current_is_resolved = True
        elif not in_topics:
            header_lines.append(line)
            
    if current_item_lines:
        current_items.append(("".join(current_item_lines), current_is_resolved))
    if current_topic or current_items:
        topic_sections.append((current_topic, current_items))
        
    active_topics_content: List[str] = list(header_lines)
    archive_topics_content: List[str] = []
    
    total_active = 0
    total_resolved = 0
    
    for topic, items in topic_sections:
        active_items = [it for it, res in items if not res]
        resolved_items = [it for it, res in items if res]
        
        total_active += len(active_items)
        total_resolved += len(resolved_items)
        
        if active_items:
            active_topics_content.append(topic)
            active_topics_content.extend(active_items)
            
        if resolved_items:
            archive_topics_content.append(topic)
            archive_topics_content.extend(resolved_items)
            
    if not dry_run:
        with open(src_path, "w", encoding="utf-8") as f:
            f.write("".join(active_topics_content))
            
        archive_existing = ""
        if os.path.exists(archive_path):
            with open(archive_path, "r", encoding="utf-8") as f:
                archive_existing = f.read()
                
        with open(archive_path, "w", encoding="utf-8") as f:
            if archive_existing:
                f.write(archive_existing)
                if not archive_existing.endswith("\n"):
                    f.write("\n")
            f.write("".join(archive_topics_content))
            
    return {"active_count": total_active, "resolved_count": total_resolved}
