#!/bin/bash
set -o pipefail
# Main Launcher for grep_flight - Launches current configured version
# Reads stable.json to determine which version to launch

WARRIOR_FLOW_DIR="/home/commander/3_Inventory/Warrior_Flow"
STABLE_JSON="$WARRIOR_FLOW_DIR/stable.json"
LOG_ENABLED=0
log_msg() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg"
    if [ "$LOG_ENABLED" -eq 1 ]; then
        echo "$msg" >> "$LOG_FILE"
    fi
}

log_stream() {
    if [ "$LOG_ENABLED" -eq 1 ]; then
        tee -a "$LOG_FILE"
    else
        cat
    fi
}

notify_desktop() {
    if command -v notify-send >/dev/null 2>&1; then
        notify-send "Grep Flight Launcher" "$1" >/dev/null 2>&1 || true
    fi
}

find_fallback_version() {
    python3 - <<'PY'
import json
import sys

stable_path = "/home/commander/3_Inventory/Warrior_Flow/stable.json"
try:
    with open(stable_path, 'r') as f:
        data = json.load(f)
except Exception:
    sys.exit(0)

current = data.get("current_stable_version")
entries = []
for name, details in data.get("versions", {}).items():
    status = str(details.get("status", "")).lower()
    if name == current or status != 'stable':
        continue
    created = details.get('created_at') or ''
    entries.append((created, name))

if not entries:
    sys.exit(0)

entries.sort(reverse=True)
print(entries[0][1])
PY
}

run_traceback_mode() {
    log_msg "Attempting traceback-only mode for $ACTIVE_VERSION"
    notify_desktop "Trying traceback view for $ACTIVE_VERSION"
    if [ ! -f "$GREP_FLIGHT_MODULE" ]; then
        log_msg "Traceback mode aborted: module missing at $GREP_FLIGHT_MODULE"
        notify_desktop "Traceback mode failed (module missing)"
        exit 1
    fi

    (cd "$VERSION_ROOT" && python3 "$GREP_FLIGHT_MODULE" --traceback "$@") 2>&1 | log_stream
    status=$?
    if [ $status -eq 0 ]; then
        log_msg "Traceback window launched for $ACTIVE_VERSION"
        exit 0
    fi

    log_msg "Traceback mode failed (code $status). Falling back to CLI output."
    if [ "$LOG_ENABLED" -eq 1 ]; then
        notify_desktop "Traceback failed; running CLI fallback (log saved)."
    else
        notify_desktop "Traceback failed; running CLI fallback (no log file)."
    fi
    (cd "$VERSION_ROOT" && python3 "$GREP_FLIGHT_MODULE" --cli "$@") 2>&1 | log_stream
    status=$?
    if [ $status -eq 0 ]; then
        if [ "$LOG_ENABLED" -eq 1 ]; then
            log_msg "CLI fallback completed. Output saved to $LOG_FILE"
            notify_desktop "grep_flight CLI completed (see logs)"
        else
            log_msg "CLI fallback completed. Logging disabled; output printed to console"
            notify_desktop "grep_flight CLI completed (no log file)"
        fi
    else
        if [ "$LOG_ENABLED" -eq 1 ]; then
            log_msg "CLI fallback exited with code $status. See $LOG_FILE"
            notify_desktop "grep_flight CLI exited with code $status"
        else
            log_msg "CLI fallback exited with code $status. Logging disabled"
            notify_desktop "grep_flight CLI exited with code $status (no log file)"
        fi
    fi
    exit $status
}

echo "============================================"
echo "🚀 Warrior Flow - grep_flight Launcher"
echo "============================================"

# Check if stable.json exists
if [ ! -f "$STABLE_JSON" ]; then
    msg="❌ Error: stable.json not found at $STABLE_JSON"
    echo "$msg"
    notify_desktop "$msg"
    exit 1
fi

