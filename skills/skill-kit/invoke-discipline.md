# Skill Invoke Discipline — slash command, multi-topic, and dispatch rules

Discipline rules for invoking skills correctly: slash command → Skill tool, multi-topic topic Read, post-decision auto-invoke, interactive script execution, and vendor dispatch.

## 1. Slash command inject ≠ Skill tool call (HARD STOP)

System auto-injecting SKILL.md content on `<command-name>/<slug></command-name>` input ≠ Skill tool call completion. Inject = text exposure in context only. The procedure execution obligation starts only with a `Skill` tool call.

### Don't / Do

| # | Don't | Do |
|---|-------|----|
| 1 | See SKILL.md content from slash command inject → judge "skill loaded" → skip tool call + do inline procedure | Call `Skill("<slug>", "<args>")` in the same response turn after inject. Inject = text exposure; tool call = procedure start signal — they are separate acts |
| 2 | Assume "inject = equivalent to tool call" | Inject = system shows SKILL.md. Tool call = author's explicit act declaring procedure entry intent. No tool call trace = cause for `fix` in next turn |
| 3 | Avoid tool call thinking "calling Skill again would duplicate SKILL.md exposure, inefficient" | Duplicate exposure is system design — not the author's responsibility domain. Tool call is the forcing function for procedure start |
| 4 | See inject text and perform Edit/Bash etc. procedure inline directly | Inline before tool call = rule violation. Skill call → return → start from Step 1 is the correct path |

### Self-check (immediately after slash command input)

1. Does the user's previous input contain `/<slug>` or `<command-name>/<slug></command-name>` pattern? → If match, this rule applies
2. Does the same response turn include a `Skill("<slug>", ...)` tool call? → If no, call immediately (inline procedure forbidden)
3. Even if system injected SKILL.md content, tool call is a separate obligation — inject body is for reference only
4. After tool call returns SKILL.md, re-read and start from Step 1

Violation case reference: `failed-attempts.md` "slash command → Skill tool call missing"

## 2. Multi-topic skill — each topic `.md` Read before step execution (HARD STOP)

In multi-topic skills with a Topics table + Quick Reference + "Step execution order" in SKILL.md, the **Quick Reference is an index (index), not the procedure body**. The actual procedure for each step is in the topic `.md` file — **must Read the topic `.md` before executing that step**.

### Don't / Do

| # | Don't | Do |
|---|-------|----|
| 1 | After `Skill("consolidate", ...)` returns, read Quick Reference → immediately run gh query + inline Edit + self-authored Summary | Follow "Step execution order" in Quick Reference, **sequentially Read** each topic — `pr.md` Read → execute Steps 1·2·2.4·2.5·2.6·2.7 → `collect.md` Read → execute Step 3 → ... to final step |
| 2 | Look at Topics table + Quick Reference only and judge "understood the procedure" | Topics table is an index. Procedure body is in each topic `.md`. Inferring procedure without Read = skill bypass |
| 3 | Read only some topics and skip rest as "contextually understood" | Read **all** topics listed in "Step execution order" in order. Skip = partial procedure omission |
| 4 | Not aware of skip until user says "/cmd wasn't called, was it?" | Self-check "Have I Read this step's topic.md?" before each step execution |
| 5 | Write self-authored Summary format based on Quick Reference one-liner ("Step 7 Post Summary") | Read `post.md` → apply the Summary template/Don't-Do/self-check stated there directly |
| 6 | On a repeat invocation of the same skill+topic later in the session (e.g., a Stop hook re-triggers a skill call it triggered earlier), skip the topic `.md` Read because "I already read it earlier this session, I remember the command" | Read the topic `.md` again on **every** invocation, regardless of how recently it was read in this same session. In-session memory of a command is not a substitute for re-verifying against the authoritative doc — the doc may have changed, or memory may silently drift from the actual current syntax |

### Self-check (immediately after every multi-topic skill call)

1. Does the returned SKILL.md have a Topics table + "Step execution order"? → Yes = multi-topic skill
2. Was the first topic in "Step execution order" read with the Read tool? → No → read immediately
3. After reading the first topic, were the step procedures inside followed? — Quick Reference one-liner ≠ topic body
4. Before entering the next step, was the next topic read? — repeat per step
5. After all steps complete, was the final topic (usually next.md etc.) also read + applied?
6. **Is this a repeat invocation of a skill/topic already read earlier in this same session?** → Read it again anyway. "I read this topic before in this session" is not a valid reason to skip the Read on a later invocation

### Multi-topic skill identification signals

At least 1 of these in SKILL.md:
- `## Topics` or `## Commands` table (Topic / Description / Guide row structure)
- "Step execution order" or topic execution sequence text
- Topic Dependencies diagram
- `## Quick Reference` that summarizes each topic in 1-2 lines

If any match, this rule applies. Single-topic skills (SKILL.md only, no topic files) are exempt.

## 3. Post-decision skill topic auto-invocation (HARD STOP — ask bypass forbidden)

**Immediately after a user selects an option / direction is confirmed, if the next procedure is mapped to a skill topic, calling the `Skill` tool is the #1 priority.** After a confirmed decision, asking "shall we enter the next procedure?" via AskUserQuestion again is forbidden.

