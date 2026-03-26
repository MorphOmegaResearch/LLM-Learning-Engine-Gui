# MASTER TASK LIST - Process Monitoring & Security Suite

===========================================================
PHASE 1.5: HIERARCHY SYSTEM & MONITOR TAB [COMPLETED]
===========================================================
1.5.1: ✅ Right Panel Tabbed Notebook
       - Converted right panel from single LabelFrame to ttk.Notebook
       - Created [📡 Logs] tab with existing log selector and display
       - Created [📊 Monitor] tab for process hierarchy visualization
       - Validation: Right panel now has two tabs, logs still functional

1.5.2: ✅ Hierarchy Analyzer System (hierarchy_analyzer.py)
       - ProcessNode dataclass: pid, parent/children, depth, descendants, dominance score
       - Tracks: CPU/memory aggregates, network connections, source files
       - Code analysis: imports, classes, functions (via pyview integration)
       - HierarchySnapshot: complete system state with roots/stems/dominant processes
       - Dominance scoring: weighs children count, depth, resources, network activity
       - Validation: Successfully captures 200+ process hierarchies with metrics

1.5.3: ✅ Monitor Tab TreeView
       - Columns: PID, Depth, Children, Dominance Score, Category
       - Shows top 20 dominant processes with expandable children
       - Color-coded by process category
       - Double-click shows detailed context (imports, classes, functions, connections)
       - Routes to editor if source file available
       - Validation: Hierarchy displays correctly, drill-down works

1.5.4: ✅ Freeze Time / Snapshot System
       - [❄️ Freeze Time] button captures complete system snapshot
       - Frozen snapshots preserve: all processes, hierarchy, dominance, code context
       - Freeze indicator shows timestamp and status (🔴 Live vs ❄️ Frozen)
       - Export functionality saves detailed hierarchy to /logs
       - Integration with brain_viz frozen state
       - Validation: Snapshot captures state, can review frozen moment

1.5.5: ✅ Brain Map ↔ Monitor Tab Sync
       - Selecting "Brain Map" tab auto-switches right panel to Monitor tab
       - Auto-refreshes hierarchy in live mode when Brain Map activated
       - Maintains frozen snapshot when in freeze mode
       - Provides context for 3D visualization
       - Validation: Tab switching triggers Monitor display

LINEAGE TRACKING IMPLEMENTED:
  Process (PID) → Category → Source File → Imports → Classes → Functions → Strings/IPs
  Full dominance calculation: root → stems → leaves with depth/descendant metrics

FILES CREATED/MODIFIED:
  - hierarchy_analyzer.py (NEW): Core hierarchy analysis engine
  - secure_view.py: Right panel redesign, Monitor tab, freeze functionality
  - Tasks.md: This documentation

===========================================================
PHASE 2: GUI UTILITY & STABILITY [CURRENT]
===========================================================
2.7: Editor Utilities: [Search/Find] and [Replace] dialogs.
     - Validation: Successfully locate and highlight strings in the Editor.
2.8: Shared Popup UI: Separate tabs for "Default Tools" and "Custom Tools (/tools)".
     - Validation: Verify scripts in /tools are detected and executable from the UI.
2.9: Baseline Security: Implement 'py_compile' check during Integrity Updates.
     - Validation: Update Gate blocks/warns if a script contains Syntax Errors.

===========================================================
PHASE 3: CONFIGURATION & PERSISTENCE [NEXT]
===========================================================
3.1: Config-to-GUI Bridge: Map 'monitor_config.json' to live GUI state (Theme/Lines).
     - Validation: Changing config manually updates GUI on next launch.
3.2: Live Theme Switching: Implement Dark/Light/Monokai live application.
     - Validation: Immediate UI color shift without app restart.
3.3: User Pref Persistence: Save window geometry and editor toggles.
     - Validation: 'monitor_config.json' reflects GUI changes in real-time.

===========================================================
PHASE 4: ADVANCED BEHAVIORAL ANALYSIS [CRITICAL]
===========================================================
4.1: [NEW] Object Matching: Right-click UI elements (Frames/Tabs/Buttons) to lock focus and map back to source script.
4.2: [NEW] Context Hover: Mouse-over UI objects to show relationship chain (File <-> Function <-> Handle) with configurable cooldown.
4.3: Active Controls: [Kill], [Suspend], and [Refresh] in Process Monitor.
     - Validation: Verify PID termination and state suspension from Target Focus.
