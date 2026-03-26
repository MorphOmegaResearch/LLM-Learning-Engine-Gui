#!/bin/bash
# Import Organizer Launch Script
# Generated: 2026-02-23T01:03:20.784913

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python version
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)"; then
    echo "Error: Python 3.7+ required"
    exit 1
fi

# Run the organizer
python3 "import_organizer.py" "$@"

# Return exit code
exit $?
