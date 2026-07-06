# Plugin Clustering Recommendation

Score the **affinity between skills** across the ecosystem and recommend which
skills should be bundled into a shared plugin. High mutual affinity → ship
together; low affinity → keep standalone. The output of this topic feeds
directly into the [create](./create.md) topic (which becomes the `plugins/<name>`
membership list) and the [marketplace](./marketplace.md) topic (where bundled
plugins are published).

## When to Use

- "Which of these skills belong in the same plugin?"
- Before publishing a plugin bundle — decide membership by signal, not by guesswork
- After a cluster of skills grows cross-references organically and you want to formalize the boundary

**Pre-flight (MANDATORY)**: before authoring any new scoring/clustering tooling
here, run a remote ecosystem search via `Skill("skill-kit", "route")` Step 2b
(this skill's own `find` topic / ClawHub) for an existing affinity/clustering
skill. Reuse over rebuild applies to this capability too.

## Two Modes — Discovery vs Candidate-set Audit

Clustering is invoked in two different shapes. The scoring model is the same;
the *scope of iteration* and the *handling of references that point outside
that scope* differ. Pick the mode before measuring.

| Mode | Input | Iteration scope | What to do with references to skills outside the scope |
|------|-------|-----------------|-------------------------------------------------------|
| **Discovery** | None — scan all installed skills | All `~/.claude/skills/*/` | N/A (scope = universe; nothing is "outside") |
| **Candidate-set audit** | A given list of N skills (e.g., a dependency-diagram subgraph, a proposed plugin's tentative membership) | The N candidates | **Surface separately as cluster-expansion candidates and external-bundle signals** (see "Outside-set references" below). Do not silently drop them |

In audit mode, an edge from candidate A to a non-candidate skill X is a real
signal — it means either X belongs in the cluster (expand the candidate set) or
X is an external dependency the bundle must track (Dim 2-style). Dropping these
edges by restricting both loops to the candidate set produces an
under-recommended cluster.

## Scoring Model

Three dimensions feed a pairwise affinity score. The first two pull skills
*together*; the third gates whether bundling is *worth it at all*.

| # | Dimension | Weight | Pulls toward | Signal source |
|---|-----------|--------|--------------|---------------|
| 1 | Cross-skill topic coupling | High | Bundling A+B | Directed topic→topic references between two skills (`Skill("B", "topic")`, `B/topic.md`, `/B <topic>` inside A's topic files) |
| 2 | Shared external dependency | Medium | Bundling A+B (and/or co-locating the dependency) | `depends-on` overlap, esp. on external skills/plugins (e.g., `superpowers`). Two skills depending on the same external surface have aligned release/version needs |
| 3 | Command + hook footprint | Low (gate, not pull) | Whether *any* plugin is justified | Count of installed command aliases + `resources/*.sh` hooks + hook criticality (see below). **Low hook footprint lowers the need to convert at all** — a skill that installs no hooks works fine standalone and gains little from plugin packaging |

### Dimension 1 — Cross-skill topic coupling (primary)

The strongest bundling signal. Count **directed topic-level edges** between every
pair of skills (the same data the dependency graphs are built from). Edge sources
to extract:

| Edge source | Pattern | Example |
|-------------|---------|---------|
| `Skill()` tool call in topic body | `Skill("<name>", "<topic>")` | `Skill("github-flow", "merge")` |
| Topic markdown link | `<name>/<topic>.md` | `github-flow/pr.md` |
| Slash-command reference | `/<name> <topic>` | `/cleanup retrospect` |
| **Frontmatter `depends-on`** (inline) | `depends-on: [a, b, c]` | `depends-on: [github-flow, tdd]` |
| **Frontmatter `depends-on`** (YAML block) | `depends-on:` then `  - <name>` lines | `depends-on:\n  - commit-tidy` |

```bash
# For skill A, find which other skills its topics reference (topic + depends-on)
# Patterns are intentionally narrow to avoid false positives from filesystem
# paths like `org/repo` and shell commands like `/repo remote`.
SKILLS_DIR=~/.claude/skills

extract_refs() {
  local A="$1" a; a=$(basename "$A")
  # 1. Skill() tool call — most specific, high precision
  grep -rhoE 'Skill\("[a-z][a-z-]*"' "$A" 2>/dev/null \
    | grep -oE '"[a-z][a-z-]*"' | tr -d '"'
  # 2. Markdown link to a topic file: require boundary char before <skill>/<topic>.md
  #    (excludes `/works/group/repo/file.md` style paths)
  grep -rhoE '(^|[[:space:]("`./])([a-z][a-z-]+)/([a-z][a-z-]+)\.md' "$A" 2>/dev/null \
    | grep -oE '[a-z][a-z-]+/[a-z][a-z-]+\.md' | cut -d/ -f1
  # 3. Slash-command reference: require boundary so `~/path/repo remote` is excluded
  grep -rhoE '(^|[[:space:]"`(])/[a-z][a-z-]+ +[a-z][a-z-]+' "$A" 2>/dev/null \
    | grep -oE '/[a-z][a-z-]+' | tr -d '/'
  # 4. frontmatter depends-on — inline AND YAML block
  awk '/^---$/{f=!f; next} f' "$A/SKILL.md" 2>/dev/null | awk '
    /^depends-on: *\[/ { gsub(/.*\[|\].*/, ""); gsub(/,/, " "); print; next }
    /^depends-on:/    { block=1; next }
    block && /^  *- / { gsub(/^  *- */, ""); print; next }
    block && /^[^ ]/  { block=0 }
  '
}

for A in "$SKILLS_DIR"/*/; do
  a=$(basename "$A")
  extract_refs "$A" | sort -u | while read tok; do
    [ -d "$SKILLS_DIR/$tok" ] && [ "$tok" != "$a" ] && echo "$a -> $tok"
  done
done | sort | uniq -c | sort -rn
```

**False-positive verification (MANDATORY before publishing results)**: any edge
the extractor reports must be confirmed by reading the cited file:line. A skill
name that also exists as a common shell-command word (`repo`, `next`, `wip`,
`fix`, `run`) is at high risk of matching a literal path or command fragment.
For every outside-set edge in the result, open the source file and verify the
match is a real `Skill()` call, markdown link, slash-command, or `depends-on`
entry — not `~/path/repo remote`, `gh pr view -R owner/repo`, or similar
placeholder. Failing to verify the top hits before reporting will produce a
worked example that is partly wrong.

| # | Don't | Do |
|---|-------|-----|
| 1 | Trust the grep output for skills whose name is a common word (`repo`, `next`, `wip`, `fix`, `run`) | Open every cited file:line for these skills before classifying. Strip matches that are path placeholders, gh CLI URLs, git command fragments |
| 2 | Loose patterns like `/[a-z-]+ [a-z-]+` without boundary | Require boundary char (`(^|[[:space:]"`(])`) before `/` so `~/works/group/repo remote` does not match `/repo remote` |
| 3 | Pattern `[a-z-]+/[a-z-]+\.md` against full text | Require boundary before the first segment so `/works/group/repo/file.md` does not look like `repo/file.md` |
| 4 | Sample-of-1 verification ("I checked git-repo and the count looked right") | Sample-of-5+ verification across skills whose names collide with shell words; do not report results until all 5 verify |

- **Score**: `coupling(A,B) = edges(A→B) + edges(B→A)`. Mutual (bidirectional) coupling scores higher than one-way.
- A `depends-on` declaration that is *also* exercised by an actual topic reference counts double — declared + used.

#### Outside-set references (candidate-set audit mode only)

When clustering is run in **audit mode** (Two Modes table above), every edge
`A → X` where `X` is **not in the candidate set** must be captured and
classified, not dropped. There are two valid classifications:

| Classification | When | Action |
|----------------|------|--------|
| **Cluster-expansion candidate** | Most candidates in the set reference `X`, OR `X` itself heavily references candidates back (mutual coupling) | Propose adding `X` to the candidate set and re-score. Re-run the audit with the expanded set |
| **External bundle signal** | Only one or two candidates reference `X`, and `X` doesn't reciprocate (one-way, narrow) | Treat like Dim 2's shared external dep: either vendor `X` into the plugin, or pin `X` as a cross-plugin dependency. Do not pull `X` into the cluster |

| # | Don't | Do |
|---|-------|-----|
| 1 | Restrict both loops to the candidate set and call the result "the cluster's couplings" | Iterate inner loop over **all** skills; report inside-set edges as coupling and outside-set edges in a separate "outside refs" section |
| 2 | Treat a single outside reference (e.g., `git-repo → commit-tidy` alone) as noise and discard | Surface it. The user decides if `commit-tidy` should expand the set or be a bundle/dep signal — that decision is part of the audit |
| 3 | Conflate outside refs with Dim 2 only when **N** candidates share them | Even **1** candidate's outside ref is a signal in audit mode. Dim 2's "shared" threshold is about *which dependency to vendor*, not whether the edge exists |
| 4 | Hide outside refs from the AskUserQuestion options | Add an explicit "Expand cluster with `<X>`" option when outside refs cross the cluster-expansion threshold (≥half the candidates reference `X`, or `X` reciprocates) |

### Dimension 2 — Shared external dependency

```bash
# Map each skill's depends-on (inline OR YAML block), then find shared external dep
for S in ~/.claude/skills/*/; do
  s=$(basename "$S")
  dep=$(awk '/^---$/{f=!f; next} f' "$S/SKILL.md" 2>/dev/null | awk '
    /^depends-on: *\[/ { gsub(/.*\[|\].*/, ""); gsub(/,/, " "); print; next }
    /^depends-on:/    { block=1; next }
    block && /^  *- / { gsub(/^  *- */, ""); printf "%s ", $0; next }
    block && /^[^ ]/  { block=0; print "" }
    END { if (block) print "" }
  ')
  [ -n "$dep" ] && echo "$s: $dep"
done
```

The parser handles both forms — a skill that uses YAML block style (`depends-on:\n  - x`) instead of inline `[x, y]` is otherwise silently invisible to Dim 2, and any external-dep shared via the block form gets undercounted.

- Two skills sharing an **external** dependency (a plugin not in this repo — e.g., `superpowers`) score higher than two sharing an internal one, because they must track that external surface's versions together.
- Output also flags: if N skills all depend on the same external skill, consider whether that external surface should be **vendored into the plugin** (see `skill-kit/portability` topic) rather than left as a cross-plugin dead reference.

### Dimension 3 — Command + hook footprint (the gate)

```bash
# Per-skill hook + command footprint
for S in ~/.claude/skills/*/; do
  s=$(basename "$S")
  hooks=$(ls "$S"/resources/*.sh 2>/dev/null | wc -l | tr -d ' ')
  cmd=$(ls ~/.claude/commands/"$s".md 2>/dev/null | wc -l | tr -d ' ')
  echo "$s: hooks=$hooks cmd=$cmd"
done
```

Hook **criticality** weighting (read matcher type from `~/.claude/settings.json`):

| Hook type | Criticality | Plugin-conversion value |
|-----------|-------------|-------------------------|
| `PreToolUse` blocking (exit 2 / deny) | High | High — guard machinery benefits from versioned plugin packaging |
| `SessionStart` context injection | High | High — always-on behavior shipped as a unit |
| `PostToolUse` warning (non-blocking) | Medium | Medium |
| `Stop` / `UserPromptSubmit` advisory | Low | Low |
| No hooks at all | — | **Low — standalone skill is sufficient; do not force a plugin** |

This dimension does **not** pull two skills together. It scales the final
recommendation: a tightly-coupled pair with zero hooks may still be fine as two
standalone skills; a pair that also installs critical guard hooks gains real
value from plugin packaging (shared install/version/settings registration).

**Measurement caveat — count by ownership, not keyword match**: a skill's hook
footprint is the hooks it *owns* (`<skill>/resources/*.sh`), not every installed
`~/.claude/hooks/*.sh` whose name matches the skill's domain. An installed hook may be:

- **UNMANAGED / ORPHAN** — no `resources/` owner (a `Skill("hook-kit", "audit")` cleanup item, not this skill's footprint)
- **cross-cutting general guard** — fires on a broad matcher (e.g., "all UI file edits", "any SSH-config Read") rather than this skill's own workflow

Neither counts toward plugin-conversion value. Verify both ownership and matcher
scope before crediting a hook to a skill:

```bash
# OWNERSHIP: resources/ is the source of truth — does this skill own the hook?
ls ~/.claude/skills/<skill>/resources/*.sh 2>/dev/null
# An installed hook with a domain-matching name but no resources/ owner is
# UNMANAGED (cross-check `Skill("hook-kit", "audit")`) — it is NOT this skill's footprint.
```

## Forming Clusters

1. Build a pairwise `affinity(A,B) = coupling*w1 + sharedExternalDep*w2` matrix (dimensions 1–2).
2. Group skills whose mutual affinity exceeds a threshold (transitive: A–B and B–C with no A–C still cluster via B).
3. **Process outside-set references** (audit mode only — see "Outside-set references" subsection): for each `A → X` where `X` is outside the candidate set, classify as cluster-expansion candidate or external-bundle signal. If any `X` qualifies as expansion, surface it as an option *before* finalizing the cluster.
4. Apply the dimension-3 gate per candidate cluster: compute total hook/command footprint + max criticality. Low footprint → annotate "bundling optional, standalone OK"; high-criticality hooks → annotate "bundling recommended".
5. Name each cluster after its highest-coupling hub skill.

## Present Results via AskUserQuestion

```
AskUserQuestion {
  question: "Affinity scoring suggests these plugin clusters. Which should be bundled?",
  multiSelect: true,
  options: [
    { label: "Bundle {hub} + {a} + {b}", description: "Coupling N edges, shared dep {X}, critical hooks {H} → high value" },
    { label: "Keep {c} standalone", description: "Couples to {hub} but installs no hooks → low conversion value" },
    { label: "Vendor {ext} into the plugin", description: "M skills share external dep {ext}; bundling avoids dead cross-refs" }
  ]
}
```

After the user selects a cluster, hand off to [create](./create.md) to author
the `plugins/<name>/` directory with the chosen membership.

## Optional d3 export — affinity graph dispatch

Render the clustering result as a force-directed d3 graph for visual review of
cluster boundaries, outside-set bundle signals, and ownership-gate failures.
**Companion to `skill-kit/graph` Step 4** — both topics expose the same
`--render=<skill>:<topic>` abstract dispatch contract so a single d3 receiver
can render either dependency edges (graph) or affinity-weighted clusters
(clustering).

### Inputs

| Input | Form | Example |
|-------|------|---------|
| Candidate set | list of slugs (audit mode) or omitted (discovery mode) | `code-workflow github-flow consolidate git-repo tdd web-browser` |
| `--render=<skill>:<topic>` (optional) | abstract dispatch contract for d3 receiver | `--render=es6kr:force-graph` |
| `--threshold=<N>` (optional) | minimum coupling score to emit a link (default: 1) | `--threshold=2` |

### Nodes / links conversion

The clustering result (Dim 1/2/3 + outside-set) maps to a `{nodes, links}` JSON
payload the d3 receiver consumes. Each node carries cluster membership +
ownership-gate metadata so the receiver can color/group consistently with the
audit decision.

```json
{
  "nodes": [
    {
      "id": "<slug>",
      "cluster": "<hub-skill>|standalone|outside",
      "hooks": <int — owned resources/*.sh count>,
      "criticality": "high|medium|low|none",
      "role": "candidate|outside-bundle-signal|cluster-expansion"
    }
  ],
  "links": [
    {
      "source": "<slug>",
      "target": "<slug>",
      "value": <coupling score — Dim 1 inside-set edges A→B + B→A>,
      "kind": "inside|outside|shared-dep",
      "shared_dep": "<external skill name — only when kind=shared-dep>"
    }
  ]
}
```

Field semantics:

| Field | Source dimension | Notes |
|-------|------------------|-------|
| `nodes[].cluster` | Forming Clusters Step 5 | Outside-set bundle signals get `cluster: "outside"` so the receiver can hull-separate them from inside-set clusters |
| `nodes[].hooks` + `nodes[].criticality` | Dim 3 ownership gate | Count `<skill>/resources/*.sh` only — **UNMANAGED / cross-cutting general guards do not count** (per the "Measurement caveat" subsection) |
| `nodes[].role` | Outside-set classification | `candidate` = inside the audit set; `outside-bundle-signal` = single-source narrow outside ref (vendor/pin); `cluster-expansion` = outside ref that crosses the ≥half candidates / reciprocation threshold |
| `links[].value` | Dim 1 coupling | `value = edges(A→B) + edges(B→A)` — bidirectional coupling sums |
| `links[].kind` | Mode separation | `inside` = both endpoints in candidate set; `outside` = audit-mode candidate → non-candidate; `shared-dep` = Dim 2 shared external dep edge (synthetic, not a direct `Skill()` call) |

### Dispatch

```bash
/cc-plugin clustering <slugs> --render=<receiver-skill>:<receiver-topic>
```

When the flag is supplied, the clustering topic invokes the receiver with the
`{nodes, links}` JSON. The receiver owns the HTML template, force-tuning
controls (charge / link distance / collision radius), and convex-hull rendering
that visually groups each cluster. **Do NOT hardcode a specific receiver name**
— see `skill-kit/portability` Rule B (Generic skills must expose abstract
dispatch, not vendor-specific calls).

When the flag is omitted, the procedure stops at the AskUserQuestion result +
Worked Example deliverable.

### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Hardcode a specific render receiver (e.g., `es6kr:force-graph`) in clustering topic body | Use abstract `--render=<skill>:<topic>` dispatch — caller chooses the receiver (Rule B of `skill-kit/portability`) |
| 2 | Emit only inside-set links in the JSON payload | Audit mode emits `kind: "outside"` links separately so the receiver can hull-separate outside-bundle-signal nodes from inside-set clusters (Outside-set Don't/Do #1) |
| 3 | Include keyword-matched but UNMANAGED hooks in `nodes[].hooks` count | Count only `<skill>/resources/*.sh` ownership (per the "Measurement caveat" subsection) — UNMANAGED / cross-cutting guards inflate plugin-conversion value falsely |
| 4 | Reuse `skill-kit/graph`'s edge JSON directly as clustering links | Graph emits raw dependency edges; clustering links carry **affinity score** (coupling sums + Dim 2 synthetic edges). They are companion outputs, not interchangeable |
| 5 | Drop the `--threshold` filter and emit every pair | Default `--threshold=1` filters zero-coupling pairs; raise the threshold when the graph is dense (audit mode with many outside refs) so visualization stays legible |

### Outputs

| Output | Always | When `--render` |
|--------|--------|------------------|
| AskUserQuestion options (clusters + outside-set decisions) | ✅ | ✅ |
| Worked Example summary table (Cluster / Members / Rationale) | ✅ | ✅ |
| `{nodes, links}` JSON payload | — | ✅ |
| d3 force-directed graph (via receiver) | — | ✅ |

### Self-check (before invoking dispatch)

1. Did the audit run produce a final cluster assignment (Forming Clusters Step 5)? — dispatch must follow scoring, not precede it
2. Are outside-set edges classified per "Outside-set references" (cluster-expansion vs external-bundle-signal) before mapping to `nodes[].role`?
3. Is the dispatch flag abstract (`--render=<skill>:<topic>`) — no hardcoded receiver in topic body?
4. Does the JSON payload schema match the receiver's contract? Receivers may extend the schema, but the four fields above (`cluster`, `hooks`, `criticality`, `role` on nodes; `value`, `kind` on links) are MANDATORY for hull/color/size mapping
5. Is `--threshold` set appropriately for graph density? Discovery mode often needs `--threshold=2+` to avoid hairball

## Worked Example — code-workflow dependency cluster

Applying the model in **candidate-set audit mode** to the skills in the
code-workflow dependency graph (code-workflow, github-flow, tdd, web-browser,
consolidate, git-repo; superpowers external).

- **Dim 1 (coupling — inside-set, grep + diagram edges)**: github-flow ↔ consolidate = 11 (gf→co 8 Step-9 follow-up, co→gf 3) strongest bidirectional; code-workflow ↔ github-flow = 5+ (companion/deps/plan-to-issue/pr/merge, depends-on both ways); code-workflow→tdd 2, →web-browser 1, consolidate→git-repo 1 (depends-on, one-way).
- **Dim 1 (outside-set references — audit-mode surfacing)**: `git-repo → commit-tidy` (frontmatter `depends-on`, one-way, narrow); `consolidate/next → next` and `→ wip` (`Skill()` calls, one-way, narrow). None of `commit-tidy / next / wip` are in the candidate set, and each reference is single-source + non-reciprocated → classify as **external bundle signal** (Dim 2-style), not cluster-expansion candidate. The bundle either vendors them or pins them as cross-plugin deps. Without the Outside-set Don't/Do #2 rule, these edges would have been silently dropped by inner-loop restriction.
- **Dim 2 (shared external dep)**: code-workflow, consolidate, github-flow all pull `superpowers` → bundling signal.
- **Dim 3 (ownership gate)**: code-workflow owns 1 hook, consolidate owns 1; github-flow / tdd / web-browser / git-repo own 0. tdd/web-browser/git-repo matched `ui-change`/`ssh-config` installed hooks by keyword, but those are **UNMANAGED cross-cutting guards** → footprint 0 (per the caveat above).

**Result:**

| Cluster | Members | Rationale |
|---------|---------|-----------|
| Core PR-workflow plugin (hub = github-flow) | code-workflow + github-flow + consolidate | strong bidirectional coupling + shared `superpowers` + owns guard hooks |
| Standalone | tdd, web-browser, git-repo | depends-on targets but one-way + zero **owned** hooks → Dim-3 gate keeps them standalone |
| External bundle signals (vendor or pin) | superpowers (shared by 3 — Dim 2), commit-tidy (narrow from git-repo `depends-on`), next + wip (narrow from `consolidate/next` `Skill()` handoff) | Dim 2 + outside-set surfacing |

Two discriminators kept the cluster honest:
- **Dim-3 ownership gate** for tdd/web-browser/git-repo (heavily referenced but own no hooks → standalone).
- **Outside-set surfacing** for `commit-tidy`, `next`, `wip` (would have been dropped by inner-loop restriction — the audit must report them as bundle signals even though no inside-set member matches).

## Notes

- Affinity scoring is a **recommendation aid**, not an automatic action — never create/move a plugin without the AskUserQuestion above.
- Dimension 3 is the discriminator most often ignored: do not recommend a plugin for a coupled pair that installs no hooks/commands and gains nothing from packaging.
- Reuse the cross-skill edge data already produced for dependency diagrams if one exists (e.g., `~/.agents/docs/skill-dependencies*.md`) instead of recomputing.
