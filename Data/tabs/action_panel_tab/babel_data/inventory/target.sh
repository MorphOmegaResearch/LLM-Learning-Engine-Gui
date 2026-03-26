#!/bin/bash
# Babel Target Dispatcher
# Routes right-click actions to appropriate Babel tool based on file type

TARGET="$1"
ACTION="${2:-query}"  # Default action: query

# Resolve Babel root: Script is in babel_data/inventory/ -> Go up 2 levels
BABEL_ROOT="$(dirname "$(readlink -f "$0")")/../.."

# Change to root dir so tools find their data
cd "$BABEL_ROOT" || exit 1

# Ensure paths are correct
if [ ! -f "Os_Toolkit.py" ]; then
    # Fallback to current directory if script moved
    echo "[!] Os_Toolkit.py not found in $(pwd)"
    exit 1
fi

# Detect file type
if [ -d "$TARGET" ]; then
    TYPE="directory"
elif [ -f "$TARGET" ]; then
    EXT="${TARGET##*.}"
    case "$EXT" in
        py) TYPE="python" ;;
        sh|bash) TYPE="shell" ;;
        js|ts) TYPE="javascript" ;;
        json|yaml|yml|toml) TYPE="config" ;;
        md|txt|rst) TYPE="text" ;;
        *) TYPE="unknown" ;;
    esac
else
    TYPE="unknown"
fi

# Route to appropriate command
case "$ACTION" in
    query)
        case "$TYPE" in
            directory)
                # Directory -> Launch Grep Flight with target
                python3 "babel_data/inventory/action_panel/grep_flight_v0_2b/grep_flight_babel.py" \
                    --gui --target "$TARGET"
                ;;
            *)
                # File -> Show Os_Toolkit Profile in Zenity
                OUTPUT=$(python3 "Os_Toolkit.py" file "$TARGET" --depth 2 2>&1)
                echo "$OUTPUT" | zenity --text-info --title="Babel Profile: $(basename "$TARGET")" \
                    --width=900 --height=700 --font="Monospace 10"
                ;;
        esac
        ;;

    grep)
        # Grep Flight Launch Logic
        if [ "$TYPE" == "directory" ]; then
             python3 "babel_data/inventory/action_panel/grep_flight_v0_2b/grep_flight_babel.py" \
                --gui --target "$TARGET"
        else
             # For files: Set target to parent dir, pattern to filename
             PARENT=$(dirname "$TARGET")
             NAME=$(basename "$TARGET")
             python3 "babel_data/inventory/action_panel/grep_flight_v0_2b/grep_flight_babel.py" \
                --gui --target "$PARENT" --pattern "$NAME"
        fi
        ;;

    organize)
        python3 "Filesync.py" "$TARGET" --organize -z
        ;;

    profile)
        if [ "$TYPE" = "python" ]; then
            python3 "Os_Toolkit.py" file "$TARGET" --depth 2 -z
        else
            zenity --info --text="Profiling only available for Python files (use Query for others)"
        fi
        ;;

    *)
        zenity --error --text="Unknown action: $ACTION"
        ;;
esac