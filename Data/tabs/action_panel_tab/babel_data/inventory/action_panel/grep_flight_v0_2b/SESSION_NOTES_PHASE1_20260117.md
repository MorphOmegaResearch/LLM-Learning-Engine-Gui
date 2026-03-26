# Session Notes - Phase 1: workspace_manager Enhancement
**Date:** 2026-01-17
**Milestone:** 2 - Unified Directory Structure
**Phase:** 1 - Foundation Layer
**Status:** COMPLETE ✅

---

## Overview

Enhanced `workspace_manager.py` with repository-level workspace support and multi-level priority path resolution.

**Goal:** Enable workspace_manager to support 3-level architecture:
- Project level (highest priority)
- Version level (current behavior)
- Repository level (new - for shared resources)

---

## Files Modified

### workspace_manager.py
**Backup:** `workspace_manager_backup_20260117_135007.py`
**Size:** 15K → ~20K (estimated)
**Lines Added:** ~100
**Lines Modified:** ~30

---

## Changes Implemented

### 1. Repository Root Detection (Lines ~27-98)

#### Added Cache Variable
**Location:** `__init__` method, line ~32
```python
self._repo_root_cache: Optional[Path] = None
```
**Purpose:** Cache repo root for performance

#### Added _find_repo_root() Method
**Location:** Lines ~68-84
```python
def _find_repo_root(self) -> Path:
    """Find repository root by searching upward for stable.json"""
    current = self.version_dir
    for _ in range(5):  # Max 5 levels up
        stable_json = current / "stable.json"
        if stable_json.exists():
            return current
        # ... handle parent traversal
    # Fallback: 2 levels up from version
    return fallback
```
**Features:**
- Searches up to 5 levels for stable.json
- Handles filesystem root edge case
- Fallback to version_dir.parent.parent

#### Added repo_root Property
**Location:** Lines ~86-93
```python
@property
def repo_root(self) -> Path:
    """Get repository root (cached for performance)"""
    if self._repo_root_cache is None:
        self._repo_root_cache = self._find_repo_root()
    return self._repo_root_cache
```
**Features:**
- Cached on first access
- Returns repository root containing stable.json

---

### 2. Repository Workspace Methods (Lines ~250-292)

#### get_repo_workspace_dir()
```python
def get_repo_workspace_dir(self) -> Path:
    """Returns: repo/.docv2_workspace/"""
    return self.repo_root / ".docv2_workspace"
```

#### get_main_dev_dir()
```python
def get_main_dev_dir(self) -> Path:
    """Returns: repo/.docv2_workspace/main_dev/"""
    return self.get_repo_workspace_dir() / "main_dev"
```
**Purpose:** Main branch plans, tasks, and shared development

#### get_shared_projects_dir()
```python
def get_shared_projects_dir(self) -> Path:
    """Returns: repo/.docv2_workspace/projects/"""
    return self.get_repo_workspace_dir() / "projects"
```
**Purpose:** Business and app_dev project pool

#### get_templates_dir()
```python
def get_templates_dir(self) -> Path:
    """Returns: repo/.docv2_workspace/templates/"""
    return self.get_repo_workspace_dir() / "templates"
```
**Purpose:** Project templates (code_project, ag_business, general)

#### get_main_branch_dir()
```python
def get_main_branch_dir(self) -> Path:
    """Returns: repo/versions/main_branch/"""
    return self.repo_root / "versions" / "main_branch"
```
**Purpose:** Stable production modules

---

### 3. Updated Path Resolution with 4-Level Priority

**Priority System:**
1. **Project** - If current_project is set
2. **Version** - Version/.docv2_workspace/ (if exists)
3. **Repository** - Repo/.docv2_workspace/main_dev/ or projects/ (if exists)
4. **Default** - Version-level (create if needed)

#### get_plans_dir() - UPDATED
**Location:** Lines ~104-125
**Before:**
```python
if self.has_project():
    return self.current_project / "PlannerSuite"
return self.docv2_workspace / "plans"
```
**After:**
```python
# Priority 1: Project
if self.has_project():
    return self.current_project / "PlannerSuite" or "plans"

# Priority 2: Version workspace
version_path = self.docv2_workspace / "plans"
if version_path.exists():
    return version_path

# Priority 3: Repository main_dev
repo_path = self.get_main_dev_dir() / "plans"
if repo_path.exists():
    return repo_path

# Priority 4: Default
return version_path
```

#### get_tasks_dir() - UPDATED
**Location:** Lines ~127-146
**Added:** Repo main_dev/tasks/ fallback

#### get_inventory_dir() - UPDATED
**Location:** Lines ~148-168
**Added:** Repo shared_projects/inventory/ fallback
**Note:** Allows shared inventory across versions

#### get_diffs_dir() - UPDATED
**Location:** Lines ~170-190
**Added:** Repo main_dev/diffs/ fallback

---

### 4. Context Information Methods (Lines ~294-350)

#### get_workspace_level() - NEW
**Location:** Lines ~294-306
```python
def get_workspace_level(self) -> str:
    """Returns: "project" | "version" | "repo" """
    if self.has_project():
        return "project"

    plans_dir = self.get_plans_dir()
    version_plans = self.docv2_workspace / "plans"

    return "version" if plans_dir == version_plans else "repo"
```
**Purpose:** Determine which level is active for UI display