4.2: [NEW] Monitor UX: Add [Refresh Rate] slider (0.1s to 30s) for live tracking.
4.3: [NEW] Right-Click Routing: Context menu on Process/File to open in [Editor] or [Hier-View].
4.4: [NEW] Hover Intelligence: Mouse-over on-screen symbols to show the "Chain" (File <-> Function <-> Socket).
4.5: Process Clone Tracker: Group PIDs by script; flag "Server Outliers."
4.6: Capability Tags: UI icons for [Net], [Disk], [Root] based on runtime handles.
4.7: Runtime Validation: Cross-reference active sockets against Manifest.json.


===========================================================
PHASE 5: BIAS-HARDENING & POLISH [FINAL]
===========================================================
5.1: Sensitivity-Aware Integrity: Diffing logic changes vs comment changes.
     - Validation: Baseline update ignores whitespace but triggers on new imports.
5.2: Deep Mapping: Finalize [File <-> Code <-> Alias <-> Socket] relationships.
     - Validation: Manifest correctly traces a specific socket to a line of code.
5.3: Asset Generation: Status icons for the Monitor and Tree-view.
     - Validation: Visual clarity for Secure vs Modified files.

===========================================================
PHASE 6: 3D BRAIN MAP REDESIGN [CRITICAL FIX]
===========================================================
[DATE: 2026-01-26] - [ISSUE: Current implementation uses basic Canvas 2D projection instead of proper matplotlib 3D]

6.1: [CRITICAL] Replace Canvas-based Brain Map with brain_viz_3d.py Implementation
     CURRENT STATE (secure_view.py lines 946-1069):
     ✗ Uses tk.Canvas with manual 3D projection math (project_3d method)
     ✗ Basic rotation with numpy sin/cos calculations
     ✗ Particle clustering poorly implemented (random node offsets)
     ✗ No proper mouse interaction (rotation, zoom, node picking)
     ✗ No matplotlib Axes3D - just Canvas oval drawing

     TARGET STATE (from tools/tabs/models_tab/brain_viz_3d.py):
     ✓ Use matplotlib Axes3D for real 3D rendering
     ✓ FigureCanvasTkAgg for Tkinter embedding
     ✓ Proper mouse event handling (button_press, motion, scroll, pick)
     ✓ Interactive node selection with drill-down panels
     ✓ Component tree panel showing brain structure

     SUB-TASKS:
     6.1.a: Review brain_viz_3d.py implementation (lines 1-200: initialization, 160-210: FigureCanvasTkAgg setup)
     6.1.b: Review rendering logic (lines 1168-1292: _render_brain method with Axes3D.scatter/plot)
     6.1.c: Extract reusable components from brain_viz_3d.py for process monitoring context
     6.1.d: Replace setup_brain_map_tab() in secure_view.py with matplotlib-based implementation

     Validation: Brain Map tab shows proper 3D view with mouse rotation, zoom, and node interaction

6.2: [NEW] PID-Centric Visualization with Communication Tracking
     DESIGN GOAL: Center = PID, Regions = Categories, Nodes = Related Processes, Edges = Communication

     LINEAGE FLOW:
     PID (center kernel)
       → Process Category (brain region: MY SCRIPTS, GPU & MEDIA, WEB, DEV TOOLS, etc.)
         → Source File (extracted from cmdline via psutil)
           → Code Elements (from pyview.analyze_file: imports, classes, functions)
             → Suspicious Strings (IPs, URLs from pyview strings analysis)

     SUB-TASKS:
     6.2.a: Map focused_pid to center kernel (replace model_kernel concept)
     6.2.b: Map process categories from get_category() to brain regions (6 categories)
     6.2.c: Detect communication between processes (psutil connections, parent/child relationships)
     6.2.d: Draw edges between communicating PIDs as neural pathways
     6.2.e: Color-code pathways by communication type (IPC, Network, Parent-Child)

     Validation: Selecting a PID shows it at center with edges to related processes

