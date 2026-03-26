#!/bin/bash

# Navigate to the script's directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Execute the Python application
# Pass all arguments from the desktop entry or direct shell call to the Python script
/usr/bin/python3 clip.py "$@"
