#!/usr/bin/env python3
"""PreToolUse:Edit|Write guard - enforce /wip register-before-execute.

Blocks an Edit/Write when the LAST genuine user prompt is a registration-mode
/wip invocation and NO TaskCreate/TodoWrite tool_use has run since. Reading
files (Bash/Read) before registering is allowed; only producing the deliverable
(Edit/Write) before the task exists is blocked.

Robustness (tested against real transcripts, not just synthetic):
  - tool_result user-messages (AskUserQuestion answers, Bash/tool results are
    recorded as type=user) are SKIPPED when locating the last user turn, so
    tool output containing "/wip" or verb-like words does not false-positive.
  - /wip detection requires the genuine slash-command marker
    <command-name>[/]wip</command-name>, which appears only in real command
    messages - not in quoted tool output.

Registration-mode verbs: English defaults + optional Korean via env
(HG_WIP_REGISTER_VERBS, exported by the sibling .sh from data/, git-ignored).

Fail-open: any parse/IO uncertainty -> exit 0 (allow). Only the deterministic
"last genuine prompt == registration /wip, no TaskCreate since" case fires; the
interrupt-stacked variant is covered by wip SKILL.md Step 0 instead.

Cross-platform I/O contract (es6kr/skills issue #265 Phase 2 pilot):
  - Claude Code:  stdin {tool_name, tool_input, transcript_path}; block =
                  stderr + exit 2.
  - Antigravity:  stdin {toolCall.name, toolCall.args...}; block = stdout
                  {"decision":"deny","reason":...} + exit 0. Antigravity has
                  no TaskCreate/TodoWrite tool - per wip/antigravity.md, its
                  registration medium is the task.md artifact instead, so the
                  "was a task registered since /wip" check is reinterpreted as
                  "is THIS write targeting task.md itself" (the write to
                  task.md IS the registration act).
  Same script is registered in ~/.claude/settings.json AND
  ~/.gemini/config/hooks.json (precedent:
  consolidate/resources/block-noncompliant-review-comment.sh).

  NOTE (unverified): Antigravity's transcript-equivalent (conversation log
  used elsewhere in this codebase as transcript.jsonl, per next/SKILL.md Step
  0-1) is not confirmed reachable from a hook's stdin payload, so the
  "last genuine user prompt was a registration /wip" scan that Claude Code
  performs via transcript_path has NO Antigravity equivalent here - this is a
  known, explicit gap (see ANTIGRAVITY_SKIP_REPORT below), not a silent
  omission. The Antigravity branch instead fails open on any Edit/Write that
  is not itself a task.md write, deferring the fuller check to when transcript
  access is confirmed in a live session (see es6kr/skills issue #265 task
  "live-verify pilot hook fires in a real Antigravity session").
ANTIGRAVITY_SKIP_REPORT = [
    "transcript-scan for 'last prompt was registration /wip' - no confirmed "
    "stdin field carries transcript/conversation-log path; needs live-session "
    "verification of the actual Antigravity PreToolUse payload shape",
]
"""
import sys, json, os, re

def allow():
    sys.exit(0)

def deny_antigravity(reason):
    sys.stdout.write(json.dumps({"decision": "deny", "reason": reason}) + "\n")
    sys.exit(0)

REGISTER_VERBS = os.environ.get(
    "HG_WIP_REGISTER_VERBS",
    "add|write|create|draft|record|register",
)

try:
    payload = json.load(sys.stdin)
except Exception:
    allow()

CLAUDE_TOOL = payload.get("tool_name", "")
AG_TOOL = payload.get("toolCall", {}).get("name", "") if isinstance(payload.get("toolCall"), dict) else ""

def find_last_genuine_user_prompt(events):
    """Return (raw_line, event) for the most recent non-tool-result user turn, or None."""
    def is_tool_result(e):
        if not isinstance(e, dict):
            return False
        m = e.get("message", {})
        c = m.get("content") if isinstance(m, dict) else None
        if isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    return True
        return False

    for i in range(len(events) - 1, -1, -1):
        _, e = events[i]
        if isinstance(e, dict) and e.get("type") == "user" and not is_tool_result(e):
            return i
    return None

def text_of(e):
    if not isinstance(e, dict):
        return ""
    m = e.get("message", {})
    c = m.get("content", m) if isinstance(m, dict) else m
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for b in c:
            if isinstance(b, dict):
                parts.append(str(b.get("text", "")))
            else:
                parts.append(str(b))
        return " ".join(parts)
    return str(c)

def load_events(log_path):
    with open(log_path, encoding="utf-8") as fh:
        rawlines = [ln for ln in fh.read().splitlines() if ln.strip()]
    events = []
    for ln in rawlines:
        try:
            events.append((ln, json.loads(ln)))
        except Exception:
            events.append((ln, None))
    return events

