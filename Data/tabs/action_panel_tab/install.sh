#!/usr/bin/env bash
# Babel Installation Script
# Checks dependencies and sets up environment

set -e

echo "======================================"
echo "Babel v0.1.0 - Installation"
echo "======================================"
echo ""

# Check Python version
echo "[1/5] Checking Python..."
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version | cut -d' ' -f2)
    PY_MAJOR=$(echo $PY_VERSION | cut -d'.' -f1)
    PY_MINOR=$(echo $PY_VERSION | cut -d'.' -f2)

    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 8 ]; then
        echo "  ✓ Python $PY_VERSION (OK)"
    else
        echo "  ✗ Python $PY_VERSION (need >= 3.8)"
        exit 1
    fi
else
    echo "  ✗ Python 3 not found"
    exit 1
fi

# Check optional dependencies
echo ""
echo "[2/5] Checking optional dependencies..."

if command -v zenity &> /dev/null; then
    echo "  ✓ Zenity (GUI dialogs available)"
else
    echo "  ⚠ Zenity not found (GUI features disabled)"
    echo "    Install: sudo apt install zenity"
fi

if command -v git &> /dev/null; then
    echo "  ✓ Git (version control available)"
else
    echo "  ⚠ Git not found (some features limited)"
    echo "    Install: sudo apt install git"
fi

# Create data directories
echo ""
echo "[3/5] Creating data directories..."
mkdir -p babel_data/{profile,timeline,inventory}/{sessions,manifests,organized}
mkdir -p plans
mkdir -p .babel
echo "  ✓ Directory structure created"

# Make scripts executable
echo ""
echo "[4/5] Making scripts executable..."
chmod +x babel 2>/dev/null || true
chmod +x bin/Os_Toolkit.py 2>/dev/null || Os_Toolkit.py 2>/dev/null || true
chmod +x bin/Filesync.py 2>/dev/null || Filesync.py 2>/dev/null || true
chmod +x bin/onboarder.py 2>/dev/null || onboarder.py 2>/dev/null || true
echo "  ✓ Scripts made executable"

# Offer to add to PATH
echo ""
echo "[5/5] PATH configuration..."
BABEL_DIR="$(pwd)"
if echo "$PATH" | grep -q "$BABEL_DIR"; then
    echo "  ✓ Already in PATH"
else
    echo "  ⚠ Not in PATH"
    read -p "  Add to PATH? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        SHELL_RC="$HOME/.bashrc"
        if [ -f "$HOME/.zshrc" ]; then
            SHELL_RC="$HOME/.zshrc"
        fi
        echo "" >> "$SHELL_RC"
        echo "# Babel launcher" >> "$SHELL_RC"
        echo "export PATH=\"$BABEL_DIR:\$PATH\"" >> "$SHELL_RC"
        echo "  ✓ Added to $SHELL_RC"
        echo "  Run: source $SHELL_RC"
    fi
fi

echo ""
echo "======================================"
echo "Installation Complete!"
echo "======================================"
echo ""
echo "Quick Start:"
echo "  ./babel --help          Show help"
echo "  ./babel morning         Morning briefing"
echo "  ./babel catalog         Full system catalog"
echo "  ./babel latest -z       System state (GUI)"
echo ""
echo "If added to PATH, use: babel <command>"
echo ""