### When to apply

| Decision moment | Next procedure | Skill topic to call |
|----------------|---------------|---------------------|
| Fix direction (A/B/C/D) confirmed (code change PR needed) | GitHub issue registration | `Skill("github-flow", "register")` |
| Option D / implementation entry confirmed | issue → branch → implement | `Skill("github-flow", "register")` → follow procedure |
| After PR consolidate + merge decision | merge procedure | `Skill("github-flow", "merge")` |
| After external feedback response confirmed | consolidate procedure | `Skill("consolidate", "pr-review")` |
| After plan approved (no issue exists) | plan → issue conversion | `Skill("github-flow", "plan-to-issue")` |
| After review feedback apply confirmed | code fix + summary update | `Skill("github-flow", "review-apply")` |

### Don't / Do

| # | Don't | Do |
|---|-------|----|
| 1 | After Option D confirmed, re-present "issue register + implement / issue only / hold" AskUserQuestion | Call `Skill("github-flow", "register")`. The topic procedure handles redundant confirmation, body writing, and entry decision |
| 2 | After decision, ask "shall we enter the next step?" | Decision = intent to proceed expressed. If next procedure maps to a skill topic, call it. ask only when there are **real branch points** (hold vs different direction) |
| 3 | Skip checking if skill topic exists → bypass with ask | Self-check immediately after decision: "Does this next procedure map to a skill topic?" — confirm with `Glob ~/.claude/skills/<domain>/*.md` |
| 4 | "Topic has another ask inside, let me ask ahead of time" reasoning | Topic-internal ask is part of the procedure — after calling the topic, let it ask on its own |
| 5 | Optionize procedure entry itself ("issue register + implement" as a choice) | State in option description "(after deciding, github-flow register will be called automatically)". Only diverging branches (hold / different direction) are real options |

### Self-check (immediately after every direction/option decision)

1. Did the user select an option or is a direction confirmed? (Yes/No)
2. If yes, what is the next procedure? — state clearly in one sentence
3. Does that procedure map to a skill topic? — check the table above + `Glob ~/.claude/skills/<domain>/<topic>.md`
4. If mapped → **call `Skill` immediately**. Re-calling AskUserQuestion forbidden
5. If not mapped or a real branch (hold etc.) → AskUserQuestion allowed. But options must be **real branches only**

## 4. Interactive script execution (HARD STOP)

**If a skill has scripts (`scripts/*.sh`), script call is #1 priority.** Even if interactive (`read`, `select`, interactive prompt) and cannot run from Bash, don't abandon the script.

### Don't / Do

| # | Don't | Do |
|---|-------|----|
| 1 | Script is interactive so can't run → manually substitute find/grep/rm | Guide user to run `! bash <script-path> <args>` |
| 2 | "Doesn't work in Bash, I'll do it manually" decision | `!` prefix = Claude Code feature for user to run interactive commands directly in session |
| 3 | Enter manual procedure without user confirmation | AskUserQuestion: "script `!` run vs manual handling" — only enter manual path after confirmation |

## 5. Generic skill vendor dispatch auto-supply (HARD STOP)

When a generic skill exposes dispatch flags (`--<verb>=<skill>:<topic>` form), the caller (Claude) must auto-detect available environment receivers + supply them. Even if the user didn't explicitly type it, it's the caller's responsibility.

### Don't / Do

| # | Don't | Do |
|---|-------|----|
| 1 | User didn't type the flag → skip dispatch | Detect available receivers → auto-supply. User explicit typing = receiver selection override |
| 2 | "Generic skill, so OK without flag" judgment | No flag invocation = information loss. If receiver available, dispatch is default |
| 3 | Receiver auto-dispatch judged as ambiguous user intent | Receiver registered in environment = intent stated. Auto-supply is safe |
| 4 | Multiple candidates → silently pick first without asking | Multiple candidates → AskUserQuestion for user decision |
| 5 | Receiver presence judged by MCP existence only → silent skip if absent | Receiver can operate as network endpoint without MCP. Scan all 3 axes: MCP + receiver topic + reachability. Uncertain = ask, not silent skip |

### Auto-detection procedure (caller responsibility, 3-axis)

Before calling generic skill:

1. Grep calling target skill topic docs — confirm `--<verb>=<skill>:<topic>` or abstract dispatch contract pattern
2. Available receiver candidate 3-axis scan (check all):
   - **MCP server**: `mcp__<vendor>__*` → vendor skill candidate
   - **Skill registry**: whether receiver topic with dispatch protocol declared exists (MCP absent ≠ receiver absent)
   - **Endpoint reachability**: healthcheck stated in receiver topic (`curl -m 6 <endpoint>/healthz`)
3. Branch:
   - 0 → omit flag
   - 1 reachable confirmed → auto-supply
   - Uncertain → AskUserQuestion (skip vs dispatch). Silent skip forbidden
   - 2+ → AskUserQuestion for selection

**Self-check**: dispatch flag exposure / 3-axis scan / branch decision / auto-supply default applied.
