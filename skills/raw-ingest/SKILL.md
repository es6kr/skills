---
name: raw-ingest
metadata:
  author: es6kr
  version: "0.1.0"
depends-on:
  - doc-convert
description: |
  Ingest raw source files (PDF, HWP, DOCX, Markdown, web pages, meeting notes) into LLM Wiki raw sources (`raw/<slug>.md`). Converts rich documents while preserving layout/tables, updates frontmatter metadata (`source_path`, `converted_at`, `original_format`), and logs to `log.md`. Triggers — "raw ingest", "raw-ingest", "ingest raw", "wiki ingest", "raw intake", "source intake", "llm-wiki ingest".
---

# Raw Ingest (LLM Wiki Raw Source Ingestion)

Convert external documents and raw sources (PDF, HWP, DOCX, RTF, Markdown, web pages) into `raw/<slug>.md` for karpathy-style LLM-Wiki workflows.

## Overview & Workflow

1. **Format Conversion**: Convert rich documents (HWP/DOCX/PDF) to plain Markdown text while preserving structure and table formatting (utilizing `doc-convert` / `LibreOffice` / `pandoc` / `hwp5txt`).
2. **File Save**: Save converted text into target LLM-Wiki's `raw/<slug>.md`.
3. **Frontmatter Standardization**:
   ```yaml
   ---
   title: <document title>
   source_path: <HTTP/HTTPS URL (Google Drive, Nextcloud, WebDAV, public/internal web URL) — Local absolute/tilde file paths are strictly prohibited>
   converted_at: <YYYY-MM-DD>
   original_format: <HWP | DOCX | PDF | MD | WEB>
   ---
   ```
4. **Wiki Ingestion Logging**: Append entry to `log.md`:
   `[YYYY-MM-DD HH:MM] ingest raw/<slug>: <one-line summary>`
5. **Qdrant / Vector Indexing**: Trigger `artifact_post_ingest.py` (or Python ingest script) to keep vector search in sync.

## Quick Usage

```bash
/raw-ingest path/to/document.hwp --slug my-meeting-note
```
