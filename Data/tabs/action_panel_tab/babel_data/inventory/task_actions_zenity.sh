#!/bin/bash
# Babel Task Manager - Zenity GUI
# Fast path to self-contained task workflow

BABEL_ROOT="/home/commander/Desktop/System_Journal/System_Journal/inventory/tools/scripts/Babel_v01a"
cd "$BABEL_ROOT"

while true; do
    ACTION=$(zenity --list --title="🏛️ Babel Task Manager" \
        --width=500 --height=400 \
        --text="Self-Contained Task Workflow" \
        --column="Action" --column="Description" \
        "List Tasks" "View all todos from 3 sources" \
        "Create Task" "New task (syncs everywhere)" \
        "Spawn Claude" "Launch Claude CLI session" \
        "Sync Todos" "3-way reconciliation" \
        "Mark Faulty" "Mark code/file as faulty" \
        "View Logs" "Show Os_Toolkit journal" \
        "Export Session" "Export complete Babel state" \
        "Exit" "Close task manager" \
        --hide-column=2)

    case "$ACTION" in
        "List Tasks")
            # Show all todos
            TASKS=$(python3 Os_Toolkit.py todo list 2>&1)

            zenity --text-info --title="📋 All Tasks" \
                --width=800 --height=600 \
                --text="$TASKS"
            ;;

        "Create Task")
            # Multi-field input
            RESULT=$(zenity --forms --title="Create New Task" \
                --text="Enter task details:" \
                --add-entry="Subject" \
                --add-entry="Description" \
                --add-entry="Tags (comma-separated)" \
                --add-entry="File/Target (optional)")

            if [ $? -eq 0 ]; then
                IFS='|' read -r SUBJECT DESC TAGS FILE <<< "$RESULT"

                # Create task via Os_Toolkit
                if [ -n "$FILE" ]; then
                    python3 Os_Toolkit.py todo create \
                        --subject "$SUBJECT" \
                        --description "$DESC" \
                        --tags "$TAGS" \
                        --file "$FILE"
                else
                    python3 Os_Toolkit.py todo create \
                        --subject "$SUBJECT" \
                        --description "$DESC" \
                        --tags "$TAGS"
                fi

                # Auto-sync
                python3 Os_Toolkit.py actions --run sync_all_todos

                zenity --info --title="✅ Success" \
                    --text="Task created & synced to all sources!\n\nSubject: $SUBJECT\nTags: $TAGS"
            fi
            ;;

        "Spawn Claude")
            # Get working directory
            WORK_DIR=$(zenity --file-selection --directory \
                --title="Select Working Directory" \
                --filename="$BABEL_ROOT/")

            if [ $? -eq 0 ]; then
                # Find Claude CLI
                CLAUDE_BIN="$HOME/.claude/local/node_modules/.bin/claude"
                if [ ! -f "$CLAUDE_BIN" ]; then
                    CLAUDE_BIN="claude"
                fi

                # Launch positioned terminal with Claude
                xfce4-terminal --title="🧠 Claude Session" \
                    --geometry=100x30+50+50 \
                    --working-directory="$WORK_DIR" \
                    --command="$CLAUDE_BIN" &

                CLAUDE_PID=$!

                zenity --info --title="🧠 Claude Started" \
                    --text="Claude CLI session launched!\n\nWorking dir: $WORK_DIR\nPID: $CLAUDE_PID\n\nTasks will auto-sync when you close it."

                # Wait for Claude to exit, then auto-sync
                (
                    wait $CLAUDE_PID
                    python3 Os_Toolkit.py actions --run sync_all_todos
                    zenity --notification --text="Claude session ended. Tasks synced!"
                ) &
            fi
            ;;

        "Sync Todos")
            # Run sync with GUI output
            python3 Os_Toolkit.py actions --run sync_all_todos -z
            ;;

        "Mark Faulty")
            # Select target (file or describe issue)
            CHOICE=$(zenity --list --title="Mark Faulty" \
                --column="Target Type" \
                "File/Directory" \
                "General Issue")

            if [ "$CHOICE" = "File/Directory" ]; then
                FILE=$(zenity --file-selection --title="Select File/Directory to Mark")
                if [ $? -eq 0 ]; then
                    REASON=$(zenity --entry --title="Faulty Reason" \
                        --text="Why is this faulty?")

                    if [ -n "$REASON" ]; then
                        # Add mark to code (if text file)
                        if [ -f "$FILE" ] && file "$FILE" | grep -q text; then
                            echo "" >> "$FILE"
                            echo "# [Mark:FAULTY:$REASON]" >> "$FILE"
                        fi

                        # Create debug todo
                        python3 Os_Toolkit.py todo create \
                            --subject "Debug: $(basename $FILE)" \
                            --description "Marked faulty: $REASON\n\nFile: $FILE" \
                            --tags "faulty,debug,auto-created"

                        # Log to journal
                        python3 Os_Toolkit.py journal --add \
                            --type "debug" \
                            --content "Marked faulty: $FILE - $REASON"

                        # Sync
                        python3 Os_Toolkit.py actions --run sync_all_todos

                        zenity --info --text="✅ Marked faulty!\n\nFile: $FILE\nReason: $REASON\n\nDebug todo created & synced."
                    fi
                fi
            else
                # General issue
                ISSUE=$(zenity --text-info --editable \
                    --title="Describe Issue" \
                    --width=600 --height=400)

                if [ -n "$ISSUE" ]; then
                    # Create debug todo
                    python3 Os_Toolkit.py todo create \
                        --subject "Debug: General Issue" \
                        --description "$ISSUE" \
                        --tags "faulty,debug,general"

                    python3 Os_Toolkit.py actions --run sync_all_todos

                    zenity --info --text="✅ Debug todo created & synced!"
                fi
            fi
            ;;

        "View Logs")
            # Show journal entries
            LOGS=$(python3 Os_Toolkit.py journal --query "" --limit 50 2>&1)

            zenity --text-info --title="📜 Os_Toolkit Journal" \
                --width=900 --height=700 \
                --text="$LOGS"
            ;;

        "Export Session")
            # Export with GUI
            python3 Os_Toolkit.py export -z
            ;;

        "Exit")
            zenity --question --title="Exit" \
                --text="Close Babel Task Manager?"

            if [ $? -eq 0 ]; then
                exit 0
            fi
            ;;

        *)
            # User cancelled
            exit 0
            ;;
    esac
done
