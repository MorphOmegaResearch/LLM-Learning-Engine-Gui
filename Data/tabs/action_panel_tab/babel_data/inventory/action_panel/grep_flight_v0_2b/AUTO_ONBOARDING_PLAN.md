# Safe Auto-Onboarding System - 3-Tier Approval Architecture

## Current Problem
- User manually onboards scripts via custom_scripts.json
- No automatic discovery of scripts in tool_suites
- No safety classification before execution
- Engineer's toolkit launches when user wanted syntax check
- No context awareness of what scripts do

## Solution: 3-Tier Progressive Trust System

---

## Tier 1: Discovery & Profiling (Automatic, Safe)

**What happens:** System automatically discovers and profiles scripts

**Location:** Runs via `onboard_prober.py` orchestrator

**Process:**
1. Scan tool_suites directories for Python scripts
2. Run `onboard_prober.py` on each script
3. Extract:
   - CLI arguments (via --help)
   - Function signatures (via AST)
   - Dependencies (imports)
   - UI components (tkinter detection)
   - Log/print statements
   - File I/O patterns

**Output:** Cached in `.docv2_workspace/prober_cache.json`

**Risk Level:** ZERO - No execution, only static analysis

**Example Profile:**
```json
{
  "target": "/path/to/engineers_toolkit.py",
  "file_hash": "abc123...",
  "cli_schema": {
    "description": "Engineer's Toolkit GUI",
    "flags": [
      {"short": "-p", "long": "--project", "description": "Load project directory"}
    ]
  },
  "plumbing": {
    "ui_components": [
      {"type": "Notebook", "label": "Tools Tab", "line": 42}
    ],
    "logs": [...],
    "function_chains": [...]
  },
  "dependencies": ["tkinter", "black", "ruff"]
}
```

---

## Tier 2: Classification (Automatic with Rules)

**What happens:** System classifies scripts by capabilities and safety

**Location:** New `ScriptClassifier` class

**Classification Categories:**

### A. Capabilities Detection
```python
capabilities = []
if "tkinter" in dependencies:
    capabilities.append("GUI_REQUIRED")
if any(flag for flag in cli_flags if "file" in flag):
    capabilities.append("FILE_IO")
if "argparse" in dependencies or cli_flags:
    capabilities.append("CLI_ARGUMENTS")
if any(log for log in logs if "print" in log or "log" in log):
    capabilities.append("PRODUCES_OUTPUT")
```

### B. Safety Classification
```python
safety_level = "UNKNOWN"

# Check for read-only indicators
safe_keywords = ["check", "lint", "analyze", "scan", "view", "read", "list"]
if any(keyword in description.lower() for keyword in safe_keywords):
    safety_level = "SAFE"  # Green light

# Check for destructive indicators
dangerous_keywords = ["delete", "remove", "modify", "write", "overwrite"]
if any(keyword in description.lower() for keyword in dangerous_keywords):
    safety_level = "DANGEROUS"  # Red light

# Check for GUI (may not work headless)
if "GUI_REQUIRED" in capabilities:
    safety_level = "NEEDS_REVIEW"  # Yellow light
```

### C. Target Recommendation
```python
# What should this script operate on?
if "--file" in cli_flags or "--path" in cli_flags:
    recommended_targets = ["file"]
if "--directory" in cli_flags or "--project" in cli_flags:
    recommended_targets.append("folder")
```

**Output:** Enhanced profile with classification

**Risk Level:** ZERO - Still no execution

---

## Tier 3: User Approval (Interactive)

**What happens:** User reviews and approves scripts

**Location:** New approval UI window

### UI Design (Tkinter Window)

```
┌─────────────────────────────────────────────────────────┐
│  🛡️ Script Approval Center                              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Discovered 5 new scripts in tool_suites:               │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │ [✓] engineers_toolkit.py                       │    │
│  │     Safety: 🟡 NEEDS_REVIEW (Has GUI)          │    │
│  │     Capabilities: GUI_REQUIRED, FILE_IO        │    │
│  │     Description: Engineer's Toolkit GUI...     │    │
│  │     Targets: [folder, project]                 │    │
│  │                                                 │    │
│  │     [ View Profile ] [ Run Once ]              │    │
│  ├────────────────────────────────────────────────┤    │
│  │ [✓] syntax_checker.py                          │    │
│  │     Safety: 🟢 SAFE (Read-only analysis)       │    │
│  │     Capabilities: CLI_ARGUMENTS, PRODUCES_OUT  │    │
│  │     Description: Python syntax validation      │    │
│  │     Targets: [file]                            │    │
│  │                                                 │    │
│  │     [ View Profile ] [ Run Once ]              │    │
│  ├────────────────────────────────────────────────┤    │
│  │ [ ] data_wiper.py                              │    │
│  │     Safety: 🔴 DANGEROUS (Destructive)         │    │
│  │     Capabilities: FILE_IO, WRITE_ACCESS        │    │
│  │     Description: Delete all files matching...  │    │
│  │     Targets: [folder]                          │    │
│  │                                                 │    │
│  │     [ View Profile ] [ Run Once ]              │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  [ Approve Selected (2) ]  [ Approve All Safe ]         │
│  [ Reject All ]            [ Save & Close ]             │
└─────────────────────────────────────────────────────────┘
```

### Approval Actions

1. **View Profile** - Shows full onboard_prober output
2. **Run Once** - Test run with manual confirmation
3. **Approve Selected** - Add to action registry
4. **Approve All Safe** - Auto-approve green-light scripts
5. **Save & Close** - Persist approvals to `approved_scripts.json`

### Approval Storage

