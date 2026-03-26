# Revised Implementation Plan - Integrated Approach
**Date:** 2026-01-17 14:00
**Context:** User feedback - Simplify, integrate existing systems, focus on workflow not structure

---

## Key Insights from User Feedback

### What's Already Working:
1. ✅ **[Files] tab** - Already has expand/collapse directory listing
2. ✅ **stable.json** - Already identifies default/stable version
3. ✅ **Target context** - grep_flight traceback logs target context
4. ✅ **Backup manifest** - Tracks latest working files
5. ✅ **stash_script.py** - Handles quick file shifting
6. ✅ **[Sandbox] sub-tab** - Already exists for dev workflows

### What Doesn't Work:
1. ❌ **[Browse...] button** - Sets directory but no context propagation
2. ❌ **No toggles yet** - Can't switch between version/main/shared contexts
3. ❌ **No stash controls in grep_flight** - stash_script isolated
4. ❌ **No file lineage/profile view** - Can't see file history

### Design Philosophy Shift:
- **OLD:** Create new directory structures, copy files around
- **NEW:** Work with provisions/inventory of files being worked on
- **Focus:** Milestone backups + code_alchemist sandbox, not full directory mirroring

---

## Simplified Architecture

### "Main Branch" Definition:
```
Main Branch = Current stable/default version from stable.json
NOT a separate /versions/main_branch/ directory
```

**Rationale:**
- Avoid duplication
- Use existing stable.json logic
- Milestone backups stored in suggested /.docv2_workspace/main_dev/
- Active development uses version workspace + sandbox

### Directory Usage:

```
Repository Root
├── .docv2_workspace/
│   ├── main_dev/
│   │   ├── milestones/           ← Milestone backups (not full copies)
│   │   ├── plans/                ← Shared planning docs
│   │   └── diffs/                ← Cross-version diffs
│   │
│   ├── projects/
│   │   ├── buisness/             ← Business project PROVISIONS (not full projects)
│   │   │   └── {project_name}/
│   │   │       ├── inventory/    ← Working file provisions
│   │   │       └── knowledge/    ← ag_forge knowledge base
│   │   └── app_dev/              ← App project provisions
│   │
│   └── templates/                ← Project templates
│
└── versions/
    └── {version_name}/           ← Active version (identified by stable.json)
        ├── .docv2_workspace/     ← Version-local workspace
        └── Modules/              ← Actual working code
```

**Key Concept:**
- Provisions = Files being worked on (from backup manifest)
- NOT full directory copies
- Sandbox in code_alchemist handles actual work

---

## Integration Points - What Connects Where

### 1. Target Context Flow
```
User targets file/dir → grep_flight IPC → Traceback log → Context available to:
  ├── warrior_gui (if connected via app_ref)
  ├── Task creation (auto-populate target)
  └── Profile view (show target lineage)
```

### 2. Backup Manifest as Provisions Source
```
backup_manifest.json (latest entries) → "Working Files" list →
  ├── Displayed in [Inventory] > [Provisions] sub-tab
  ├── Used by stash_script for quick access
  └── Linked to task system
```

### 3. Stable Version as "Main Branch"
```
stable.json["current_stable_version"] → Identified as main/stable →
  ├── Milestone backups stored in main_dev/milestones/
  ├── Toggle in warrior_gui shows "Main/Stable Version"
  └── Plans routed to main_dev/ when main selected
```

### 4. stash_script Integration
```
stash_script.py → Controls in grep_flight [Inventory] tab →
  ├── Button: "Stash Current Target"
  ├── Button: "Unstash to Sandbox"
  └── Listbox: Show stashed files
```

---

## Revised Phase Breakdown

### Phase 1: workspace_manager ✅ COMPLETE
- Repository root detection
- Priority path resolution
- Context methods

### Phase 2: Context Propagation & Integration (REVISED)

#### 2.1: Fix [Browse...] Context Issue
**File:** warrior_gui.py
**Problem:** Browse button sets path but doesn't propagate context
**Solution:**
```python
def _on_browse_project_dir(self):
    path = filedialog.askdirectory()
    if path:
        # Set project
        self.workspace_manager.set_current_project(Path(path))

        # Propagate to grep_flight if connected
        if hasattr(self, 'grep_flight_ref'):
            self.grep_flight_ref.target_var.set(str(path))
            self.grep_flight_ref.engine.set_target(str(path))

        # Update UI
        self._refresh_inventory_tabs()
        self._log_context_change("browse", path)
```

