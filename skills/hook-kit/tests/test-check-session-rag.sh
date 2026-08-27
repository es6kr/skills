#!/usr/bin/env bash
# Tests for check-session-rag.sh — the session-end RAG store/find guard.
#
# Regression under test: the guard demanded a RAG store from a workspace
# that has no RAG receiver configured at all, blocking session end with an
# instruction the session could not possibly follow. It could not tell
# "receiver absent" from "session was negligent" because it never consulted
# the workspace config — it only pattern-matched tool names.
#
# Run: bash ~/.agents/skills/hook-kit/tests/test-check-session-rag.sh

set -uo pipefail

HOOK="$(cd "$(dirname "$0")/../resources" && pwd)/check-session-rag.sh"
FIXTURE="$(mktemp -d)"
HTTP_PID=""
trap 'rm -rf "$FIXTURE"; [ -n "$HTTP_PID" ] && kill "$HTTP_PID" 2>/dev/null' EXIT

pass=0
fail=0

check() { # name expected actual
  if [ "$2" = "$3" ]; then
    pass=$((pass + 1)); printf 'PASS  %s\n' "$1"
  else
    fail=$((fail + 1)); printf 'FAIL  %s\n        expected exit=[%s]\n        actual   exit=[%s]\n' "$1" "$2" "$3"
  fi
}

# A session with a finding signal (audit prompt) and zero RAG-store calls —
# the exact shape that tripped the guard.
cat > "$FIXTURE/findings.jsonl" <<'JSONL'
{"message":{"role":"user","content":[{"type":"text","text":"please run an audit of the hook registrations"}]}}
{"message":{"role":"assistant","content":[{"type":"tool_use","name":"Read","input":{"file_path":"/tmp/x.md"}}]}}
JSONL

# Same, but the session did store to a RAG receiver.
cat > "$FIXTURE/stored.jsonl" <<'JSONL'
{"message":{"role":"user","content":[{"type":"text","text":"please run an audit of the hook registrations"}]}}
{"message":{"role":"assistant","content":[{"type":"tool_use","name":"mcp__qdrant__qdrant-find","input":{}}]}}
{"message":{"role":"assistant","content":[{"type":"tool_use","name":"mcp__qdrant__qdrant-store","input":{}}]}}
JSONL

cat > "$FIXTURE/rag-none.json" <<'JSON'
{"version":2,
 "profiles":{"wsNoRag":{"match":{"path_components":["wsNoRag"]},
                        "roles":{"rag":{"kind":"none"}}}}}
JSON

cat > "$FIXTURE/rag-on.json" <<'JSON'
{"version":2,
 "profiles":{"wsRag":{"match":{"path_components":["wsRag"]},
                      "roles":{"rag":{"kind":"qdrant","mcp_prefix":"mcp__qdrant__"}}}}}
JSON

# A receiver declared without an MCP prefix: nothing to match a health line
# against, so connectivity is unknowable and the guard must not relax.
cat > "$FIXTURE/rag-noprefix.json" <<'JSON'
{"version":2,
 "profiles":{"wsRagNP":{"match":{"path_components":["wsRagNP"]},
                        "roles":{"rag":{"kind":"qdrant"}}}}}
JSON

# Stand-in for the CLI so the suite never health-checks the real servers.
# FAKE_MCP_OUTPUT selects the canned health report, FAKE_MCP_FAIL makes the
# command fail, and FAKE_MCP_MARKER records that it ran at all.
mkdir -p "$FIXTURE/bin"
cat > "$FIXTURE/bin/claude" <<'SH'
#!/usr/bin/env bash
[ -n "${FAKE_MCP_MARKER:-}" ] && printf 'x' >> "$FAKE_MCP_MARKER"
[ "${FAKE_MCP_FAIL:-0}" = "1" ] && exit 1
cat "${FAKE_MCP_OUTPUT:-/dev/null}"
SH
chmod +x "$FIXTURE/bin/claude"

cat > "$FIXTURE/mcp-connected.txt" <<'TXT'
plugin:playwright:playwright: npx @playwright/mcp@latest - ✔ Connected
qdrant: docker run --rm -i -e QDRANT_URL --entrypoint mcp-server-qdrant img --transport stdio - ✔ Connected
TXT

cat > "$FIXTURE/mcp-down.txt" <<'TXT'
plugin:playwright:playwright: npx @playwright/mcp@latest - ✔ Connected
qdrant: docker run --rm -i -e QDRANT_URL --entrypoint mcp-server-qdrant img --transport stdio - ✘ Failed to connect — -32000: MCP error -32000: Connection closed
TXT

