#!/bin/bash
# Ag Forge Wrapper Script
# Navigates to the project directory and executes the Python launcher
# Hardened for debugging: Captures all output and alerts on failure.

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Navigate to that directory
cd "$DIR"

# Ensure logs directory exists
mkdir -p logs

# Define log file
LOG_FILE="$DIR/logs/launch_crash.log"

# Timestamp the start
echo "--- Launching Ag Forge at $(date) ---" >> "$LOG_FILE"

# Execute the Python launcher, capturing ALL output to log
# We also use 'tee' to show output in terminal if run manually
python3 launch_ag_forge.py "$@" 2>&1 | tee -a "$LOG_FILE"

# Capture exit code
EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -ne 0 ]; then
    echo "Ag Forge crashed with exit code $EXIT_CODE" >> "$LOG_FILE"
    
    # Try to show a GUI error message if possible
    if command -v zenity &> /dev/null; then
        zenity --error --text="Ag Forge crashed!\n\nCheck logs at:\n$LOG_FILE" --width=400
    elif command -v kdialog &> /dev/null; then
        kdialog --error "Ag Forge crashed!\n\nCheck logs at:\n$LOG_FILE"
    elif command -v xmessage &> /dev/null; then
        xmessage -center "Ag Forge crashed! Check logs at $LOG_FILE"
    fi
fi

exit $EXIT_CODE