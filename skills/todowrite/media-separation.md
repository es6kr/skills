# Work Record Media Separation (3-Layer Model)

**Work output is separated into 3 layers by nature — tracking (current state) = plain tracking files, recording (completed history) = RAG, knowledge (domain facts/decisions) = LLM Wiki.**

## Why

- RAG (vector store) is strongest at semantic search but cannot guarantee "one current state" — it may return stale entries as if current. Immutable completed history, however, has zero staleness risk and zero maintenance cost.
- Wiki maintains consistency via lint (contradiction/stale-claim detection), but that maintenance cost is only justified for low-churn, high-value knowledge. High-churn state and immutable history should not go there.
- Trade-off analysis led to adopting the 3-layer model (including per-company/personal record separation).

## Layer table

| Layer | Data nature | Medium |
|-------|-------------|--------|
| Tracking | High-churn current state (pending → in-progress → done transitions) | fix_plan.md / checklist.md / TaskList |
| Recording | Immutable completed history (accumulate + semantic "did we do this before?" search) | RAG (Qdrant or similar vector store) |
| Knowledge | Low-churn domain facts / decisions / patterns | LLM Wiki (raw → pages) |

## Don't / Do

| # | Don't | Do |
|---|-------|----|
| 1 | Manage task-state tracking via wiki pages or RAG upserts | Use tracking files only (fix_plan.md / checklist.md / TaskList). Wiki is for knowledge only |
| 2 | Accumulate completed-work records as wiki pages | RAG store via `/cleanup` rag-store flow. Only distilled knowledge (not records) goes to wiki |
| 3 | Bury decisions/facts from completed work in RAG alone | Promote knowledge to a wiki page — recording ("what did we do") ≠ knowledge ("what is true") |

## Exceptions

- Per-company media instances (wiki path, RAG collection, tracking file location) must NOT be defined here — define them in each workspace's `.claude/rules/` (per the company-info storage-location policy).
- Session-scoped ephemeral notes need not go to any of the 3 layers (conversation context is sufficient).
