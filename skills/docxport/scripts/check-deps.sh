#!/bin/bash
# docxport dependency check and install helper

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Conversion mode flags — control which tools are required per selected output flags.
#   --doc / --docx : docx-related workflows (md → docx → pdf via LibreOffice)
#   --pdf          : Markdown → PDF (LibreOffice-first; prince/md-to-pdf only when --internal)
#   --slides       : Marp slide conversion (Mermaid, checklists, overflow)
#   --internal     : Internal-only medium; unlocks watermarked converters (prince, md-to-pdf)
WANT_DOC=false
WANT_PDF=false
WANT_SLIDES=false
WANT_INTERNAL=false
for arg in "$@"; do
    case "$arg" in
        --doc|--docx) WANT_DOC=true ;;
        --pdf) WANT_PDF=true ;;
        --slides) WANT_SLIDES=true ;;
        --internal) WANT_INTERNAL=true ;;
    esac
done

echo "=== Document Export tool check ==="
echo

check_tool() {
    local tool=$1
    local brew_pkg=$2
    local description=$3

    if command -v "$tool" &> /dev/null; then
        echo -e "${GREEN}v${NC} $tool - $description"
        return 0
    else
        echo -e "${RED}x${NC} $tool - $description (not installed)"
        return 1
    fi
}

MISSING=()
MISSING_CASKS=()

# Required baseline — LibreOffice-first plan: pandoc + LibreOffice cover the Official medium.
check_tool "pandoc" "pandoc" "Markdown -> HTML/DOCX conversion" || MISSING+=("pandoc")
check_tool "pdftoppm" "poppler" "PDF -> PNG conversion" || MISSING+=("poppler")

# LibreOffice (docx -> pdf, Markdown -> PDF via docx chain, HWP legacy conversion) is required
# whenever --doc, --pdf, or --slides is requested. It is the LibreOffice-first default (§Medium).
if [ "$WANT_DOC" = true ] || [ "$WANT_PDF" = true ] || [ "$WANT_SLIDES" = true ]; then
    if command -v soffice &> /dev/null || command -v libreoffice &> /dev/null; then
        echo -e "${GREEN}v${NC} soffice/libreoffice - DOCX / HWP -> PDF conversion (LibreOffice-first)"
    else
        echo -e "${RED}x${NC} soffice/libreoffice - DOCX / HWP -> PDF conversion (not installed)"
        MISSING_CASKS+=("libreoffice")
    fi
fi

echo

# Optional tools
echo "=== Optional tools ==="
# ImageMagick 7 uses `magick`; older versions expose `convert`. Accept either.
if command -v magick &> /dev/null || command -v convert &> /dev/null; then
    echo -e "${GREEN}v${NC} magick/convert - PNG merge"
else
    echo -e "${RED}x${NC} magick/convert - PNG merge (not installed)"
fi
echo

# --slides (Marp) — check for Marp CLI when slide conversion is requested
if [ "$WANT_SLIDES" = true ]; then
    echo "=== Marp CLI (--slides) ==="
    if command -v marp &> /dev/null; then
        echo -e "${GREEN}v${NC} marp - Marp slide conversion"
    elif command -v npx &> /dev/null; then
        echo -e "${YELLOW}!${NC} marp not installed — will invoke via 'npx --yes @marp-team/marp-cli' on first use"
    else
        echo -e "${RED}x${NC} marp / npx - Marp slide conversion (not installed)"
        echo "    install: npm install -g @marp-team/marp-cli   # or run via npx --yes @marp-team/marp-cli"
    fi
    echo
fi

# Internal-only converters — prince (watermarked, non-commercial), md-to-pdf (Chromium 150MB).
# Never required for Official/external medium; opt-in via --internal.
if [ "$WANT_INTERNAL" = true ]; then
    echo "=== Internal-only converters (--internal) ==="
    check_tool "prince" "prince" "HTML -> PDF (watermarked, non-commercial license)" || true
    echo "    Note: prince stamps 'non-commercial' watermark — Internal medium only, never for external delivery"
    echo
fi

# Install guidance
if [ ${#MISSING[@]} -gt 0 ] || [ ${#MISSING_CASKS[@]} -gt 0 ]; then
    echo -e "${YELLOW}=== Install required ===${NC}"
    echo
    echo "Install the missing tools with:"
    echo
    for pkg in "${MISSING[@]}"; do
        echo "  brew install $pkg"
    done
    for cask in "${MISSING_CASKS[@]}"; do
        echo "  brew install --cask $cask"
    done
    echo
    if [ ${#MISSING[@]} -gt 0 ]; then
        echo "Install formulae at once:"
        echo "  brew install ${MISSING[*]}"
        echo
    fi
    if [ ${#MISSING_CASKS[@]} -gt 0 ]; then
        echo "Install casks at once:"
        echo "  brew install --cask ${MISSING_CASKS[*]}"
        echo
    fi

    read -p "Install now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        [ ${#MISSING[@]} -gt 0 ] && brew install "${MISSING[@]}"
        [ ${#MISSING_CASKS[@]} -gt 0 ] && brew install --cask "${MISSING_CASKS[@]}"
        echo -e "${GREEN}Install complete.${NC}"
    fi
else
    echo -e "${GREEN}All required tools are installed.${NC}"
fi
