# Directory Structure Clarification - User's Vision
**Date:** 2026-01-19
**Status:** NEEDS CLARIFICATION BEFORE PROCEEDING

---

## What User Explained

### `/projects/` - Project-Specific Storage
**Contains:** diffs, stashes, inventory

#### `/projects/buisness/`
**Purpose:** Professional services documentation (NOT necessarily apps)
**Content Types:**
- Financials
- Forecasts
- Plans/task docs
- Diffs with forecasted expectations vs market valuations
- Economic viability variables

#### `/projects/app_dev/`
**Purpose:** [NOT YET CLARIFIED]
**Assumption:** App development projects?

---

### `main_dev/` - Main Branch Differences

#### `main_dev/buisness/`
**Purpose:** [NOT CLARIFIED - How does this differ from /projects/buisness/?]

#### `main_dev/versions/`
**Purpose:** Documentation storage for version management
**Coordinates with:**
- [New Version] button
- [Migrate] button

**Behavior:**
When user creates new version → spawns whole `/versions/` with:
- Full modules
- File structure
- [WHAT ELSE?]

#### `main_dev/plans/`
**Purpose:** [CREATED BY ME - Subdirs: Epics, Plans, Phases, Tasks, etc.]
**Question:** Was this correct or should it be elsewhere?

---

## What I Created (Possibly Wrong)

### Created by workspace_manager:
- `main_dev/tasks/` ← User says they DIDN'T create this
- `main_dev/plans/` subdirs (Epics, Plans, Phases, Tasks, Milestones, Diffs, Refs)
- `main_dev/config/`
- `main_dev/sessions/`
- `main_dev/sandboxes/`
- `main_dev/pfc_history/`

### Questions:
1. Should `tasks/` exist? If not, where do tasks go?
2. Are the `plans/` subdirs correct?
3. What about config/sessions/sandboxes/pfc_history?

---

## GUI Tab Routing - UNCLEAR

### Current Toggle Implementation:
- **"Current"** → Routes to version workspace (`.docv2_workspace/`)
- **"Default"** → Routes to `main_dev/` [BUT WHERE EXACTLY?]
- **"Shared"** → Routes to `projects/` [BUT WHERE EXACTLY?]

### Questions:
1. Which GUI tab shows which directory?
2. [Plans] tab → Shows what when "Default" is selected?
3. [Plans] tab → Shows what when "Shared" is selected?
4. [Sandbox] tab → Looks for `.docv2_workspace/sandboxes/` - is this right?

---

## Main Branch vs Versions - UNCLEAR

User said: "main_branch/versions defines documentation storage"

**Questions:**
1. Is it `main_dev/versions/` or something else?
2. What's stored there vs actual `/versions/Warrior_Flow_v09x/`?
3. How does "New Version" button use this?
4. How does "Migrate" button use this?

---

## Business vs App_Dev - UNCLEAR

**Question:** What's the distinction?
- Is "buisness" for professional services documentation?
- Is "app_dev" for application code projects?
- Can both contain documentation AND code?
- Should they have the same subdirectory structure?

---

## What User Said (Verbatim)

> "projects' will contain diffs, stashes, inventory, /buisness dirs will contain specific (per project/buisness, which may not be apps) documentation for professional services from financials to forecasts to plans/task docs exp diffs (w/forecasted expectations vs market valuations and economic viability variables)"

> "the 'main_branch' dirs define the differences between versions of the working systems eg warrior gui grep flight and /modules"

> "the main_branch/versions defines documentation storage for leverage of the 'new version' and 'migrate' buttons, the user can create new versions which spawns a whole /versions with the full modules and file structure ect"

> "idk it might be too complicated your about to compact too..."

---

## CRITICAL: What I Need to Know

### Before Making ANY More Changes:

1. **Full directory map with purpose:**
   ```
   /.docv2_workspace/
   ├── main_dev/
   │   ├── buisness/        ← PURPOSE?
   │   ├── versions/        ← PURPOSE? STRUCTURE?
   │   ├── plans/           ← CORRECT? SUBDIRS OK?
   │   ├── tasks/           ← SHOULD EXIST?
   │   ├── config/          ← CORRECT?
   │   ├── sessions/        ← CORRECT?
   │   ├── sandboxes/       ← CORRECT?
   │   └── pfc_history/     ← CORRECT?
   │
   ├── projects/
   │   ├── buisness/        ← vs main_dev/buisness?
   │   └── app_dev/         ← PURPOSE?
   │
   └── templates/           ← PURPOSE?
   ```

2. **GUI Tab Mappings:**
   - [Plans] tab shows → ?
   - [Tasks] tab shows → ?
   - [Sandbox] tab shows → ?
   - When "Default" selected → routes to → ?
   - When "Shared" selected → routes to → ?

3. **Version Management Flow:**
   - [New Version] button → creates what where?
   - [Migrate] button → moves what from where to where?
   - main_dev/versions/ → stores what?
   - How does this relate to /versions/Warrior_Flow_v09x/?

---

## User's Warning

> "it might be too complicated your about to compact too..."

**Action:** STOP making changes, get clarification, THEN proceed

---

## Next Steps (After Clarification)

1. User explains full intended structure
2. I document it clearly
3. We agree on routing logic
4. I fix what I broke
5. We test with real docs

**DO NOT PROCEED WITHOUT CLARIFICATION**
