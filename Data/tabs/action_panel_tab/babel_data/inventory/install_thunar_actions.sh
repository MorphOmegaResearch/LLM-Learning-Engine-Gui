#!/bin/bash
# Install Babel Thunar Custom Actions

UCA_FILE="$HOME/.config/Thunar/uca.xml"
BACKUP_FILE="$HOME/.config/Thunar/uca.xml.backup.$(date +%Y%m%d_%H%M%S)"

# Backup existing UCA
if [ -f "$UCA_FILE" ]; then
    cp "$UCA_FILE" "$BACKUP_FILE"
    echo "[+] Backed up existing UCA: $BACKUP_FILE"
fi

# Get absolute path to Babel
# Script is in babel_data/inventory/ -> Go up 2 levels for root
BABEL_ROOT="$(dirname "$(readlink -f "$0")")/../.."
# Resolve to absolute path
BABEL_ROOT="$(cd "$BABEL_ROOT" && pwd)"

TARGET_SCRIPT="$BABEL_ROOT/babel_data/inventory/target.sh"

if [ ! -f "$TARGET_SCRIPT" ]; then
    echo "[!] target.sh not found at $TARGET_SCRIPT"
    exit 1
fi

chmod +x "$TARGET_SCRIPT"

# Generate UCA XML (append to existing or create new)
# Note: This appends to the file. If <actions> tag is closed, it might be invalid XML.
# ideally we should insert before </actions>

if [ ! -f "$UCA_FILE" ]; then
    echo '<?xml version="1.0" encoding="UTF-8"?>' > "$UCA_FILE"
    echo '<actions>' >> "$UCA_FILE"
    echo '</actions>' >> "$UCA_FILE"
fi

# Prepare action XML
ACTION_XML="
<action>
    <icon>system-search</icon>
    <name>Babel Target</name>
    <unique-id>babel-target-$(date +%s)</unique-id>
    <command>bash $TARGET_SCRIPT %f query</command>
    <description>Query target with Babel (Os_Toolkit/Grep Flight)</description>
    <patterns>*</patterns>
    <directories/>
    <audio-files/>
    <image-files/>
    <other-files/>
    <text-files/>
    <video-files/>
</action>
<action>
    <icon>edit-find</icon>
    <name>Babel: Grep Flight</name>
    <unique-id>babel-grep-$(date +%s)</unique-id>
    <command>bash $TARGET_SCRIPT %f grep</command>
    <description>Launch grep_flight with this target</description>
    <patterns>*</patterns>
    <directories/>
    <text-files/>
</action>"

# Insert before </actions>
# Use temporary file to construct new XML
sed -i '$d' "$UCA_FILE" # Remove last line (</actions>)
echo "$ACTION_XML" >> "$UCA_FILE"
echo '</actions>' >> "$UCA_FILE"

echo "[+] Installed Babel Thunar actions"
echo "[*] Restart Thunar to see changes: thunar -q && thunar &"
