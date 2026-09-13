#!/usr/bin/env bash
# PreToolUse:Bash — Block `gh pr merge --squash` when subject is missing or lacks (#<PR>) suffix
#
# Trigger: Bash command that actually *invokes* `gh pr merge ... --squash ...`
# Action: Deny if either:
#   1. --subject option absent (subject must be explicit so the suffix can be enforced)
#   2. --subject value does not end with `(#<digits>)` suffix
#
# Background: failed-attempts.md "squash merge subject missing (#PR) suffix" (1st recurrence 2026-06-12).
# User explicit rule: the first line of a squash commit must end with the PR number (#XXX) + block even when --subject is absent.
# Rule body: github-flow/merge.md "Squash Merge" section HARD STOP.
#
# Precision note: the grep gates below are only a cheap *prefilter* — they match
# raw command text, so they also fire on literal data (heredoc bodies, string
# literals, comments) that merely mentions the command. The Python block is the
# authoritative check: it strips heredoc bodies, splits the command into simple-
# command segments at shell operators, and only acts when `gh pr merge` is the
# command actually being executed in one of those segments.

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
if [[ -z "$CMD" ]]; then
  exit 0
fi

# Cheap prefilter (necessary condition only — see precision note above).
if ! echo "$CMD" | grep -qE '\bgh[[:space:]]+pr[[:space:]]+merge\b'; then
  exit 0
fi
if ! echo "$CMD" | grep -qE '(--squash|[[:space:]]-s[[:space:]]|[[:space:]]-s$)'; then
  exit 0
fi

# Use Python for accurate quoted-arg parsing (CMD passed via env, not stdin)
RESULT=$(SQUASH_HOOK_CMD="$CMD" python3 - <<'PY'
import os
import re
import shlex

cmd = os.environ.get("SQUASH_HOOK_CMD", "")

# Characters shlex(punctuation_chars=True) groups into operator tokens.
PUNCT = set("();<>|&")

# Leading words that wrap a command without changing which command it is.
WRAPPERS = {
    "command", "builtin", "exec", "sudo", "nohup",
    "time", "env", "stdbuf", "nice",
}

ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
DURATION_RE = re.compile(r"^\d+(\.\d+)?[smhd]?$")


def strip_heredocs(text):
    """Drop heredoc bodies.

    A heredoc body is input *data*, never a command the shell executes, so any
    `gh pr merge --squash` appearing there (test fixtures, documentation, a
    python program being piped in) must not be treated as a merge invocation.
    Handles <<DELIM, <<-DELIM, <<'DELIM' and <<"DELIM", including several
    heredocs opened on the same line.
    """
    lines = text.split("\n")
    kept = []
    i = 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        openers = re.findall(r"<<(-?)\s*([\"']?)([A-Za-z_][A-Za-z0-9_]*)\2", line)
        i += 1
        for dash, _quote, delim in openers:
            while i < len(lines):
                candidate = lines[i].strip() if dash else lines[i].rstrip("\r")
                i += 1
                if candidate == delim:
                    break
    return "\n".join(kept)


def normalize_newlines(text):
    """Make unquoted newlines behave as command separators.

    Collapses `\\`+newline continuations into a space (as the shell does) and
    turns every remaining *unquoted* newline into `;`, so that a later line in a
    multi-line script is recognised as its own command rather than being glued
    onto the first one.
    """
    out = []
    quote = None
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if quote == "'":
            if ch == "'":
                quote = None
            out.append(ch)
            i += 1
            continue
        if ch == "\\" and i + 1 < n:
            if text[i + 1] == "\n":
                out.append(" ")
                i += 2
                continue
            out.append(ch)
            out.append(text[i + 1])
            i += 2
            continue
        if quote == '"':
            if ch == '"':
                quote = None
            out.append(ch)
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            i += 1
            continue
        out.append(";" if ch == "\n" else ch)
        i += 1
    return "".join(out)


def tokenize(text):
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def is_separator(token):
    return bool(token) and all(ch in PUNCT for ch in token)


def segments(tokens):
    """Split a token stream into simple-command segments at shell operators."""
    current = []
    for token in tokens:
        if is_separator(token):
            if current:
                yield current
            current = []
        else:
            current.append(token)
    if current:
        yield current


def strip_wrappers(segment):
    i = 0
    n = len(segment)
    while i < n:
        token = segment[i]
        if ASSIGN_RE.match(token) or token in WRAPPERS:
            i += 1
            continue
        if token == "timeout":
            i += 1
            while i < n and (segment[i].startswith("-") or DURATION_RE.match(segment[i])):
                i += 1
            continue
        break
    return segment[i:]


def is_gh_pr_merge(segment):
    if len(segment) < 3:
        return False
    program = os.path.basename(segment[0])
    if program.endswith(".exe"):
        program = program[: -len(".exe")]
    return program == "gh" and segment[1] == "pr" and segment[2] == "merge"


try:
    tokens = tokenize(normalize_newlines(strip_heredocs(cmd)))
except ValueError:
    # Unbalanced quotes — cannot parse reliably. Fail open rather than block.
    print("PASS")
    raise SystemExit(0)

merge_args = None
for segment in segments(tokens):
    segment = strip_wrappers(segment)
    if is_gh_pr_merge(segment):
        merge_args = segment[3:]
        break

if merge_args is None:
    # The prefilter matched literal text only (heredoc body, string literal,
    # comment) — no `gh pr merge` is actually being executed.
    print("PASS")
    raise SystemExit(0)

if not any(arg in ("--squash", "-s") for arg in merge_args):
    # `--squash` / `-s` appeared elsewhere in the command, not on this merge.
    print("PASS")
    raise SystemExit(0)

subject = None
for i, token in enumerate(merge_args):
    if token == "--subject":
        if i + 1 < len(merge_args):
            subject = merge_args[i + 1]
        break
    if token.startswith("--subject="):
        subject = token[len("--subject="):]
        break

if subject is None:
    print("DENY_NO_SUBJECT")
    raise SystemExit(0)

if not re.search(r"\(#\d+\)\s*$", subject):
    print(f"DENY_BAD_SUFFIX:{subject}")
    raise SystemExit(0)

print("PASS")
PY
)

