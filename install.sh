#!/bin/bash
# VaultLock Installer
# Installs the app so it appears in your Linux application menu
#
# Usage:
#   chmod +x install.sh
#   ./install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="vaultlock"
APP_DISPLAY_NAME="VaultLock"

echo "=== VaultLock Installer ==="
echo ""

# --- 1. Install the app launcher ---
echo "[1/4] Installing app launcher..."
mkdir -p "$HOME/.local/share/applications"

# Create a proper .desktop file with absolute Exec path
cat > "$HOME/.local/share/applications/vaultlock.desktop" << EOF
[Desktop Entry]
Name=$APP_DISPLAY_NAME
Comment=Lock and unlock folders with encryption
Exec=python3 $SCRIPT_DIR/main.py %f
Icon=$APP_NAME
Terminal=false
Type=Application
Categories=Utility;Security;System;
MimeType=inode/directory;
Keywords=folder;lock;encrypt;vault;security;
StartupNotify=true
EOF

echo "  → $HOME/.local/share/applications/vaultlock.desktop"

# --- 2. Install icons ---
echo "[2/4] Installing icons..."
ICON_DIR="$HOME/.local/share/icons/hicolor"
SIZES=(16 32 48 64 128 256 512)

for size in "${SIZES[@]}"; do
    mkdir -p "$ICON_DIR/${size}x${size}/apps"
    if [ -f "$SCRIPT_DIR/icons/vaultlock-${size}x${size}.png" ]; then
        cp "$SCRIPT_DIR/icons/vaultlock-${size}x${size}.png" "$ICON_DIR/${size}x${size}/apps/$APP_NAME.png"
        echo "  → ${size}x${size} icon installed"
    fi
done

# Also install a scalable SVG if available (use the 512px as fallback)
mkdir -p "$ICON_DIR/scalable/apps"

# --- 3. Update icon cache ---
echo "[3/4] Updating icon cache..."
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
echo "  → Icon cache updated"

# --- 4. Update desktop database ---
echo "[4/4] Updating desktop database..."
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo "  → Desktop database updated"

echo ""
echo "=== Installation complete! ==="
echo ""
echo "You can now:"
echo "  • Search for 'VaultLock' in your application menu"
echo "  • Right-click folders → 'Lock with VaultLock'"
echo "  • Run: python3 $SCRIPT_DIR/main.py"
echo ""
echo "To uninstall:"
echo "  rm $HOME/.local/share/applications/vaultlock.desktop"
echo "  rm -r $HOME/.local/share/icons/hicolor/*/apps/$APP_NAME.png"