def was_registration_wip_without_followup(log_path, registered_pattern):
    """Shared scan: last genuine user prompt was a registration-mode /wip and no
    matching registration event (registered_pattern) occurred since. Returns
    True only on the deterministic block condition; any uncertainty raises so
    the caller can fail open."""
    events = load_events(log_path)
    last_user = find_last_genuine_user_prompt(events)
    if last_user is None:
        return False
    raw_user, e_user = events[last_user]
    if not re.search(r"command-name>/?wip<", raw_user):
        return False
    utext = text_of(e_user) or raw_user
    if not re.search(r"(" + REGISTER_VERBS + r")", utext, re.I):
        return False
    for j in range(last_user + 1, len(events)):
        rawj, _ = events[j]
        if re.search(registered_pattern, rawj):
            return False
    return True

def find_antigravity_active_log_path():
    brain_root = os.path.expanduser("~/.gemini/antigravity-ide/brain")
    if not os.path.isdir(brain_root):
        return ""
    candidates = []
    try:
        for d in os.listdir(brain_root):
            full_d = os.path.join(brain_root, d)
            log_file = os.path.join(full_d, ".system_generated", "logs", "transcript.jsonl")
            if os.path.isfile(log_file):
                try:
                    candidates.append((os.path.getmtime(log_file), log_file))
                except Exception:
                    pass
    except Exception:
        return ""
    if not candidates:
        return ""
    candidates.sort(reverse=True)
    return candidates[0][1]

def was_workflow_or_registration_without_followup(log_path, registered_pattern):
    events = load_events(log_path)
    last_user = find_last_genuine_user_prompt(events)
    if last_user is None:
        return False
    raw_user, e_user = events[last_user]
    utext = text_of(e_user) or raw_user
    
    # Check for slash commands or explicit task directives
    is_workflow = bool(re.search(r"/(fix|fa|code-workflow|deploy|consolidate|wip|fix-plan)\b", utext, re.I)
                      or re.search(r"command-name>/?(fix|fa|code-workflow|deploy|consolidate|wip|fix-plan)<", raw_user, re.I)
                      or (re.search(r"command-name>/?wip<", raw_user) and re.search(r"(" + REGISTER_VERBS + r")", utext, re.I)))
    
    if not is_workflow:
        return False

    for j in range(last_user + 1, len(events)):
        rawj, _ = events[j]
        if re.search(registered_pattern, rawj):
            return False
    return True

if AG_TOOL:
    # Antigravity runtime. Matcher mirrors ~/.gemini/config/hooks.json's
    # "Edit|Write|write_to_file|replace_file_content|multi_replace_file_content"
    if AG_TOOL not in ("Edit", "Write", "write_to_file", "replace_file_content", "multi_replace_file_content"):
        allow()
    ag_args = payload.get("toolCall", {}).get("args", {}) or {}
    target_path = (
        ag_args.get("path")
        or ag_args.get("TargetFile")
        or ag_args.get("file_path")
        or ""
    )
    if str(target_path).endswith("task.md"):
        # The write IS the registration act - never block it.
        allow()
    
    ag_log_path = (
        payload.get("transcriptPath")
        or payload.get("transcript_path")
        or (payload.get("toolCall", {}) or {}).get("transcriptPath")
        or find_antigravity_active_log_path()
        or ""
    )
    if ag_log_path and os.path.exists(ag_log_path):
        try:
            if was_workflow_or_registration_without_followup(ag_log_path, r"task\.md"):
                deny_antigravity(
                    "Tool Call #1 MANDATORY & /wip register-before-execute (HARD STOP): "
                    "A workflow slash-command (/fix, /fa, /wip, /code-workflow, etc.) was invoked "
                    "but task.md has not been updated in the current turn. "
                    "The VERY FIRST tool call MUST update task.md before editing deliverable files. "
                    "Ref: GEMINI.md 'Tool Call #1 MANDATORY' & wip/antigravity.md Step 2."
                )
        except Exception:
            pass  # fall through to allow()
    allow()

if CLAUDE_TOOL not in ("Edit", "Write"):
    allow()

tp = payload.get("transcript_path", "")
if not tp or not os.path.exists(tp):
    allow()

try:
    if was_registration_wip_without_followup(tp, r'"name"\s*:\s*"(TaskCreate|TodoWrite)"'):
        sys.stderr.write(
            "/wip register-before-execute (HARD STOP): a registration-mode /wip was invoked "
            "but no TaskCreate/TodoWrite has run since.\n"
            "  Register the wip task FIRST (TaskCreate), THEN edit the deliverable.\n"
            "  Ref: wip SKILL.md Step 1 'Register BEFORE execute'.\n"
        )
        sys.exit(2)
except Exception:
    allow()

allow()