case "$RESULT" in
  PASS)
    exit 0
    ;;
  DENY_NO_SUBJECT)
    cat >&2 <<'MSG'
[~/.claude/hooks/block-squash-subject-without-pr.sh]: DENIED: `gh pr merge --squash` requires an explicit `--subject` argument.

Why blocked:
  - Subject must end with `(#<PR_NUMBER>)` suffix per github-flow/merge.md HARD STOP.
  - Without `--subject`, the suffix contract cannot be verified by this hook.
  - GitHub's native squash default also appends `(#N)`, but explicit `--subject` is required so the suffix is auditable in the merge command itself.

Required action:
  - Add `--subject "<prefix>: <description> (#<PR_NUMBER>)"` to the gh pr merge call.

Reference: failed-attempts.md "squash merge subject missing (#PR) suffix" (1st recurrence).
MSG
    exit 2
    ;;
  DENY_BAD_SUFFIX:*)
    SUBJ="${RESULT#DENY_BAD_SUFFIX:}"
    cat >&2 <<MSG
[~/.claude/hooks/block-squash-subject-without-pr.sh]: DENIED: squash subject does not end with \`(#<PR_NUMBER>)\` suffix.

Subject: ${SUBJ}

Why blocked:
  - Squash subject must end with \`(#<PR_NUMBER>)\` per github-flow/merge.md HARD STOP.
  - Matches GitHub's native squash default format.

Required action:
  - Append \` (#<PR_NUMBER>)\` to the --subject value (e.g., "ci: add npm-semantic-release workflow (#177)").

Reference: failed-attempts.md "squash merge subject missing (#PR) suffix" (1st recurrence).
MSG
    exit 2
    ;;
  *)
    # Unexpected output — pass to avoid false-blocking
    exit 0
    ;;
esac
