#!/bin/bash
# Grep Flight v2 - Launcher Script

# Get the directory where the script is located to ensure it runs in the correct context
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Change to the script's directory
cd "$SCRIPT_DIR"

# Execute the python script, passing along any command-line arguments
python3 grep_flight_v2.py "$@"
