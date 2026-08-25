# Pre-Search Topic (`pre-search.md`)

## Mandatory RAG & Knowledge Pre-Search Gate (HARD STOP)

Before drafting any research or plan document, conducting a comprehensive pre-lookup across existing knowledge repositories and vector memory is MANDATORY.

### Core Capabilities & Protocol (ES6KR-124)

1. **Automated Corpus Availability Determination**:
   - Detect available knowledge backends in the current environment:
     - Active Qdrant Memory (`http://<qdrant-host>:<port>` `claude-memory`)
     - Local/Global LLM Wiki (`llm-wiki/pages/`, `llm-wiki/outputs/`)
     - Workspace Artifacts (`.agents/docs/generated/`)
     - Serena RAG / Project KI records.

2. **Direct Standard Qdrant Vector Search**:
   - Execute Qdrant vector semantic search using standard tools:
     ```bash
     python ~/.claude/skills/cleanup/resources/qdrant-search.py "<query keywords>" --collection claude-memory --limit 5
     ```
   - Embed high-relevance findings directly into `## Prior Knowledge & Context` in the research document.

3. **Curated LLM Wiki Pre-Lookup via `artifact_pre_lookup.py`**:
   - Search canonical wiki pages and past plan outcomes before proposing new designs:
     ```bash
     python ~/.claude/skills/fix-plan/scripts/artifact_pre_lookup.py --query "<topic-keyword>"
     ```
   - Ground decisions on established patterns to prevent duplicated or contradicting designs.
