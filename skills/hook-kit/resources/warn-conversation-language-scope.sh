#!/bin/bash
# warn-conversation-language-scope.sh — UserPromptSubmit hook: warn when the
# assistant's own narration drifted into English inside a ko_KR-scope session.
#
# Why: ~/.agents/rules/language.md's conversation-language override is
# cwd-scope-based (es6kr paths -> English, everything else -> ko_KR), and is
# independent of any English-required artifact (skill files, PUBLIC-repo PR
# bodies/commits) the assistant may be editing in the same turn. A sustained
# stretch of English-artifact work has repeatedly dragged the assistant's own
# conversational narration into English even in a ko_KR-scope session — this
# is the "conversation-language-scope" failed-attempts class, 3rd recurrence
# (2026-07-28), whose own escalation note declared a hook mandatory at this
# count. Warning-only, not blocking: detecting "should this turn be Korean"
# from content is inherently heuristic (a code-heavy or PUBLIC-repo-quoting
# Korean turn can legitimately have long English stretches), so a hard block
# risks false positives on exactly the artifact work language.md already
# permits to stay English. See failed-attempts.md "conversation-language-scope".
#
# Input (stdin): JSON { session_id, transcript_path, cwd, prompt, ... }
# Output (stdout): a warning line when drift is detected (injected as
#   additionalContext, exit 0). No output = no drift detected or scope is
#   English already. Fail-open on any parse error (exit 0, no output).

INPUT=$(cat)

PY=""
for _c in python3 python; do
  if command -v "$_c" >/dev/null 2>&1 && "$_c" -c "pass" >/dev/null 2>&1; then
    PY="$_c"; break
  fi
done
[ -n "$PY" ] || exit 0

export CLAUDE_HOOK_INPUT="$INPUT"
"$PY" - <<'PYEOF' 2>/dev/null || exit 0
import json, os, re, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ENGLISH_SCOPE_PATTERNS = (
    "ghq/github.com/es6kr/",
    ".claude/skills/",
    ".agents/skills/",
)

CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`]*`")
HANGUL_RE = re.compile(r"[가-힣]")

MIN_PROSE_CHARS = 300

try:
    payload = json.loads(os.environ.get("CLAUDE_HOOK_INPUT", "{}"))
    cwd = (payload.get("cwd") or "").replace("\\", "/")
    transcript_path = payload.get("transcript_path", "")

    if not cwd or not transcript_path or not os.path.isfile(transcript_path):
        sys.exit(0)

    # Scope check: skip entirely when cwd is already English-scope per
    # language.md's table — this hook only guards the ko_KR-default case.
    # Normalize with a trailing "/" before matching: every pattern above
    # carries a trailing slash, so a cwd that IS a pattern's root exactly
    # (no subdirectory — e.g. the es6kr org root itself) would otherwise
    # fail the substring check and false-positive as "outside scope".
    cwd_for_match = cwd if cwd.endswith("/") else cwd + "/"
    if any(pat in cwd_for_match for pat in ENGLISH_SCOPE_PATTERNS):
        sys.exit(0)

    # Find the last assistant text message in the transcript.
    last_text = ""
    with open(transcript_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"role":"assistant"' not in line and '"role": "assistant"' not in line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = ev.get("message") or {}
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    t = c.get("text", "").strip()
                    if t:
                        last_text = t

    if not last_text:
        sys.exit(0)

    # Strip fenced/inline code — these legitimately carry English identifiers,
    # commands, and quoted PR/commit text under the artifact-language exception.
    prose = CODE_FENCE_RE.sub("", last_text)
    prose = INLINE_CODE_RE.sub("", prose)

    if len(prose) < MIN_PROSE_CHARS:
        sys.exit(0)

    if HANGUL_RE.search(prose):
        sys.exit(0)

    print(
        "[language.md] This session's cwd is outside the English-scope table "
        "(ghq/es6kr, .claude|.agents/skills) -> conversation language should be "
        "ko_KR, but the last assistant response had 300+ prose characters with "
        "zero Hangul. If recent turns involved editing English-required "
        "artifacts (skill files, PUBLIC-repo PR/commit text), that does not "
        "change the conversation-language scope for your own narration -- "
        "language.md Don't/Do #7. Re-run the scope self-check before the next "
        "conversational response."
    )
except Exception:
    sys.exit(0)
PYEOF
