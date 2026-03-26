# Directory Structure Analysis - Repository vs Version Level
**Date:** 2026-01-17
**Context:** Evaluating proposed unified directory structure

---

## Current Situation

### User's Created Structure (Repository-Level)
```
/home/commander/3_Inventory/Warrior_Flow/     # REPO ROOT
├── versions/
│   ├── main_branch/                          # [NEW] Main branch modules/functions
│   └── Warrior_Flow_v09x_Monkey_Buisness_v2/ # Current version
│
├── .docv2_workspace/                         # [NEW] Repo-level workspace
│   ├── main_dev/                             # Main branch plans/tasks
│   │   ├── buisness/                         # Business planning
│   │   └── versions/
│   │       └── Warrior_Flow_v09x_Monkey_Buisness_v2/
│   └── projects/
│       ├── buisness/                         # ag_forge/quick_clip business apps
│       └── app_dev/                          # Other app types
```

### Original Planned Structure (Version-Level)
```
{version_dir}/                                # e.g., Warrior_Flow_v09x_Monkey_Buisness_v2/
├── .docv2_workspace/                         # Version workspace
│   ├── plans/
│   ├── tasks/
│   └── sessions/
├── projects/                                 # Version-specific projects
│   └── {project_name}/
└── templates/
```

---

## Architectural Comparison

### Repository-Level Approach (User's Proposal)

**Why This Makes Sense:**

1. **Cross-Version Collaboration**
   - Multiple versions can contribute to the same main_dev plans
   - Experimental versions don't pollute the main planning structure
   - Version-specific work tracked under main_dev/versions/{version_name}

2. **Centralized Project Pool**
   - Business projects (/ag_forge, /quick_clip) live in one location
   - All versions access the same business project pool
   - Reduces duplication of ag_forge knowledge bases

3. **Main Branch Clarity**
   - `/versions/main_branch/` clearly represents stable code
   - Separation between stable modules and experimental versions
   - Easy to identify "production-ready" vs "development" code

4. **Logical Grouping**
   - Business planning in main_dev/buisness/
   - Business projects in .docv2_workspace/projects/buisness/
   - Clear intent: planning vs implementation

5. **Migration-Friendly**
   - Version migration can consolidate to main_dev/
   - Easy to track which versions contributed what
   - warrior_gui [Migrate] functions can leverage this structure

**Challenges to Address:**

1. **workspace_manager Adaptation**
   - Currently expects version-level .docv2_workspace
   - Need to add repo-level fallback logic
   - Priority system: version > project > repo > default

2. **Path Resolution Complexity**
   - Systems need to check both repo-level and version-level
   - Need clear priority rules for conflicts
   - Documentation required for developers

3. **Coordination Overhead**
   - Multiple systems accessing shared repo-level resources
   - Need locking/conflict resolution for concurrent edits
   - Session management across versions

### Version-Level Approach (Original Plan)

**Advantages:**
- Simpler path resolution (already implemented)
- Version isolation (good for experimentation)
- Self-contained (easy to package/share)
- workspace_manager already works this way

**Disadvantages:**
- Project duplication across versions
- No cross-version collaboration
- Main branch location unclear
- Doesn't align with ag_forge/quick_clip multi-version workflows

---

## Recommended Hybrid Approach

### Structure
```
/home/commander/3_Inventory/Warrior_Flow/     # REPOSITORY ROOT
│
├── .docv2_workspace/                         # REPO-LEVEL WORKSPACE
│   ├── main_dev/                             # Main development branch
│   │   ├── plans/                            # Shared/stable plans
│   │   ├── tasks/                            # Shared tasks
│   │   ├── epics/                            # Long-term epics
│   │   ├── buisness/                         # Business planning docs
│   │   └── versions/                         # Version tracking
│   │       └── {version_name}/               # Version-specific work
│   │           ├── plans/                    # Version-contributed plans
│   │           └── diffs/                    # Version changes
│   │
│   ├── projects/                             # Shared project pool
│   │   ├── buisness/                         # Business/ag_forge projects
│   │   │   ├── {project_name}/
│   │   │   │   ├── PlannerSuite/
│   │   │   │   ├── inventory/
│   │   │   │   ├── knowledge/
│   │   │   │   └── .project_meta.json
│   │   │   └── ...
│   │   └── app_dev/                          # App development projects
│   │       └── {project_name}/
│   │
│   └── templates/                            # Project templates
│       ├── code_project/
│       ├── ag_business/
│       └── general/
│
├── versions/
│   ├── main_branch/                          # MAIN BRANCH (stable code)
│   │   ├── Modules/                          # Production modules
│   │   ├── warrior_gui.py                    # Stable launcher
│   │   └── README.md                         # Main branch docs
│   │
│   └── {version_name}/                       # EXPERIMENTAL VERSION
│       ├── .docv2_workspace/                 # VERSION-LEVEL WORKSPACE
│       │   ├── plans/                        # Version-local plans
│       │   ├── tasks/                        # Version-local tasks
│       │   ├── sessions/                     # Session state
│       │   └── config/                       # Version config
│       ├── Modules/                          # Version modules
│       ├── warrior_gui.py                    # Version launcher
│       └── version_manifest.json             # Version metadata
│
└── stable.json                               # Version registry
```

