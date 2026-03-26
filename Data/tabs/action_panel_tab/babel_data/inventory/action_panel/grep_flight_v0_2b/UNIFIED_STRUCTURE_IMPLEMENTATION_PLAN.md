# Unified Directory Structure Implementation Plan
**Date:** 2026-01-17
**Milestone:** Repository-Level Workspace Integration
**Previous:** Milestone 1 - CLI Working Directory (Complete ✅)

---

## 🔒 BACKUP PROTOCOL - CRITICAL

**BEFORE ANY IMPLEMENTATION:**
1. Create backup of all files to be modified
2. Update backup_manifest.json with new entries
3. Verify backup appears in restore menu
4. Document backup in Milestones.md

**AFTER MILESTONE TESTING:**
1. Create post-testing backup
2. Mark milestone complete in Milestones.md
3. Document revert instructions if needed

---

## Overview - Milestone 2: Unified Directory Structure

**Goal:** Integrate repository-level and version-level workspace management with full UI/UX routing

**Scope:**
- Update workspace_manager.py for dual-level support
- Audit and route all [New X] buttons in warrior_gui
- Add context toggles to warrior_gui [Inventory] tab
- Implement grep_flight [Inventory] tab with sub-tabs
- Surface all path decisions to traceback for transparency
- Integrate with code_alchemist, planner_wizard, ag_forge

---

## Phase 1: Foundation - workspace_manager Enhancement

### Task 1.1: Locate and Audit workspace_manager.py
**Files:** `workspace_manager.py`
**Actions:**
- [x] Read current workspace_manager implementation
- [ ] Document all public methods and their purposes
- [ ] Identify where version_dir and current_project are used
- [ ] Map all path resolution methods

**Grep Patterns:**
```bash
grep -n "def get_.*_dir\|def get_.*_path" workspace_manager.py
grep -n "self.version_dir\|self.current_project" workspace_manager.py
```

### Task 1.2: Add Repository Root Detection
**Files:** `workspace_manager.py`
**Actions:**
- [ ] Add `_find_repo_root()` method
  - Search upward from version_dir for stable.json
  - Cache result for performance
- [ ] Add `repo_root` property to class
- [ ] Add validation: repo_root must contain stable.json

**Implementation:**
```python
def _find_repo_root(self) -> Path:
    """Find repository root by searching for stable.json"""
    current = self.version_dir
    for _ in range(5):  # Max 5 levels up
        if (current / "stable.json").exists():
            return current
        current = current.parent
    return self.version_dir.parent.parent  # Fallback
```

### Task 1.3: Add Repository Workspace Methods
**Files:** `workspace_manager.py`
**Actions:**
- [ ] Add `get_repo_workspace_dir()` → repo/.docv2_workspace/
- [ ] Add `get_main_dev_dir()` → repo/.docv2_workspace/main_dev/
- [ ] Add `get_shared_projects_dir()` → repo/.docv2_workspace/projects/
- [ ] Add `get_templates_dir()` → repo/.docv2_workspace/templates/
- [ ] Add `get_main_branch_dir()` → repo/versions/main_branch/

**Example:**
```python
def get_main_dev_dir(self) -> Path:
    """Get main development workspace (repo-level)"""
    return self.repo_root / ".docv2_workspace" / "main_dev"
```

### Task 1.4: Update Existing Path Resolution with Priority System
**Files:** `workspace_manager.py`
**Methods to Update:**
- [ ] `get_plans_dir()` - Add repo-level fallback
- [ ] `get_tasks_dir()` - Add repo-level fallback
- [ ] `get_inventory_dir()` - Add repo-level fallback
- [ ] `get_diffs_dir()` - Add repo-level fallback

**Priority Logic:**
```python
def get_plans_dir(self) -> Path:
    # Priority 1: Project-specific
    if self.has_project():
        return self.current_project / "PlannerSuite"

    # Priority 2: Version workspace
    version_path = self.docv2_workspace / "plans"
    if version_path.exists():
        return version_path

    # Priority 3: Repo main_dev
    repo_path = self.get_main_dev_dir() / "plans"
    if repo_path.exists():
        return repo_path

    # Priority 4: Default (create version-level)
    return version_path
```

### Task 1.5: Add Context Information Methods
**Files:** `workspace_manager.py`
**Actions:**
- [ ] Update `get_context_info()` to include repo-level paths
- [ ] Add `get_workspace_level()` → "project" | "version" | "repo"
- [ ] Add `get_all_workspace_locations()` → dict of all active paths

