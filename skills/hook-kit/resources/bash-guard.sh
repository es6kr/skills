#!/usr/bin/env bash
# bash-guard.sh — PreToolUse:Bash integrated guard
# Phase 1: Immediate block (dangerous command pattern matching)
# Phase 2: Informational checks + conditional block (complex logic)
# Exit codes: 0 = allow, 1 = soft block (BLOCK), 2 = hard block
#
# Self-test:  bash bash-guard.sh --test   (git FN/FP regression suite)

# ── Self-test harness (MUST precede the stdin read below) ──
if [ "${1:-}" = "--test" ]; then
  SELF="$(realpath "$0")"
  pass=0; fail=0
  check() {  # check <BLOCK|ALLOW> <command>
    local expect="$1" cmd="$2" rc got
    CLAUDE_TOOL_INPUT="$(jq -n --arg c "$cmd" '{tool_input:{command:$c}}')" "$SELF" >/dev/null 2>&1
    rc=$?
    case "$rc" in 2|1) got=BLOCK;; *) got=ALLOW;; esac
    if [ "$expect" = "$got" ]; then
      pass=$((pass+1))
    else
      fail=$((fail+1)); printf 'FAIL  expected=%-5s got=%-5s :: %s\n' "$expect" "$got" "$cmd"
    fi
  }

  # ── FN cases: destructive git that MUST be blocked (global-opt forms included) ──
  check BLOCK 'git reset --hard'
  check BLOCK 'git reset --hard HEAD~3'
  check BLOCK 'git -C /srv/app reset --hard'
  check BLOCK 'git -C /srv/app reset --hard origin/main'
  check BLOCK 'git -c core.pager=cat reset --hard'
  check BLOCK 'git --git-dir=/srv/app/.git reset --hard'
  check BLOCK 'git -C /p -c a.b=c reset --hard'
  check BLOCK 'sudo git reset --hard'
  check BLOCK 'time git -C /p reset --hard'
  check BLOCK 'bash -c "git reset --hard"'
  check BLOCK "sh -c 'git -C /p reset --hard'"
  check BLOCK 'ssh host "git -C /srv/app reset --hard"'
  check BLOCK 'git -C /p push origin main --force'
  check BLOCK 'git -C /p push --force-with-lease'
  check BLOCK 'git -C /p push -f'
  check BLOCK 'git -C /p clean -fd'
  check BLOCK 'git -C /p branch -f main deadbeef'
  check BLOCK 'git -C /p branch --force main deadbeef'
  check BLOCK 'git -C /p stash drop'
  check BLOCK 'git -C /p stash clear'
  check BLOCK 'git -C /p checkout .'
  check BLOCK 'git -C /p restore .'
  check BLOCK 'git -C /p add -A'
  check BLOCK 'git -C /p read-tree HEAD'
  check BLOCK 'git -C /p commit --allow-empty -m x'
  check BLOCK 'git -C /p merge --abort'
  check BLOCK 'git    -C   /p    reset   --hard'
  check BLOCK 'GIT -C /p RESET --HARD'
  check BLOCK 'git -C "/path with space" reset --hard'
  check BLOCK 'foo && git -C /p reset --hard'

  # ── FP cases: mentions / safe commands that MUST be allowed ──
  check ALLOW 'git status'
  check ALLOW 'git -C /srv/app log --oneline -5'
  check ALLOW 'git -C /p reset --soft HEAD~1'
  check ALLOW 'git clean -n'
  check ALLOW 'echo "git reset --hard undoes uncommitted work"'
  check ALLOW "grep 'git reset --hard' /tmp/notes.md"
  check ALLOW 'echo "run git -C /p reset --hard to wipe"'
  check ALLOW 'printf "%s" "git push --force is dangerous"'
  check ALLOW 'git commit -m "document git reset --hard behaviour"'
  check ALLOW 'git commit -m "fix: git push --force guard"'
  check ALLOW 'rg "git -C \S+ reset --hard" skills/'
  check ALLOW "$(printf "cat <<'EOF'\ncase history: git push --force overwrites remote history\nEOF")"
  check ALLOW "$(printf "tee -a /tmp/notes.md <<'EOF'\nexample: git reset --hard deletes work\nEOF")"
  check BLOCK "$(printf "bash <<'EOF'\ngit push --force origin main\nEOF")"

  check_bg() {  # check_bg <BLOCK|ALLOW> <command>  (run_in_background: true)
    local expect="$1" cmd="$2" rc got
    CLAUDE_TOOL_INPUT="$(jq -n --arg c "$cmd" '{tool_input:{command:$c, run_in_background:true}}')" "$SELF" >/dev/null 2>&1
    rc=$?
    case "$rc" in 2|1) got=BLOCK;; *) got=ALLOW;; esac
    if [ "$expect" = "$got" ]; then
      pass=$((pass+1))
    else
      fail=$((fail+1)); printf 'FAIL(bg) expected=%-5s got=%-5s :: %s\n' "$expect" "$got" "$cmd"
    fi
  }

  # ── background time-bound guard ──
  check_bg BLOCK 'git push origin main'
  check_bg BLOCK 'gh run watch 12345'
  check_bg BLOCK 'ssh host "docker ps"'
  check_bg ALLOW 'timeout 120 git push origin main'
  check_bg ALLOW 'cd /repo && timeout 300 gh pr create --draft'
  check_bg ALLOW 'curl --max-time 30 http://example.com'
  check_bg ALLOW 'curl -m 10 http://example.com'
  check_bg ALLOW 'ssh -o ConnectTimeout=10 host uptime'
  # foreground: same commands must stay allowed (tool timeout param governs)
  check ALLOW 'git push origin main'
  check ALLOW 'gh run watch 12345'

  printf '\n%d passed, %d failed\n' "$pass" "$fail"
  [ "$fail" -eq 0 ]; exit
