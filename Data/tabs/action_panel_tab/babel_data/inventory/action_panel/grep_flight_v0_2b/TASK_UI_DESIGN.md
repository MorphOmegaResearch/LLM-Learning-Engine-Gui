# task_ui.py - Unified Task Manager Design
**Comprehensive Task Creation & Management System**

---

## Current Systems Analysis

### 1. warrior_gui.py Task System
**Location:** warrior_gui.py:4161 `create_task()`

**Key Features:**
- Routes to TaskPanel
- Works with/without project context
- Phase-based task creation
- Workspace integration

**Task Data Fields (from warrior_gui + taskforge.py):**
```python
@dataclass
class Task:
    id: str
    description: str
    status: TaskStatus  # pending, active, completed, deleted, waiting
    created: datetime
    modified: datetime
    due: Optional[datetime]
    priority: str  # H/M/L
    tags: List[str]
    project: str
    dependencies: List[str]
    assigned_profile: Optional[str]
    notes: str
    metadata: Dict[str, Any]
```

### 2. planner_wizard.py Business Plan System
**Location:** Modules/plan/planner_wizard.py

**5-Step Wizard:**
1. **Context** - Epic name, description
2. **Strategy** - Approach, methodology
3. **Structure** - Phases breakdown
4. **Tasks** - Task definitions per phase
5. **Review** - Final validation

**Plan Data Fields:**
```python
{
    "epic_name": str,
    "description": str,
    "phases": [
        {
            "name": str,
            "tasks": [
                {
                    "name": str,
                    "type": str,
                    "description": str,
                    "estimated_time": str
                }
            ]
        }
    ]
}
```

### 3. grep_flight Tasks Tab (Current)
**Location:** grep_flight_v2.py:1219

**Current Features:**
- Task list display
- Type filter (research/plan/implement/review/test/debug)
- Status filter (pending/in_progress/completed)
- Links to warrior_gui Tasks & Planner tabs
- Task details view

**Missing Features (To Add):**
- ✗ Task creation UI
- ✗ Task editing UI
- ✗ File type specifications
- ✗ Expected content tracking
- ✗ Backup-targets button
- ✗ Restore-point button
- ✗ Traceback log linking

---

## New Unified Task Data Model

### Enhanced task.json Schema

