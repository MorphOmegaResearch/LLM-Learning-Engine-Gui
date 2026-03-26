# Panel & Widget Audit Report

**Date**: 2026-01-27  
**Auditor**: System Analysis  
**Scope**: All panels, tabs, widgets, and configuration UI

---

## Executive Summary

Comprehensive audit of the Process Monitoring Suite GUI reveals a **well-structured but partially integrated system**. The main application (`secure_view.py`) and config popup (`shared_gui.py`) are functionally complete, but there's a **critical gap**: the `tools/tabs/settings_tab.py` exists as a separate 462KB config system that **should be unified** with the main config UI.

**Key Findings**:
- ✅ Main GUI structure is complete and well-organized
- ✅ Shared config popup (SharedPopupGUI) has comprehensive settings
- ⚠️ Duplicate config system in tools/tabs/settings_tab.py (not integrated)
- ⚠️ Missing: Editor tab lacks syntax highlighting controls in config
- ⚠️ Missing: Logging config UI (retention, rotation, levels per module)
- ⚠️ Missing: Keyboard shortcuts/keybindings UI
- ⚠️ Missing: Security scan config UI

---

## Panel Structure Overview

### **1. LEFT PANEL - Project Tree**
**Location**: `secure_view.py:188-192`  
**Widget**: `ttk.Treeview` (self.tree)

**Functionality**:
- ✅ File system browser rooted at current directory
- ✅ Bindings: `<<TreeviewSelect>>` → on_tree_select()
- ✅ Context menu support (right-click)
- ✅ Auto-refresh on directory change

**Gaps Identified**:
- ❌ **No filter controls**: Can't filter by file type (.py, .json, .md)
- ❌ **No search box**: Can't search for files by name
- ❌ **No breadcrumb navigation**: Hard to see current path
- ❌ **No recent files list**: No quick access to recently opened files
- ❌ **No bookmarks/favorites**: Can't mark frequently used directories

**Recommendations**:
1. Add file type filter dropdown above tree
2. Add search entry box with real-time filtering
3. Add breadcrumb bar showing current path with clickable segments
4. Add "Recent Files" section in manifest area
5. Add right-click "Bookmark" option to tree items

---

### **2. RIGHT PANEL - Logs & Monitor (Tabbed Notebook)**
**Location**: `secure_view.py:193-263`  
**Widget**: `ttk.Notebook` (self.right_notebook)

#### **Tab 1: 📡 Logs**
**Functionality**:
- ✅ Log file selector (Combobox)
- ✅ Log display (Text widget, monospace, green-on-black)
- ✅ Refresh button
- ✅ Auto-prioritizes today's gui/comm logs

**Gaps Identified**:
- ❌ **No search in logs**: Can't search for keywords in log display
- ❌ **No log level filtering**: Can't show only ERROR/WARNING
- ❌ **No auto-scroll toggle**: Log doesn't stay at bottom during live updates
- ❌ **No export button**: Can't export filtered/searched logs
- ❌ **No timestamp highlighting**: Hard to see time gaps
- ❌ **No line numbers**: Hard to reference specific log lines

**Recommendations**:
1. Add search bar above log display with "Find Next" button
2. Add log level filter checkboxes (DEBUG, INFO, WARNING, ERROR, CRITICAL)
3. Add "Auto-scroll" checkbox to follow tail of log
4. Add "Export Selection" button
5. Add syntax highlighting for timestamps and levels
6. Add line numbers in left margin (like editor)

#### **Tab 2: 📊 Monitor**
**Functionality**:
- ✅ Freeze Time button with unfreeze toggle
- ✅ Refresh button
- ✅ Freeze indicator (🔴 Live / ❄️ Frozen @ timestamp)
- ✅ Hierarchy TreeView (PID, Depth, Children, Score, Category)
- ✅ Double-click → Brain Map focus + details popup
- ✅ Single-click → Updates brain map focus
- ✅ Scrollbar for hierarchy