#### 2.2: Add Context Toggles (Simplified)
**Location:** warrior_gui [Inventory] tab header
**Toggles:**
- ◉ Current Version (active version from stable.json)
- ○ Main/Stable Version (default version from stable.json)
- ○ Shared Projects (repo/.docv2_workspace/projects/)

**Behavior:**
- "Current Version" → Use version workspace (existing behavior)
- "Main/Stable" → Route plans to main_dev/, use stable version context
- "Shared Projects" → Show shared project provisions

#### 2.3: Integrate Backup Manifest as Provisions
**File:** grep_flight_v2.py
**New Sub-Tab:** [Inventory] > [Provisions]
**Data Source:** backup_manifest.json (latest 20 entries)
**Display:**
```
Working Files (from recent backups):
  □ grep_flight_v2.py          [📂 Open] [🎯 Target] [📊 Profile] [💾 Stash]
  □ workspace_manager.py        [📂 Open] [🎯 Target] [📊 Profile] [💾 Stash]
  □ warrior_gui.py              [📂 Open] [🎯 Target] [📊 Profile] [💾 Stash]
```

#### 2.4: Add [Profile] Button for File Lineage
**Purpose:** Show file history, backups, context
**Data Sources:**
- backup_manifest.json (backup history)
- Target context from traceback
- Task associations (if file linked to task)
- stash_script registry

**Popup Display:**
```
═══════════════════════════════════════
File Profile: grep_flight_v2.py
═══════════════════════════════════════
Path: /path/to/grep_flight_v2.py
Size: 250KB
Last Modified: 2026-01-17 13:57

Backup History:
  [20260117_133049] Milestone 1 Complete
  [20260117_115840] Pre-Phase 1 Backup

Target History:
  [13:30] Set via target.sh
  [12:15] Set from warrior_gui

Associated Tasks:
  [task_001] CLI Working Directory Fix

Stash Status:
  Not currently stashed

[View Diffs] [Restore] [Stash] [Close]
═══════════════════════════════════════
```

---

### Phase 3: grep_flight [Inventory] Tab (REVISED)

#### Sub-Tabs:
1. **[Provisions]** - Working files from backup manifest
2. **[Stash]** - stash_script integration
3. **[Projects]** - Shared projects (business/app_dev)
4. **[Templates]** - Project templates

#### [Provisions] Sub-Tab
**Purpose:** Show files being worked on (not full directories)
**Source:** backup_manifest.json latest entries
**Features:**
- List recent backups
- [Profile] button per file
- [Stash] button per file
- [Target] button to set grep context

#### [Stash] Sub-Tab
**Purpose:** stash_script.py controls
**Features:**
```python
# Stash controls
[Stash Current Target]  # Calls stash_script with target

# Stashed files list
Stashed Files:
  □ feature_branch_code.py    [Unstash] [Delete]
  □ experimental_fix.py       [Unstash] [Delete]

# Unstash location selector
Unstash to: [Dropdown: Sandbox | Current Dir | Custom]
```

#### [Projects] Sub-Tab
**Purpose:** Show shared project provisions (not full projects)
**Display:**
```
Business Projects:
  ag_forge_integration/
    inventory/              [📂 Open]
      - provision_1.py      [🎯 Target] [📊 Profile]
      - provision_2.py      [🎯 Target] [📊 Profile]
    knowledge/              [📂 Open]

App Development:
  task_manager_v2/
    inventory/              [📂 Open]
```

---

### Phase 4: warrior_gui Button Routing (REVISED)

#### [New Project] Button
**Current:** Creates project with hardcoded structure
**New:** Creates provision directory in shared projects
```python
def create_new_project(self, name, project_type):
    # Route based on type
    if project_type == "business":
        parent = workspace_manager.get_shared_projects_dir() / "buisness"
    else:
        parent = workspace_manager.get_shared_projects_dir() / "app_dev"

    project_path = parent / name

    # Create PROVISION structure (not full project)
    (project_path / "inventory").mkdir(parents=True)
    (project_path / "knowledge").mkdir(parents=True)
    (project_path / ".project_meta.json").write_text(json.dumps({
        "name": name,
        "type": project_type,
        "created": datetime.now().isoformat(),
        "provision_type": "project_workspace"
    }))
```