```json
{
  "id": "task_20260116_234500_abc123",
  "version": "2.0",
  "created": "2026-01-16T23:45:00",
  "modified": "2026-01-16T23:50:00",

  "core": {
    "title": "Implement user authentication",
    "description": "Add JWT-based authentication to API",
    "type": "feature_implementation",
    "status": "in_progress",
    "priority": "high",
    "tags": ["security", "backend", "api"]
  },

  "assignment": {
    "assigned_to": "commander",
    "assigned_profile": "code_bert",
    "due_date": "2026-01-20T17:00:00",
    "estimated_hours": 8.0
  },

  "context": {
    "project": "warrior_flow",
    "phase": "implementation",
    "epic_id": "epic_auth_system",
    "dependencies": ["task_database_setup"],
    "blocks": []
  },

  "files": {
    "operations": [
      {
        "type": "new",
        "path": "Modules/auth/jwt_handler.py",
        "purpose": "JWT token generation and validation",
        "expected": {
          "lines": "100-150",
          "imports": ["jwt", "datetime", "hashlib"],
          "classes": ["JWTHandler"],
          "functions": ["generate_token", "validate_token", "refresh_token"],
          "tests": true
        }
      },
      {
        "type": "edit",
        "path": "Modules/api/routes.py",
        "purpose": "Add authentication middleware",
        "expected": {
          "lines_added": "50-75",
          "functions_modified": ["init_routes"],
          "new_imports": ["jwt_handler"]
        }
      },
      {
        "type": "remove",
        "path": "Modules/auth/old_auth.py",
        "reason": "Deprecated, replaced by JWT system"
      }
    ],
    "provisions": [
      {
        "type": "research_file",
        "path": "docs/jwt_best_practices.md",
        "purpose": "Security guidelines reference"
      },
      {
        "type": "script_dependency",
        "path": "scripts/test_auth.sh",
        "purpose": "Testing authentication flow"
      },
      {
        "type": "package_requirement",
        "package": "PyJWT",
        "version": ">=2.8.0",
        "purpose": "JWT library"
      }
    ]
  },

  "expectations": {
    "success_criteria": [
      "JWT tokens generated successfully",
      "Token validation working",
      "All tests passing"
    ],
    "validation_checks": [
      "syntax_check",
      "type_check",
      "security_scan",
      "test_coverage"
    ],
    "quality_gates": {
      "min_test_coverage": 0.80,
      "max_complexity": 10,
      "security_level": "strict"
    }
  },

  "tracking": {
    "backup_targets": [
      {
        "snapshot_id": "backup_20260116_234500",
        "timestamp": "2026-01-16T23:45:00",
        "files": [
          {"path": "Modules/api/routes.py", "hash": "abc123..."},
          {"path": "Modules/auth/jwt_handler.py", "hash": "def456..."}
        ],
        "description": "Before JWT implementation"
      }
    ],
    "restore_points": [
      {
        "id": "restore_20260116_235000",
        "timestamp": "2026-01-16T23:50:00",
        "trigger": "completion_milestone",
        "conditions": {
          "tests_passed": true,
          "bugs_tracked": 0,
          "completion_percentage": 50
        },
        "snapshot_ref": "backup_20260116_234500"
      }
    ],
    "traceback_logs": [
      {
        "log_id": "traceback_20260116_235500",
        "timestamp": "2026-01-16T23:55:00",
        "export_path": ".docv2_workspace/logs/grep_flight_log_20260116_235500.log",
        "event_types": ["ERROR", "WARNING", "TASK"],
        "event_count": 15
      }
    ]
  },

  "progress": {
    "completion_percentage": 50,
    "time_spent_hours": 4.0,
    "milestones": [
      {
        "name": "JWT handler implemented",
        "completed": true,
        "timestamp": "2026-01-16T23:50:00"
      },
      {
        "name": "Tests written",
        "completed": false
      }
    ],
    "blockers": [],
    "notes": [
      {
        "timestamp": "2026-01-16T23:45:00",
        "author": "commander",
        "content": "Using PyJWT library as recommended"
      }
    ]
  },

  "results": {
    "outcome": null,  // success | failure | partial
    "artifacts": [],
    "lessons_learned": [],
    "follow_up_tasks": []
  }
}
```

---

## task_ui.py Implementation

### UI Components

```
┌─────────────────────────────────────────────────────────────┐
│  📋 Task Manager                                   [✕]      │
├─────────────────────────────────────────────────────────────┤
│  [New Task ▼] [Edit Task] [Delete Task] [Duplicate]        │
│  [Backup Targets] [Create Restore Point] [Export Log]      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Task Type: [Feature Implementation    ▼]          │    │
│  │                                                     │    │
│  │ Title: ┌──────────────────────────────────────┐   │    │
│  │        │ Implement user authentication        │   │    │
│  │        └──────────────────────────────────────┘   │    │
│  │                                                     │    │
│  │ Description: ┌──────────────────────────────┐     │    │
│  │              │ Add JWT-based auth...         │     │    │
│  │              │                                │     │    │
│  │              └──────────────────────────────┘     │    │
│  │                                                     │    │
│  │ ┌─── File Operations ───────────────────────┐     │    │
│  │ │                                            │     │    │
│  │ │ [+] New File                              │     │    │
│  │ │ [+] Edit Existing File                    │     │    │
│  │ │ [+] Remove File                           │     │    │
│  │ │                                            │     │    │
│  │ │ ▶ jwt_handler.py (NEW)                    │     │    │
│  │ │   Expected Lines: 100-150                 │     │    │
│  │ │   Imports: jwt, datetime, hashlib         │     │    │
│  │ │   Classes: JWTHandler                     │     │    │
│  │ │   Functions: generate_token, validate...  │     │    │
│  │ │   Tests Required: ✓                       │     │    │
│  │ │                                            │     │    │
│  │ │ ▶ routes.py (EDIT)                        │     │    │
│  │ │   Lines Added: 50-75                      │     │    │
│  │ │   Functions Modified: init_routes         │     │    │
│  │ │                                            │     │    │
│  │ └────────────────────────────────────────────┘     │    │
│  │                                                     │    │
│  │ ┌─── Provisions ────────────────────────────┐     │    │
│  │ │                                            │     │    │
│  │ │ [+] Research File                         │     │    │
│  │ │ [+] Script Dependency                     │     │    │
│  │ │ [+] Package Requirement                   │     │    │
│  │ │                                            │     │    │
│  │ │ 📄 jwt_best_practices.md (RESEARCH)       │     │    │
│  │ │ 🔧 test_auth.sh (SCRIPT)                  │     │    │
│  │ │ 📦 PyJWT>=2.8.0 (PACKAGE)                 │     │    │
│  │ └────────────────────────────────────────────┘     │    │
│  │                                                     │    │
│  │ Priority: ⚪ Low ⚫ Medium ⚪ High                 │    │
│  │ Tags: [security] [backend] [api] [+]             │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  [Save Task] [Cancel] [Save & Create Milestone]            │
└─────────────────────────────────────────────────────────────┘
```

