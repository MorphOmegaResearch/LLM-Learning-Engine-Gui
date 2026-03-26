# Manual Integration Guide: scope_flow.py → workflow_profiles.json

## Current State

Your Scope profile in `.docv2_workspace/config/workflow_profiles.json` has:
- ✅ 2 existing actions: Scope Analyzer, Scope Monitor
- 🔲 6 placeholder slots: "[Add Custom]"

## Integration Strategy

You have **two options**:

### Option 1: Fill Placeholder Slots (Recommended)
Replace the 6 "[Add Custom]" placeholders with scope_flow.py variants.

### Option 2: Create New Profile
Create a new "Scope + Flow" profile alongside existing profiles.

---

## Option 1: Fill Placeholders

### Step 1: Open Config File
```bash
nano /home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/.docv2_workspace/config/workflow_profiles.json
```

### Step 2: Replace First Placeholder (Line ~177)

**Replace this:**
```json
{
  "name": "[Add Custom]",
  "type": "placeholder",
  "source": "",
  "target_mode": "auto",
  "output_to": "results",
  "expectations": ""
}
```

**With this (Progressive Analysis):**
```json
{
  "name": "🔬 Progressive Analysis",
  "type": "workflow_suite",
  "source": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "target_mode": "file_required",
  "output_to": "results",
  "expectations": "analysis_report",
  "command": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "args": "--analyze --file={target} --depth=4"
}
```

### Step 3: Replace Second Placeholder

**With this (Quick Fix):**
```json
{
  "name": "⚡ Quick Fix",
  "type": "workflow_suite",
  "source": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "target_mode": "file_required",
  "output_to": "results",
  "expectations": "auto_fix",
  "command": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "args": "--workflow=quick_fix --file={target} --auto"
}
```

### Step 4: Replace Third Placeholder

**With this (Full Analysis):**
```json
{
  "name": "🎯 Full Analysis",
  "type": "workflow_suite",
  "source": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "target_mode": "file_required",
  "output_to": "results",
  "expectations": "comprehensive_report",
  "command": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "args": "--workflow=full_analysis --file={target} --auto"
}
```

### Step 5: Replace Fourth Placeholder

**With this (Tkinter Analysis):**
```json
{
  "name": "🎨 Tkinter Analysis",
  "type": "workflow_suite",
  "source": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "target_mode": "file_required",
  "output_to": "results",
  "expectations": "gui_analysis",
  "command": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "args": "--workflow=tkinter_only --file={target}"
}
```

### Step 6: Replace Fifth Placeholder

**With this (Diff Review GUI):**
```json
{
  "name": "📋 Diff Review GUI",
  "type": "workflow_suite",
  "source": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "target_mode": "file_required",
  "output_to": "diff_queue",
  "expectations": "interactive_review",
  "command": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "args": "--gui-review --file={target}"
}
```

### Step 7: Replace Sixth Placeholder

**With this (Auto-Fix):**
```json
{
  "name": "🔧 Auto-Fix",
  "type": "workflow_suite",
  "source": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "target_mode": "file_required",
  "output_to": "results",
  "expectations": "auto_fix",
  "command": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "args": "--auto-fix --file={target} --backup"
}
```

### Step 8: Update tool_locations Section

Find the `"tool_locations"` section in the Scope profile (around line 226) and **add** these entries:

```json
"tool_locations": {
  "Scope Analyzer": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9u_Monkeys_Toolsv2a/Modules/action_panel/scope/scope.py",
  "Scope Monitor": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9u_Monkeys_Toolsv2a/Modules/action_panel/scope/scope.py",
  "🔬 Progressive Analysis": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "⚡ Quick Fix": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "🎯 Full Analysis": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "🎨 Tkinter Analysis": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "📋 Diff Review GUI": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "🔧 Auto-Fix": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py"
}
```

### Step 9: Update timestamp

Change the `"last_updated"` field to current timestamp:
```json
"last_updated": "2026-01-14T<current-time>"
```

### Step 10: Save and Test

Save the file and reload your panel system.

---

## Option 2: Create New Profile

If you want to keep the current Scope profile clean, add this complete profile:

### Location
`.docv2_workspace/config/workflow_profiles.json`

### Insert After "Scope" Profile

Add this complete profile (before the closing `}` of `"profiles"`):

