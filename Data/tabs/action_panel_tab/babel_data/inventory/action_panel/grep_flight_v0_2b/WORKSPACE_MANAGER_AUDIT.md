# workspace_manager.py - Method Audit and Documentation
**Date:** 2026-01-17
**Purpose:** Complete inventory of existing methods before enhancement

---

## Class Structure Overview

### WorkspaceManager (Lines 13-279)
**Purpose:** Centralized workspace path resolution for Warrior Flow
**Key Properties:**
- `version_dir`: Root directory of current version
- `current_project`: Currently active project path (optional)
- `docv2_workspace`: Version-level workspace (.docv2_workspace/)

---

## Method Inventory

### Initialization & Structure

#### `__init__(version_dir, current_project=None)` - Line 19
**Purpose:** Initialize workspace manager
**Parameters:**
- version_dir: Path to version root
- current_project: Optional project path
**Actions:**
- Sets version_dir and current_project
- Initializes docv2_workspace path
- Calls _ensure_workspace_structure()

#### `_ensure_workspace_structure()` - Line 34
**Purpose:** Create default .docv2_workspace directory tree
**Creates:**
- .docv2_workspace/
- plans/ (with subdirs: Epics, Plans, Phases, Tasks, Milestones, Diffs, Refs)
- config/
- sessions/
- pfc_history/

### Project Management

#### `set_current_project(project_path)` - Line 54
**Purpose:** Update the active project
**Actions:** Sets self.current_project

#### `has_project()` - Line 58
**Purpose:** Check if project is set and exists
**Returns:** bool

---

## Path Resolution Methods (Primary)

### Priority System (Current):
1. Project-specific paths (if project set)
2. Version workspace (.docv2_workspace/)

### Methods:

#### `get_plans_dir()` - Line 66
**Priority:**
1. project/PlannerSuite/ (if exists)
2. project/plans/ (fallback)
3. version/.docv2_workspace/plans/ (default)
**Returns:** Path

#### `get_tasks_dir()` - Line 79
**Priority:**
1. project/tasks/
2. version/.docv2_workspace/plans/Tasks/
**Returns:** Path

#### `get_planner_base_path()` - Line 89
**Priority:**
1. project/PlannerSuite/
2. version/.docv2_workspace/plans/
**Returns:** Path

#### `get_inventory_dir()` - Line 98
**Priority:**
1. project/inventory/
2. version/.docv2_workspace/inventory/
**Returns:** Path
**Note:** Currently creates inventory at version level if not exists

#### `get_diffs_dir()` - Line 104
**Priority:**
1. project/diffs/
2. version/.docv2_workspace/plans/Diffs/
**Returns:** Path

#### `get_pfc_history_dir()` - Line 110
**Priority:**
1. project/.docv2_workspace/pfc_history/
2. version/.docv2_workspace/pfc_history/
**Returns:** Path

#### `get_chat_dir()` - Line 116
**Priority:**
1. project/chats/
2. version/.docv2_workspace/chats/
**Returns:** Path
**Note:** Creates chats/ if not exists

#### `get_sessions_dir()` - Line 122
**Priority:** Version-level only
**Returns:** version/.docv2_workspace/sessions/
**Note:** No project-level override

---

## PlannerSuite Specific Methods

#### `get_epics_dir()` - Line 130
**Returns:** planner_base_path/Epics/

#### `get_plans_files_dir()` - Line 135
**Returns:** planner_base_path/Plans/

#### `get_phases_dir()` - Line 140
**Returns:** planner_base_path/Phases/

#### `get_milestones_dir()` - Line 145
**Returns:** planner_base_path/Milestones/

#### `get_refs_dir()` - Line 150
**Returns:** planner_base_path/Refs/

---

## Context Information Methods

#### `get_context_info()` - Line 159
**Purpose:** Get workspace context for display/logging
**Returns:** Dict with:
- has_project: bool
- project_name: str | "No Project"
- project_path: str | None
- version_dir: str
- workspace_mode: "project" | "version-local"
- plans_dir: str
- tasks_dir: str