### File Operation Dialog

```
┌─────────────────────────────────────────────────────┐
│  Add File Operation                       [✕]      │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Operation Type:  ⚫ New  ⚪ Edit  ⚪ Remove        │
│                                                      │
│  File Path: ┌──────────────────────┐ [Browse...]   │
│             │ Modules/auth/jwt...  │               │
│             └──────────────────────┘               │
│                                                      │
│  Purpose: ┌────────────────────────────────┐       │
│           │ JWT token generation and...    │       │
│           └────────────────────────────────┘       │
│                                                      │
│  ┌─── Expected Content (Optional) ──────────┐      │
│  │                                           │      │
│  │ Lines: [100] to [150]                    │      │
│  │                                           │      │
│  │ Imports (comma-separated):               │      │
│  │ ┌───────────────────────────────────┐    │      │
│  │ │ jwt, datetime, hashlib            │    │      │
│  │ └───────────────────────────────────┘    │      │
│  │                                           │      │
│  │ Classes (comma-separated):               │      │
│  │ ┌───────────────────────────────────┐    │      │
│  │ │ JWTHandler                        │    │      │
│  │ └───────────────────────────────────┘    │      │
│  │                                           │      │
│  │ Functions (comma-separated):             │      │
│  │ ┌───────────────────────────────────┐    │      │
│  │ │ generate_token, validate_token... │    │      │
│  │ └───────────────────────────────────┘    │      │
│  │                                           │      │
│  │ ☑ Tests Required                         │      │
│  └───────────────────────────────────────────┘      │
│                                                      │
│  [Add] [Cancel]                                     │
└─────────────────────────────────────────────────────┘
```

### Backup Targets Dialog

```
┌─────────────────────────────────────────────────────┐
│  Backup Current Targets                   [✕]      │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Files to backup:                                   │
│  ☑ Modules/api/routes.py                           │
│  ☑ Modules/auth/jwt_handler.py                     │
│  ☐ Modules/auth/__init__.py                        │
│                                                      │
│  Description: ┌────────────────────────────────┐   │
│               │ Before JWT implementation      │   │
│               └────────────────────────────────┘   │
│                                                      │
│  Backup Location:                                   │
│  ⚫ Task-linked (.docv2_workspace/backups/task_id) │
│  ⚪ Custom location                                 │
│                                                      │
│  [Create Backup] [Cancel]                          │
└─────────────────────────────────────────────────────┘
```

### Restore Point Dialog