fi

INPUT="${CLAUDE_TOOL_INPUT:-$(cat)}"
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // .command // empty' 2>/dev/null)
RUN_BG=$(echo "$INPUT" | jq -r '.tool_input.run_in_background // false' 2>/dev/null)
[ -z "$COMMAND" ] && exit 0

SCRIPT_DIR="$(dirname "$(realpath "$0")")"

# ── Common functions ──
if command -v ggrep &>/dev/null; then GREP=ggrep; else GREP=grep; fi

block() {
  echo "[Safety Hook] BLOCKED: $1" >&2
  echo "Attempted command: $COMMAND" >&2
  echo "If genuinely needed, run it directly in a terminal." >&2
  exit 2
}

WARNINGS=""
BLOCKS=""
warn()       { WARNINGS+="[${1}] ${2}\n"; }
soft_block() { BLOCKS+="BLOCK: ${1}\n"; }

# ══════════════════════════════════════════════
# Phase 1: Immediate block (simple patterns)
# ══════════════════════════════════════════════

# Background dispatch without a command-level time bound
# (claudify/background-polling.md HARD STOP: the Bash tool `timeout` parameter does
#  NOT apply to run_in_background — a hung command is never notified. A time bound
#  inside the command itself is mandatory: `timeout N <cmd>` prefix, curl -m/--max-time,
#  or ssh ConnectTimeout.)
if [ "$RUN_BG" = "true" ]; then
  if ! echo "$COMMAND" | $GREP -qP '(^|[;&|(]\s*|\s)(g?timeout)\s+(-[a-zA-Z-]+\s+)*[0-9]|--max-time[= ]|(^|\s)-m\s*[0-9]+|ConnectTimeout'; then
    block "run_in_background without a command-level time bound. The tool timeout parameter does not apply to background — prefix with 'timeout N <cmd>' (or add curl --max-time / ssh -o ConnectTimeout)"
  fi
fi

# System / file destruction
echo "$COMMAND" | $GREP -qiP '\brm\s+-rf\s+/'          && block "rm -rf / is extremely dangerous"
echo "$COMMAND" | $GREP -qiP '\brm\s+-rf\s+~'          && block "rm -rf ~ deletes your home directory"
echo "$COMMAND" | $GREP -qiP '\brm\s+-rf\s+\.\.'       && block "rm -rf .. can delete a parent directory"
echo "$COMMAND" | $GREP -qiP '\brm\s+-rf\s+\*'         && block "rm -rf * is dangerous"

# .tmp shared temporary directory protection (file-operations.md ".tmp/ shared temp dir" convention)
# .tmp/ is shared by concurrent sessions in the same repo → deleting the whole folder or glob-all
# destroys other sessions' in-progress files.
# Only specific .tmp/<file> or .tmp/<subpath> deletions are allowed (patterns below define what to block).
echo "$COMMAND" | $GREP -qiP '\brm\b[^|;&]*\s(\./)?\.tmp(?![\w/.\-])'  && block "Deleting the entire .tmp/ folder (rm -rf .tmp) will destroy in-progress files of concurrent sessions. Delete only your specific .tmp/<file>"
echo "$COMMAND" | $GREP -qiP '\brm\b[^|;&]*\s(\./)?\.tmp/\*'           && block "Glob-deleting .tmp/* will destroy other sessions' files. Delete only your specific .tmp/<file>"

# Docker destruction
echo "$COMMAND" | $GREP -qiP 'docker\s+volume\s+rm'    && block "docker volume rm permanently deletes volume data"
echo "$COMMAND" | $GREP -qiP 'docker\s+rm\b'           && block "docker rm deletes the container. Check if stop is sufficient"

