---
name: docxport
depends-on:
  - docx
description: |
  Convert Markdown / HWP / DOCX / RTF to PDF, PNG, HTML, DOCX. LibreOffice is the top-priority converter (watermark-free, MPL 2.0, faithful layout, handles HWP natively). prince / md-to-pdf are internal-only fallbacks — prince stamps a non-commercial watermark, so it must not touch external deliverables. Topics — pandoc (Markdown to PDF/PNG), docx (Word + md-to-docx-to-pdf chain, delegates to the docx skill) [docx.md], legacy (HWP / DOC / RTF via LibreOffice, in this SKILL.md), marp (slides with Mermaid, checklists, overflow) [marp.md]. Rich-format analysis defaults to PDF or HTML with images/tables preserved, never a silent txt fallback. Triggers — "PDF conversion", "PNG conversion", "DOCX conversion", "Word conversion", "HWP conversion", "hwp pdf", "hwp analysis", "legacy document", "document export", "export pdf", "md to pdf", "md to docx", "docx to pdf", "marp mermaid", "official PDF", "watermark-free PDF", "LibreOffice conversion", "document analysis".
metadata:
  version: "0.0.0"
  type: skill
---

# Document Export

Convert documents (Markdown, HWP, DOCX, RTF) to PDF, PNG, HTML slides.

## Usage mandate (HARD STOP)

All `Markdown | HWP | DOCX → PDF / PNG / HTML / DOCX` conversion **must go through this skill.** Do not assemble `pandoc` / `prince` / `md-to-pdf` / `soffice` commands ad-hoc — direct assembly repeats mistakes (duplicated titles, watermark leakage on official documents, missing images on HWP txt fallback, etc.).

| # | Don't | Do |
|---|-------|-----|
| 1 | Directly assemble `pandoc ... && prince ...` in Bash | Invoke `/doc-export <file>` → follow the Instructions procedure below |
| 2 | Reconstruct conversion options from memory each time | Follow "Conversion cautions (recurrence prevention)" + Instructions every time |
| 3 | For an HWP / DOCX / PDF `document analysis` request, silently fall back to `txt` extraction | Rich-format analysis defaults to **PDF or HTML with images/tables preserved**. txt is opt-in only (user must explicitly say "txt only") |
| 4 | Use prince / md-to-pdf for official / external-submission documents | Watermark risk (prince inserts "non-commercial" mark). Route official documents through LibreOffice (§Medium policy below) |

## Topics

| Topic | Description | Guide |
|-------|-------------|-------|
| docx | Word conversion + md → docx → pdf chain (pandoc + LibreOffice) | [docx.md](./docx.md) |
| legacy | HWP / DOC / RTF → PDF / HTML via LibreOffice (below in this file) | — |
| marp | Marp slide conversion (Mermaid, checklists, overflow) | [marp.md](./marp.md) |
| pandoc | Markdown → PDF / PNG (pandoc + LibreOffice or prince) | below in this file |

## Quick Start

```bash
/doc-export path/to/document.md
```

## Instructions

### 1. Classify the target medium (MANDATORY — before tool selection)

Before picking a converter, classify the deliverable into **one of the two mediums** below. The medium decides which tool is legal, not which tool is available.

| Medium | Definition | Watermark-clean required? | Default converter |
|--------|-----------|---------------------------|-------------------|
| **Official / external** | Submitted to a customer, consortium, government, external partner, or any recipient outside your workspace. Also: reports embedded into contract deliverables, quotes, RFP responses | **Yes (HARD STOP)** | **LibreOffice** (§tool table row 1) |
| **Internal / draft** | Working draft only, staying inside the workspace. Review copies, session artifacts, `.tmp/` scratch, throwaway previews | Not required | Any row of the tool table; pick by availability |

If the user has not stated the medium explicitly, **default to "Official / external"** — false positives (watermark-clean tool used on a scratch draft) waste nothing; false negatives (watermarked prince output emailed to a customer) are unrecoverable.

### 2. Tool priority (fallback order)

Use the **first available** tool that satisfies the medium classification from §1. Skip any tool marked "internal only" if the medium is Official / external.

| Rank | Tool | Check command | Watermark? | License | Allowed medium |
|------|------|---------------|------------|---------|----------------|
| 1 | **LibreOffice (soffice)** | `command -v soffice \|\| command -v libreoffice` | **None** | MPL 2.0 (fully free) | Official + Internal |
| 2 | pandoc + wkhtmltopdf | `command -v pandoc && command -v wkhtmltopdf` | None | LGPL / GPL | Official + Internal |
| 3 | pandoc + xelatex | `command -v pandoc && command -v xelatex` | None | LPPL / free | Official + Internal |
| 4 | pandoc + prince | `command -v pandoc && command -v prince` | **Yes** ("This document was created with the unregistered version of Prince") | Non-commercial free / commercial paid | **Internal only** |
| 5 | md-to-pdf (npx puppeteer) | `npx --yes md-to-pdf --version` | None (uses headless Chromium) | MIT | Official + Internal (but Chromium install downloads ~150MB) |

