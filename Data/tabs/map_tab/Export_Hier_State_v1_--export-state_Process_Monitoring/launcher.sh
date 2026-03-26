#!/bin/bash
# Secure View Launcher with GUI Error Reporting

# Get script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

LOG_FILE="$DIR/logs/LAUNCH_ERROR.log"
mkdir -p "$DIR/logs"

echo "Starting Secure View..."

# Run the application. If it exits with a non-zero code, trigger the GUI Error Reporter.
(python3 secure_view.py > "$LOG_FILE" 2>&1) || {
    EXIT_CODE=$?
    # Use a small python snippet to show a GUI popup about the crash
    # It reads the last few lines of the error log to show the traceback context.
    TRACEBACK=$(tail -n 15 "$LOG_FILE" | sed 's/"/\\"/g')
    
    python3 -c "
import tkinter as tk
from tkinter import messagebox
import os

root = tk.Tk()
root.withdraw()
msg = \"Secure View failed to start or crashed.\n\nExit Code: $EXIT_CODE\nLog Location: $LOG_FILE\n\n--- Recent Traceback ---
$TRACEBACK\" 
messagebox.showerror('Secure View - Launch Failure', msg)
root.destroy()
"
}
