#!/bin/bash
# ============================================================
# Cross-compile QuickJS per Synology DS216j (ARM Marvell Armada 385)
# Esegui questo script dal tuo PC Linux x86
# ============================================================
set -e

echo "=== STEP 1: Installa cross-compiler ARM ==="
sudo apt install -y gcc-arm-linux-gnueabihf

echo "=== STEP 2: Scarica QuickJS ==="
cd /tmp
wget -q https://bellard.org/quickjs/quickjs-2025-04-26.tar.xz
tar xf quickjs-2025-04-26.tar.xz

echo "=== STEP 3: Compila per ARM ==="
cd quickjs-2025-04-26
make clean
make CROSS_PREFIX=arm-linux-gnueabihf- qjs

echo "=== STEP 4: Verifica ==="
file qjs
# Deve dire: ELF 32-bit LSB executable, ARM, ...

echo ""
echo "============================================"
echo "COMPILAZIONE COMPLETATA!"
echo "Il binario e' in: /tmp/quickjs-2025-04-26/qjs"
echo ""
echo "Ora copia sul NAS con:"
echo "  scp /tmp/quickjs-2025-04-26/qjs pitto@<IP-NAS>:~/qjs"
echo ""
echo "Poi sul NAS via SSH esegui:"
echo "  mkdir -p ~/bin"
echo "  mv ~/qjs ~/bin/qjs"
echo "  chmod +x ~/bin/qjs"
echo "  echo 'export PATH=\"\$HOME/bin:\$PATH\"' >> ~/.profile"
echo "  source ~/.profile"
echo "  qjs --help"
echo ""
echo "Infine aggiorna l'app sul NAS:"
echo "  cd /path/to/youtube-napoletano"
echo "  git pull"
echo "  .venv/bin/pip install -r requirements.txt"
echo "============================================"