# Determine version to launch
# Priority: current_grep_flight_version > current_stable_version
VERSION_INFO=$(python3 -c "
import json
import os
try:
    with open('$STABLE_JSON', 'r') as f:
        data = json.load(f)
    
    # Try grep_flight specific version first
    gf_version = data.get('current_grep_flight_version', '')
    if gf_version:
        details = data.get('grep_flight_versions', {}).get(gf_version)
        if details:
            path = details.get('path', '')
            print(f'{gf_version}|grep_flight|{path}')
            exit(0)
        
    # Fallback to stable version
    stable_version = data.get('current_stable_version', '')
    path = ''
    if stable_version:
        details = data.get('versions', {}).get(stable_version)
        if details:
            path = details.get('path', '')
    print(f'{stable_version}|stable|{path}')
except Exception:
    print('|error|')
")

ACTIVE_VERSION=$(echo "$VERSION_INFO" | cut -d'|' -f1)
VERSION_TYPE=$(echo "$VERSION_INFO" | cut -d'|' -f2)
RELATIVE_PATH=$(echo "$VERSION_INFO" | cut -d'|' -f3)

if [ -z "$ACTIVE_VERSION" ]; then
    msg="❌ Error: Could not determine active version from stable.json"
    echo "$msg"
    notify_desktop "$msg"
    exit 1
fi

# Construct path to version-specific launcher / module
# Use the path from stable.json if available
if [ -n "$RELATIVE_PATH" ]; then
    VERSION_ROOT="$WARRIOR_FLOW_DIR/$RELATIVE_PATH"
else
    # Fallback to assumption
    VERSION_ROOT="$WARRIOR_FLOW_DIR/versions/$ACTIVE_VERSION"
fi

# For grep_flight versions pointing directly to the module dir, adjust paths
if [ "$VERSION_TYPE" == "grep_flight" ]; then
    # In this case, VERSION_ROOT is likely pointing to .../grep_flight_v0_2b
    # So the module is directly inside
    GREP_FLIGHT_MODULE="$VERSION_ROOT/grep_flight_v2.py"
    VERSION_LAUNCHER="$VERSION_ROOT/launcher.sh" # If it exists
    LOG_DIR="$VERSION_ROOT/logs"
else
    # Standard full version structure
    VERSION_LAUNCHER="$VERSION_ROOT/Launchers/launcher.sh"
    GREP_FLIGHT_MODULE="$VERSION_ROOT/Modules/action_panel/grep_flight_v0_2b/grep_flight_v2.py"
    LOG_DIR="$VERSION_ROOT/logs"
fi

DEFAULT_LOG_FILE="$LOG_DIR/grep_flight_launcher.log"
LOG_FILE="$DEFAULT_LOG_FILE"

# Log setup
LOG_TARGETS=()
LOG_TARGETS+=("$LOG_FILE")
ALT_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/warrior_flow"
LOG_TARGETS+=("$ALT_CACHE_DIR/grep_flight_launcher.log")
LOG_TARGETS+=("/tmp/grep_flight_launcher.log")

for candidate in "${LOG_TARGETS[@]}"; do
    if python3 - "$candidate" >/dev/null 2>&1 <<'PY'; then
from pathlib import Path
import sys

target = Path(sys.argv[1])
try:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('a'):
        pass
except OSError:
    sys.exit(1)
PY
        LOG_FILE="$candidate"
        LOG_ENABLED=1
        break
    fi
done

if [ "$LOG_ENABLED" -eq 0 ]; then
    echo "⚠️ Warning: Unable to write grep_flight log file; continuing without persistent logging." >&2
elif [ "$LOG_FILE" != "$DEFAULT_LOG_FILE" ]; then
    echo "ℹ️ Log file redirected to $LOG_FILE" >&2
fi

log_msg "Launching Grep Flight ($VERSION_TYPE) - $ACTIVE_VERSION"
echo "📦 Active Version: $ACTIVE_VERSION"
echo ""

# Determine launch method
if [ "$VERSION_TYPE" == "grep_flight" ]; then
    # Direct launch for pure grep_flight versions if they don't have full launchers
    if [ -f "$GREP_FLIGHT_MODULE" ]; then
        echo "🔗 Direct Launch: $GREP_FLIGHT_MODULE"
        cd "$VERSION_ROOT"
        python3 "$GREP_FLIGHT_MODULE" "$@"
        status=$?
    else
        echo "❌ Error: Module not found at $GREP_FLIGHT_MODULE"
        status=1
    fi
else
    # Standard launch for full versions
    if [ ! -f "$VERSION_LAUNCHER" ]; then
        echo "❌ Error: Launcher not found for $ACTIVE_VERSION"
        echo "   Expected: $VERSION_LAUNCHER"
        echo "Falling back to direct module launch..."
        
        if [ ! -f "$GREP_FLIGHT_MODULE" ]; then
            msg="❌ Error: grep_flight not found at $GREP_FLIGHT_MODULE"
            echo "$msg"
            log_msg "$msg"
            exit 1
        fi

        cd "$VERSION_ROOT"
        run_traceback_mode "$@"
    else
        echo "🔗 Launching via: $VERSION_LAUNCHER"
        "$VERSION_LAUNCHER" "$@"
        status=$?
    fi
fi

if [ $status -ne 0 ]; then
    log_msg "Launch failed with code $status"
    # Fallback logic could go here if needed
    notify_desktop "Launch failed ($ACTIVE_VERSION)"
else
    log_msg "Launch successful for $ACTIVE_VERSION"
fi

exit $status