#### [New Plan] Button
**Routing:**
- If "Main/Stable" toggle selected → main_dev/plans/
- If "Current Version" → version/.docv2_workspace/plans/
- If project selected → project/PlannerSuite/

#### [New Task] Button
**Enhancement:** Auto-populate with target context
```python
def create_new_task(self):
    # Get target from grep_flight if available
    target = None
    if hasattr(self, 'grep_flight_ref'):
        target = self.grep_flight_ref.target_var.get()

    # Create task with target pre-filled
    task_dialog = TaskDialog(
        initial_target=target,
        workspace_manager=self.workspace_manager
    )
```

---

### Phase 5: Milestone Backup Integration

#### Milestone Backup Storage
**Location:** /.docv2_workspace/main_dev/milestones/
**Format:** `{filename}_milestone{N}_{timestamp}.{ext}`
**When:** User marks milestone complete

**Integration with grep_flight backup system:**
```python
def create_milestone_backup(self, files: List[str], milestone_name: str):
    """Create milestone backup set"""
    milestone_dir = workspace_manager.get_main_dev_dir() / "milestones" / milestone_name
    milestone_dir.mkdir(parents=True, exist_ok=True)

    for file_path in files:
        # Copy file to milestone dir
        backup_name = f"{Path(file_path).stem}_milestone_{timestamp}{Path(file_path).suffix}"
        backup_path = milestone_dir / backup_name
        shutil.copy2(file_path, backup_path)

        # Update backup manifest with milestone tag
        self._update_backup_manifest(file_path, backup_path, milestone=milestone_name)
```

---

### Phase 6: code_alchemist Sandbox Integration

**Purpose:** Use code_alchemist unified structure for actual work
**Flow:**
```
1. User marks file for work (from Provisions or Target)
2. File copied to sandbox (code_alchemist inventory)
3. Work performed in sandbox
4. Diff generated
5. Changes applied back OR milestone backup created
```

**Integration:**
```python
def send_to_sandbox(self, file_path: str):
    """Send file to code_alchemist sandbox"""
    # Use code_alchemist --hybrid mode
    subprocess.Popen([
        "python3", code_alchemist_path,
        "--hybrid",
        file_path,
        "--output", workspace_manager.get_shared_projects_dir() / "sandbox"
    ])
```

---

### Phase 7: Migrate & New Version Consideration

#### [Migrate] Button
**Purpose:** Create milestone backup of current version
**NOT:** Copy entire directory structure
**Process:**
```
1. Identify files to preserve (from backup manifest)
2. Create milestone backup in main_dev/milestones/{version_name}/
3. Update stable.json with migration record
4. Optionally create new version from template
```

#### [New Version] Button
**Purpose:** Create new version workspace
**Structure:** Use version/.docv2_workspace/ (existing pattern)
**Link:** Reference shared projects from repo level

---

## Updated Task List

### Immediate (Next Session):
1. Fix [Browse...] context propagation in warrior_gui
2. Add context toggles (Current/Main/Shared) to warrior_gui [Inventory]
3. Implement backup manifest → provisions display in grep_flight
4. Add [Profile] button popup for file lineage

### Next:
5. Add stash_script controls to grep_flight [Inventory] > [Stash]
6. Update [New Project] to create provisions (not full structure)
7. Update [New Plan]/[New Task] to respect context toggle
8. Integrate target context auto-population

### Later:
9. Milestone backup system
10. code_alchemist sandbox integration
11. [Migrate] revision to use milestone backups
12. Complete packaging system

---

## What NOT to Do

### ❌ Don't Create:
- /versions/main_branch/ directory (use stable.json instead)
- Full project directory copies in shared projects
- Duplicate version structures

### ✅ Do Create:
- Provision directories (inventory/, knowledge/)
- Milestone backups (not full copies)
- Context propagation between systems

---

## End Goal: Complete Packages

**Vision:** Distributable packages with:
- Milestone backups (historical versions)
- Provisions (current working files)
- Knowledge base (ag_forge integration)
- Templates (reusable structures)
- Linear application path

**NOT:** Massive directory duplication

---

**Revised Plan Status:** Ready for implementation
**User Status:** Taking 30-minute break
**Next Action:** Fix Browse context + Add toggles (30-45 min work)