cat > "$FIXTURE/mcp-absent.txt" <<'TXT'
plugin:playwright:playwright: npx @playwright/mcp@latest - ✔ Connected
context7: npx -y @upstash/context7-mcp - ✔ Connected
TXT

export FAKE_MCP_OUTPUT="$FIXTURE/mcp-connected.txt"

run() { # transcript
  printf '{"transcript_path":"%s"}' "$1" | PATH="$FIXTURE/bin:$PATH" "$HOOK" >/dev/null 2>&1
  echo "$?"
}

# --- The regression -----------------------------------------------------
export AGENT_WORKSPACE_CONFIG="$FIXTURE/rag-none.json"
export AGENT_WORKSPACE_PROFILE=wsNoRag
check "R1 no RAG receiver configured -> allow stop" "0" "$(run "$FIXTURE/findings.jsonl")"

# --- The guard must still work where a receiver exists ------------------
export AGENT_WORKSPACE_CONFIG="$FIXTURE/rag-on.json"
export AGENT_WORKSPACE_PROFILE=wsRag
check "R2 receiver configured + findings + no store -> block" "2" "$(run "$FIXTURE/findings.jsonl")"
check "R3 receiver configured + store + find -> allow"        "0" "$(run "$FIXTURE/stored.jsonl")"

# --- Existing escape hatches must survive -------------------------------
cat > "$FIXTURE/skip.jsonl" <<'JSONL'
{"message":{"role":"user","content":[{"type":"text","text":"please run an audit of the hook registrations"}]}}
{"message":{"role":"user","content":[{"type":"text","text":"no RAG store needed"}]}}
JSONL
check "R4 explicit user skip phrase -> allow"                 "0" "$(run "$FIXTURE/skip.jsonl")"

RALPH_LOOP=1 check "R5 ralph loop bypass -> allow"            "0" "$(RALPH_LOOP=1 run "$FIXTURE/findings.jsonl")"

# --- Configured but not connected in this session -----------------------
# A receiver the session cannot reach cannot be stored to, so demanding a
# store would be an instruction the session has no way to follow.
export AGENT_WORKSPACE_CONFIG="$FIXTURE/rag-on.json"
export AGENT_WORKSPACE_PROFILE=wsRag

export FAKE_MCP_OUTPUT="$FIXTURE/mcp-down.txt"
check "R6 receiver configured but not connected -> allow"     "0" "$(run "$FIXTURE/findings.jsonl")"

export FAKE_MCP_OUTPUT="$FIXTURE/mcp-absent.txt"
check "R7 receiver not registered at all -> allow"            "0" "$(run "$FIXTURE/findings.jsonl")"

export FAKE_MCP_OUTPUT="$FIXTURE/mcp-connected.txt"
check "R8 receiver connected + findings + no store -> block"  "2" "$(run "$FIXTURE/findings.jsonl")"

# Unknowable connectivity must keep the guard blocking, not open a silent
# escape hatch: no prefix to match on, and a health command that failed.
export AGENT_WORKSPACE_CONFIG="$FIXTURE/rag-noprefix.json"
export AGENT_WORKSPACE_PROFILE=wsRagNP
check "R9 no mcp_prefix to match -> block"                    "2" "$(run "$FIXTURE/findings.jsonl")"

export AGENT_WORKSPACE_CONFIG="$FIXTURE/rag-on.json"
export AGENT_WORKSPACE_PROFILE=wsRag
export FAKE_MCP_FAIL=1
check "R10 health command failed -> block"                    "2" "$(run "$FIXTURE/findings.jsonl")"
unset FAKE_MCP_FAIL

# --- The health check is expensive, so it runs only on the block path ---
export FAKE_MCP_MARKER="$FIXTURE/marker"
rm -f "$FAKE_MCP_MARKER"
run "$FIXTURE/stored.jsonl" >/dev/null
if [ -e "$FAKE_MCP_MARKER" ]; then ran="yes"; else ran="no"; fi
check "R11 allow path does not health-check every server"     "no" "$ran"

rm -f "$FAKE_MCP_MARKER"
run "$FIXTURE/findings.jsonl" >/dev/null
if [ -e "$FAKE_MCP_MARKER" ]; then ran="yes"; else ran="no"; fi
check "R12 block path does health-check"                      "yes" "$ran"
unset FAKE_MCP_MARKER