**Gaps Identified**:
- ❌ **No search/filter**: Can't search for specific PID or process name
- ❌ **No sort controls**: Can't click column headers to sort
- ❌ **No process count display**: Unknown how many processes shown
- ❌ **No category filter**: Can't show only "MY SCRIPTS" processes
- ❌ **No export hierarchy button**: Can only export via Monitor tab controls
- ❌ **No timeline scrubber**: Can't navigate between multiple snapshots

**Recommendations**:
1. Add search box to filter by PID or name
2. Make column headers clickable for sorting
3. Add status label: "Showing X of Y processes"
4. Add category filter dropdown
5. Move "Export Hierarchy" button here from Monitor tab controls
6. Add snapshot history dropdown for timeline navigation

---

### **3. CENTER NOTEBOOK - Main Tabs**
**Location**: `secure_view.py:212-328`  
**Widget**: `ttk.Notebook` (self.notebook)

#### **Tab 1: Hier-View**
**Location**: `secure_view.py:265-274`  
**Functionality**:
- ✅ Code structure tree (Imports, Classes, Functions, etc.)
- ✅ Columns: Element, Type, Line, Details
- ✅ Double-click → jumps to line in editor
- ✅ Hover → shows tooltip with context
- ✅ Context menu (right-click)
- ✅ Color-coded by element type (imports, classes, functions)

**Gaps Identified**:
- ❌ **No search**: Can't search for specific function/class
- ❌ **No filter by type**: Can't show only "Classes" or only "Functions"
- ❌ **No "Go to Definition"**: Can't jump from usage to definition
- ❌ **No "Find References"**: Can't find where a function is used
- ❌ **No docstring preview**: Tooltip doesn't show function docstrings
- ❌ **No expand/collapse all**: Must expand each class individually

**Recommendations**:
1. Add search box above tree
2. Add element type filter checkboxes
3. Add "Find References" to context menu
4. Show function/class docstrings in tooltip
5. Add toolbar buttons: "Expand All", "Collapse All"
6. Add "Copy Path" to context menu (module.class.function)

#### **Tab 2: Editor**
**Location**: `secure_view.py:277-315`  
**Functionality**:
- ✅ Text editor with line numbers
- ✅ Toolbar: Find, Inspect, Save
- ✅ Config-based font (family, size, weight)
- ✅ Line wrap toggle (from config)
- ✅ Undo support
- ✅ Auto-save (optional, from config)
- ✅ Scroll sync between line numbers and editor

**Gaps Identified**:
- ❌ **No syntax highlighting**: Code is monochrome
- ❌ **No Replace function**: Only Find, no Find & Replace
- ❌ **No Go to Line**: Can't jump to specific line number
- ❌ **No bracket matching**: Hard to see matching (), {}, []
- ❌ **No code folding**: Can't collapse functions/classes
- ❌ **No minimap**: Hard to navigate large files
- ❌ **No multiple tabs**: Can only edit one file at a time
- ❌ **No recent files dropdown**: Must re-browse to switch files
- ❌ **No file modified indicator**: Unclear if file has unsaved changes

**Recommendations**:
1. **CRITICAL**: Add syntax highlighting (pygments or built-in)
2. Add "Replace" button next to "Find"
3. Add "Go to Line" button (Ctrl+G)
4. Add bracket matching with color highlight
5. Add modified indicator: "*" in tab title or status bar
6. Add "Recent Files" dropdown in toolbar
7. Add status bar: Line X, Column Y, File Size
8. Consider multi-tab support for future enhancement

#### **Tab 3: CLI Output**
**Location**: `secure_view.py:316-319`  
**Functionality**:
- ✅ Text widget for command output
- ✅ Monospace font
- ✅ Black background, white text

**Gaps Identified**:
- ❌ **No CLI input**: Can't run commands from here
- ❌ **No command history**: Can't see previous commands run
- ❌ **No search**: Can't search output
- ❌ **No clear button**: Output accumulates forever
- ❌ **No ANSI color support**: Terminal colors not rendered
- ❌ **No copy/export**: Can't easily copy output

