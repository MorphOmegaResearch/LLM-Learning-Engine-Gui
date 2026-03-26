#!/usr/bin/env python3
"""
Project Status Generator
========================
Automates the creation of PROJECT_STATUS.md following the strict
Project_Template_1.md schema.

Scans for:
1. #[Mark:...] tags in the codebase.
2. Todo items in plans/todos.json.
3. Recent file modifications.
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime

# Configuration
TEMPLATE_FILE = "Project_Template_1.md"
OUTPUT_FILE = "PROJECT_STATUS_GENERATED.md"
PLANS_DIR = Path("plans")
TODO_FILE = PLANS_DIR / "todos.json"

def get_marks(root_dir):
    """Scan for #[Mark:...] tags."""
    marks = []
    for root, _, files in os.walk(root_dir):
        if "archive" in root or "node_modules" in root or "__pycache__" in root:
            continue
        for file in files:
            if not file.endswith(('.py', '.md', '.js', '.json')):
                continue
            
            path = Path(root) / file
            try:
                with open(path, 'r', errors='ignore') as f:
                    for i, line in enumerate(f):
                        if "#[Mark:" in line:
                            # Extract Mark ID
                            start = line.find("#[Mark:") + 7
                            end = line.find("]", start)
                            if end != -1:
                                mark_id = line[start:end]
                                marks.append({
                                    "file": str(path),
                                    "line": i + 1,
                                    "mark": mark_id,
                                    "content": line.strip()
                                })
            except Exception:
                pass
    return marks

def get_todos():
    """Load todos from JSON."""
    if not TODO_FILE.exists():
        return []
    try:
        with open(TODO_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def get_active_context():
    """Retrieve active process context from Os_Toolkit session."""
    try:
        # Find latest session
        sessions_dir = Path("babel_data/profile/sessions")
        if not sessions_dir.exists():
            return []
            
        sessions = sorted([d for d in sessions_dir.iterdir() if d.is_dir()], 
                         key=lambda x: x.stat().st_mtime)
        if not sessions:
            return []
            
        latest_session = sessions[-1]
        artifacts_file = latest_session / "artifacts.json"
        
        if not artifacts_file.exists():
            return []
            
        with open(artifacts_file, 'r') as f:
            artifacts = json.load(f)
            
        processes = []
        for art in artifacts.values():
            if art.get('artifact_type') == 'process':
                props = art.get('properties', {})
                cmd = props.get('command', 'unknown')
                user = props.get('user', 'unknown')
                processes.append(f"{cmd} (User: {user})")
        
        return processes[:10] # Limit to 10
    except Exception as e:
        print(f"[-] Error getting context: {e}")
        return []

def generate_report():
    print(f"[*] Scanning codebase for Marks and Todos...")
    
    marks = get_marks(".")
    todos = get_todos()
    active_processes = get_active_context()
    
    # Organize Marks by File
    marks_by_file = {}
    for m in marks:
        f = m['file']
        if f not in marks_by_file:
            marks_by_file[f] = []
        marks_by_file[f].append(m)

    # Build the Content
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    content = f"""</PROJECT_TEMPLATE_001>
###
</High_Level>:
- **Automated Status Report**: Generated at {timestamp}
- **System**: Babel_v01a (Project Intelligence Layer)
- **Status**: Integration Active

<High_Level>. |
##
</Mid_Level>:
- **Active Plans**: {len([t for t in todos if t.get('status') == 'in-progress'])} in-progress
- **Completed Tasks**: {len([t for t in todos if t.get('status') == 'done'])} done
- **Code Annotations**: {len(marks)} Marks found across codebase
- **Active Processes**: {len(active_processes)} detected in latest session

<Mid_Level/>. |
##
</Low_Level>:
- **Sync Status**: plans/todos.json is source of truth.
- **Traceability**: Code blocks are explicitly linked via #[Mark] tags.

<Low_Level/>. |
##
</Meta_Links>:
- **Todos**: `plans/todos.json`
- **Manifests**: `babel_data/timeline/manifests/`

<Meta_Links/>. |
##
</Provisions>:
#
[Packages]
- python3
- json
#
[Tools/Scripts]
- generate_project_status.py
- Filesync.py
- Os_Toolkit.py

<Provisions/>. |
##
</Current_Targets>:

[Context]
"""
    if active_processes:
        for p in active_processes:
            content += f"- {p}\n"
    else:
        content += "- No active processes detected in latest session.\n"

    content += """
[Files]:
"""
    # List top 5 most marked files
    sorted_files = sorted(marks_by_file.items(), key=lambda x: len(x[1]), reverse=True)[:5]
    for f, m_list in sorted_files:
        content += f"- {f} ({len(m_list)} marks)\n"

    content += """
[Goal(s)]:
- Standardize documentation format across projects.
- Automate status reporting.

<Current_Targets/>. |
##
</Diffs>: (Detected Marks)
"""
    
    for f, m_list in marks_by_file.items():
        content += f"#\n[File/Doc] - [{os.path.basename(f)}]\n"
        content += f"-{f}\n"
        for m in m_list:
            content += f" -Line {m['line']}\n"
            content += f"-#[Mark:{m['mark']}] - [Detected in Code]\n"
        content += "\n"

    content += """<Diffs/>. |
#
</Plans_manifested>:
- `generate_project_status.py`

<Plans_Manifested>. |
#
</Current_Todos>:
"""
    
    for todo in todos:
        status_char = "x" if todo.get('status') == 'done' else " "
        content += f"- [{status_char}] {todo.get('title', 'Untitled')} (ID: {todo.get('id')})\n"

    content += "\n<Current_Todos>. |"

    with open(OUTPUT_FILE, 'w') as f:
        f.write(content)
    
    print(f"[+] Report generated: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_report()