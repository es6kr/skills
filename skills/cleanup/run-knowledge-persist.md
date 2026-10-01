# Step 3: Knowledge Persist (documentation + infra check + memory)

Step 3 of the `run` pipeline. Entry point: [run.md](./run.md).

## Step 3: Knowledge Persist (documentation + infra check + memory)

**Topic reference**: [claudify/persist.md](../claudify/persist.md) — planned conversion to a `Skill("claudify", "persist")` call.
Currently the procedure below runs directly within cleanup.

Store knowledge discovered in the session to the appropriate location.

### 3-A. Documentation recommendation (including LLM Wiki scope check — HARD STOP)

Suggest a location to document new information discovered during the conversation. **This is an explicit check, not a silent skip** — same discipline level as 3-C.1/3-C.2, just a different destination.

**Detection targets**: troubleshooting solutions, project/infra structure, failed attempts, external service usage, environment configuration

**Documentation location recommendations**:

| Information type | Recommended location |
|----------|----------|
| Project structure/configuration | The project's `CLAUDE.md` or `README.md` |
| Personal/dev-machine infra fact (VPN client quirk, local tool path, this-session-only debugging) | Domain skill topic (`/skill-kit route`) + RAG fact point (3-C.2) — **not** the LLM Wiki |
| Company/domain knowledge (a concept, process, or fact relevant to teammates outside the current chat — the kind of thing a new hire or another department would need explained) | The workspace's **LLM Wiki** (`<workspace>/llm-wiki/`), if one exists — see below |
| Failed attempts | `pages/FAILED_ATTEMPTS.md` |
| External service integration | The project's `docs/` |
| Personal workflow | `~/.claude/CLAUDE.md` (global) |
| Troubleshooting record | Today's Logseq journal |

- Exclude information that's already documented, or sensitive information (API keys, etc.)

**LLM Wiki scope check (trigger: does `<workspace>/llm-wiki/AGENTS.md` exist for the current workspace?)**:

