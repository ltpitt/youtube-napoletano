#!/bin/bash
# ============================================================
# Cross-compile QuickJS per Synology DS216j (ARM Marvell Armada 385)
# Esegui questo script dal tuo PC Linux x86
# ============================================================
set -e

QJS_VERSION="2025-04-26"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$REPO_ROOT/runtimes/nas/armv7/ds216j"
OUT_BIN="$OUT_DIR/qjs"

echo "=== STEP 1: Installa cross-compiler ARM ==="
sudo apt install -y gcc-arm-linux-gnueabihf

if ! command -v arm-linux-gnueabihf-gcc >/dev/null 2>&1; then
	echo "Errore: arm-linux-gnueabihf-gcc non trovato nel PATH"
	exit 1
fi

echo "=== STEP 2: Scarica QuickJS ==="
cd /tmp
wget -q "https://bellard.org/quickjs/quickjs-${QJS_VERSION}.tar.xz"
rm -rf "quickjs-${QJS_VERSION}"
tar xf "quickjs-${QJS_VERSION}.tar.xz"

echo "=== STEP 3: Compila per ARM ==="
cd "quickjs-${QJS_VERSION}"
make clean
make CROSS_PREFIX=arm-linux-gnueabihf- LDFLAGS='-static' qjs

echo "=== STEP 4: Verifica ==="
file qjs
# Deve dire: ELF 32-bit LSB executable, ARM, ... ideally "statically linked"

echo "=== STEP 5: Copia nel repo ==="
mkdir -p "$OUT_DIR"
cp qjs "$OUT_BIN"
chmod +x "$OUT_BIN"
file "$OUT_BIN"

echo ""
echo "============================================"
echo "COMPILAZIONE COMPLETATA!"
echo "Binario aggiornato nel repo: $OUT_BIN"
echo ""
echo "Ora copia sul NAS nella stessa cartella del repo:"
echo "  scp $OUT_BIN pitto@<IP-NAS>:~/scripts/youtube-napoletano/runtimes/nas/armv7/ds216j/qjs"
echo ""
echo "Poi sul NAS via SSH esegui:"
echo "  cd ~/scripts/youtube-napoletano/runtimes/nas/armv7/ds216j"
echo "  chmod +x qjs"
echo "  file qjs"
echo "  ./qjs --help"
echo ""
echo "Infine aggiorna l'app sul NAS:"
echo "  cd ~/scripts/youtube-napoletano"
echo "  .venv/bin/pip install -r requirements.txt"
echo "  .venv/bin/python youtube_napoletano.py"
echo "============================================"