```json
{
  "approved_scripts": {
    "/path/to/engineers_toolkit.py": {
      "approved_at": "2026-01-16T23:30:00",
      "approved_by": "commander",
      "file_hash": "abc123...",
      "safety_level": "NEEDS_REVIEW",
      "allowed_targets": ["folder", "project"],
      "requires_confirmation": true,
      "notes": "Approved for project analysis only"
    },
    "/path/to/syntax_checker.py": {
      "approved_at": "2026-01-16T23:30:00",
      "approved_by": "commander",
      "file_hash": "def456...",
      "safety_level": "SAFE",
      "allowed_targets": ["file"],
      "requires_confirmation": false,
      "auto_executable": true
    }
  },
  "rejected_scripts": {
    "/path/to/data_wiper.py": {
      "rejected_at": "2026-01-16T23:30:00",
      "reason": "Too dangerous for auto-execution"
    }
  }
}
```

---

## Integration Flow

### Step 1: Periodic Discovery (Background)
```python
# Runs every 5 minutes or on-demand
orchestrator = ProberOrchestrator("/path/to/Warrior_Flow")
orchestrator.scan_version("current_stable_version")
# New scripts detected and profiled automatically
```

### Step 2: Classification (Immediate)
```python
classifier = ScriptClassifier()
for script_path, profile in new_scripts.items():
    classification = classifier.classify(profile)
    # Adds safety_level, capabilities, target_recommendations
```

### Step 3: Approval UI (On-Demand)
```python
# User triggers via menu: "Tools > Review New Scripts"
# Or: Auto-popup when new scripts detected
approval_ui = ApprovalWindow(new_classified_scripts)
approved = approval_ui.run()  # Returns list of approved scripts

# Register approved scripts
for script in approved:
    action_registry.register_from_approval(script)
```

### Step 4: Action Availability (Automatic)
```python
# When target is set, approved scripts become available
target_context = resolver.resolve("/path/to/file.py", "file")
actions = registry.get_compatible_actions(target_context)
# Returns: ["Syntax Check", "engineers_toolkit", "syntax_checker"]
# Filters by: target_type, file_patterns, safety_level
```

---

## Safety Guarantees

### What CAN'T Execute Without Approval:
- Scripts with `safety_level = "DANGEROUS"`
- Scripts with GUI requirements (may hang headless)
- Scripts not in `approved_scripts.json`
- Scripts whose file hash changed since approval

### What CAN Execute Automatically:
- Scripts with `safety_level = "SAFE"` AND `auto_executable = true`
- Scripts explicitly approved by user
- Built-in actions (syntax check, lint, etc.)

### Re-Approval Triggers:
- Script file modified (hash changed)
- Script moved to different path
- User explicitly revokes approval
- Script dependencies changed

---

## Configuration

### User Settings
```json
{
  "auto_onboarding": {
    "enabled": true,
    "scan_interval_minutes": 5,
    "auto_approve_safe": false,  // Still show UI for safe scripts
    "require_confirmation_gui": true,  // Always confirm GUI scripts
    "scan_paths": [
      "versions/*/Modules/**/*.py",
      "custom_scripts/**/*.py"
    ],
    "ignore_paths": [
      "__pycache__",
      "venv",
      ".git"
    ]
  }
}
```

---

## Example: Engineer's Toolkit Onboarding

### Current Behavior (PROBLEM):
1. User targets `/path/to/chat_backend.py` with target.sh
2. User wants syntax check
3. System launches **engineers_toolkit** (wrong!)
4. GUI pops up, user confused

### New Behavior (SOLUTION):

#### First Time (One-Time Setup):
1. Prober discovers `engineers_toolkit.py`
2. Extracts: "GUI tool for project analysis"
3. Classifies: `NEEDS_REVIEW` (has GUI)
4. User sees approval UI
5. User approves for `target_types=["folder", "project"]`
6. Script registered with metadata

#### Every Time After:
1. User targets `/path/to/chat_backend.py` (file)
2. Context resolver: `type=file, is_python=true`
3. Compatible actions:
   - ✅ "Syntax Check" (file, *.py, SAFE)
   - ✅ "Lint (Ruff)" (file, *.py, SAFE)
   - ❌ "engineers_toolkit" (folder/project only)
4. Default action: "Syntax Check"
5. User sees: "Available: Syntax Check, Lint"
6. **Engineer's toolkit NOT offered** (incompatible target type)

---

## Implementation Priority

### Phase 1: Foundation (Already Done)
- ✅ target_context_system.py
- ✅ Integration patches documented

### Phase 2: Classification (Next)
- [ ] ScriptClassifier class
- [ ] Safety rule engine
- [ ] Capability detection

### Phase 3: Approval UI (After Phase 2)
- [ ] ApprovalWindow GUI
- [ ] approved_scripts.json storage
- [ ] Hash-based change detection

### Phase 4: Integration (Final)
- [ ] Apply INTEGRATION_PATCH.md
- [ ] Connect classifier to action_registry
- [ ] Add "Review New Scripts" menu item

---

## Discussion Points

1. **Approval Frequency**: Show UI every time? Or silent approve safe scripts?
2. **Hash Changes**: Re-approve or auto-update for minor changes?
3. **GUI Detection**: How strict? Some tools work headless with DISPLAY=""
4. **Target Recommendation**: Auto-detect from CLI flags or manual config?
5. **Integration Order**: Apply target context first, then add onboarding? Or reverse?

---

## Questions for You

- Does this 3-tier approach feel right?
- Should safe scripts auto-execute or always ask?
- When should the approval UI appear? (on-demand vs auto-popup)
- How to handle scripts that work with ANY target type?
- Should we integrate with existing tool_suites structure or create new?
