#!/bin/bash
# Update script for youtube-napoletano
# Downloads latest files from GitHub main branch and updates local files
# Usage: bash scripts/update.sh

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# The root directory is the parent of scripts/
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"
# Change to project root
cd "$PROJECT_ROOT" || exit 1

REPO="ltpitt/youtube-napoletano"
BRANCH="main"
TEMP_DIR=".update_temp"

echo "🔄 Aggiornando youtube-napoletano da GitHub..."

# Check if we can write to the directory
if [ ! -w "." ]; then
    echo "❌ Errore: Non hai i permessi di scrittura nella directory corrente."
    exit 1
fi

# Cleanup function
cleanup() {
    echo "🧹 Pulizia file temporanei..."
    rm -rf "$TEMP_DIR"
}

trap cleanup EXIT

# Download latest ZIP from GitHub
echo "⬇️  Scaricando i file dal branch '$BRANCH'..."
if ! command -v curl &> /dev/null; then
    echo "❌ Errore: curl non trovato. Installa curl per procedere."
    exit 1
fi

ZIP_FILE="$TEMP_DIR/repo.zip"
mkdir -p "$TEMP_DIR"

if ! curl -L -o "$ZIP_FILE" "https://github.com/$REPO/archive/refs/heads/$BRANCH.zip" 2>/dev/null; then
    echo "❌ Errore: Non riesco a scaricare i file da GitHub."
    exit 1
fi

# Extract ZIP using Python (built-in, no unzip needed)
echo "📦 Estraendo i file..."
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "❌ Errore: python non trovato. Assicurati che Python sia installato."
    exit 1
fi

# Use python to extract ZIP
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

$PYTHON_CMD << PYEOF
import zipfile
import sys
try:
    with zipfile.ZipFile('$ZIP_FILE', 'r') as zip_ref:
        zip_ref.extractall('$TEMP_DIR')
    print("✓ File estratti con successo")
except Exception as e:
    print(f"✗ Errore nell'estrazione: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF

# Find the extracted directory (usually youtube-napoletano-main)
EXTRACTED_DIR=$(find "$TEMP_DIR" -maxdepth 1 -type d -name "*youtube-napoletano*" | head -1)
if [ -z "$EXTRACTED_DIR" ]; then
    echo "❌ Errore: Non riesco a trovare i file estratti."
    exit 1
fi

# Files/directories to update (exclude sensitive files)
EXCLUDE_PATTERNS=(
    ".git"
    ".gitignore"
    "__pycache__"
    ".DS_Store"
    "*.pyc"
    ".venv"
    "downloads"
    "youtube_napoletano/config.py"
    "yt-dlp-last-update.txt"
    "@eaDir"
)

# Create exclude pattern for rsync
EXCLUDE_ARGS=""
for pattern in "${EXCLUDE_PATTERNS[@]}"; do
    EXCLUDE_ARGS="$EXCLUDE_ARGS --exclude='$pattern'"
done

# Copy files
echo "📋 Aggiornando i file..."
eval "rsync -av --force $EXCLUDE_ARGS --delete '$EXTRACTED_DIR/' '.'"

echo ""
echo "✅ Aggiornamento completato con successo!"
echo ""
echo "Prossimi step:"
echo "  1. Verifica le modifiche: git status"
echo "  2. Se stai usando una configurazione personalizzata, controlla 'youtube_napoletano/config.py'"
echo "  3. Riavvia l'applicazione"