```
┌─────────────────────────────────────────────────────┐
│  Create Restore Point                     [✕]      │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Restore Point Name: ┌───────────────────────┐     │
│                      │ 50% Complete Milestone│     │
│                      └───────────────────────┘     │
│                                                      │
│  Link to Backup: [backup_20260116_234500    ▼]    │
│                                                      │
│  ┌─── Auto-Trigger Conditions (Future) ────┐       │
│  │                                          │       │
│  │ Trigger Type: [Manual              ▼]   │       │
│  │                                          │       │
│  │ ☐ On completion milestone (%)           │       │
│  │   Percentage: [50]%                      │       │
│  │                                          │       │
│  │ ☐ On bug count threshold                │       │
│  │   Max bugs: [0]                          │       │
│  │                                          │       │
│  │ ☐ On test failure                        │       │
│  │                                          │       │
│  │ ☐ On runtime error in traceback         │       │
│  └──────────────────────────────────────────┘       │
│                                                      │
│  [Create Restore Point] [Cancel]                   │
└─────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Core task_ui.py Module
**File:** `grep_flight_v0_2b/task_ui.py`

```python
#!/usr/bin/env python3
"""
task_ui.py - Unified Task Manager UI
Comprehensive task creation and management for grep_flight & warrior_flow
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid

class TaskType:
    """Task type constants"""
    RESEARCH = "research"
    PLAN = "plan"
    IMPLEMENT = "implement"
    REVIEW = "review"
    TEST = "test"
    DEBUG = "debug"
    FEATURE = "feature_implementation"
    REFACTOR = "refactoring"
    DOCUMENTATION = "documentation"

class FileOperationType:
    NEW = "new"
    EDIT = "edit"
    REMOVE = "remove"

class ProvisionType:
    RESEARCH_FILE = "research_file"
    SCRIPT_DEPENDENCY = "script_dependency"
    PACKAGE_REQUIREMENT = "package_requirement"

class TaskManagerUI(tk.Toplevel):
    """Main task manager UI"""

    def __init__(self, parent, mode="create", task_data=None):
        super().__init__(parent)
        self.title("Task Manager")
        self.geometry("800x900")
        self.configure(bg='#1e1e1e')

        self.mode = mode  # "create" or "edit"
        self.task_data = task_data or self._default_task_data()

        self.setup_ui()

    def _default_task_data(self) -> Dict:
        """Generate default task data structure"""
        return {
            "id": f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
            "version": "2.0",
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
            "core": {
                "title": "",
                "description": "",
                "type": TaskType.IMPLEMENT,
                "status": "pending",
                "priority": "medium",
                "tags": []
            },
            "files": {
                "operations": [],
                "provisions": []
            },
            "tracking": {
                "backup_targets": [],
                "restore_points": [],
                "traceback_logs": []
            }
        }

    def setup_ui(self):
        """Setup UI components"""
        # Header toolbar
        self._create_toolbar()

        # Scrollable content
        canvas = tk.Canvas(self, bg='#1e1e1e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)

        self.content_frame = tk.Frame(canvas, bg='#1e1e1e')
        self.content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")

        # Core fields
        self._create_core_fields()

        # File operations section
        self._create_file_operations_section()

        # Provisions section
        self._create_provisions_section()

        # Footer buttons
        self._create_footer_buttons()

    def _create_toolbar(self):
        """Create top toolbar"""
        toolbar = tk.Frame(self, bg='#2b2b2b', height=40)
        toolbar.pack(fill=tk.X, padx=10, pady=5)
        toolbar.pack_propagate(False)

        tk.Button(toolbar, text="💾 Save", command=self.save_task,
                 bg='#0e639c', fg='white', relief=tk.FLAT).pack(side=tk.LEFT, padx=5)

        tk.Button(toolbar, text="📦 Backup Targets", command=self.create_backup,
                 bg='#d67e00', fg='white', relief=tk.FLAT).pack(side=tk.LEFT, padx=5)

        tk.Button(toolbar, text="⏮️ Restore Point", command=self.create_restore_point,
                 bg='#8b7d00', fg='white', relief=tk.FLAT).pack(side=tk.LEFT, padx=5)

        tk.Button(toolbar, text="📋 Export Log", command=self.export_traceback_log,
                 bg='#5d5d5d', fg='white', relief=tk.FLAT).pack(side=tk.LEFT, padx=5)

    # Additional methods for file operations, provisions, etc.
    # ... (implementation continues)
```

### Phase 2: Integration with grep_flight

**Modify grep_flight_v2.py _create_tasks_tab():**

```python
# Add task management buttons
task_mgmt_frame = tk.Frame(tasks_tab, bg=self.config.BG_COLOR)
task_mgmt_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

tk.Button(task_mgmt_frame, text="➕ New Task", command=self._create_new_task_ui,
         bg='#0e639c', fg='white', font=('Arial', 10), padx=10).pack(side=tk.LEFT, padx=5)

tk.Button(task_mgmt_frame, text="✏️ Edit Task", command=self._edit_selected_task_ui,
         bg='#3c3c3c', fg='#cccccc', font=('Arial', 10), padx=10).pack(side=tk.LEFT, padx=5)

tk.Button(task_mgmt_frame, text="🗑️ Delete Task", command=self._delete_selected_task,
         bg='#5c0000', fg='white', font=('Arial', 10), padx=10).pack(side=tk.LEFT, padx=5)

def _create_new_task_ui(self):
    """Open task_ui for creating new task"""
    from task_ui import TaskManagerUI
    TaskManagerUI(self, mode="create")

def _edit_selected_task_ui(self):
    """Open task_ui for editing selected task"""
    selection = self.task_listbox.curselection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select a task to edit")
        return

    task_data = self.tasks_data[selection[0]]
    from task_ui import TaskManagerUI
    TaskManagerUI(self, mode="edit", task_data=task_data)
```

---

## Usage Examples

### Example 1: Creating a New Feature Task

1. User clicks "➕ New Task" in grep_flight Tasks tab
2. Task Manager UI opens
3. User fills in:
   - Type: Feature Implementation
   - Title: "Implement user authentication"
   - Description: "Add JWT-based authentication to API"
4. User clicks "[+] New File"
5. Adds: `Modules/auth/jwt_handler.py`
   - Expected lines: 100-150
   - Imports: jwt, datetime, hashlib
   - Classes: JWTHandler
   - Functions: generate_token, validate_token
   - Tests: ✓
6. User clicks "[+] Package Requirement"
7. Adds: PyJWT>=2.8.0
8. User clicks "💾 Save"
9. Task saved to `.docv2_workspace/tasks/task_20260116_234500.json`

### Example 2: Creating Backup Before Implementation

1. User has active task open
2. User clicks "📦 Backup Targets"
3. Dialog shows files from task file operations
4. User selects files to backup
5. Adds description: "Before JWT implementation"
6. Clicks "Create Backup"
7. Backup created in `.docv2_workspace/backups/task_id/backup_timestamp/`
8. Backup metadata added to task.json `tracking.backup_targets`

### Example 3: Creating Restore Point at Milestone

1. User completes 50% of task
2. User clicks "⏮️ Restore Point"
3. Names it: "50% Complete Milestone"
4. Links to previous backup
5. Sets future trigger: "On completion milestone 50%"
6. Clicks "Create Restore Point"
7. Restore point metadata saved to task.json
8. Future: System auto-creates restore points at milestones

---

## Next Steps

1. **Create task_ui.py** - Main module with UI components
2. **Integrate with grep_flight** - Add buttons to Tasks tab
3. **Implement backup system** - File snapshotting logic
4. **Implement restore point system** - Metadata tracking (smart logic deferred)
5. **Link traceback exports** - Connect grep_flight logs to tasks
6. **Test workflow** - Create → Backup → Work → Restore

---

## Questions for Review

1. **Task Type Granularity** - Are the task types comprehensive enough? Need more?
2. **File Operations** - Is the expected content specification detailed enough?
3. **Provisions** - Should we add more provision types (e.g., API endpoints, database schemas)?
4. **Backup Strategy** - File-level or git-style diffs?
5. **Restore Point Logic** - Which auto-triggers are most important for v1?
6. **UI Layout** - Is the task manager UI too complex or just right?

Ready to implement!