**Rank rationale**:
- LibreOffice is #1 because it is watermark-clean, MPL-licensed, and handles the widest input format list (Markdown via pandoc pre-step, DOCX, HWP, RTF, ODT). It is the only converter that can render HWP without loss.
- prince is dropped to internal-only because the free build stamps every page. Paid Prince removes the stamp but is per-machine licensed — do not silently rely on user's paid seat.
- md-to-pdf is a valid watermark-clean alternative on Windows / npm-heavy machines but pulls Chromium on first run, so LibreOffice remains #1 on macOS / Linux.

### 3. LibreOffice install-check + install-ask procedure (MANDATORY)

Before every LibreOffice-backed conversion:

```bash
if command -v soffice >/dev/null 2>&1 || command -v libreoffice >/dev/null 2>&1; then
  echo "LibreOffice available"
else
  echo "LibreOffice NOT installed"
fi
```

If **not installed**, do NOT silently fall through to prince / md-to-pdf when the medium is Official / external. Instead:

1. Run `AskUserQuestion` with these options (single-select):
   - `Install LibreOffice (~400MB, Recommended for official documents)` — description mentions `brew install --cask libreoffice` (macOS) or `scoop install libreoffice` (Windows) or `apt install libreoffice` (Linux). Runtime ~2–10 min depending on network
   - `Fall back to next watermark-clean rank (wkhtmltopdf / xelatex / md-to-pdf)` — if any is available. State which one and its trade-off
   - `Downgrade medium to Internal-only and use prince` — only offer when the user is willing to accept the watermark
2. Wait for the answer. Do NOT proceed with prince output on an Official-medium document without explicit user approval.
3. If the user selects install: run the appropriate install command in the appropriate way for the platform, then verify with the check command above before continuing.

#### Don't / Do

| # | Don't | Do |
|---|-------|-----|
| 1 | Detect "soffice not found" and silently switch to prince for an Official document | Run the install-ask above. Prince output on Official medium requires explicit user override |
| 2 | Assume LibreOffice from a prior session is still installed | Run `command -v soffice` at the start of every conversion. State the check result in the response |
| 3 | Install LibreOffice without asking (400MB download is user-visible impact) | AskUserQuestion first. Install only after approval |
| 4 | Report "conversion done" when the medium is Official but the output was produced by prince (with watermark) | Watermark verification: `pdftotext output.pdf - | grep -i "unregistered\|non-commercial\|prince"`. If matched on Official medium = conversion failure, retry via LibreOffice |

### 4. Execution

**Method A — LibreOffice (default, watermark-clean)**