**Traceback Integration:**
```python
def get_context_info(self) -> Dict:
    return {
        "workspace_level": self.get_workspace_level(),
        "repo_root": str(self.repo_root),
        "main_dev_dir": str(self.get_main_dev_dir()),
        "shared_projects_dir": str(self.get_shared_projects_dir()),
        # ... existing fields ...
    }
```

---

## Phase 2: UI Discovery - warrior_gui Button Audit

### Task 2.1: Locate All [New X] Buttons
**Files:** `warrior_gui.py`
**Grep Patterns:**
```bash
grep -n "New Project\|New project\|new_project" warrior_gui.py
grep -n "New Plan\|New plan\|new_plan" warrior_gui.py
grep -n "New Task\|New task\|new_task" warrior_gui.py
grep -n "New Epic\|New epic\|new_epic" warrior_gui.py
grep -n "New Phase\|New phase\|new_phase" warrior_gui.py
grep -n "\.Button.*command=" warrior_gui.py | grep -i new
```

**Documentation Format:**
```
[Button Name] | [Tab Location] | [Method Called] | [Line Number] | [Current Routing]
```

### Task 2.2: Audit [Inventory] Tab Structure
**Files:** `warrior_gui.py`
**Actions:**
- [ ] Find [Inventory] tab notebook setup
- [ ] Document current sub-tabs: [Files] [Plans] [Modules] [Sandbox]
- [ ] Locate project directory dropdown/selector
- [ ] Find where `.docv2_workspace` is currently referenced
- [ ] Map data flow: dropdown → path resolution → tab display

**Grep Patterns:**
```bash
grep -n "Inventory\|inventory" warrior_gui.py
grep -n "\.add.*text.*Files\|Plans\|Modules\|Sandbox" warrior_gui.py
grep -n "docv2_workspace" warrior_gui.py
grep -n "ttk.Combobox\|tk.OptionMenu" warrior_gui.py  # Find dropdowns
```

### Task 2.3: Find Current Project Setting Logic
**Files:** `warrior_gui.py`
**Actions:**
- [ ] Locate `set_project()` or similar method
- [ ] Find where `current_project` is stored/updated
- [ ] Identify project dropdown population logic
- [ ] Document how projects are discovered/listed

**Grep Patterns:**
```bash
grep -n "def.*set.*project\|current_project =" warrior_gui.py
grep -n "self.current_project" warrior_gui.py
```

### Task 2.4: Audit workspace_manager Usage
**Files:** `warrior_gui.py`
**Actions:**
- [ ] Find WorkspaceManager initialization
- [ ] Document all calls to workspace_manager methods
- [ ] Identify where paths are resolved for UI display
- [ ] Map which tabs use which workspace_manager methods

**Grep Patterns:**
```bash
grep -n "WorkspaceManager\|workspace_manager" warrior_gui.py
grep -n "\.get_.*_dir()\|\.get_.*_path()" warrior_gui.py
```

---

## Phase 3: warrior_gui [Inventory] Context Toggle Implementation

### Task 3.1: Design Context Toggle UI
**Files:** `warrior_gui.py` (Inventory tab section)
**Actions:**
- [ ] Add context level selector (Radio buttons or Dropdown)
  - Options: "Version Workspace" | "Main Development" | "Shared Projects"
- [ ] Add visual indicator showing current context level
- [ ] Add directory path display showing resolved location

**UI Layout:**
```
[Inventory Tab]
┌─────────────────────────────────────────┐
│ Context: ◉ Version Workspace            │
│          ○ Main Development (Repo)      │
│          ○ Shared Projects              │
│                                         │
│ Current: /versions/v09x/.docv2_workspace│
├─────────────────────────────────────────┤
│  [Files] [Plans] [Modules] [Sandbox]    │
```

### Task 3.2: Implement Context Switch Handler
**Files:** `warrior_gui.py`
**Actions:**
- [ ] Add `_on_inventory_context_change()` method
- [ ] Update workspace_manager with selected context
- [ ] Refresh all [Inventory] sub-tabs with new context
- [ ] Log context switch to grep_flight traceback (if connected)

**Implementation:**
```python
def _on_inventory_context_change(self):
    context = self.inventory_context_var.get()

    if context == "Main Development":
        base_dir = self.workspace_manager.get_main_dev_dir()
    elif context == "Shared Projects":
        base_dir = self.workspace_manager.get_shared_projects_dir()
    else:  # Version Workspace
        base_dir = self.workspace_manager.docv2_workspace

    # Update all sub-tabs
    self._refresh_inventory_tabs(base_dir)

    # Log to traceback if grep_flight connected
    self._log_to_traceback(f"📂 Inventory context: {context} → {base_dir}")
```

