#!/bin/bash
# Update script for youtube-napoletano
# Downloads latest files from GitHub main branch and updates local files
# Usage: bash scripts/update.sh

set -e

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

# Extract ZIP
echo "📦 Estraendo i file..."
if ! command -v unzip &> /dev/null; then
    echo "❌ Errore: unzip non trovato. Installa unzip per procedere."
    exit 1
fi

unzip -q "$ZIP_FILE" -d "$TEMP_DIR"

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
)

# Create exclude pattern for rsync
EXCLUDE_ARGS=""
for pattern in "${EXCLUDE_PATTERNS[@]}"; do
    EXCLUDE_ARGS="$EXCLUDE_ARGS --exclude='$pattern'"
done

# Copy files
echo "📋 Aggiornando i file..."
eval "rsync -av $EXCLUDE_ARGS --delete '$EXTRACTED_DIR/' '.'"

echo ""
echo "✅ Aggiornamento completato con successo!"
echo ""
echo "Prossimi step:"
echo "  1. Verifica le modifiche: git status"
echo "  2. Se stai usando una configurazione personalizzata, controlla 'youtube_napoletano/config.py'"
echo "  3. Riavvia l'applicazione"