#### get_context_info() - UPDATED
**Location:** Lines ~308-324
**Added Fields:**
- `workspace_level`: str ("project" | "version" | "repo")
- `repo_root`: str
- `main_dev_dir`: str
- `shared_projects_dir`: str

**Before:** 8 fields
**After:** 12 fields

#### get_all_workspace_locations() - NEW
**Location:** Lines ~326-350
```python
def get_all_workspace_locations(self) -> Dict[str, str]:
    """Get ALL workspace locations for comprehensive display"""
    return {
        # Repository level
        "repo_root": ...,
        "repo_workspace": ...,
        "main_dev": ...,
        "shared_projects": ...,
        "templates": ...,
        "main_branch": ...,

        # Version level
        "version_dir": ...,
        "version_workspace": ...,

        # Project level
        "project_root": ...,

        # Active paths (resolved)
        "active_plans_dir": ...,
        "active_tasks_dir": ...,
        "active_inventory_dir": ...,
        "active_diffs_dir": ...,
    }
```
**Purpose:** Complete inventory for debugging and UI display
**Returns:** 16 location mappings

---

## Summary Statistics

### Methods Added: 7
1. `_find_repo_root()`
2. `get_repo_workspace_dir()`
3. `get_main_dev_dir()`
4. `get_shared_projects_dir()`
5. `get_templates_dir()`
6. `get_main_branch_dir()`
7. `get_all_workspace_locations()`

### Methods Updated: 5
1. `get_plans_dir()` - Added repo fallback
2. `get_tasks_dir()` - Added repo fallback
3. `get_inventory_dir()` - Added repo fallback
4. `get_diffs_dir()` - Added repo fallback
5. `get_context_info()` - Added repo fields

### Properties Added: 1
- `repo_root` (cached)

### Total Lines Added: ~100

---

## Testing Requirements

### Test 1: Repository Root Detection
**Setup:** Launch from version directory
**Verify:**
```python
wm = WorkspaceManager(version_dir)
assert wm.repo_root.name == "Warrior_Flow"
assert (wm.repo_root / "stable.json").exists()
```

### Test 2: Priority Resolution - Plans
**Scenario A:** No project, version plans exist
```python
wm = WorkspaceManager(version_dir, current_project=None)
plans = wm.get_plans_dir()
assert "/.docv2_workspace/plans" in str(plans)  # Version level
```

**Scenario B:** No project, no version plans, repo main_dev exists
```python
# Remove version plans
plans = wm.get_plans_dir()
assert "/main_dev/plans" in str(plans)  # Repo level
```

**Scenario C:** Project set
```python
wm = WorkspaceManager(version_dir, current_project=project_path)
plans = wm.get_plans_dir()
assert str(project_path) in str(plans)  # Project level
```

### Test 3: Workspace Level Detection
```python
# No project, version exists
wm = WorkspaceManager(version_dir)
assert wm.get_workspace_level() == "version"

# No project, using repo
# (after removing version plans)
assert wm.get_workspace_level() == "repo"

# Project set
wm.set_current_project(project_path)
assert wm.get_workspace_level() == "project"
```

### Test 4: Context Information
```python
wm = WorkspaceManager(version_dir)
context = wm.get_context_info()

assert "repo_root" in context
assert "main_dev_dir" in context
assert "workspace_level" in context
assert context["workspace_level"] in ["project", "version", "repo"]
```

### Test 5: All Locations
```python
locations = wm.get_all_workspace_locations()
assert len(locations) == 16
assert "main_dev" in locations
assert "shared_projects" in locations
assert "active_plans_dir" in locations
```

---

## Integration Points

### Affects:
- **warrior_gui.py** - Will use updated path resolution
- **grep_flight_v2.py** - Can access repo-level paths via app_ref.workspace_manager
- **planner_wizard.py** - Should use workspace_manager instead of hardcoded paths
- **code_alchemist.py** - Should respect shared projects/ directory

### Required Updates (Next Phases):
- warrior_gui: Add context toggles to switch between version/main_dev/shared_projects
- grep_flight: Add [Inventory] tab to expose all workspace levels
- planner_wizard: Accept workspace_manager instance, remove hardcoded paths

---

## Backward Compatibility

### Preserved Behavior:
- Existing code calling `get_plans_dir()` without project will get version workspace (if exists)
- Project-based resolution unchanged
- No breaking changes to method signatures

### New Behavior:
- If version workspace doesn't exist, falls back to repo main_dev
- Enables shared resources across versions

---

## Next Steps - Phase 2

### Immediate:
1. Test workspace_manager with sample data
2. Grep warrior_gui for [New X] buttons
3. Audit [Inventory] tab structure
4. Document current button routing

### Dependencies:
- warrior_gui needs to adopt workspace_manager for [New X] buttons
- grep_flight needs [Inventory] tab to surface new locations
- traceback logging for all path resolutions (Phase 6)

---

**Phase 1 Status: COMPLETE ✅**
**Ready for:** Phase 2 - UI Discovery
**Backup Created:** workspace_manager_backup_20260117_135007.py