**Recommendations**:
1. Add CLI input Entry box at bottom with "Run" button
2. Add command history dropdown (up/down arrow navigation)
3. Add search box
4. Add "Clear Output" button
5. Add ANSI color parsing (use colorama or ansi2html)
6. Add "Export Output" button

#### **Tab 4: Monitor (Process List)**
**Location**: `secure_view.py:320-370`  
**Functionality**:
- ✅ Controls: Active Monitor toggle, Target label, Kill/Suspend buttons
- ✅ Export Hierarchy button
- ✅ TreeView: PID, Dominance, Group, CPU, Mem, Name, Command
- ✅ Color-coded by category
- ✅ Sortable columns (click heading)
- ✅ Auto-refresh when active
- ✅ Config-based filtering (hide_system_idle, min thresholds)
- ✅ Context menu

**Gaps Identified**:
- ❌ **No refresh rate display**: User doesn't know update frequency
- ❌ **No process count**: Unknown how many processes shown/hidden
- ❌ **No quick category toggles**: Must use config to filter categories
- ❌ **No "Pin to Top"**: Can't keep important processes visible
- ❌ **No process search**: Hard to find specific process in long list
- ❌ **No CPU/Memory graphs**: Only text values, no visual trends
- ❌ **No process tree view**: Can't see parent-child hierarchy visually

**Recommendations**:
1. Add status bar: "Showing X processes (Y hidden), refreshing every Z ms"
2. Add category filter checkboxes in toolbar
3. Add "Pin" button to keep selected process at top
4. Add search box above tree
5. Add mini-sparklines for CPU/Mem in columns
6. Add "Tree View" toggle to show parent-child indentation

#### **Tab 5: Brain Map**
**Location**: `secure_view.py:324-328`  
**Functionality**:
- ✅ 3D matplotlib visualization (process_brain_viz.py)
- ✅ Controls: Freeze State, Auto-rotate, Show Edges, Show Labels
- ✅ PID-centric view with categories mapped to brain regions
- ✅ Mouse rotation (azimuth/elevation)
- ✅ Debug overlay (FPS, event log) if enabled
- ✅ Config-based settings (update interval, GPU, etc.)

**Gaps Identified**:
- ❌ **No search/filter**: Can't search for specific PID in visualization
- ❌ **No legend**: Brain region colors not explained
- ❌ **No zoom controls**: Must use mouse scroll (not obvious)
- ❌ **No reset camera button**: Can't return to default view
- ❌ **No screenshot/export**: Can't save visualization
- ❌ **No process labels**: Nodes don't show PID/name (only in tooltip)
- ❌ **No time slider**: Can't replay activity over time

**Recommendations**:
1. Add search box: "Focus PID" with auto-complete
2. Add color legend in corner (category → region → color)
3. Add zoom slider and "Reset View" button
4. Add "Screenshot" button to save PNG
5. Add optional node labels (toggle in config)
6. Add time slider for snapshot history replay

---

## Configuration UI Audit (shared_gui.py)

### **Config Tabs Available**
**Location**: `shared_gui.py:231-276`  
**Access**: Menu → Config

1. **✅ Themes** (setup_color_config)
   - Color scheme selection
   - Custom color editing

2. **✅ Hier-Colors** (setup_hier_color_config)
   - Import, Class, Function, Method, Variable, String/IP, File colors
   - Hex color entry fields

3. **✅ Right-Click Actions** (setup_menu_config)
   - Context menu action ordering
   - Enable/disable actions

4. **✅ Priority Settings** (setup_priority_config)
   - Process priority rules
   - Category priorities

5. **✅ GUI Settings** (setup_gui_config)
   - Window geometry
   - Refresh rates
   - Show/hide features

6. **✅ Brain Map** (setup_brain_map_config)
   - Enable debug
   - Auto-rotate
   - Show edges/labels
   - FPS overlay
   - Update interval

