# DOCX conversion (Word) — md → docx → pdf

Convert Markdown to Word `.docx`, and optionally chain that docx to PDF (md → docx → pdf).

## When to use

- When you need an **editable Word deliverable (.docx)** (external submission, collaborative editing)
- When you need to render a submission PDF **through Word styles (heading / table styles)** — the Word-style consistency beats direct md → pdf conversion
- When you need to apply an existing `.docx` template's styles (fonts, headings, tables) to match an in-house document template

## 1. md → docx

### 1-A. Delegate to the `docx` skill (primary — high quality)

**If the `docx` skill (Anthropic, native OOXML) is installed, prefer it.** It produces much more polished Word output (styles, TOC, tables, page numbers, letterheads, images, tracked changes) than pandoc.

```text
1. Check docx skill install: ls ~/.claude/skills/docx/SKILL.md (or "docx" in the available-skills list)
2. If installed → Skill("docx") delegation to generate/edit the .docx from md
3. Not installed + user wants high quality → suggest install: npx skills add anthropics/skills@docx -g -y
```

| # | Don't (Windows) | Do |
|---|-----------------|-----|
| 1 | Run the docx skill `validate.py` as-is (Korean document) | `PYTHONUTF8=1 ... validate.py` — Windows cp949 locale cannot read UTF-8 XML and misreports `cp949 codec can't decode`. This is a locale issue, not a docx skill defect |
| 2 | Try to `require` docx-js as a Windows global module | `npm install docx` inside the build directory and run `node` from there (global `require` fails due to exports constraints) |

| # | Don't | Do |
|---|-------|-----|
| 1 | `docx` skill is installed but converting directly with pandoc (crude output) | Delegate to the `docx` skill first — native Word formatting |
| 2 | Assume `--doc(x)` = pandoc unconditionally | Check install → if present, docx skill; else §1-B pandoc fallback |

### 1-B. pandoc fallback (when the docx skill is not installed)

If the `docx` skill is unavailable and speed matters, pandoc supports docx natively:

```bash
pandoc document.md -o document.docx
```

| Option | Effect |
|--------|--------|
| `--reference-doc=template.docx` | Apply an existing docx's styles (headings / tables / fonts / headers) — in-house template |
| `--toc` | Auto-generate a table of contents |
| `--toc-depth=N` | TOC depth (default 3) |
| `-V lang=ko-KR` | Language metadata (activates Word Korean spell-check) |
| `--resource-path=DIR` | Base directory for relative image paths |
| `--metadata title="Title"` | Document title metadata |

To build a reference template: `pandoc -o template.docx --print-default-data-file reference.docx` → edit styles in Word → pass with `--reference-doc`.

> pandoc output uses stock styles and looks crude. For polished submissions, use the §1-A `docx` skill.

## 2. docx → pdf (LibreOffice headless)

LibreOffice is the cross-platform standard for docx → pdf:

```bash
# macOS / Linux
soffice --headless --convert-to pdf --outdir <OUTDIR> document.docx

# Windows
& "C:\Program Files\LibreOffice\program\soffice.exe" --headless --convert-to pdf --outdir <OUTDIR> document.docx
```

| # | Don't | Do |
|---|-------|-----|
| 1 | Run `--headless` while the LibreOffice GUI is already open | `--headless` may be ignored → close the GUI first, or use `-env:UserInstallation=file:///tmp/lo-profile` to pin a separate profile |
| 2 | Omit `--outdir` and expect a different output name | LibreOffice outputs `input-basename.pdf`. Rename after conversion with `mv` |

## 3. Full chain (md → docx → pdf)

```bash
pandoc document.md -o document.docx --reference-doc=template.docx --toc -V lang=ko-KR
soffice --headless --convert-to pdf --outdir . document.docx
# → document.docx (editable) + document.pdf (submission) produced together
```

## Tool priority (fallback)

| Stage | Rank | Tool | Check | Command |
|-------|------|------|-------|---------|
| md → docx | **1 (high quality)** | **`docx` skill** (Anthropic OOXML) | `ls ~/.claude/skills/docx/SKILL.md` | `Skill("docx")` delegation |
| md → docx | 2 (fallback) | pandoc | `command -v pandoc` | `pandoc doc.md -o doc.docx` |
| docx → pdf | 1 | LibreOffice | `command -v soffice \|\| command -v libreoffice` | `soffice --headless --convert-to pdf doc.docx` |
| docx → pdf | 2 (Windows, LibreOffice absent) | Word COM | `Get-Command winword` or Word install | §4 below |

## 4. Windows Word COM fallback (when LibreOffice is absent)

On Windows with Word installed, use PowerShell + COM for docx → pdf:

```powershell
$w = New-Object -ComObject Word.Application
$w.Visible = $false
$d = $w.Documents.Open("C:\path\document.docx")
$d.SaveAs([ref]"C:\path\document.pdf", [ref]17)  # 17 = wdFormatPDF
$d.Close(); $w.Quit()
```

## Install

| Tool | Purpose | macOS | Windows |
|------|---------|-------|---------|
| pandoc | md → docx | `brew install pandoc` | `scoop install pandoc` |
| LibreOffice | docx → pdf | `brew install --cask libreoffice` | `scoop install libreoffice` or the official site |

## Auto-conversion (when the skill is invoked)

Given a file path + output-format flags, **execute directly**:

1. **Check the `docx` skill install** (`ls ~/.claude/skills/docx/SKILL.md`):
   - **Installed → delegate to `Skill("docx")` for md → high-quality .docx** (§1-A, primary)
   - Not installed → §1-B pandoc fallback (dependency check `bash scripts/check-deps.sh <flag>` → `pandoc <md> -o <docx>`)
2. **When both `--doc --pdf` are specified**: after the docx is generated, verify `soffice` (or Word COM) → convert `docx → pdf`
3. Report the output file paths (`document.docx`, and `document.pdf` when applicable)

| Flag combination | Output | Required tools (in priority) |
|------------------|--------|-------------------------------|
| `--doc` / `--docx` | document.docx | **`docx` skill** (if present) → pandoc (fallback) |
| `--doc --pdf` (chain) | document.docx + document.pdf | (docx above) + LibreOffice |
| `--pdf` (skipping docx) | document.pdf | LibreOffice (Official) / prince or md-to-pdf (Internal only — see `SKILL.md`) |

## Related

- `SKILL.md` (pandoc topic) — direct md → **PDF / PNG / HTML** conversion (when docx is not needed)
- `marp.md` — slides (`.marp.md`) → HTML / PDF / PPTX
