#!/usr/bin/env bash
# bash-guard.sh — PreToolUse:Bash integrated guard
# Phase 1: Immediate block (dangerous command pattern matching)
# Phase 2: Informational checks + conditional block (complex logic)
# Exit codes: 0 = allow, 1 = soft block (BLOCK), 2 = hard block

INPUT="${CLAUDE_TOOL_INPUT:-$(cat)}"
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // .command // empty' 2>/dev/null)
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

# Git history destruction
echo "$COMMAND" | $GREP -qiP 'git\s+reset\s+--hard'    && block "git reset --hard deletes uncommitted work"
echo "$COMMAND" | $GREP -qiP 'git\s+branch\s+[^|;&]*(?:-f\b|--force)' && block "git branch -f force-moves a branch ref, equivalent to reset --hard (previous commits on that ref become unreachable)"
echo "$COMMAND" | $GREP -qiP 'git\s+push\s+.*--force'  && block "git push --force overwrites remote history"
echo "$COMMAND" | $GREP -qiP 'git\s+push\s+.*-f\b'     && block "git push -f overwrites remote history"

# Git working directory destruction
echo "$COMMAND" | $GREP -qiP 'git\s+clean\s+-.*f'      && block "git clean -f permanently deletes untracked files"
echo "$COMMAND" | $GREP -qiP 'git\s+checkout\s+\.\s*$' && block "git checkout . discards all changes"
echo "$COMMAND" | $GREP -qiP 'git\s+restore\s+\.\s*$'  && block "git restore . discards all changes"
echo "$COMMAND" | $GREP -qiP 'git\s+stash\s+drop'      && block "git stash drop permanently deletes the stash"
echo "$COMMAND" | $GREP -qiP 'git\s+stash\s+clear'     && block "git stash clear deletes all stashes"

# GitHub PR/Issue close (permanent history pollution)
echo "$COMMAND" | $GREP -qiP 'gh\s+(pr|issue)\s+close'   && block "gh pr/issue close is forbidden without explicit user instruction. close/reopen history is permanently recorded on GitHub"

# Git staging / other
echo "$COMMAND" | $GREP -qiP 'git\s+add\s+-A'                && block "git add -A causes indiscriminate staging. Specify individual files"
echo "$COMMAND" | $GREP -qiP 'git\s+add\s+\.\s*($|&&|\|)'    && block "git add . causes indiscriminate staging. Specify individual files"
echo "$COMMAND" | $GREP -qiP 'git\s+read-tree'               && block "git read-tree destroys staged changes"
echo "$COMMAND" | $GREP -qiP 'git\s+commit\s+--allow-empty'  && block "Empty commits risk being abused as CI/CD triggers"
echo "$COMMAND" | $GREP -qiP 'git\s+merge\s+--abort'         && block "git merge --abort discards in-progress conflict resolution work"

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