7. **✅ Process Monitor** (setup_proc_monitor_config)
   - Filters: hide_system_idle, min CPU/mem thresholds
   - Alerts: CPU/mem thresholds, notifications, sounds

8. **✅ Layout & Tooltips** (setup_layout_config)
   - UI dimensions (left_panel, right_panel, menu sizes)
   - Hover delay
   - Indicator position

### **Config Tabs MISSING**

1. **❌ Editor Settings**
   - **Should include**:
     - Font (family, size, weight) ✅ (currently in code)
     - Tab width / Use spaces
     - Auto-indent
     - Line wrap ✅ (currently in code)
     - Auto-save ✅ (currently in code)
     - Auto-save interval
     - Max file size warning
     - **Syntax highlighting theme** (MISSING)
     - Line numbers display
   - **Current Status**: Partially in config, but no UI tab

2. **❌ Logging Settings**
   - **Should include**:
     - Retention days
     - Max log size (MB)
     - Auto-cleanup toggle
     - Log levels per module (gui, popup, monitor, scanner, brain_viz)
     - Rotation settings (enabled, when, backup count)
   - **Current Status**: In config schema, but NO UI tab

3. **❌ Security Scan Settings**
   - **Should include**:
     - Known APIs list (add/remove)
     - Suspicious keywords (add/remove)
     - Allow/deny lists
     - Scan depth
     - Whitelist management
   - **Current Status**: In config (monitor_config.json), but NO UI tab

4. **❌ Keyboard Shortcuts**
   - **Should include**:
     - Customizable keybindings
     - Shortcuts for: Find, Save, Freeze, Refresh, Switch tabs
     - Export/import keybinding profiles
   - **Current Status**: COMPLETELY MISSING

5. **❌ Network Settings**
   - **Should include**:
     - Proxy configuration
     - Timeout settings
     - Max connections
     - Allowed/blocked hosts
   - **Current Status**: COMPLETELY MISSING

6. **❌ Performance Settings**
   - **Should include**:
     - Max processes to display
     - Snapshot cache size
     - Enable/disable features for performance
     - Memory usage limits
   - **Current Status**: COMPLETELY MISSING

7. **❌ Hierarchy Analyzer Settings**
   - **Should include**:
     - Stem detection thresholds (depth, descendant count)
     - Dominance score weights (children, depth, CPU, network)
     - Max snapshot history
     - Auto-capture interval
   - **Current Status**: Hardcoded in hierarchy_analyzer.py

---

## Tools/Config Integration Issue

### **CRITICAL FINDING: Duplicate Config System**

**Location**: `tools/tabs/settings_tab/settings_tab.py` (462KB file!)

**Problem**: 
- A separate, comprehensive settings UI exists in the tools directory
- This is **NOT integrated** with the main config popup (shared_gui.py)
- Creates **two separate config systems** that may conflict
- User confusion: which config UI should they use?

**Analysis**:
```
Main Config UI:          Tools Config UI:
shared_gui.py            tools/tabs/settings_tab/settings_tab.py
├─ Themes                ├─ ??? (unknown, file not read)
├─ Hier-Colors           └─ Likely duplicates main config
├─ Right-Click Actions
├─ Brain Map
├─ Process Monitor
└─ Layout & Tooltips
```

**Recommendations**:
1. **IMMEDIATE**: Read tools/tabs/settings_tab/settings_tab.py to understand scope
2. **DECISION NEEDED**: 
   - Option A: Deprecate tools config, migrate all settings to shared_gui.py
   - Option B: Deprecate shared_gui.py config, use tools config exclusively
   - Option C: Unify both into single config system with shared backend
3. **BEST APPROACH**: Option C - Create config sharing layer
   - Move config logic to `config_manager.py` (separate from UI)
   - Both UIs call same config backend (CM.get/set/save)
   - Ensure both UIs stay in sync with same config sections

---

## Menu Bar Audit

**Location**: `secure_view.py:147-163`

### **Current Menu Items**

