# Persist (Knowledge Persistence)

Save session-discovered knowledge to appropriate long-term storage.

## When to Use

- `/claudify persist` — direct invocation
- `/cleanup run` Step 3 — automatic as part of session cleanup

## Workflow

### A. Documentation Recommendation

Suggest where to document new information discovered during conversation.

**Detection targets**: Troubleshooting solutions, project/infra structure, failed attempts, external service usage, environment setup.

**Location recommendations**:

| Information type | Recommended location |
|-----------------|---------------------|
| Project structure/config | Project `CLAUDE.md` or `README.md` |
| Infrastructure/server info | `pages/` or Logseq |
| Failed attempts | `pages/FAILED_ATTEMPTS.md` |
| External service integration | Project `docs/` |
| Personal workflow | `~/.claude/CLAUDE.md` (global) |
| Troubleshooting record | Logseq daily journal |

Exclude already-documented info and sensitive data (API keys, passwords).

### B. Infrastructure Documentation Check

**Skip condition**: No infrastructure work in session.

When infra work was performed, verify that discovered information (config file paths, port mappings, network routing, service connection structure) is documented in CLAUDE.md.

### C. Memory Save

Save session-learned project knowledge to persistent memory.

#### Pre-check: Storage Location Classification

| Information type | Storage | Example |
|-----------------|---------|---------|
| Volatile session-only fact (no reuse value beyond this session) | **Memory** (only if no domain skill owns the topic) | A one-time debug value, current resource usage snapshot |
| Tool/credential/config reference tied to an existing domain | **Skill** (`/skill-kit route` — add to the owning domain skill, e.g. a vault/credential-location table) | Server IP, API key location, install path |
| IaC/infra knowledge | **Skill** (`/skill-kit route`) | Terraform structure, ArgoCD procedures |
| Domain knowledge, procedures | **Skill** (`/skill-kit route`) | Deploy procedures, troubleshooting guides |
| Behavior rules, prohibitions | **Rules** | Mistake prevention (handled in improve topic) |

**Decision criteria**: Procedurally reusable → skill. Fits existing skill topic → skill. Tied to a credential/tool a domain skill already documents → that skill (not memory). Purely session-local with no domain skill owning it → memory. Claude Code's project memory is a harness-specific medium — prefer a skill destination whenever one owns the topic.

#### Storage Tool Priority

| Priority | Condition | Tool |
|----------|-----------|------|
| 1 | RAG receiver available (readyz / MCP responds) | RAG receiver structured-store dispatch — the cross-session semantic-search medium, already primary for 3-C.1 (session chunk) / 3-C.2 (structured fact). Prefer it whenever available. **Dual-write, not replacement**: RAG is the search index; pair every fact with a source-of-truth text entry (domain skill / memory) per 3-C.2 — RAG does not substitute for the durable text medium |
| 2 | Serena MCP available | `activate_project` → `list_memories` → `read_memory` → `edit_memory` / `write_memory` |
| 3 | RAG + Serena unavailable (fallback) | Claude Code auto memory (`memory/MEMORY.md` + individual `.md` files) |

**Serena procedure**: `read_memory` to check existing topic → `edit_memory` if exists, `write_memory` if not. No overwrites.

**Claude Code fallback note**: In vibe-kanban worktrees, save to **main project path** only.

#### What to Save (Context Preservation Focus)

- **Decisions**: Why this approach was chosen (vs alternatives)
- **Deploy/infra state**: Current versions, deploy progress, pending work
- **Discovered patterns/rules**: Code conventions, project-specific quirks
- **In-progress work**: Work state to continue in next session

**Not saved here** (experience-logger domain): Hot Files, tool usage patterns.

## Ralph Mode

**Detection**: see SKILL.md — only when both `.ralph/` directory exists **and** environment variable `RALPH_LOOP=1` is set.

A (documentation location) / B (infra doc check): detect + record to `.ralph/improvements.md` only — these are storage-location judgment calls that would normally prompt the user.

**C (Memory Save) — split by sub-step, do not blanket-restrict (HARD STOP)**: the RAG receiver session-chunk import (cleanup/run.md 3-C.1) and structured discovery-chunk store (3-C.2) carry **no ask even in normal mode** (see cleanup/run.md's top-level "Ask-bypass axis vs. passive-persistence axis" carve-out) — they still run automatically in Ralph Mode, logging the result to `.ralph/improvements.md` instead of a chat report row. Only the Serena/Claude-Code-memory storage-location classification (Pre-check table above) stays recording-only, since picking a destination is itself a judgment call.

## Phase 2 Integration

This topic does NOT call AskUserQuestion directly. All findings are returned to the caller (cleanup run.md) for batch Phase 2 confirmation.

**Return format** (internal):
```
{
  docs: [{ label, description, location }],
  infra: [{ label, description }],
  memory: [{ label, description, storageType: "serena"|"claude-memory"|"skill" }]
}
```