### Task 3.3: Update Sub-Tab Display Logic
**Files:** `warrior_gui.py`
**Actions:**
- [ ] Modify [Files] tab to show context-appropriate directory
- [ ] Modify [Plans] tab to use workspace_manager.get_plans_dir()
- [ ] Modify [Modules] tab to respect context level
- [ ] Modify [Sandbox] tab with context awareness

### Task 3.4: Add Auto-Set Default Project Directory
**Files:** `warrior_gui.py`
**Actions:**
- [ ] Detect project type (business vs app_dev)
- [ ] Auto-select appropriate shared project directory
- [ ] Add logic in project creation workflow:
  ```python
  if project_type == "business":
      default_parent = repo/.docv2_workspace/projects/buisness/
  elif project_type == "app_dev":
      default_parent = repo/.docv2_workspace/projects/app_dev/
  ```

---

## Phase 4: warrior_gui Button Routing Updates

### Task 4.1: Update [New Project] Button
**Files:** `warrior_gui.py`
**Current Routing:** (To be discovered in Task 2.1)
**New Routing:**
- [ ] Show project type selector: Business | App Dev | General
- [ ] Auto-route to appropriate shared projects directory
- [ ] Offer version-specific vs repo-level option
- [ ] Use workspace_manager.get_shared_projects_dir()
- [ ] Create project with unified structure (PlannerSuite/, inventory/, knowledge/, workspace/, diffs/)

**Template Structure:**
```python
def create_new_project(self, project_name, project_type):
    if project_type == "business":
        parent_dir = self.workspace_manager.get_shared_projects_dir() / "buisness"
    elif project_type == "app_dev":
        parent_dir = self.workspace_manager.get_shared_projects_dir() / "app_dev"
    else:
        parent_dir = self.workspace_manager.docv2_workspace / "projects"

    project_path = parent_dir / project_name
    # Create unified structure
    (project_path / "PlannerSuite").mkdir(parents=True)
    (project_path / "inventory").mkdir(parents=True)
    # ... etc
```

### Task 4.2: Update [New Plan] Button
**Files:** `warrior_gui.py`, `planner_wizard.py`
**Current Routing:** (To be discovered in Task 2.1)
**New Routing:**
- [ ] Use workspace_manager.get_plans_dir() for path resolution
- [ ] Offer context selector: Version | Main Dev | Project
- [ ] If Main Dev selected → save to repo/.docv2_workspace/main_dev/plans/
- [ ] Update planner_wizard.py to accept workspace_manager instance
- [ ] Remove hardcoded paths from planner_wizard

**planner_wizard.py Updates:**
```python
class PlannerWizard:
    def __init__(self, mode="new_epic", epic_id=None, workspace_manager=None):
        # ... existing init ...
        self.workspace_manager = workspace_manager

    def finish(self):
        # OLD: base_path = Path("/home/.../Epics") / name
        # NEW:
        base_path = self.workspace_manager.get_plans_dir() / "Epics" / name
```

### Task 4.3: Update [New Task] Button
**Files:** `warrior_gui.py`
**Current Routing:** (To be discovered in Task 2.1)
**New Routing:**
- [ ] Use workspace_manager.get_tasks_dir()
- [ ] Respect current context (version/repo/project)
- [ ] Add task type field: Version-specific | Shared | Project
- [ ] Auto-populate with target context from grep_flight (if available)

### Task 4.4: Add Input Field Standardization
**All [New X] Buttons:**
- [ ] Add project type selector where appropriate
- [ ] Add workspace level selector (version/repo)
- [ ] Add target context display (from grep_flight if connected)
- [ ] Add path preview showing where item will be created
- [ ] Add tags/metadata fields for searchability

---

## Phase 5: grep_flight [Inventory] Tab Implementation

### Task 5.1: Create [Inventory] Tab Structure
**Files:** `grep_flight_v2.py`
**Location:** After [Chat] tab in notebook
**Actions:**
- [ ] Find notebook widget creation in grep_flight_v2.py
  ```bash
  grep -n "notebook\|ttk.Notebook" grep_flight_v2.py
  grep -n "\.add.*text.*Grep\|Tasks\|Chat" grep_flight_v2.py
  ```
- [ ] Add [Inventory] tab after [Chat]
- [ ] Create sub-notebook for [Inventory] with 4 sub-tabs