### Path Resolution Priority (Updated)

```python
def get_workspace_path(self, resource_type: str) -> Path:
    """
    Priority system for workspace path resolution
    """
    # Priority 1: Active project (if set)
    if self.current_project:
        path = self.current_project / resource_type
        if path.exists():
            return path

    # Priority 2: Version-level workspace
    version_path = self.version_dir / ".docv2_workspace" / resource_type
    if version_path.exists():
        return version_path

    # Priority 3: Repo-level workspace
    repo_root = self._find_repo_root()
    repo_path = repo_root / ".docv2_workspace" / resource_type
    if repo_path.exists():
        return repo_path

    # Priority 4: Default (version-level, create if needed)
    return version_path
```

---

## Why User's Approach is Better

### 1. Aligns with Real Workflow
- ag_forge and quick_clip are business suites that span versions
- Business projects naturally live at repo level
- Main branch code needs a home separate from experiments

### 2. Supports Multi-Version Development
- Can work on v09x and v09y simultaneously
- Shared knowledge base doesn't duplicate
- Plans can be version-specific or shared

### 3. Migration Path is Clear
```
Old Structure:
  versions/{version}/.docv2_workspace/

Migration Strategy:
  1. Move stable plans → repo/.docv2_workspace/main_dev/
  2. Keep version experiments → versions/{version}/.docv2_workspace/
  3. Consolidate business projects → repo/.docv2_workspace/projects/buisness/
  4. Create main_branch → versions/main_branch/
```

### 4. Integration with warrior_gui [Migrate]
- [Migrate] UI can show repo-level vs version-level resources
- Toggle between "Version Workspace" and "Main Development"
- Clear visualization of what's shared vs isolated

---

## Implementation Roadmap

### Phase 1: Update workspace_manager.py ✅
- Add repo_root detection
- Implement multi-level path resolution
- Add get_repo_workspace_path() method
- Maintain backward compatibility

### Phase 2: Update warrior_gui.py [Inventory] Tab
**Current:** [Files] [Plans] [Modules] [Sandbox]
**Add Context Toggles:**
- [ ] "Version Workspace" (current behavior)
- [ ] "Main Development" (repo-level main_dev/)
- [ ] "Shared Projects" (repo-level projects/)

**Auto-set default project directory:**
- Check if business project type → default to projects/buisness/
- Check if app dev type → default to projects/app_dev/
- Fallback to version workspace

### Phase 3: Update grep_flight [Inventory] Tab
**New Tab Structure:**
- [Grep] [Tasks] [Chat] [Inventory] ← NEW
  - Sub-tabs:
    - [Version Files] - Current version directory
    - [Main Branch] - /versions/main_branch/
    - [Projects] - Repo-level projects/
    - [Templates] - Project templates
  - Thunar launch buttons for each directory
  - Context indicator showing which level (version/repo)

### Phase 4: Update System Integration
- [ ] code_alchemist.py: Respect --output to projects/ dirs
- [ ] planner_wizard.py: Use workspace_manager for path resolution
- [ ] ag_forge: Point knowledge_forge_data to repo projects/
- [ ] Audit [New projects] [New plans] [New task] buttons

### Phase 5: Documentation & Transparency
- [ ] Surface all path resolutions to grep_flight traceback
- [ ] Export event logs for migrations
- [ ] Document routing for all creation buttons
- [ ] Update stable.json schema for repo-level metadata

---

## Decision: Use User's Repository-Level Structure ✅

**Rationale:**
1. Better aligns with actual multi-version, multi-suite workflow
2. Supports ag_forge/quick_clip business use case naturally
3. Provides clear main branch home
4. Enables cross-version collaboration
5. User has already created examples - shows this is the intuitive structure

**Next Steps:**
1. Update workspace_manager to support dual-level (repo + version)
2. Add context toggles to warrior_gui [Inventory]
3. Implement grep_flight [Inventory] tab with sub-tabs
4. Audit and document all [New X] button routing

---

**End of Analysis**