1. If no `llm-wiki/` exists in the workspace, skip this sub-check (report "no LLM Wiki in this workspace").
2. If it exists, **read `<workspace>/llm-wiki/index.md`'s category list first** (the `## <Category> (\`pages/<domain>/\`)` headers) — this is the Wiki's actual, currently-in-use scope, not just its abstract `AGENTS.md` definition. A category like "Harness & Tools" can already cover exactly the kind of personal-tooling/harness-debugging knowledge that the abstract "company/domain knowledge for teammates" framing (below) would wrongly exclude on its own.
3. Only after checking the real category list, ask: does anything this session discovered fit an **existing category** (including a tooling/harness category if one exists), or the Wiki's abstract scope per `AGENTS.md` (curated domain knowledge — concepts, processes, meeting outcomes, terms someone outside this chat would need explained) — **as opposed to** genuinely session-local/one-off debug values that belong in RAG only?
4. Never write directly to `pages/*.md` — the Wiki's own HARD STOP requires raw knowledge ingestion first (`raw/<slug>.md` with a real `source_path`), then `pages/` updates derive from that raw source. Dispatch to the raw knowledge ingest skill (e.g. `raw-ingest` if available); do not hand-author `pages/` content inline from cleanup.
5. State the outcome explicitly in the Step 5 comprehensive report, even when the answer is "nothing this session belongs in the Wiki" — silence here is exactly the gap this section closes.

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat writing to a skill file (e.g., an infra fact added to a domain skill topic) as satisfying the LLM Wiki check too | They're different destinations for different audiences — skill files are Claude Code's own operational knowledge; the Wiki is curated for human teammates. Doing one doesn't exempt checking the other |
| 2 | Recommend the Wiki for every infra/troubleshooting fact discovered this session, regardless of audience | Personal dev-machine/session-local facts (a VPN client quirk on *this* machine, a local file path) stay in skill/RAG — pushing them into the company Wiki is scope creep the Wiki's own curation principle doesn't want |
| 3 | Silently omit the Wiki row from the Step 5 report when there's nothing to store | Always state the outcome — "N candidates found" or "0 candidates — session content was tooling-local, not company-facing" |
| 4 | Author `pages/*.md` directly from cleanup to save a step | Raw knowledge ingestion first (HARD STOP per the Wiki's own `AGENTS.md`) — cleanup dispatches to the ingest skill, it does not hand-write pages |
| 5 | Apply only the abstract "company/domain knowledge for teammates" definition from `AGENTS.md` and conclude "0 candidates" without reading `index.md`'s actual category list first | Read `index.md`'s categories before judging scope — a category already covering harness/tooling knowledge (e.g. "Harness & Tools") means session-local-sounding tooling facts can still be in-scope. The abstract definition alone under-scopes relative to the Wiki's real, curated content |

**Self-check (every cleanup run, before the Step 5 report)**:
1. Does `<workspace>/llm-wiki/AGENTS.md` exist? If no, report N/A and move on.
2. If yes, did you Read `index.md`'s category list before judging scope? If not, do that first — do not judge from the abstract `AGENTS.md` definition alone.
3. Does any session discovery meet an existing category's actual scope (not just the abstract "company knowledge" framing), or the Wiki's abstract scope for teammates?
4. If yes, dispatch to the raw knowledge ingest skill — never hand-author `pages/`.
4. State the explicit outcome (candidates found + dispatched, or none) in the Step 5 report — this row is mandatory whenever `llm-wiki/` exists in the workspace, matching the RAG row's mandatory-reporting discipline.

### 3-B. Infra documentation check

**Skip condition**: skip if there was no infra work

If infra-related work was performed, check whether the discovered information has been documented in CLAUDE.md.

### 3-C. Memory storage

Store project knowledge learned in this session to memory.

#### Pre-review: storage location classification

| Information type | Storage location | Example |
|----------|----------|------|
| Volatile session-only fact (changes every run, no reuse value beyond this session) | **Memory** (only if no domain skill owns the topic) | Current resource usage snapshot, a one-time debug value |
| Tool/credential/config reference tied to an existing domain (Vault path, API key location, server IP, install path) | **Skill** (`/skill-kit route` — add to or create a topic in the owning domain skill, e.g. `es6kr/vault.md`'s credential-location tables) | Where a PAT/token/config file lives, which CLI manages a service |
| Infra/IaC configuration knowledge | **Skill** (`/skill-kit route`) | Terraform structure, ArgoCD management procedure |
| Domain knowledge, procedure, guide | **Skill** (`/skill-kit route`) | Deployment procedure, troubleshooting guide |
| Behavioral rule, prohibition | **Rules** | Mistake-prevention rule (handled in Step 2 retrospect) |

**Judgment criterion**: usable procedurally → skill, addable to an existing skill topic → skill, tied to a credential/tool that a domain skill already documents → that skill (not memory), purely session-local with no domain skill owning it → memory.

**Why this table changed**: Claude Code's project memory (`~/.claude/projects/*/memory/*.md`) is a harness-specific, non-portable medium — it disappears in other environments (Antigravity, OpenClaw) and doesn't travel with the workspace's own rule/skill system. A credential-location or tool-reference fact is exactly the kind of thing a future session (in any environment) needs to rediscover — routing it to memory silently ties it to "this Claude Code project only." Prefer the domain skill that already owns the topic (see the existing credential-location tables in `es6kr/vault.md`, `es6kr/infra.md` as the established pattern) over creating a new memory file.

#### Storage tools (usable in parallel — different purposes)

| Tool | Condition | Purpose | Invocation |
|------|------|------|------|
| **RAG receiver import dispatch** | RAG receiver available (readyz responds) | **Whole-session semantic chunk** — searchable via the receiver's find tool for conversation flow in the next session | 3-C.1 procedure below |
| Serena MCP | `activate_project` responds | Structured key-value facts (memory_set/memory_get) | `list_memories` → `edit_memory` / `write_memory` |
| Claude Code auto memory | Only for facts genuinely valid in Claude Code alone (this harness's own settings/session state) — NOT a default fallback for domain/reference facts. See "Pre-review" table above; most facts route to a skill instead | Markdown file (`memory/MEMORY.md` + individual) | Edit/Write |

RAG and Serena are used in parallel where available. Claude Code auto memory is conditional, not a third parallel default — check the Pre-review table first; a skill destination usually applies instead.

#### 3-C.1 Session semantic chunk storage (RAG receiver dispatch)

**Call when the condition is met**:

##### Availability check — 2 stages (HARD STOP)

This step is mandatory before entering RAG store. **Do not conclude "unreachable" from a single signal**.

| Order | Signal | Meaning | Action |
|-----|------|------|------|
| 1 | RAG receiver MCP tool available (in the system reminder's "available tools" list or matched via `ToolSearch` — the receiver's store/find tool name) | MCP is already connected to the receiver — primary availability signal | Run [rag-store.md](./rag-store.md) "Purpose-fit priority for 3-C.1" detection procedure FIRST — a purpose-built session-importer script (medium 2) outranks this generic MCP tool for whole-session import, even though the MCP tool is available. Only call the MCP store tool directly for 3-C.1 if no purpose-built importer is found |
| 2 | The endpoint readyz probe explicitly documented by the receiver skill (use only the endpoint from the receiver's `<skill>:<topic>.md` doc) | Direct HTTP probe — secondary availability signal | MCP not connected, but the endpoint is alive. Enter via the script path |
| **FAILED** | (1) MCP unavailable AND (2) endpoint probe timeout/HTTP 5xx | Both must fail to be unreachable | **Entire cleanup status = FAILED. Do not declare "✅ Complete"** — apply the "RAG store failure = cleanup failure" procedure below |

##### After a successful import: advance the receiver's gap baseline (HARD STOP)

The session import performed here is the **same operation** that a receiver's mid-session gap hook triggers on its own. Such a hook typically decides whether to fire by comparing the transcript's current line count against a per-session checkpoint file that, by default, **only the hook itself writes**. If cleanup imports without advancing that checkpoint, the baseline stays stale — right after this cleanup the hook still measures against the old point, fires again, and demands a duplicate import of the very turns 3-C.1 just stored.

So on a successful 3-C.1 import, advance the receiver's baseline **in the same step**. The receiver skill documents the exact path and command (for the es6kr receiver, see its `qdrant-import` topic, "The checkpoint is a shared baseline"). Skip only when the receiver exposes no such checkpoint.

| # | Don't | Do |
|---|-------|-----|
| 1 | End 3-C.1 at "import succeeded" and leave the checkpoint untouched | Advance the receiver's baseline in the same step — the import is not finished until the state tracking it agrees |
| 2 | Treat the checkpoint as the hook's private state | It records "where a session import last happened", whichever entry point performed it |
| 3 | Let the hook fire right after cleanup and satisfy it with another import | That import is a no-op re-run over turns already stored; the fix is the stale baseline, not another import |

##### RAG store failure = cleanup failure (HARD STOP)

**3-C.1 RAG store is a mandatory cleanup step — on failure/unavailability, report the entire cleanup as FAILED.** RAG store is the core medium for "session-end state preservation" (this skill's philosophy #2), and if the session ends in a missed state, the opportunity to store the session chunk is effectively lost ("retry next session" is a weak trigger, so actual retries rarely happen).

**On failure, all of the following are mandatory**:

1. **Recovery-attempt decision is a mandatory ask, not an autonomous judgment (HARD STOP)** — when the failure occurs and connection info for the underlying service is knowable (an endpoint documented in the receiver topic, a local process/port, a VPN state, etc. — i.e., there is *something* to check or restart), do NOT autonomously decide either "attempt recovery" or "skip straight to fallback." Call `AskUserQuestion` immediately: state the failure (tool/endpoint + error text), and offer options such as "Attempt recovery now (check/restart the underlying service, re-probe)" / "Skip recovery — fall back to local pending queue now" / "Investigate more (I'll look at the connection details first)". Only proceed with whichever path the user selects. This applies even mid-cleanup — do not defer the ask to the end-of-cleanup Phase 2 batch, since the RAG store step blocks subsequent steps' correctness (retry-task registration content depends on the outcome).
   - **Exception**: if no connection info is knowable at all (no documented endpoint, no local process to check, receiver skill provides no diagnostic path) — there is nothing to ask about; skip directly to the FAILED procedure below without asking (asking "recover?" with no actionable path is a hollow ask).
2. On confirmed recovery failure (whether reached via the user selecting "skip" or via an attempted-and-failed recovery), mark the Step 5 completion-report table's "3-C.1 RAG Store" row as **`❌ FAILED`** (not worded as "Skipped"/"held")
3. Use **"⚠️ cleanup FAILED (RAG store failed)"** instead of "✅ cleanup complete" in the report title/header
4. **Medium (4) local pending-import queue file — the actual preservation mechanism (HARD STOP, do this BEFORE step 5)**: write `~/.claude/skills/cleanup/data/rag-pending/<session-uuid>.md` per [rag-store.md](./rag-store.md) "Medium (4)" spec (session UUID + date, artifact paths, distilled facts with metadata, one-line unreachable-reason). A `TaskCreate`/fix_plan retry note alone is a reminder, not preservation — per rag-store.md's own self-check, the queue file is the durable guarantee that survives even if no future session reads the retry task.
5. **Retry task registration obligation**: register a "Retry RAG store (session <UUID> + N artifacts)" pending task via `TaskCreate` — do not end with carryover text alone. This is supplementary to step 4's queue file, not a substitute for it.
   - **Fallback when `TaskCreate` itself is disconnected (HARD STOP)**: do not silently drop the retry obligation. Register it in the workspace's `fix_plan.md` `## Hold` section instead, using the same `[BLOCKED] ... **trigger: <condition>**` format as other hold items (trigger = "Task tools reconnect" or equivalent). This mirrors step4-wrapup.md's medium-separation principle (BLOCKED external-wait items go to fix_plan.md hold, not a task) extended to the case where the task-tracking tool itself is the unavailable dependency. Step 4's queue file write still applies regardless of `TaskCreate` availability — it is a plain file write, not gated on the task tool.
6. Report the failure cause (MCP disconnected / endpoint down / underlying network down / **TaskCreate disconnected**) + recovery path + queue file path in 1 line

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Declare "✅ Session cleanup complete" after skipping the RAG store | RAG failure = cleanup FAILED. State ⚠️ FAILED in the header |
| 2 | End with only "Skipped — retry candidate for next session" carryover text | Write the medium (4) local pending-import queue file (item 4 above) + register a `TaskCreate` retry task (pending) + report failure cause/recovery path |
| 3 | Judge "complete" because other cleanup steps finished | Even 1 mandatory step FAILED = the entire cleanup is FAILED. Show per-step status in the report table |
| 4 | Judge FAILED immediately after confirming RAG receiver unavailability with no recovery decision | Confirm the underlying connectivity state, then `AskUserQuestion` whether to attempt recovery (per item 1 / row 5) before judging FAILED — do not autonomously restart |
| 5 | Autonomously attempt recovery (or autonomously skip it) when connection info is knowable, then only report the outcome after the fact | `AskUserQuestion` first whenever there's an actionable recovery path — recovery may touch infra state (restarting a service, etc.) the user should decide on, not something to silently do or silently skip |
| 6 | Treat "I have a safe local pending-queue fallback" as satisfying the recovery-attempt obligation | The fallback (medium 4) is the *terminal* step after recovery is declined/fails — it does not substitute for asking whether to attempt recovery first |

**Don't / Do**:

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Guess an endpoint on your own (default localhost port, etc.) | Use only the endpoint documented in the receiver skill topic (`<skill>/<topic>.md`). Do not check a guessed endpoint |
| 2 | Downgrade the MCP-available reminder to ambient context + judge based solely on endpoint probe | The system reminder's "MCP available" signal = primary availability evidence. Prioritize ToolSearch + tool calls |
| 3 | Decide to skip RAG store after 1 probe failure | Both stages above must be checked. Even if the probe fails, proceed with import if MCP is available (MCP abstracts the endpoint) |
| 4 | Narrowly interpret "readyz response" as an HTTP probe only | An MCP call round-trip success is also included in "readyz response" |
| 5 | Enter endpoint checking without reading the receiver topic body | Reading the receiver topic's endpoint section is mandatory → use only the documented address |

**Self-check (immediately before entering 3-C.1 every time)**:
1. Does the system reminder show the RAG receiver MCP tool as available? — If yes, signal 1 satisfied, enter immediately
2. Attempt to load the receiver store/find tool schema via ToolSearch — success satisfies signal 1
3. If both 1 and 2 are unmet, probe the endpoint documented in the receiver topic (query for the exact address in the receiver topic first)
4. If the response is OK, enter
5. If 1, 2, and 3 all fail, **is there any connection info to act on** (documented endpoint, known local process/port, VPN state)? → If yes, `AskUserQuestion` before doing anything else (recovery vs skip vs investigate) — do not decide autonomously. If no actionable info exists at all, apply the **cleanup FAILED procedure** directly (above)
6. **Before calling ANY store/import command, have you Read the receiver skill's topic file THIS TURN** (e.g. `es6kr/qdrant-import.md`)? — A generic MCP tool (e.g. `mcp__qdrant__qdrant-store`) succeeding is NOT proof the receiver's documented protocol (session-turn import script, WSL execution requirement, sanitize/compress preprocessing, idempotent chunk IDs) was followed. "The tool call worked" ≠ "the receiver's Mode A/B/C contract was satisfied" — Read the topic file first, then use its documented invocation (case history: failed-attempts.md "RAG store/search handled ad-hoc instead of the existing permanent script")

##### Invocation command (delegated to the receiver topic)

The receiver's endpoint, script, and sanitize policy are defined by the receiver topic (`<skill>:<topic>.md`). cleanup performs only abstract dispatch:

```bash
# For confirming signal 2 (skip if signal 1 is satisfied)
# The endpoint is delegated to the receiver topic's availability procedure
# (e.g., the URL documented in the receiver topic)

# Store the session chunk (idempotent — re-importing the same session embeds/upserts only new turns)
# --raw: current session = the user's own context + active JSONL, so opt out of the receiver's sanitize procedure
#   (see the receiver topic's "opt-out conditions" for importing the current session)
<rag-import-command-per-receiver-topic> \
  --session-id <current-session-uuid> \
  --raw
```

`<current-session-uuid>` is extracted from `/session id` or the "Current session ID" inject from the UserPromptSubmit hook. For automatic invocation, the user enters the RAG-import skill's trigger command → the hook injects both the session/message uuid.

If the RAG receiver is unavailable (probe timeout/HTTP 5xx), **apply the cleanup FAILED procedure** (see "RAG store failure = cleanup failure" above — do not proceed to skip). The session chunk complements the fix_plan/failed-attempts context — a separate medium from fact storage (Serena/auto memory).

**Reason for using `--raw`**:
- The current session's JSONL is still being written — in-place clean-profanity modification risks damaging the active file
- This is the user's own raw context (profanity/emotional expressions have value as semantic search signals)
- Not an externally shared medium (internal vector store on a private network)

For importing other sessions (past sessions, sessions planned for external sharing, etc.), omit this flag and follow the receiver topic's sanitize procedure.

#### Storage targets (focused on context preservation)

- **Decisions**: why this approach was chosen (compared to alternatives)
- **Deployment/infra state**: current version, deployment progress, pending work
- **Discovered patterns/rules**: code conventions, project-specific quirks
- **Work in progress**: work state that needs to continue in the next session

#### 3-C.2 Distilled reusable fact dual-write (structured precise recall)

3-C.1 (session turn chunk) is for **preserving conversation flow**. However, **reusable single facts** discovered this session (infra details · decisions · gotchas) are hard to recall precisely if buried in turns. Such facts should be **recorded in both media together**:

| Medium | Role | Method |
|------|------|------|
| (a) Domain skill / memory | **Source of truth** (permanent text, always-loaded or on-demand) | Add a section to a domain skill topic (use `/skill-kit route` to decide the location) or a project memory file |
| (b) RAG receiver separate structured point | **Semantic search** (distinct from session turns, with type/topic metadata) | The receiver's fact-storage script (below) |

**Dual-write criteria — record as a fact if any of the following applies**:
- An infra fact that took significant time to diagnose (paths, ports, mount points, etc.)
- Load-bearing knowledge that the next session/another person would hit the same wall on
- Not "why it turned out this way" (turn flow) but "what is the fact" (a standalone fact)

**(b) RAG receiver fact point storage** (delegated to the receiver topic's fact-storage procedure):

```bash
<rag-fact-command-per-receiver-topic> \
  --id-seed "fact:<topic-slug>" \
  --document "<self-contained fact text>" \
  --type infra-fact --project <repo/domain> --category <cat> --topic <slug>
```

- `--id-seed` is stable → re-recording the same fact updates it (no duplicates)
- See the receiver topic's "single fact structured storage" section
- **Record (a) the source-of-truth first, then (b) the RAG receiver point** — the source of truth is authoritative, the RAG receiver is a search index

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Only import the session (3-C.1) and leave distilled facts buried in turns | Record reusable facts to both (a) domain skill/memory + (b) RAG receiver fact point |
| 2 | Write an ad-hoc script on the spot to record a single fact in the RAG receiver | Reuse the receiver's fact-storage script |
| 3 | Only a RAG receiver point, no domain skill | Source of truth (skill/memory) first. The RAG receiver is a search aid, not the source of truth |
| 4 | Treat "I wrote a memory/skill file this session" as evidence that dual-write is already satisfied, and report 3-C.2 as "none — already covered by the memory files above" | A memory file write is (a) only. It is not evidence against doing (b) — it is evidence a fact was distilled, which is exactly 3-C.2's trigger. Writing (a) without (b) is the Don't-row-3 violation restated with different wording |

**Self-check (immediately before writing the Step 5 "3-C.2" report row)**: for **each** memory/skill file (a) written or edited in this session's Step 3-C, was a corresponding RAG receiver fact-point (b) also stored for that same fact? Enumerate them by filename — if any (a) has no matching (b), that is an open dual-write, not a completed one; store it now before reporting 3-C.2. "Already covered by memory files" is never a valid 3-C.2 skip justification — the only valid skip is "no reusable discovery this session" (no memory/skill files were written at all).

#### 3-C.3 Check for missed active plan/research/analysis RAG store (HARD STOP)

The `skill-usage.md` "Generic skill artifact RAG store obligation" rule says **immediately after writing** is the store trigger. However, without an enforcement medium (a hook, etc.), the write-time trigger is sometimes missed. cleanup serves as that fallback — check active artifacts generated in this session for anything missing from RAG + store them.

**Check targets (Hybrid Sweep — Option C)**:
- `**/.ralph/docs/generated/{plan,research,analysis,report,postmortem}-*.md`
- `**/.omc/plans/*.md`
- **Session-Brain Root Sweep (`<appDataDir>/brain/<conversation-id>/*.md`)**:
  - Direct non-recursive check of all `.md` files in the active session's brain root.
  - **Automation Helper Script**: `python .agents/skills/cleanup/scripts/hybrid_sweep_rag.py <session_brain_dir>`
  - If a `.metadata.json` sidecar exists (`<file>.md.metadata.json`), check `userFacing` value.
  - Fallback: If no `.metadata.json` or schema differs, exclude known internal control files (`task.md`, `ask.md`), and treat all other unrecognized `.md` files (e.g. `outputs_classification_report.md`, `llm_wiki_structure_report.md`) as active artifact candidates for RAG store.
- **Dual LLM Wiki Sync Helper**:
  - `python .agents/skills/cleanup/scripts/sync_dual_wiki.py` (Syncs public artifacts between the workspace's own internal LLM Wiki repos)


**Procedure**:

1. **Identify files via Glob/Hybrid Sweep with mtime ≥ session start time** — active artifacts written/edited in this session (including unrecognized session-brain `.md` files captured via Option C)
2. **Query the RAG receiver's scroll for each file**: search for chunks whose `filename` or `source_path` metadata matches that file path
3. **Branch**:
   - 1+ existing chunk → already stored. Skip
   - 0 existing chunks → not stored. Store immediately
4. **Storage medium**:
   - Full-body RAG chunk: the receiver's raw-import command with `--file <path>` or an equivalent medium (prefer the vendor receiver's store tool if available)
   - If a distilled fact is clearly extractable, also do the 3-C.2 dual-write procedure (optional)
5. **Report the store result quantitatively** — format `RAG store summary: N chunks added for {file}` (apply the skill-usage.md "RAG store report format" rule)

**Don't / Do**:

| # | Don't | Do |
|---|-------------|-----------------|
| 1 | Import only the 3-C.1 session chunk and assume it's sufficient since artifact-specific facts are included in it | Session chunks preserve turn flow. Artifact bodies are stored as separate fact points/chunks. Search precision differs |
| 2 | Handle only via `.bak/` archive-time REPEAT items (does not cover active artifacts) | Also check active artifacts in this sub-step. Archive time is a separate trigger |
| 3 | Report as text "unsure if there are artifacts at session end" | Glob + scroll are mandatory. Do not assume 0 — confirm with primary sources |
| 4 | Skip and end when the RAG receiver is unavailable | RAG receiver unavailability = this sub-step is BLOCKED. State it in the Step 4.5 BLOCKED row + set a trigger for the next session |
| 5 | Check an IDE session-brain directory for only one known file pattern (e.g. `walkthrough.md`) and treat the directory as covered | Every file pattern the directory can produce needs its own Glob row — a directory being "already on the list" does not mean every artifact type inside it is checked |

**Self-check (every time during cleanup Step 3)**:
1. Identify `**/{plan,research,analysis,report,postmortem}-*.md` files written/edited this session (Glob mtime filter)
2. Count of identified files = N. If N=0, skip
3. If N≥1, run the RAG receiver's scroll per file → check existing chunk count
4. Files with 0 chunks = storage obligation. Call immediately + report quantitatively
5. Omitting the report = this sub-step is incomplete

**Ralph mode**: still stores un-stored files (per the "Ask-bypass axis vs. passive-persistence axis" carve-out in the top-level "Ralph Mode" section — 3-C.3 needs no ask in normal mode either). Log the artifact list + store result to `.ralph/improvements.md` instead of a chat report row.

**Ralph mode**: 3-A/3-B (documentation-location recommendation, infra-doc edit check) perform detection+recording only (`.ralph/improvements.md`) — these would normally prompt the user for a location/edit decision. **3-C.1/3-C.2/3-C.3 (RAG session/discovery/artifact store) are exempt from this restriction and still run automatically** — they carry no ask in normal mode, so Ralph Mode's ask-bypass rationale does not apply to them (see top-level "Ask-bypass axis vs. passive-persistence axis"). Only direct modification of rules/skills/hooks/memory files stays recording-only.

#### 3-C.4 Workspace fix_plan-history sync (mode C — HARD STOP)

**3-C.1/3-C.2 alone do not satisfy a workspace's "all deliverables must be persisted" obligation** — session chunks and discovery chunks are conversation-shaped, not deliverable-shaped. When `fix_plan.md` gained new `## Completed` entries this session, the deliverable record itself (not just the conversation about it) must reach the RAG store. `rag-store.md`'s "fix_plan.md Completed Item RAG Sync + Delete Obligation" section owns the full sync/delete procedure — this sub-step's only job is to make sure that procedure actually gets invoked as part of cleanup, instead of remaining a rule that's easy to forget because nothing in this checklist named it.

**Procedure**:
1. Did this session add any `## Completed` entries to the current workspace's `fix_plan.md`? If no, skip (report "none — no new Completed entries this session")
2. Does the current workspace expose a fix_plan→RAG sync script (e.g. a `fix-plan-to-qdrant`-style topic under that workspace's own skill)? Search installed skills' Topics tables for a description matching "fix_plan Completed → RAG" / "workspace fix-plan history". If none exists, report "no sync script for this workspace" — this sub-step does not mandate building one
3. If both hold, run `rag-store.md`'s "fix_plan.md Completed Item RAG Sync + Delete Obligation" procedure (bulk-sync → delete synced `## Completed` body) and report the point count

**Don't / Do**:

| # | Don't | Do |
|---|-------|-----|
| 1 | Treat 3-C.1 (session import) as covering fix_plan's Completed history because the conversation that produced it was imported | Session import preserves turn-by-turn dialogue; it does not make "what got completed, and when" independently queryable. Run the workspace sync script separately |
| 2 | Skip this sub-step silently because it's new and easy to forget | Report one of the three outcomes explicitly (synced P points / none this session / no script for this workspace) in the Step 5 table |

**Self-check (every time during cleanup Step 3, after 3-C.3)**:
1. Grep this session's `fix_plan.md` diff for new `## Completed` lines — count ≥1?
2. If yes, does a workspace-specific sync script exist? (Topics-table search, not a guess)
3. If both yes, run it and get the point count before reporting Step 5

---