# --- The receiver is reachable without MCP at all ------------------------
# The domain skill stores through a script that talks HTTP to the same
# endpoint. Treating MCP as the only transport gets this wrong twice: a
# script-based store earns no credit, and an MCP outage waves the session
# through even though the script path still works.

# A session that stored via the skill's import script, not via an MCP tool.
# It searched via MCP, so only the store side is under test here.
cat > "$FIXTURE/script-stored.jsonl" <<'JSONL'
{"message":{"role":"user","content":[{"type":"text","text":"please run an audit of the hook registrations"}]}}
{"message":{"role":"assistant","content":[{"type":"tool_use","name":"mcp__qdrant__qdrant-find","input":{}}]}}
{"message":{"role":"assistant","content":[{"type":"tool_use","name":"Bash","input":{"command":"uvx --from fastembed --with requests python scripts/qdrant-import.py --session-id abc --collection claude-memory"}}]}}
JSONL

# Neither side went through MCP: stored with the import script, consulted with
# the search script. Counting only MCP names reports this as write-only data.
cat > "$FIXTURE/script-both.jsonl" <<'JSONL'
{"message":{"role":"user","content":[{"type":"text","text":"please run an audit of the hook registrations"}]}}
{"message":{"role":"assistant","content":[{"type":"tool_use","name":"Bash","input":{"command":"python3 scripts/qdrant-search.py --recent Ralph --limit 5"}}]}}
{"message":{"role":"assistant","content":[{"type":"tool_use","name":"Bash","input":{"command":"uvx --from fastembed --with requests python scripts/qdrant-store-chunk.py --document x"}}]}}
JSONL

# Merely naming the script is not storing with it.
cat > "$FIXTURE/script-mentioned.jsonl" <<'JSONL'
{"message":{"role":"user","content":[{"type":"text","text":"please run an audit of the hook registrations"}]}}
{"message":{"role":"assistant","content":[{"type":"tool_use","name":"Bash","input":{"command":"find ~/.agents/skills -name 'qdrant-import*'"}}]}}
JSONL

HTTP_PORT=8973
python3 -m http.server "$HTTP_PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
HTTP_PID=$!
for _ in 1 2 3 4 5 6 7 8 9 10; do
  curl -sS -o /dev/null -m 1 "http://127.0.0.1:$HTTP_PORT" >/dev/null 2>&1 && break
  sleep 0.3
done

cat > "$FIXTURE/rag-reachable.json" <<JSON
{"version":2,
 "profiles":{"wsReach":{"match":{"path_components":["wsReach"]},
                        "roles":{"rag":{"kind":"qdrant",
                                        "endpoint":"http://127.0.0.1:$HTTP_PORT",
                                        "mcp_prefix":"mcp__qdrant__"}}}}}
JSON

# Port 1 is privileged and unbound: connection is refused at once, no waiting.
cat > "$FIXTURE/rag-unreachable.json" <<'JSON'
{"version":2,
 "profiles":{"wsUnreach":{"match":{"path_components":["wsUnreach"]},
                          "roles":{"rag":{"kind":"qdrant",
                                          "endpoint":"http://127.0.0.1:1",
                                          "mcp_prefix":"mcp__qdrant__"}}}}}
JSON

export AGENT_WORKSPACE_CONFIG="$FIXTURE/rag-reachable.json"
export AGENT_WORKSPACE_PROFILE=wsReach
export FAKE_MCP_OUTPUT="$FIXTURE/mcp-connected.txt"
check "S1 script-based store counts as a store"               "0" "$(run "$FIXTURE/script-stored.jsonl")"
check "S2 naming the script is not storing with it"           "2" "$(run "$FIXTURE/script-mentioned.jsonl")"
check "S5 script search counts as consulting the receiver"    "0" "$(run "$FIXTURE/script-both.jsonl")"

export FAKE_MCP_OUTPUT="$FIXTURE/mcp-down.txt"
check "S3 MCP down but endpoint reachable -> still block"     "2" "$(run "$FIXTURE/findings.jsonl")"

export AGENT_WORKSPACE_CONFIG="$FIXTURE/rag-unreachable.json"
export AGENT_WORKSPACE_PROFILE=wsUnreach
check "S4 MCP down and endpoint unreachable -> allow"         "0" "$(run "$FIXTURE/findings.jsonl")"

printf -- '---\npass=%d fail=%d\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