```json
"Scope_Flow": {
  "workflow_actions": [
    {
      "name": "🔍 Scope Analyzer",
      "type": "debug_suite",
      "source": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/scope.py",
      "target_mode": "auto",
      "output_to": "traceback",
      "expectations": "scope_inspect",
      "command": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/scope.py",
      "args": "--scope"
    },
    {
      "name": "👁️ Scope Monitor",
      "type": "debug_suite",
      "source": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/scope.py",
      "target_mode": "auto",
      "output_to": "traceback",
      "expectations": "scope_monitor",
      "command": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/scope.py",
      "args": "--monitor"
    },
    {
      "name": "🔬 Progressive Analysis",
      "type": "workflow_suite",
      "source": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
      "target_mode": "file_required",
      "output_to": "results",
      "expectations": "analysis_report",
      "command": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
      "args": "--analyze --file={target} --depth=4"
    },
    {
      "name": "⚡ Quick Fix",
      "type": "workflow_suite",
      "source": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
      "target_mode": "file_required",
      "output_to": "results",
      "expectations": "auto_fix",
      "command": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
      "args": "--workflow=quick_fix --file={target} --auto"
    },
    {
      "name": "🎯 Full Analysis",
      "type": "workflow_suite",
      "source": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
      "target_mode": "file_required",
      "output_to": "results",
      "expectations": "comprehensive_report",
      "command": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
      "args": "--workflow=full_analysis --file={target} --auto"
    },
    {
      "name": "🎨 Tkinter Analysis",
      "type": "workflow_suite",
      "source": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
      "target_mode": "file_required",
      "output_to": "results",
      "expectations": "gui_analysis",
      "command": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
      "args": "--workflow=tkinter_only --file={target}"
    },
    {
      "name": "📋 Diff Review GUI",
      "type": "workflow_suite",
      "source": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
      "target_mode": "file_required",
      "output_to": "diff_queue",
      "expectations": "interactive_review",
      "command": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
      "args": "--gui-review --file={target}"
    },
    {
      "name": "🔧 Auto-Fix",
      "type": "workflow_suite",
      "source": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
      "target_mode": "file_required",
      "output_to": "results",
      "expectations": "auto_fix",
      "command": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
      "args": "--auto-fix --file={target} --backup"
    }
  ],
  "last_updated": "2026-01-14T<timestamp>",
  "tool_locations": {
    "🔍 Scope Analyzer": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/scope.py",
    "👁️ Scope Monitor": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/scope.py",
    "🔬 Progressive Analysis": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
    "⚡ Quick Fix": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
    "🎯 Full Analysis": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
    "🎨 Tkinter Analysis": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
    "📋 Diff Review GUI": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
    "🔧 Auto-Fix": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py"
  }
}
```

---

## Understanding the Structure

### Key Fields

**name**: Display name with emoji (shows in UI as button)

**type**:
- `debug_suite` - Diagnostic/inspection tools
- `workflow_suite` - Analysis/fix workflows
- `toolkit` - Engineer toolkit operations
- `builtin` - Core system features

**target_mode**:
- `auto` - No target required
- `file_required` - Needs file path
- `dir_required` - Needs directory path

**output_to**:
- `results` - Show in results panel
- `traceback` - Show in traceback/debug panel
- `diff_queue` - Send to diff review queue
- `pfc+results` - Both panels

**args**: Command line arguments with `{target}` placeholder

### Argument Templating

The system can parse `{target}` and other placeholders:
```json
"args": "--analyze --file={target} --depth={depth}"
```

Your panel system should replace:
- `{target}` → Selected file/dir path
- `{depth}` → User-selected value (if UI provides)

---

## Auto-Onboarding (Future)

When implemented, your system could:

1. **Detect New Tool**
```bash
python3 scope_flow.py --help
```

2. **Parse Available Arguments**
```
--analyze         → Button: "Progressive Analysis"
--workflow=TYPE   → Dropdown: ["quick_fix", "full_analysis", "tkinter_only"]
--gui-review      → Button: "Diff Review GUI"
--auto-fix        → Button: "Auto-Fix"
--organization    → Button: "Project Schema"
```

3. **Auto-Generate Profile Entry**
```json
{
  "name": "Auto-detected: <arg>",
  "args": "--<arg> --file={target}"
}
```

4. **Offer to User**
"Found new tool: scope_flow.py with 8 workflows. Add to Scope profile?"

---

## Testing

After integration, test each action:

### Test Progressive Analysis
```bash
# Manually from CLI:
python3 scope_flow.py --analyze --file=/path/to/test.py --depth=4

# From panel (after integration):
# Select test.py → Click "🔬 Progressive Analysis" button
```

### Test Quick Fix
```bash
# From panel:
# Select file → Click "⚡ Quick Fix" button
# Should auto-fix and show results
```

### Test Diff Review GUI
```bash
# From panel:
# Select file → Click "📋 Diff Review GUI" button
# Should open side-by-side diff window
```

---

## Bonus: Project Schema Action

You can also add the **Project Schema** action if you have space:

```json
{
  "name": "📊 Project Schema",
  "type": "workflow_suite",
  "source": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "target_mode": "dir_required",
  "output_to": "results",
  "expectations": "organization_report",
  "command": "/home/commander/3_Inventory/Warrior_Flow/versions/Warrior_Flow_v0_9w_Monkey_Buisness_v1/Modules/action_panel/scope/variants/scope_flow.py",
  "args": "--organization --dir={target}"
}
```

This requires `dir_required` mode - user selects a directory instead of a file.

---

## Summary

**What You Get After Integration:**

1. **Original Scope Tools** (unchanged)
   - 🔍 Scope Analyzer
   - 👁️ Scope Monitor

2. **New Flow Tools** (6 new actions)
   - 🔬 Progressive Analysis
   - ⚡ Quick Fix
   - 🎯 Full Analysis
   - 🎨 Tkinter Analysis
   - 📋 Diff Review GUI
   - 🔧 Auto-Fix

3. **Complete Workflow**
   - Click file → Run analysis
   - See results → Click fix
   - Review changes in GUI
   - Accept/reject → Done

The variants directory structure supports future additions without touching core scope.py!