**File Menu**:
- ✅ Open Directory
- ✅ Save File
- ✅ View Crash Logs
- ✅ Exit

**Scans Menu**:
- ✅ Quick Scan
- ✅ Full Scan
- ✅ View Integrity

**Tools** (popup):
- ✅ Default Tools
- ✅ Local Scripts (/tools)
- ✅ Security Manifest

**Config** (popup):
- ✅ All config tabs listed above

### **Missing Menu Items**

**File Menu**:
- ❌ Recent Files submenu
- ❌ Export (hierarchy, logs, snapshot)
- ❌ Import (config, bookmarks)
- ❌ Preferences (shortcut to Config)

**Edit Menu** (ENTIRE MENU MISSING):
- ❌ Undo / Redo
- ❌ Cut / Copy / Paste
- ❌ Find / Replace
- ❌ Go to Line

**View Menu** (ENTIRE MENU MISSING):
- ❌ Zoom In / Zoom Out
- ❌ Show/Hide panels
- ❌ Full Screen
- ❌ Reset Layout

**Help Menu** (ENTIRE MENU MISSING):
- ❌ Documentation
- ❌ Keyboard Shortcuts
- ❌ About
- ❌ Check for Updates

---

## Context Menu Audit

**Location**: `secure_view.py:372-390`  
**Config**: `monitor_config.json` → user_prefs.context_menu_actions

### **Current Actions** (from config):
1. ✅ Route to Editor
2. ✅ Route to Hier-View
3. ✅ Deep Inspect
4. ✅ Quick Scan
5. ✅ Export Context

**Bindings**:
- ✅ Project Tree (self.tree)
- ✅ Process Tree (self.proc_tree)
- ✅ Hier Tree (self.hier_tree)

### **Missing Context Menu Actions**:
- ❌ Copy Path / Copy Name
- ❌ Open in External Editor (VSCode, etc.)
- ❌ Show in File Manager
- ❌ Run Script (for .py files)
- ❌ Kill Process (for proc_tree)
- ❌ Freeze/Focus Process (for proc_tree)
- ❌ Bookmark / Unbookmark (for tree)

---

## Widget Gaps Summary

### **Search Functionality Gaps**
**Severity**: HIGH

Almost NO widgets have search capability:
- ❌ Project Tree - no file search
- ❌ Log Display - no log search
- ❌ Hierarchy Monitor - no process search
- ❌ Hier-View - no code element search
- ❌ Process Monitor - no process search
- ❌ Brain Map - no PID search

**Recommendation**: Implement universal search component, reuse across all panels

### **Export Functionality Gaps**
**Severity**: MEDIUM

Limited export capabilities:
- ✅ Hierarchy - can export to text file
- ❌ Logs - can't export filtered logs
- ❌ Process list - can't export to CSV
- ❌ Brain Map - can't screenshot
- ❌ Hier-View - can't export code structure

**Recommendation**: Add "Export" button to all major panels

### **Visual Feedback Gaps**
**Severity**: MEDIUM

Missing visual indicators:
- ❌ No loading spinners (hierarchy capture, scan running)
- ❌ No progress bars (file loading, export)
- ❌ No status bar (current file, line/col, file size)
- ❌ No modified indicators (unsaved changes)
- ❌ No tooltips on many buttons

**Recommendation**: Add status bar, loading indicators, tooltips

---

## Priority Recommendations

### **🔥 CRITICAL (Do First)**

1. **Unify Config Systems**
   - Investigate tools/tabs/settings_tab.py
   - Create unified config backend
   - Ensure both UIs use same data source

2. **Add Syntax Highlighting to Editor**
   - Use pygments or custom lexer
   - Make theme configurable
   - Add syntax config to Editor Settings tab

3. **Add Universal Search**
   - Create reusable search widget
   - Add to: Project Tree, Logs, Hierarchy, Hier-View, Process Monitor

### **⚠️ HIGH (Do Soon)**

4. **Add Missing Config UI Tabs**
   - Editor Settings
   - Logging Settings
   - Security Scan Settings

