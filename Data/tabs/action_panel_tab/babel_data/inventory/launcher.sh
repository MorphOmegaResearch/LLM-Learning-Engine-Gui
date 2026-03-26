#!/bin/bash
# Babel System Launcher
# 1. Show System Status (Os_Toolkit latest)
# 2. Launch Grep Flight GUI

# Resolve Babel root: Script is in babel_data/inventory/ -> Go up 2 levels
BABEL_ROOT="$(dirname "$(readlink -f "$0")")/../.."

# Check paths
OS_TOOLKIT="Os_Toolkit.py"
GREP_FLIGHT="babel_data/inventory/action_panel/grep_flight_v0_2b/grep_flight_babel.py"

# Change to root dir so tools find their data
cd "$BABEL_ROOT" || exit 1

if [ ! -f "$OS_TOOLKIT" ]; then
    echo "[!] Os_Toolkit.py not found at $(pwd)/$OS_TOOLKIT"
    exit 1
fi

# 1. Show System Status (Zenity)
echo "[*] Loading System Status..."
python3 "$OS_TOOLKIT" latest -z &
STATUS_PID=$!

# Wait a moment for status to appear
sleep 2

# 2. Launch Grep Flight
echo "[*] Launching Grep Flight..."
python3 "$GREP_FLIGHT" --gui &

# Wait for status window to close (optional)
# wait $STATUS_PID
