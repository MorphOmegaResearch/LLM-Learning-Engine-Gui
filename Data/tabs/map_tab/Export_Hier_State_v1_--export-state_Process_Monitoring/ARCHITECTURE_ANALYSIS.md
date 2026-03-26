# Architecture Analysis: Hierarchy & Integration Considerations

**Date**: 2026-01-27  
**Question**: Does Process Monitoring become a tab of Custom Code, or does Custom Code become a tab of Process Monitoring?

---

## Current Architecture

```
Process_Monitoring/
├── secure_view.py (MAIN ENTRY POINT - tk.Tk())
│   ├── Left Panel: Project Tree
│   ├── Right Panel: Logs & Monitor (tabbed)
│   └── Center Notebook:
│       ├── Hier-View
│       ├── Editor
│       ├── CLI Output
│       ├── Monitor (process list)
│       └── Brain Map
│   └── Menu Bar:
│       ├── File
│       ├── Scans
│       ├── Tools → SharedPopupGUI("tools") ← POPUP ONLY
│       └── Config → SharedPopupGUI("config") ← POPUP ONLY
│
└── tools/tabs/ (Separate suite, accessed via POPUP)
    ├── custom_code_tab/ (AI training, chat interface)
    │   ├── Chat Interface
    │   ├── Settings
    │   ├── Browser
    │   └── Agent Task Queue
    ├── settings_tab/ (10,122 lines - comprehensive config)
    │   ├── General Settings
    │   ├── Paths
    │   ├── Training Defaults
    │   ├── Interface
    │   ├── Tab Manager
    │   ├── Resources
    │   ├── Custom Code Settings
    │   ├── Debug
    │   ├── System Blueprints
    │   └── Help & Guide
    │   └── **TODO BOARD** (Plans, Tasks, Bugs, Work Orders, Queue)
    │   └── **CONFORMER QUEUE** (Fix Flow, Self-Fixes)
    │   └── **PLANNER AGENT DOCK** (Session, Tasks, Conformers)
    ├── models_tab/
    ├── training_tab/
    ├── automation_tab/
    └── collections_tab/
```

---

## Socratic Analysis: Hierarchy Questions

### Q1: What is the PRIMARY purpose of each system?

**Process Monitoring Suite** (`secure_view.py`):
- Monitor running processes (CPU, memory, hierarchy)
- Analyze system behavior in real-time
- Security scanning and integrity checking
- Code structure visualization (Hier-View)
- File browsing and editing
- **Core Focus**: Understanding what's RUNNING on the system NOW

**Custom Code Suite** (`tools/tabs/*`):
- AI model training and management
- Chat interface for AI assistants
- Project TODO management (Plans, Tasks, Bugs)
- Code generation and modification workflows
- Conformer queue for approving changes
- Planner agent for task execution
- **Core Focus**: BUILDING and TRAINING code/models

### Q2: Which system provides context for the other?

**If Process Monitoring → Custom Code**:
- Monitor detects processes
- Identifies scripts running
- Routes suspicious processes to scanner
- Provides hierarchy context (PID → File → Code → Imports)
- **Then** trains on that code or monitors training processes

**If Custom Code → Process Monitoring**:
- Train models first
- Generate code
- **Then** monitor what those models/scripts do when running
- But... how do you know WHAT to train without seeing what's running?

### Q3: What is the natural workflow sequence?

```
1. OBSERVE system (Process Monitoring)
   ↓ See what's running
   ↓ Identify processes of interest
   ↓ Freeze system state
   ↓ Analyze hierarchy and code
   
2. UNDERSTAND code (Hier-View + Editor)
   ↓ View imports, classes, functions
   ↓ Inspect for security issues
   ↓ Identify bugs or improvements needed
   
3. PLAN changes (TODO Board in Settings Tab)
   ↓ Create tasks/bugs from findings
   ↓ Link to plans
   ↓ Queue for conformer approval
   
4. DEVELOP fixes (Custom Code + Planner Agent)
   ↓ AI generates fixes
   ↓ Conformer reviews changes
   ↓ Planner executes approved tasks
   
5. TRAIN models (Training Tab)
   ↓ Use observed processes as training data
   ↓ Improve detection/analysis
   
6. DEPLOY and MONITOR (back to Process Monitoring)
   ↓ Run new code
   ↓ Monitor its behavior
   ↓ Verify fixes worked
```

**Conclusion from workflow**: Process Monitoring is the ENTRY POINT and VALIDATION ENDPOINT.

### Q4: Does "process management before process training" make sense?

**YES** - for these reasons:

1. **Data Collection First**: You need to observe processes to have data to train on
2. **Security First**: Monitor before modifying (know what you're changing)
3. **Validation Loop**: Train → Deploy → Monitor → Refine
4. **Context Provision**: Process monitoring provides the "what" and "where", training provides the "how to improve"

### Q5: What would integration look like?

**Option A: Tools as Tabs in Process Monitoring**
```
secure_view.py (Main Window)
├── [Current tabs: Hier-View, Editor, CLI, Monitor, Brain Map]
├── Custom Code (NEW TAB)
├── Training (NEW TAB)
├── Models (NEW TAB)
├── Settings (NEW TAB from tools/tabs/settings_tab)
└── Automation (NEW TAB)
```

**Pros**:
- Single unified application
- Process monitoring context always available
- No popup windows
- Integrated config system
- Natural workflow: Monitor → Analyze → Fix → Train

**Cons**:
- Secure_view.py becomes massive (already 74KB, would grow to 200KB+)
- Tab overload (10+ tabs)
- Harder to focus on specific task

**Option B: Process Monitoring as Tab in Custom Code**
```
Custom Code Suite (Main Window)
├── Chat
├── Settings
├── Training
├── Models
├── Process Monitor (NEW TAB from secure_view.py)
└── Automation
```

**Pros**:
- Custom Code is already a full suite
- Settings tab already has comprehensive config (10K lines)
- TODO board and conformer queue already exist

**Cons**:
- Loses "security first" approach
- Process monitoring becomes secondary
- Harder to do live monitoring while training
- Violates "observe before modify" principle

**Option C: Hybrid - Separate but Integrated**
```
Main Application (Process Monitoring - secure_view.py)
├── [Keep current tabs]
├── Tools Menu → Launches Custom Code Suite in new window
│   └── Custom Code Suite shares config with main app
│   └── Can send processes/files to main app via callbacks
│   └── Main app can send tasks to Custom Code suite
└── Config shared via unified backend (process_organizer.py CM)
```

**Pros**:
- Clean separation of concerns
- Each app stays focused
- Inter-process communication for workflow
- Shared config prevents duplication

**Cons**:
- Still have popup windows
- More complex state management
- Need IPC between windows

---

## Integration Points Analysis

### What Settings Tab Provides (that Process Monitoring needs):

1. **TODO Board System** (Plans, Tasks, Bugs, Work Orders, Queue)
   - Process Monitoring can create bugs from security scans
   - Can create tasks from process analysis
   - Can link findings to plans

2. **Conformer Queue** ("Fix Flow" / "Self-Fixes")
   - Process Monitoring detects issues
   - Sends to conformer for approval
   - Conformer approves/rejects fixes
   - **This is the "self-fixes" you mentioned**

3. **Planner Agent Dock**
   - Automated task execution
   - Can execute fixes approved by conformer
   - Session management for long-running tasks

4. **Comprehensive Config UI** (8 tabs, 10K+ lines)
   - Already has Brain Map config
   - Already has Process Monitor config (filters, alerts)
   - Would eliminate duplicate config in shared_gui.py

### What Process Monitoring Provides (that Settings Tab needs):

1. **Live Process Data**
   - Running PIDs, CPU/memory usage
   - Process hierarchy (parent/child)
   - Network connections
   - File handles

2. **Code Analysis** (Hier-View + pyview)
   - Imports, classes, functions detection
   - Suspicious string detection
   - Code structure for training data

3. **Security Scanning**
   - Integrity checking
   - Known API detection
   - Suspicious keyword detection

4. **Real-time Monitoring**
   - Freeze time snapshots
   - Dominance calculation
   - Activity tracking

---

## Recommended Architecture (Socratic Conclusion)

### **Primary Recommendation: Process Monitoring as Root, Custom Code as Integrated Tab**

**Rationale**:
1. **"Process management before process training"** - you said it yourself
2. **Security-first approach** - observe before modifying
3. **Natural workflow** - Monitor → Analyze → Plan → Fix → Train → Validate
4. **Shared config** eliminates duplication between shared_gui.py and settings_tab.py
5. **TODO board becomes available** to track findings from process monitoring
6. **Conformer queue enables "self-fixes"** for detected issues

**Implementation**:
```
secure_view.py (Main Window)
├── [Existing Process Monitoring Tabs]
├── **Custom Code** (NEW - from tools/tabs/custom_code_tab)
│   └── Chat Interface
│   └── Agent Task Queue
├── **Training** (NEW - from tools/tabs/training_tab)
├── **Models** (NEW - from tools/tabs/models_tab)
├── **Settings** (REPLACE shared_gui.py with tools/tabs/settings_tab)
│   └── [All existing settings]
│   └── TODO Board (Plans, Tasks, Bugs, Queue)
│   └── Conformer Queue
│   └── Planner Agent Dock
└── Menu Bar:
    ├── File → [Add "Create Bug from Scan", "Create Task from Process"]
    ├── Scans → [Keep existing]
    ├── Tools → [Remove popup, now tabs]
    └── Config → [Remove popup, now Settings tab]
```

**Integration Flow**:
```
1. Process Monitor detects high CPU usage
   ↓
2. User freezes time, examines hierarchy
   ↓
3. User clicks "Create Task" → opens Settings tab, creates TODO
   ↓
4. TODO linked to detected process (PID, source file)
   ↓
5. User switches to Custom Code tab, sends task to Planner Agent
   ↓
6. Planner generates fix, sends to Conformer Queue
   ↓
7. User approves in Settings → Conformer Queue
   ↓
8. Fix applied automatically
   ↓
9. User returns to Process Monitor to verify fix worked
```

---

## Effort Estimation

### High Effort Tasks:
1. **Integrate settings_tab.py into secure_view.py** 
   - Effort: HIGH (10K lines to merge)
   - Need: Refactor settings_tab to not be popup-based
   - Need: Resolve BaseTab dependency
   - Need: Unify config backend with process_organizer.py CM

2. **Integrate custom_code_tab into secure_view.py**
   - Effort: MEDIUM-HIGH (complex tab with sub-tabs)
   - Need: Merge chat interface, agent queue
   - Need: Share config with Settings tab

3. **Create unified config backend**
   - Effort: MEDIUM
   - Need: Extend process_organizer.py CM
   - Need: Migrate all settings from settings.json to monitor_config.json
   - Need: Update both UIs to use same CM.get/set/save

### Medium Effort Tasks:
4. **Add TODO board integration to Process Monitor**
   - Effort: MEDIUM
   - Need: "Create Bug/Task" buttons in context menus
   - Need: Link process findings to TODO records
   - Need: Display TODO badge counts in UI

5. **Integrate Conformer Queue with Security Scanner**
   - Effort: MEDIUM
   - Need: Send scan findings to conformer
   - Need: Auto-generate fix proposals
   - Need: Apply approved fixes

6. **Add Planner Agent hooks**
   - Effort: MEDIUM
   - Need: Send tasks to planner from process monitor
   - Need: Display planner status in status bar
   - Need: Auto-execute approved tasks

### Low Effort Tasks:
7. **Remove SharedPopupGUI popups**
   - Effort: LOW
   - Just convert menu items to tab switching

8. **Unify shared_gui.py config into settings_tab**
   - Effort: LOW-MEDIUM
   - Migrate UI code, delete shared_gui.py

---

## Considerations & Trade-offs

### Pros of Full Integration:
- ✅ Single application to manage
- ✅ No popup windows
- ✅ Shared config eliminates duplication
- ✅ TODO board available for process findings
- ✅ Conformer queue enables "self-fixes"
- ✅ Natural workflow: Monitor → Fix → Train → Validate
- ✅ Follows "process management before training" principle

### Cons of Full Integration:
- ❌ Secure_view.py becomes very large (200KB+)
- ❌ Tab overload (potentially 12+ tabs)
- ❌ Complex refactoring needed
- ❌ Risk of breaking existing functionality
- ❌ Harder to focus on single task
- ❌ Longer startup time

### Alternative: Lightweight Integration
Keep separate apps but add:
- Shared config backend (CM)
- IPC for sending process → TODO board
- IPC for sending scan results → conformer
- Toolbar button: "Launch Custom Code Suite"
- Toolbar button: "Send to Planner"

**Effort**: LOW-MEDIUM  
**Benefit**: MEDIUM  
**Risk**: LOW

---

## Final Socratic Questions for You:

1. **Primary Use Case**: Do you spend more time monitoring processes, or training/fixing code?
   - If monitoring >> training: Keep Process Monitoring as root
   - If training >> monitoring: Consider Custom Code as root

2. **Workflow Preference**: Do you want to work in one window or multiple windows?
   - One window: Full integration (high effort)
   - Multiple windows: Lightweight integration (low effort)

3. **Tab Tolerance**: Can you handle 12+ tabs, or do you prefer focused apps?
   - 12+ tabs OK: Full integration
   - Prefer focused: Lightweight integration

4. **Self-Fixes Priority**: How critical is the conformer queue "fix flow"?
   - Critical: Must integrate (conformer needs process context)
   - Nice-to-have: Lightweight integration OK

5. **Training Data Source**: Where does your training data come from?
   - From monitored processes: Process Monitoring must be root
   - From external sources: Either architecture works

---

## Recommendation

Based on "process management before process training", I recommend:

**Phase 1 (Immediate - Low Effort)**:
- Unify config backend (extend CM in process_organizer.py)
- Both shared_gui.py and settings_tab.py use same CM
- Add "Launch Custom Code" button in Process Monitor toolbar
- Add "Send to TODO Board" in context menus

**Phase 2 (Medium-term - Medium Effort)**:
- Integrate settings_tab as a tab in secure_view.py
- Add TODO board, conformer queue, planner dock
- Remove SharedPopupGUI config popup
- Keep Custom Code as separate launcher (for now)

**Phase 3 (Long-term - High Effort)**:
- Integrate Custom Code, Training, Models as tabs
- Full unified application
- Remove all popups

**Effort**: Incremental (start low, scale up)  
**Risk**: Low (phased approach)  
**Benefit**: High (gets TODO board and conformer immediately)

---

What are your thoughts on this hierarchy?