**Structure:**
```python
# Main notebook
inventory_tab = tk.Frame(self.notebook, bg='#1e1e1e')
self.notebook.add(inventory_tab, text="📦 Inventory")

# Sub-notebook inside [Inventory]
sub_notebook = ttk.Notebook(inventory_tab)
sub_notebook.pack(fill=tk.BOTH, expand=True)

# Sub-tabs
version_tab = tk.Frame(sub_notebook)
main_branch_tab = tk.Frame(sub_notebook)
projects_tab = tk.Frame(sub_notebook)
templates_tab = tk.Frame(sub_notebook)

sub_notebook.add(version_tab, text="Version Files")
sub_notebook.add(main_branch_tab, text="Main Branch")
sub_notebook.add(projects_tab, text="Projects")
sub_notebook.add(templates_tab, text="Templates")
```

### Task 5.2: Implement [Version Files] Sub-Tab
**Files:** `grep_flight_v2.py`
**Actions:**
- [ ] Display current version directory tree
- [ ] Add Thunar launch button → `self.version_root`
- [ ] Add "Open in Editor" button
- [ ] Add "Set as Target" button (feeds back to [Grep] tab)
- [ ] Show directory stats (file count, total size)

**Button Layout:**
```python
buttons_frame = tk.Frame(version_tab)
buttons_frame.pack(fill=tk.X, pady=5)

tk.Button(buttons_frame, text="📂 Open in Thunar",
          command=lambda: self._open_thunar(self.version_root)).pack(side=tk.LEFT)
tk.Button(buttons_frame, text="🎯 Set as Target",
          command=lambda: self._set_target_from_inventory(self.version_root)).pack(side=tk.LEFT)
```

### Task 5.3: Implement [Main Branch] Sub-Tab
**Files:** `grep_flight_v2.py`
**Actions:**
- [ ] Display repo/versions/main_branch/ tree
- [ ] Add Thunar launch button
- [ ] Show main_branch modules/functions
- [ ] Add "Compare with Current Version" button
- [ ] List stable modules available

### Task 5.4: Implement [Projects] Sub-Tab
**Files:** `grep_flight_v2.py`
**Actions:**
- [ ] List all projects in repo/.docv2_workspace/projects/
- [ ] Group by type: buisness/ | app_dev/
- [ ] Add Thunar button per project
- [ ] Add "Set Project as Target" button
- [ ] Show project metadata from .project_meta.json

**Project List UI:**
```
Business Projects:
  □ ag_forge_integration     [📂 Open] [🎯 Target]
  □ quick_clip_business      [📂 Open] [🎯 Target]

App Development:
  □ task_manager_v2          [📂 Open] [🎯 Target]
```

### Task 5.5: Implement [Templates] Sub-Tab
**Files:** `grep_flight_v2.py`
**Actions:**
- [ ] List templates from repo/.docv2_workspace/templates/
- [ ] Add "New Project from Template" button
- [ ] Show template structure preview
- [ ] Add "Edit Template" button (opens in editor)

### Task 5.6: Add Thunar Launch Integration
**Files:** `grep_flight_v2.py`
**Actions:**
- [ ] Add `_open_thunar(path)` method
- [ ] Use `self.config.FILE_MANAGER` for cross-platform support
- [ ] Log thunar launches to traceback with path context

**Implementation:**
```python
def _open_thunar(self, path: str):
    """Launch file manager at specified path"""
    try:
        subprocess.Popen([self.config.FILE_MANAGER, str(path)])
        self._add_traceback(f"📂 Opened file manager: {path}", "INFO")
    except Exception as e:
        self._add_traceback(f"❌ Failed to open file manager: {e}", "ERROR")
```

### Task 5.7: Add Target Context Feedback Loop
**Files:** `grep_flight_v2.py`
**Actions:**
- [ ] Add `_set_target_from_inventory(path)` method
- [ ] Update target_var with selected path
- [ ] Trigger target IPC message (SET_TARGET)
- [ ] Switch to [Grep] tab after setting target
- [ ] Log target change to traceback

**Implementation:**
```python
def _set_target_from_inventory(self, path: str):
    """Set target from inventory selection"""
    self.target_var.set(str(path))
    self.engine.set_target(str(path))

    # Log to traceback
    self._add_traceback(f"🎯 Target set from [Inventory]: {path}", "TARGET")

    # Switch to Grep tab
    self.notebook.select(0)  # Assuming Grep is first tab
```

---

## Phase 6: Traceback Transparency & Logging

### Task 6.1: Add Path Resolution Logging
**Files:** `workspace_manager.py`
**Actions:**
- [ ] Add logging to all path resolution methods
- [ ] Format: `"📂 [METHOD] Level: {level} → {resolved_path}"`
- [ ] Include priority info: "Priority 1: Project" | "Priority 2: Version" | "Priority 3: Repo"
- [ ] Send to grep_flight traceback if connected