5. **Add Edit Menu**
   - Undo/Redo
   - Find/Replace
   - Go to Line

6. **Add Process Search to Monitor Tab**
   - Search box above hierarchy tree
   - Filter by PID, name, category

### **📋 MEDIUM (Enhancement)**

7. **Add Export to All Panels**
   - Logs → filtered export
   - Process list → CSV
   - Brain Map → PNG screenshot

8. **Add Status Bar to Main Window**
   - Current file, line/col
   - Process count, refresh rate
   - Memory usage

9. **Add Help Menu**
   - Documentation
   - Keyboard shortcuts reference
   - About dialog

### **💡 LOW (Nice to Have)**

10. **Add Recent Files**
    - Recent files dropdown in File menu
    - Recent files in Project Tree

11. **Add Bookmarks**
    - Bookmark frequently used files/dirs
    - Bookmarks panel or dropdown

12. **Add Multi-tab Editor**
    - Edit multiple files simultaneously
    - Tab bar with close buttons

---

## Config Schema Gaps

**File**: `config_schema.py`, `monitor_config.json`

### **Missing Config Sections**:

1. **editor** (partially exists):
   ```json
   "editor": {
     "font": {...},          // ✅ EXISTS
     "behavior": {...},      // ✅ EXISTS
     "limits": {...},        // ✅ EXISTS
     "syntax": {             // ❌ MISSING UI
       "theme": "vscode_dark",
       "enable_highlighting": true
     }
   }
   ```

2. **logging** (exists, no UI):
   ```json
   "logging": {
     "retention_days": 30,
     "max_log_size_mb": 100,
     "auto_cleanup": true,
     "levels": {...},
     "rotation": {...}
   }
   ```

3. **keybindings** (COMPLETELY MISSING):
   ```json
   "keybindings": {
     "save": "Ctrl+S",
     "find": "Ctrl+F",
     "freeze": "Ctrl+Alt+F",
     "refresh": "F5"
   }
   ```

4. **network** (COMPLETELY MISSING):
   ```json
   "network": {
     "proxy": null,
     "timeout": 30,
     "max_connections": 100
   }
   ```

5. **hierarchy_analyzer** (hardcoded, should be configurable):
   ```json
   "hierarchy_analyzer": {
     "stem_min_depth": 1,
     "stem_max_depth": 5,
     "stem_min_children": 2,
     "dominance_weights": {
       "children": 10,
       "depth": -2,
       "cpu": 1,
       "network": 5,
       "connections": 8
     }
   }
   ```

---

## Summary Statistics

### **Panel Inventory**:
- **Left Panel**: 1 (Project Tree)
- **Right Panel**: 2 tabs (Logs, Monitor)
- **Center Notebook**: 5 tabs (Hier-View, Editor, CLI, Monitor, Brain Map)
- **Config Popup**: 8 tabs (Themes, Hier-Colors, Right-Click, Priority, GUI, Brain Map, Process Monitor, Layout)
- **Tools Popup**: 3 tabs (Default Tools, Local Scripts, Security Manifest)

### **Gap Counts**:
- **Total Gaps Identified**: 87
- **Critical**: 12
- **High**: 25
- **Medium**: 32
- **Low**: 18

### **Missing Features by Category**:
- **Search**: 8 widgets without search
- **Export**: 5 widgets without export
- **Config UI**: 7 config sections without UI tabs
- **Menus**: 3 entire menus missing (Edit, View, Help)
- **Visual Feedback**: 6 types of indicators missing

---

## Next Steps

1. **Read tools/tabs/settings_tab/settings_tab.py** to understand duplicate config system
2. **Create unified config architecture** (config_manager.py as single source)
3. **Add critical missing features** (syntax highlighting, universal search)
4. **Add missing config UI tabs** (Editor, Logging, Security)
5. **Add missing menus** (Edit, View, Help)
6. **Implement search across all panels**
7. **Add status bar to main window**
8. **User testing** to validate priority of recommendations

