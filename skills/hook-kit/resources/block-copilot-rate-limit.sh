#!/usr/bin/env python3
# PreToolUse:Bash - Block Copilot reviewer addition during active rate limit.
#
# Trigger: gh pr edit --add-reviewer copilot-pull-request-reviewer
# Action: Deny if current time is before the reset time in ~/.claude/copilot-rate-limit.json

import sys
import json
import os
from datetime import datetime, timezone

try:
    hook_input = json.load(sys.stdin)
except Exception:
    sys.exit(0)

tool_name = hook_input.get("tool_name")
if tool_name != "Bash":
    sys.exit(0)

cmd = hook_input.get("tool_input", {}).get("command", "")
if not cmd:
    sys.exit(0)

# Check if command includes the copilot reviewer login
if "copilot-pull-request-reviewer" not in cmd:
    sys.exit(0)

cache_path = os.path.expanduser("~/.claude/copilot-rate-limit.json")
if not os.path.exists(cache_path):
    sys.exit(0)

try:
    with open(cache_path, "r") as f:
        cache = json.load(f)
    
    reset_at_str = cache.get("reset_at")
    if not reset_at_str:
        sys.exit(0)
    
    # Parse reset_at. Replace 'Z' with '+00:00' to support older python versions.
    if reset_at_str.endswith('Z'):
        reset_at_str = reset_at_str[:-1] + '+00:00'
        
    reset_at = datetime.fromisoformat(reset_at_str)
    now_utc = datetime.now(timezone.utc)
    
    if now_utc < reset_at:
        diff = reset_at - now_utc
        hours, remainder = divmod(diff.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        remaining_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        
        output = {
            "decision": "block",
            "reason": (
                f"GitHub Copilot rate limit is currently active.\n"
                f"Reset time (UTC): {cache.get('reset_at')}\n"
                f"Remaining time: {remaining_str}\n"
                f"Commands requesting Copilot review are blocked until the rate limit is reset."
            )
        }
        print(json.dumps(output, indent=2))
        sys.exit(2)
except Exception as e:
    # Do not block on unexpected errors to ensure fallback stability
    pass

sys.exit(0)
