#!/bin/bash
# target.sh - Universal Target Setter for Grep Flight
# Sends file/folder target to the ACTIVE grep_flight instance (version-aware)
# Usage: target.sh <path> [type]

set -euo pipefail

# Configuration
WARRIOR_FLOW_DIR="/home/commander/3_Inventory/Warrior_Flow"
STABLE_JSON="$WARRIOR_FLOW_DIR/stable.json"
IPC_FILE_BASE="${XDG_RUNTIME_DIR:-/tmp}/grep_flight_ipc_${USER}"
IPC_FILE="${IPC_FILE_BASE}.fifo"
LOG_FILE="${XDG_RUNTIME_DIR:-/tmp}/grep_flight_target_universal_${USER}.log"

# Notification will be sent after version is resolved (see below)

# Logging
log_debug() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S.%3N')
    echo "[${timestamp}] $*" | tee -a "${LOG_FILE}"
}

# Error handling
error_exit() {
    local exit_code=$?
    local line_no=$1
    local error_msg="${2:-Unknown error}"
    log_debug "ERROR (line ${line_no}): ${error_msg}"
    
    # Try to send error to IPC if it exists
    if [[ -p "${IPC_FILE}" ]]; then
        echo "ERROR|target.sh:${line_no}|${error_msg}|exit_code=${exit_code}" > "${IPC_FILE}" 2>/dev/null || true
    fi
    exit ${exit_code}
}
trap 'error_exit ${LINENO} "Script failed"' ERR

log_debug "=== target.sh invoked ==="

# 1. Determine Active Version
if [[ ! -f "${STABLE_JSON}" ]]; then
    error_exit ${LINENO} "stable.json not found"
fi

VERSION_INFO=$(python3 -c "
import json
try:
    with open('${STABLE_JSON}', 'r') as f:
        data = json.load(f)
    stable = data.get('current_stable_version', '')
    # Check if there is a specific grep_flight override
    gf_ver = data.get('current_grep_flight_version', '')
    path = ''
    if gf_ver:
         details = data.get('grep_flight_versions', {}).get(gf_ver)
         if details: path = details.get('path', '')
         print(f'{gf_ver}|{path}')
    elif stable:
         details = data.get('versions', {}).get(stable)
         if details: path = details.get('path', '')
         print(f'{stable}|{path}')
except:
    pass
")

ACTIVE_VERSION=$(echo "$VERSION_INFO" | cut -d'|' -f1)
RELATIVE_PATH=$(echo "$VERSION_INFO" | cut -d'|' -f2)

if [[ -z "${ACTIVE_VERSION}" ]]; then
    error_exit ${LINENO} "Could not determine active version"
fi

log_debug "Active Version: ${ACTIVE_VERSION}"
log_debug "Version Path: ${RELATIVE_PATH}"

# Enhanced notification with version/path context
if command -v notify-send &> /dev/null; then
    notify-send "grep_flight [${ACTIVE_VERSION}]" \
        "Target: $(basename "$1")\nVersion: ${ACTIVE_VERSION}\nPath: ${RELATIVE_PATH}" \
        -t 3000 -i system-search
fi

# 2. Resolve Path
if [[ $# -lt 1 ]]; then
    error_exit ${LINENO} "Usage: target.sh <path>"
fi

TARGET_PATH="$1"
TARGET_TYPE="${2:-auto}"

# Resolve absolute path
if [[ ! "${TARGET_PATH}" = /* ]]; then
    TARGET_PATH="$(cd "$(dirname "${TARGET_PATH}")" && pwd)/$(basename "${TARGET_PATH}")"
fi

if [[ ! -e "${TARGET_PATH}" ]]; then
    error_exit ${LINENO} "Path not found: ${TARGET_PATH}"
fi

# Auto-detect type
if [[ "${TARGET_TYPE}" == "auto" ]]; then
    if [[ -d "${TARGET_PATH}" ]]; then
        TARGET_TYPE="folder"
    elif [[ -f "${TARGET_PATH}" ]]; then
        TARGET_TYPE="file"
    else
        TARGET_TYPE="unknown"
    fi
fi

# Metadata
STAT_INFO=$(stat -c "size=%s,perms=%a,modified=%y" "${TARGET_PATH}" 2>/dev/null || echo "stat_failed")

# 3. Check/Launch grep_flight
# Match any process containing grep_flight_v2.py in its command line
GREP_FLIGHT_PID=$(pgrep -f "grep_flight_v2.py" | head -1 || true)

if [[ -z "${GREP_FLIGHT_PID}" ]]; then
    log_debug "grep_flight not running. Launching..."

    # Remove stale IPC file BEFORE launching (grep_flight will create fresh one)
    if [[ -p "${IPC_FILE}" ]]; then
        rm -f "${IPC_FILE}"
        log_debug "Removed stale IPC file"
    fi

    # Use the main launcher to ensure environment is correct
    LAUNCHER="${WARRIOR_FLOW_DIR}/launch_grep_flight_latest.sh"

    if [[ -f "${LAUNCHER}" ]]; then
        # Launch in background, redirecting output to avoid hanging the script
        "${LAUNCHER}" --gui > /dev/null 2>&1 &
        LAUNCHED_PID=$!
        log_debug "Launched PID: ${LAUNCHED_PID}"

        # Wait for IPC FIFO to be created (up to 20 seconds)
        log_debug "Waiting for grep_flight to create IPC FIFO..."
        for i in {1..40}; do
            if [[ -p "${IPC_FILE}" ]]; then
                log_debug "IPC FIFO appeared after ${i}/2 iterations"
                # Give grep_flight a moment to start listening
                sleep 1
                break
            fi
            sleep 0.5
        done
    else
        error_exit ${LINENO} "Launcher not found: ${LAUNCHER}"
    fi
fi

# 4. Send Target via IPC
# Wait for IPC availability and verify it's ready
log_debug "Checking IPC availability..."
for i in {1..20}; do
    if [[ -p "${IPC_FILE}" ]]; then
        log_debug "IPC FIFO exists, checking readiness..."
        break
    fi
    sleep 0.25
done

if [[ ! -p "${IPC_FILE}" ]]; then
    error_exit ${LINENO} "IPC FIFO not found: ${IPC_FILE}"
fi

# Brief pause to ensure grep_flight's monitor loop is running
sleep 0.3

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S.%3N')
# Format: MESSAGE_TYPE|path|type|metadata|timestamp
IPC_MESSAGE="SET_TARGET|${TARGET_PATH}|${TARGET_TYPE}|${STAT_INFO}|${TIMESTAMP}"

log_debug "Sending: ${IPC_MESSAGE}"

# Use a timeout to avoid hanging if the FIFO reader is stuck
# Increased timeout to 5 seconds to handle slow startup
if timeout 5 bash -c "echo '${IPC_MESSAGE}' > '${IPC_FILE}'" 2>/dev/null; then
    log_debug "✓ Target sent successfully"

    # Send success notification
    if command -v notify-send &> /dev/null; then
        notify-send "grep_flight" "✅ Target set: $(basename "${TARGET_PATH}")" -t 2000
    fi
    exit 0
else
    error_exit ${LINENO} "Failed to write to IPC (timeout or error)"
fi