**Example:**
```python
def get_plans_dir(self) -> Path:
    if self.has_project():
        path = self.current_project / "PlannerSuite"
        self._log_resolution("get_plans_dir", "Project", path, priority=1)
        return path
    # ... etc
```

### Task 6.2: Add Button Action Logging
**Files:** `warrior_gui.py`
**Actions:**
- [ ] Log all [New X] button clicks with context
- [ ] Format: `"🔘 [Button]: {button_name} | Type: {type} | Target: {path}"`
- [ ] Include all form fields in log
- [ ] Send to grep_flight traceback

### Task 6.3: Add Context Switch Logging
**Files:** `warrior_gui.py`
**Actions:**
- [ ] Log inventory context changes
- [ ] Log project selections
- [ ] Log workspace level changes
- [ ] Format with clear before/after state

### Task 6.4: Create Unified Event Export
**Files:** `grep_flight_v2.py`
**Actions:**
- [ ] Add "Export Events" button to [Inventory] tab
- [ ] Export traceback events to JSON
- [ ] Include timestamps, categories, context
- [ ] Save to version/.docv2_workspace/sessions/events_{timestamp}.json

---

## Phase 7: System Integration Updates

### Task 7.1: Update code_alchemist.py
**Files:** `code_alchemist.py`
**Actions:**
- [ ] Find argparse --output handling
  ```bash
  grep -n "\-\-output\|add_argument.*output" code_alchemist.py
  ```
- [ ] Respect workspace_manager routing if available
- [ ] Default --output to shared projects/ when appropriate
- [ ] Add --project-type flag: business | app_dev

### Task 7.2: Update ag_forge Integration
**Files:** `Modules/Ag_Forge_v1c/launch_ag_forge.py` (or similar)
**Actions:**
- [ ] Point knowledge_forge_data to repo projects/
- [ ] Use shared business project location
- [ ] Update any hardcoded paths

### Task 7.3: Update quick_clip/quick_stash
**Files:** To be located
**Actions:**
- [ ] Audit quick_clip for project directory references
- [ ] Update to use shared projects/buisness/
- [ ] Coordinate with ag_forge knowledge base

---

## Phase 8: Testing & Documentation

### Task 8.1: Create Test Cases
**Actions:**
- [ ] Test Path 1: Create new business project → verify in projects/buisness/
- [ ] Test Path 2: Create new plan from warrior_gui → verify context routing
- [ ] Test Path 3: Switch inventory context → verify UI updates
- [ ] Test Path 4: Set target from grep_flight [Inventory] → verify [Grep] receives
- [ ] Test Path 5: Launch CLI with different workspace levels

### Task 8.2: Update Milestones.md
**File:** `Milestones.md`
**Actions:**
- [ ] Document Milestone 2 completion
- [ ] Add backup reference
- [ ] Add revert instructions
- [ ] List all modified files

### Task 8.3: Create Session Notes
**File:** `SESSION_NOTES_{timestamp}.md`
**Actions:**
- [ ] Document all changes with line numbers
- [ ] Include before/after comparisons
- [ ] List new methods/functions added
- [ ] Document routing decisions

### Task 8.4: Update User Documentation
**Actions:**
- [ ] Create user guide for context toggles
- [ ] Document unified directory structure
- [ ] Create migration guide from old structure
- [ ] Add troubleshooting section

---

## Backup Checklist

### Before Implementation:
- [ ] Backup `workspace_manager.py`
- [ ] Backup `warrior_gui.py`
- [ ] Backup `grep_flight_v2.py`
- [ ] Backup `planner_wizard.py`
- [ ] Backup `code_alchemist.py`
- [ ] Update `backup_manifest.json`
- [ ] Verify backups in restore menu

### After Milestone 2 Testing:
- [ ] Create post-testing backups
- [ ] Update `Milestones.md`
- [ ] Document revert procedure
- [ ] Archive session notes

---

## Success Criteria

**Milestone 2 Complete When:**
1. ✅ workspace_manager supports dual-level (repo + version) with priority system
2. ✅ All [New X] buttons route correctly to appropriate workspace level
3. ✅ warrior_gui [Inventory] has working context toggles
4. ✅ grep_flight [Inventory] tab with 4 functional sub-tabs
5. ✅ Thunar launches work from all inventory locations
6. ✅ Target feedback loop functional (Inventory → Grep)
7. ✅ All path resolutions logged to traceback
8. ✅ code_alchemist respects unified structure
9. ✅ planner_wizard uses workspace_manager
10. ✅ Comprehensive testing completed
11. ✅ Documentation updated
12. ✅ Backups created and verified

---

**End of Implementation Plan**
