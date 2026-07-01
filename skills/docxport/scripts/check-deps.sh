#!/bin/bash
# docxport dependency check and install helper

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Conversion mode flags — used to decide whether the docx->pdf chain (LibreOffice) is required
WANT_DOC=false
WANT_PDF=false
for arg in "$@"; do
    case "$arg" in
        --doc|--docx) WANT_DOC=true ;;
        --pdf) WANT_PDF=true ;;
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

# Required tools
check_tool "pandoc" "pandoc" "Markdown -> HTML conversion" || MISSING+=("pandoc")
check_tool "prince" "prince" "HTML -> PDF conversion" || MISSING+=("prince")
check_tool "pdftoppm" "poppler" "PDF -> PNG conversion" || MISSING+=("poppler")

echo

# Optional tools
echo "=== Optional tools ==="
check_tool "convert" "imagemagick" "PNG merge" || true
echo

# docx -> pdf chain tool — md->docx is handled by pandoc (required above).
# LibreOffice (docx -> pdf) is required/checked only when both --doc (or --docx) and --pdf are specified.
if [ "$WANT_DOC" = true ] && [ "$WANT_PDF" = true ]; then
    echo "=== docx -> pdf chain tool (--doc --pdf) ==="
    if command -v soffice &> /dev/null || command -v libreoffice &> /dev/null; then
        echo -e "${GREEN}v${NC} soffice/libreoffice - DOCX -> PDF conversion"
    else
        echo -e "${RED}x${NC} soffice/libreoffice - DOCX -> PDF conversion (not installed)"
        echo "    install: macOS    brew install --cask libreoffice"
        echo "             Windows  scoop install libreoffice"
    fi
    echo
fi

# Install guidance
if [ ${#MISSING[@]} -gt 0 ]; then
    echo -e "${YELLOW}=== Install required ===${NC}"
    echo
    echo "Install the missing tools with:"
    echo
    for pkg in "${MISSING[@]}"; do
        echo "  brew install $pkg"
    done
    echo
    echo "Install all at once:"
    echo "  brew install ${MISSING[*]}"
    echo

    read -p "Install now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        brew install "${MISSING[@]}"
        echo -e "${GREEN}Install complete.${NC}"
    fi
else
    echo -e "${GREEN}All required tools are installed.${NC}"
fi