6.3: [NEW] Deep Lineage Drill-Down Integration
     INTEGRATION WITH EXISTING SYSTEMS:
     - pyview.py: Code structure analysis (imports, classes, functions, strings)
     - process_organizer.py: Category detection and security scanning
     - shared_gui.py: Popup panels for detailed context

     SUB-TASKS:
     6.3.a: On node click → route_process_to_source() → extract script path from cmdline
     6.3.b: Run pyview.analyze_file() on extracted source file
     6.3.c: Show component tree with: File → Imports → Classes → Functions → Strings
     6.3.d: Highlight suspicious strings (IPs/URLs) from pyview in tree
     6.3.e: Link hier-tree selection back to Editor tab (jump to line)

     Validation: Click node → see source file structure → click element → jump to code in Editor

6.4: [NEW] Process Communication Detection & Visualization
     METHODS TO DETECT COMMUNICATION:
     1. Parent-Child relationships (psutil.Process.parent(), .children())
     2. Network sockets (psutil.Process.connections() - match local/remote ports)
     3. IPC mechanisms (shared files, pipes - psutil.Process.open_files())
     4. Process groups (same script name but different PIDs)

     SUB-TASKS:
     6.4.a: Build process relationship graph from active_group set
     6.4.b: Detect socket connections between processes (match listening ports)
     6.4.c: Flag "server outliers" (same script, different servers - security concern)
     6.4.d: Visualize communication with animated edge pulses
     6.4.e: Log communication events to daily journal (log_communication_event)

     Validation: Grouped processes show edges; hovering edge shows communication type

6.5: [NEW] Real-Time Activity Pulsing & Behavioral Heatmap
     CURRENT: Lines 1170-1172 pulse brain regions based on CPU activity
     ENHANCE: Make it more visible and meaningful

     SUB-TASKS:
     6.5.a: Map CPU activity to region glow intensity (already partially done)
     6.5.b: Add I/O activity indicators (disk/network reads from psutil.Process.io_counters())
     6.5.c: Distinguish between types: CPU=size pulse, Disk=color shift, Net=edge pulse
     6.5.d: Add activity legend in corner of Brain Map
     6.5.e: Decay effect for activity (already at 0.92 multiplier, line 1060)

     Validation: High CPU process causes region to glow; network activity pulses edges

6.6: Configuration & Performance Optimization
     CURRENT ISSUES:
     - Canvas update loop runs at 30ms (line 1069) - may cause lag
     - No FPS limiting or performance monitoring
     - No config persistence for brain map settings

     SUB-TASKS:
     6.6.a: Add brain_map_config section to monitor_config.json
     6.6.b: Make update frequency configurable (30ms to 200ms)
     6.6.c: Add performance metrics (FPS counter, render time)
     6.6.d: Implement LOD (Level of Detail) - reduce node count when many processes
     6.6.e: Add toggle to disable auto-rotate when user interacts

     Validation: Brain Map runs smoothly with 100+ processes; settings persist across restarts

===========================================================
IMPLEMENTATION PRIORITY & DEPENDENCIES
===========================================================
HIGH PRIORITY (Core Functionality):
→ 6.1: Replace Canvas with matplotlib Axes3D (BLOCKS all other brain map work)
→ 6.2: PID-centric design with category mapping
→ 6.3: Deep lineage drill-down (integrates existing pyview/organizer systems)

MEDIUM PRIORITY (Enhanced Features):
→ 6.4: Communication detection and visualization
→ 6.5: Real-time activity heatmap

LOW PRIORITY (Polish):
→ 6.6: Config persistence and performance optimization

DEPENDENCIES:
- Task 6.1 must complete before 6.2-6.5 (foundation change)
- Task 6.3 requires 6.2 (need PID → Source file mapping first)
- Task 6.4 can run parallel to 6.3
- Task 6.6 is independent, can be done anytime after 6.1

===========================================================
FILES TO MODIFY
===========================================================
PRIMARY:
- secure_view.py: Lines 946-1069 (setup_brain_map_tab, project_3d, update_brain_viz)
- secure_view.py: Lines 1105-1182 (update_proc_list - add communication detection)

REFERENCE (DO NOT MODIFY - USE AS TEMPLATE):
- tools/tabs/models_tab/brain_viz_3d.py: Proper 3D implementation example

INTEGRATE WITH:
- pyview.py: analyze_file() for code structure
- process_organizer.py: get_category() for region mapping
- shared_gui.py: Popup panels for detailed node context

CONFIG:
- monitor_config.json: Add brain_map settings section