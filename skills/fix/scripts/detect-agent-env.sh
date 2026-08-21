#!/usr/bin/env bash
set -euo pipefail

# detect-agent-env.sh — Detect which AI agent environment is currently running
# Usage: bash detect-agent-env.sh
# Output line 1: "antigravity" | "claude-code" | "cursor" | "unknown"
# Output lines 2+: routing table (RULES_FILE, SETTINGS_FILE, SHARED_RULES_DIR)

detect_env() {
  # --- 1. Agent-specific env vars (Top priority: identify agent) ---
  # Claude Code injects its own environment variable regardless of IDE
  if [[ -n "${CLAUDE_CODE:-}" ]]; then
    echo "claude-code"
    return
  fi

  # Antigravity agent (injects ANTIGRAVITY_AGENT=1 on Windows)
  if [[ "${ANTIGRAVITY_AGENT:-}" == "1" ]]; then
    echo "antigravity-agent"
    return
  fi

  # --- 2. macOS IDE fallback: __CFBundleIdentifier ---
  # Only infer from IDE when agent-specific env vars are absent
  # Note: Claude Code running inside Antigravity IDE is caught above by CLAUDE_CODE
  case "${__CFBundleIdentifier:-}" in
    com.google.antigravity)           echo "antigravity"; return ;;
    com.google.antigravity-ide)       echo "antigravity-ide"; return ;;
    com.todesktop.230313mzl4w4u92)    echo "cursor"; return ;;
    com.microsoft.VSCode)             echo "vscode"; return ;;
  esac

  echo "unknown"
}

ENV=$(detect_env)
echo "$ENV"

# Emit routing table for the caller
case "$ENV" in
  antigravity|antigravity-agent|antigravity-ide)
    echo "RULES_FILE=GEMINI.md"
    echo "SETTINGS_FILE=$HOME/.gemini/config/config.json"
    echo "SHARED_RULES_DIR=$HOME/.agents/rules (READ-ONLY)"
    ;;
  claude-code)
    echo "RULES_FILE=CLAUDE.md"
    echo "SETTINGS_FILE=$HOME/.claude/settings.json"
    echo "SHARED_RULES_DIR=$HOME/.claude/rules (WRITABLE)"
    ;;
  cursor|vscode)
    echo "RULES_FILE=CLAUDE.md"
    echo "SETTINGS_FILE=$HOME/.claude/settings.json"
    echo "SHARED_RULES_DIR=$HOME/.claude/rules (WRITABLE)"
    ;;
  unknown)
    echo "RULES_FILE=unknown"
    echo "SETTINGS_FILE=unknown"
    echo "SHARED_RULES_DIR=unknown"
    ;;
esac