`md → pdf` chain (LibreOffice can't read `.md` directly, so pandoc pre-converts to docx):

```bash
pandoc document.md -o document.docx --toc -V lang=ko-KR
soffice --headless --convert-to pdf --outdir "$OUTDIR" document.docx
# → document.pdf (watermark-free, faithful to Word-style layout)
```

Direct format conversions (LibreOffice reads these natively):

```bash
soffice --headless --convert-to pdf --outdir "$OUTDIR" input.docx
soffice --headless --convert-to pdf --outdir "$OUTDIR" input.hwp
soffice --headless --convert-to pdf --outdir "$OUTDIR" input.rtf
soffice --headless --convert-to html --outdir "$OUTDIR" input.hwp   # HTML with images extracted
```

**Method B — pandoc + prince (Internal only; do NOT use for Official)**

```bash
# Only when medium classification = Internal AND the user has not asked for a watermark-clean output
pandoc document.md -f gfm -t html5 -s -c style.css -o document.html
prince document.html -o document.pdf
```

**PNG rendering (PDF → PNG page images)**

```bash
pdftoppm -png -r 150 document.pdf document
```

### 5. HWP / legacy document conversion (integrated procedure)

HWP (Hangul Word Processor) is a Korean office format frequently used in official Korean government / enterprise submissions.

#### Toolchain by input format

| Input | Recommended converter | Fallback | Notes |
|-------|----------------------|----------|-------|
| `.hwp` (HWP 5.x binary) | LibreOffice `--convert-to pdf` or `--convert-to html` | `uvx --from pyhwp --with six hwp5txt` (text-only, images lost) | LibreOffice preserves tables and images. pyhwp txt is a **last-resort text-only fallback**, never the default |
| `.hwpx` (HWP 2010+ XML) | LibreOffice `--convert-to pdf` | (rare) unzip + XML parse | HWPX is a zip container — LibreOffice reads it natively |
| `.doc` (Word 97-2003) | LibreOffice `--convert-to docx` then re-open | — | Legacy DOC must be upgraded before editing |
| `.rtf`, `.odt` | LibreOffice `--convert-to pdf` | — | Native support |

#### Analysis-request default (HARD STOP)

When the user asks to **analyze** a rich-format document (HWP / DOCX / PDF / legacy) without specifying the output medium:

| # | Don't | Do |
|---|-------|-----|
| 1 | Silently choose `--convert-to txt` and drop tables / images | Default to `--convert-to pdf` (or `--convert-to html`), preserving layout / tables / images |
| 2 | Fall back to `hwp5txt` because `soffice` failed once | If LibreOffice load fails, retry with a sanitized filename copy in `/tmp` first. Only after LibreOffice truly cannot open the file → offer pyhwp `hwp5txt` as an **explicit fallback with a note** that images will be lost |
| 3 | Present a `txt / html / pdf` option set without stating the default | State explicitly: "Default = PDF (images preserved). Pick another only if you need txt-only" |
| 4 | Interpret an ambiguous option label ("LibreOffice install") as "install only, then extract txt" | Read the option description. If it says "preserves images / faithful to original", the user intent is a visual-preserving format (PDF or HTML), not txt |

#### Sanitized filename workaround

LibreOffice sometimes fails on paths with Korean characters + spaces. If `soffice --convert-to pdf "<original>"` returns "source file could not be loaded":

```bash
cp "$ORIGINAL" /tmp/input.hwp
soffice --headless --convert-to pdf --outdir /tmp /tmp/input.hwp
# then rename output back to the original stem if needed
```

## Conversion cautions (recurrence prevention)

### Title — no duplication

- If the document already contains `# H1`, do NOT append `--metadata title="..."` to pandoc. `-s` emits a separate title block that duplicates the H1 → **two-line duplicated title**. Use H1 as the sole title.
- If a separate title block is required, remove the `# H1` from the source and keep only `--metadata title` (one or the other, never both).

### Change-highlight documents (`<mark>` for review)

| # | Don't | Do |
|---|-------|-----|
| 1 | Apply `<mark>` inside sections that already summarize changes (change log / summary of changes) | That section is redundant to highlight. `<mark>` is for **body content (tables / paragraphs) distinguishing changed vs unchanged** |
| 2 | Inject "review-copy / highlight legend" banners on your own | Do not inject banners without user request. If asked to "remove it", remove immediately then regenerate |
| 3 | Add `<mark>` without CSS | `mark { background: #fff3a3 }` + Korean font + table border CSS via `-c style.css` — without CSS the highlight does not render |

### Do not delete review artifacts

Review PDFs / MDs awaiting user approval are **kept until the user explicitly confirms review is complete** (see `file-operations.md` `.tmp` section). No auto-cleanup.

## Tool inventory

| Tool | Purpose | macOS install | Windows install |
|------|---------|---------------|-----------------|
| LibreOffice (soffice) | Any → PDF / HTML / DOCX (watermark-clean, top priority) | `brew install --cask libreoffice` | `scoop install libreoffice` or the official site |
| pandoc | Markdown → HTML / DOCX | `brew install pandoc` | `scoop install pandoc` |
| wkhtmltopdf | HTML → PDF (watermark-clean fallback) | `brew install wkhtmltopdf` | `scoop install wkhtmltopdf` |
| xelatex (via TeX Live) | Markdown → PDF (heavy install) | `brew install --cask mactex-no-gui` | `scoop install latex` |
| prince | HTML → PDF (**watermark on free build — internal only**) | `brew install prince` | official site |
| md-to-pdf | Markdown → PDF (watermark-clean, pulls Chromium) | `npm i -g md-to-pdf` | `npm i -g md-to-pdf` or `npx` |
| poppler (pdftoppm) | PDF → PNG | `brew install poppler` | `scoop install poppler` |
| pyhwp (fallback only) | HWP → text (images lost) | `uvx --from pyhwp --with six hwp5txt` | same via `uvx` |

## Output files

- `document.pdf` — PDF
- `document.html` — HTML (with image assets when converted from HWP / DOCX)
- `document-1.png`, `document-2.png`, ... — per-page PNG

## Options

### PNG resolution

```bash
pdftoppm -png -r 300 document.pdf document  # 300 DPI (high resolution)
pdftoppm -png -r 72  document.pdf document   # 72 DPI (low resolution)
```

### Merge PNGs into one

```bash
# Requires ImageMagick
convert document-*.png -append document-all.png
```