#### `get_display_name()` - Line 171
**Purpose:** Get friendly display name
**Returns:**
- "Project: {name}" if project set
- "Version Workspace (No Project)" otherwise

---

## Task Board Support

#### `get_version_task_board_path()` - Line 181
**Returns:** version/.docv2_workspace/sessions/current_task_board.json

#### `load_version_task_board()` - Line 188
**Purpose:** Load tasks from version task board
**Returns:** List[Dict]

#### `save_version_task_board(tasks)` - Line 200
**Purpose:** Save tasks to version task board

#### `add_task_to_version_board(task_data)` - Line 210
**Purpose:** Add task with metadata
**Adds:** added_at, board_type='version'

---

## Marked Files Support

#### `get_marked_files_path()` - Line 227
**Priority:**
1. project/.marked_files.json
2. version/.docv2_workspace/marked_files.json
**Returns:** Path

#### `load_marked_files()` - Line 233
**Returns:** List[str] of marked file paths

#### `save_marked_files(files)` - Line 244
**Purpose:** Save marked files list

---

## Utility Methods

#### `ensure_dir_exists(dir_path)` - Line 257
**Purpose:** Create directory if not exists
**Returns:** Path

#### `get_all_task_files()` - Line 263
**Purpose:** Get all task files from workspace
**Returns:** List[Path] (task_*.json, *.json)

#### `get_all_plan_files()` - Line 270
**Purpose:** Get all plan files
**Returns:** List[Path] (*.md, *.json)

#### `__repr__()` - Line 277
**Returns:** String representation with mode and path

---

## BusinessProjectManager (Lines 281-373)
**Purpose:** Coordinates business template metadata
**Key Methods:**
- reload_manifest()
- list_templates()
- get_template(identifier)
- get_template_labels()
- build_template_plan(identifier, project_root)

**Template Structure:**
- script_sources
- knowledge_paths
- launcher/onboarding/workflow commands
- providers
- inventory_patterns
- requirements_file

---

## Enhancement Requirements for Milestone 2

### Missing Functionality:
1. **No Repository-Level Support**
   - No repo_root property
   - No repo/.docv2_workspace/ awareness
   - No main_dev/ paths
   - No shared projects/ paths

2. **Two-Level Priority Only**
   - Current: project > version
   - Needed: project > version > repo > default

3. **No Main Branch Support**
   - No versions/main_branch/ references
   - No template directory support

4. **No Context Level Tracking**
   - Can't determine if using project/version/repo
   - No get_workspace_level() method

### Methods to Add:

#### Repository Detection
- `_find_repo_root()` → Search for stable.json
- `repo_root` property

#### Repository Workspace Methods
- `get_repo_workspace_dir()` → repo/.docv2_workspace/
- `get_main_dev_dir()` → repo/.docv2_workspace/main_dev/
- `get_shared_projects_dir()` → repo/.docv2_workspace/projects/
- `get_templates_dir()` → repo/.docv2_workspace/templates/
- `get_main_branch_dir()` → repo/versions/main_branch/

#### Enhanced Priority Methods (Update Existing)
- get_plans_dir() - Add repo fallback
- get_tasks_dir() - Add repo fallback
- get_inventory_dir() - Add repo fallback
- get_diffs_dir() - Add repo fallback

#### Context Methods
- `get_workspace_level()` → "project" | "version" | "repo"
- `get_all_workspace_locations()` → Dict of all paths
- Update get_context_info() with repo fields

---

## Dependencies Discovered

### Used By:
- warrior_gui.py (project management, inventory tabs)
- grep_flight_v2.py (via app_ref, task integration)
- planner_wizard.py (hardcoded paths - needs update)
- docv2_engine.py (workspace resolution)

### Uses:
- Path (pathlib)
- json
- datetime

---

**Audit Complete**
Ready for enhancement implementation.
