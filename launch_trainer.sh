#!/bin/bash

# Define paths
APP_DIR="/home/commander/Desktop/Trainer"
PYTHON_SCRIPT="$APP_DIR/Data/interactive_trainer_gui_NEW.py"
DEBUG_DIR="$APP_DIR/Data/DeBug"

# Ensure debug directory exists
mkdir -p "$DEBUG_DIR"

# Generate a unique temporary log file for this launch attempt
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TEMP_LOG="$DEBUG_DIR/startup_wrapper_temp_$TIMESTAMP.log"

# --- Attempt to launch silently ---
# Redirect stdout and stderr to the temporary log file
python3 "$PYTHON_SCRIPT" > "$TEMP_LOG" 2>&1
EXIT_CODE=$?

# Check if the application launched successfully
if [ $EXIT_CODE -eq 0 ]; then
    # If successful, the Python app would have already handled its logging.
    # We can just clean up the temp log if it's empty or not needed.
    # For now, we'll leave it for debugging the wrapper itself.
    # rm -f "$TEMP_LOG" # Uncomment to clean up temp log on success
    exit 0
else
    # --- If silent launch failed, open a terminal and re-launch ---
    # Display a user-friendly message
    zenity --error --title="Application Launch Failed" --text="The OpenCode Trainer failed to launch.\n\nDetails have been saved to the debug log.\n\nAttempting to re-launch in a terminal to show the error." 2>/dev/null

    # Re-launch in a terminal to show the error output
    # We pass the temporary log file path as an environment variable
    # so the Python app can merge it into its main log.
    # We also pass the main debug log path to ensure consistency.
    export GEMINI_WRAPPER_TEMP_LOG="$TEMP_LOG"
    export GEMINI_LOG_FILE="$DEBUG_DIR/debug_log_$TIMESTAMP.txt" # Ensure Python uses a consistent log name

    # Use xterm or gnome-terminal, depending on availability
    if command -v gnome-terminal &> /dev/null; then
        gnome-terminal --title="OpenCode Trainer - Debug Output" -- bash -c "python3 \"$PYTHON_SCRIPT\"; echo -e '\nPress Enter to close this window...'; read"
    elif command -v xterm &> /dev/null; then
        xterm -title "OpenCode Trainer - Debug Output" -e "python3 \"$PYTHON_SCRIPT\"; echo -e '\nPress Enter to close this window...'; read"
    else
        # Fallback if no common terminal is found
        zenity --error --title="Terminal Not Found" --text="Could not find gnome-terminal or xterm to display debug output. Please check the log file manually: $TEMP_LOG" 2>/dev/null
        exit 1
    fi
    exit $EXIT_CODE
fi
