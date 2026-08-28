#!/bin/bash
# VaultLock - File Manager Integration Installer
#
# This script installs VaultLock integration for:
#   - Nautilus (GNOME Files)
#   - Nemo (Linux Mint/Cinnamon)
#   - Dolphin (KDE Plasma)
#
# Usage:
#   chmod +x install.sh
#   ./install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== VaultLock File Manager Integration Installer ==="
echo ""

# --- Nautilus ---
NAUTILUS_DIR="$HOME/.local/share/nautilus/scripts"
if [ -d "$NAUTILUS_DIR" ] || command -v nautilus &>/dev/null; then
    mkdir -p "$NAUTILUS_DIR"
    cp "$SCRIPT_DIR/nautilus/Lock with VaultLock" "$NAUTILUS_DIR/"
    chmod +x "$NAUTILUS_DIR/Lock with VaultLock"
    echo "[OK] Installed Nautilus script → $NAUTILUS_DIR/Lock with VaultLock"
else
    echo "[--] Nautilus not found, skipping"
fi

# --- Nemo ---
NEMO_DIR="$HOME/.local/share/nemo/scripts"
if [ -d "$NEMO_DIR" ] || command -v nemo &>/dev/null; then
    mkdir -p "$NEMO_DIR"
    cp "$SCRIPT_DIR/nautilus/Lock with VaultLock" "$NEMO_DIR/"
    chmod +x "$NEMO_DIR/Lock with VaultLock"
    echo "[OK] Installed Nemo script → $NEMO_DIR/Lock with VaultLock"
else
    echo "[--] Nemo not found, skipping"
fi

# --- Dolphin (KDE) ---
KSERVICES_DIR="$HOME/.local/share/kservicemenus5"
if [ -d "$KSERVICES_DIR" ] || command -v dolphin &>/dev/null; then
    mkdir -p "$KSERVICES_DIR"

    # Create a wrapper script for Dolphin (service menus can't pass %d easily)
    cat > "$KSERVICES_DIR/vaultlock-lock.sh" << 'WRAPPER'
#!/bin/bash
# Dolphin wrapper for VaultLock
# Gets the directory path from the context menu
SELECTED_DIR=$(echo "$1" | head -n1)
if [ -d "$SELECTED_DIR" ]; then
    python3 -c "
import sys, os
sys.path.insert(0, '$(dirname "$(realpath "$0")")/../../..')
os.chdir('$(dirname "$(realpath "$0")")/../../..')
from gi.repository import GLib
import subprocess
subprocess.Popen(['python3', '$(dirname "$(realpath "$0")")/../../main.py', '$SELECTED_DIR'])
" &>/dev/null &
fi
WRAPPER
    chmod +x "$KSERVICES_DIR/vaultlock-lock.sh"

    # Create the service menu desktop file
    cat > "$KSERVICES_DIR/vaultlock-lock.desktop" << DESKTOP
[Desktop Entry]
Type=Service
X-KDE-ServiceTypes=ServiceMenu
X-KDE-Submenu=VaultLock
Name=Lock Folder with VaultLock
Comment=Add folder to VaultLock for encryption
Icon=changes-prevent-symbolic
MimeType=inode/directory;
Actions=lockFolder
X-KDE-Submenu[en]=VaultLock

[Desktop Action lockFolder]
Name=Lock with VaultLock
Icon=changes-prevent-symbolic
Exec=bash -c 'python3 "$PROJECT_DIR/main.py" "%f" 2>/dev/null || python3 "$PROJECT_DIR/main.py" &
DESKTOP

    echo "[OK] Installed Dolphin service menu → $KSERVICES_DIR/vaultlock-lock.desktop"
else
    echo "[--] Dolphin not found, skipping"
fi

echo ""
echo "=== Installation complete ==="
echo ""
echo "You may need to restart your file manager for changes to take effect:"
echo "  Nautilus:  nautilus -q"
echo "  Nemo:      nemo --quit"
echo "  Dolphin:   doesn't need restart"
echo ""
echo "Right-click any folder to see 'Lock with VaultLock' in the context menu."