# ── git destructive guards (global-option-aware + command-position aware) ──
# FN fix: git accepts global options between `git` and the subcommand
#         (`git -C <path> reset --hard`, `git -c x=y ...`, `git --git-dir=... ...`).
#         GITPFX absorbs any run of leading option tokens so those forms are still caught.
# FP fix: a git pattern quoted as a string arg (echo/grep "git reset --hard") must not trip.
#         GIT_SCAN strips quoted literals ONLY when no subshell/remote executor is present;
#         with bash -c / sh -c / ssh / eval / xargs the quoted git DOES execute, so we keep the
#         raw command (default = block). The realistic FN (`git -C <path> reset --hard`, quoted
#         path args included) stays fully covered by GITPFX. The only form stripping can miss is a
#         quoted-*subcommand* invocation (`git "reset" "--hard"`), which no human/tool generates.
GITPFX='\bgit(?:\s+-\S+(?:\s+[^-\s]\S*)?)*'
if echo "$COMMAND" | $GREP -qiP '\b(?:ba|z|k)?sh\s+-c\b|\bssh\b|\beval\b|\bxargs\b'; then
  GIT_SCAN="$COMMAND"
else
  # FP fix 2: heredoc bodies fed to PURE WRITERS (cat/tee) are document text, not
  # commands — documentation quoting a destructive git command (e.g. a case-history
  # entry) must not trip the guards. Heredocs feeding anything else (bash, python,
  # a pipe into an interpreter) keep their body — it may execute. Runs BEFORE the
  # quote-strip so the <<'MARKER' quotes are still intact for terminator extraction.
  GIT_SCAN=$(printf '%s\n' "$COMMAND" | awk '
    skip {
      t=$0; sub(/^[ \t]+/, "", t)
      if (t == term) skip=0
      next
    }
    $0 ~ /^[ \t]*(cat|tee)[ \t]/ && $0 ~ /<</ {
      s=$0
      sub(/.*<<-?[ \t]*/, "", s)
      gsub(/['\''"]/, "", s)
      split(s, a, /[ \t<>|;&]/)
      if (a[1] != "") { term=a[1]; skip=1 }
      print
      next
    }
    { print }
  ')
  GIT_SCAN=$(printf '%s' "$GIT_SCAN" | sed -E "s/'[^']*'//g" | sed -E 's/"[^"]*"//g')
fi
gitblock() { echo "$GIT_SCAN" | $GREP -qiP "${GITPFX}\s+$1" && block "$2"; }

# Git history destruction
gitblock 'reset\s+--hard'                       "git reset --hard deletes uncommitted work"
gitblock 'branch\s+[^|;&]*(?:-f\b|--force)'     "git branch -f force-moves a branch ref, equivalent to reset --hard (previous commits on that ref become unreachable)"
gitblock 'push\s+.*--force'                     "git push --force overwrites remote history"
gitblock 'push\s+.*-f\b'                        "git push -f overwrites remote history"

# Git working directory destruction
gitblock 'clean\s+-.*f'                         "git clean -f permanently deletes untracked files"
gitblock 'checkout\s+\.\s*$'                    "git checkout . discards all changes"
gitblock 'restore\s+\.\s*$'                     "git restore . discards all changes"
gitblock 'stash\s+drop'                         "git stash drop permanently deletes the stash"
gitblock 'stash\s+clear'                        "git stash clear deletes all stashes"

# GitHub PR/Issue close (permanent history pollution)
echo "$COMMAND" | $GREP -qiP 'gh\s+(pr|issue)\s+close'   && block "gh pr/issue close is forbidden without explicit user instruction. close/reopen history is permanently recorded on GitHub"

# Git staging / other
gitblock 'add\s+-A'                             "git add -A causes indiscriminate staging. Specify individual files"
gitblock 'add\s+\.\s*($|&&|\|)'                 "git add . causes indiscriminate staging. Specify individual files"
gitblock 'read-tree'                            "git read-tree destroys staged changes"
gitblock 'commit\s+--allow-empty'               "Empty commits risk being abused as CI/CD triggers"
gitblock 'merge\s+--abort'                      "git merge --abort discards in-progress conflict resolution work"

# K3s / cluster destruction
echo "$COMMAND" | $GREP -qiP 'curl.*get\.k3s\.io'       && block "k3s reinstall risks overwriting existing data"
echo "$COMMAND" | $GREP -qiP 'helm\s+uninstall'         && block "helm uninstall deletes the release and its resources. Use ArgoCD or the helm-orphan skill"
echo "$COMMAND" | $GREP -qiP 'k3s-uninstall'            && block "k3s-uninstall completely destroys cluster data"
echo "$COMMAND" | $GREP -qiP 'kubectl\s+delete\s+node'  && block "kubectl delete node removes a node from the cluster"
echo "$COMMAND" | $GREP -qiP 'kubectl\s+delete\s+pod'   && block "kubectl delete pod risks losing local storage data"
echo "$COMMAND" | $GREP -qiP 'kubectl\s+drain'          && block "kubectl drain evicts all workloads from the node"
echo "$COMMAND" | $GREP -qiP 'rm\s+-rf\s+/var/lib/rancher' && block "Deleting rancher data permanently destroys etcd data"

# Terraform
echo "$COMMAND" | $GREP -qiP 'terraform\s+apply.*-auto-approve' && block "terraform apply -auto-approve changes infrastructure without confirmation"

# Database destruction
echo "$COMMAND" | $GREP -qiP 'DROP\s+DATABASE'   && block "DROP DATABASE is destructive"
echo "$COMMAND" | $GREP -qiP 'DROP\s+TABLE'      && block "DROP TABLE is destructive"
echo "$COMMAND" | $GREP -qiP 'TRUNCATE\s+TABLE'  && block "TRUNCATE TABLE deletes all data"

# ══════════════════════════════════════════════
# Phase 2: Informational checks + conditional block
# ══════════════════════════════════════════════

# git commit check
if [[ "$COMMAND" =~ git[[:space:]]commit ]]; then
  if [[ ! "$COMMAND" =~ --amend ]]; then
    STAGED=$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
    if [ "$STAGED" -eq 0 ]; then
      warn "staged-guard" "No staged files. Run git add first."
    elif [ "$STAGED" -gt 2 ]; then
      warn "commit-split" "${STAGED} files staged. Consider splitting the commit."
    fi
  fi

  if [[ "$COMMAND" =~ -m[[:space:]] ]]; then
    MSG=$(echo "$COMMAND" | $GREP -oP '(?<=-m\s)["\x27]?[^"\x27]+' | head -1 | tr -d '"\x27')
    if [ -n "$MSG" ]; then
      VALID_TYPES="feat|fix|docs|style|refactor|test|chore|ci|perf|build|revert"
      if ! echo "$MSG" | $GREP -qE "^($VALID_TYPES)(\(.+\))?!?:"; then
        warn "commit-validator" "Conventional Commit format recommended: type(scope): description"
      fi
    fi
  fi
fi

# kubectl/helm production cluster delete
if [[ "$COMMAND" =~ ^(kubectl|helm)[[:space:]] ]]; then
  if [[ "$COMMAND" =~ (--context[[:space:]]+kvm|KUBECONFIG.*kvm) ]] && [[ "$COMMAND" =~ [[:space:]]delete[[:space:]] ]]; then
    TARGET=$(echo "$COMMAND" | $GREP -oE '(pod|deployment|sts|statefulset|pvc|svc|service|configmap|secret|namespace|application)s?\s+\S+' | head -1)
    [ -n "$TARGET" ] && soft_block "Attempting to delete $TARGET on production cluster. AskUserQuestion required."
  fi
fi

# Flutter build
if [[ "$COMMAND" =~ (make[[:space:]]fast-android|make[[:space:]]fast-ios|fastlane[[:space:]]beta|flutter[[:space:]]build) ]]; then
  if [ -f "./pubspec.yaml" ] && [ -x "$SCRIPT_DIR/flutter-version-check.sh" ]; then
    FLUTTER_RESULT=$(echo "$INPUT" | TOOL_INPUT="$COMMAND" "$SCRIPT_DIR/flutter-version-check.sh" 2>&1) || true
    [ -n "$FLUTTER_RESULT" ] && WARNINGS+="$FLUTTER_RESULT\n"
  fi
fi

# cat/echo file write detection
if [[ "$COMMAND" =~ (cat[[:space:]]*\<\<|cat[[:space:]]*\>|echo[[:space:]].*\>|printf[[:space:]].*\>) ]]; then
  if [[ "$COMMAND" =~ \>[[:space:]]*[\'\"]*[^\|\&\;]+\.(md|yaml|yml|json|sh|ts|js|py|txt|conf|cfg) ]]; then
    soft_block "Do not modify files via cat/echo. Use the Write tool."
  fi
fi

# ══════════════════════════════════════════════
# Output results
# ══════════════════════════════════════════════

if [ -n "$BLOCKS" ]; then
  echo -e "$BLOCKS" | sed '/^$/d'
  exit 1
fi

if [ -n "$WARNINGS" ]; then
  echo -e "$WARNINGS" | sed '/^$/d'
fi

exit 0
