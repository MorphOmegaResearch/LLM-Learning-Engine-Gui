# Backup System Integration Patch
**Adding Backup Button to grep_flight Grep Tab**

---

## Files Created

1. **backup_system.py** - Complete backup management system ✅
   - `BackupManager` class for file operations
   - `BackupConfirmationDialog` for user interaction
   - `show_backup_dialog` main entry point

---

## Integration Steps

### Step 1: Import backup_system in grep_flight_v2.py

**Location:** grep_flight_v2.py, after line 49 (after other imports)

```python
# Import backup system
try:
    from backup_system import show_backup_dialog
    BACKUP_SYSTEM_AVAILABLE = True
except ImportError as e:
    print(f"Backup system not available: {e}")
    BACKUP_SYSTEM_AVAILABLE = False
    show_backup_dialog = None
```

---

### Step 2: Add Backup Button to Grep Tab

**Location:** grep_flight_v2.py, line ~1117 (BEFORE the Scope button row)

**Current Code (line 1118-1130):**
```python
        scope_btn = tk.Button(
            controls_row,
            text="🔭 Scope",
            command=self._launch_scope_analyzer,
            bg='#1f1f1f',
            fg=self.config.FG_COLOR,
            relief=tk.RAISED,
            bd=1,
            width=10,
            height=1
        )
        scope_btn.pack(side=tk.RIGHT, padx=(4, 0))
        self._create_tooltip_simple(scope_btn, "Launch Scope Analyzer")
```

**NEW CODE TO ADD (insert ABOVE scope_btn):**
```python
        # ============================================================
        # BACKUP BUTTON ROW (above Scope and Add/Swap buttons)
        # ============================================================
        backup_row = tk.Frame(container, bg=self.config.BG_COLOR)
        backup_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        backup_btn = tk.Button(
            backup_row,
            text="📦 Backup Target",
            command=self._backup_current_target,
            bg='#d67e00',
            fg='white',
            relief=tk.RAISED,
            bd=1,
            width=15,
            height=1,
            font=('Arial', 9, 'bold')
        )
        backup_btn.pack(side=tk.LEFT, padx=(0, 4))
        self._create_tooltip_simple(backup_btn, "Backup the current target file")

        # Info label showing current target
        self.backup_target_label = tk.Label(
            backup_row,
            text="No target set",
            bg=self.config.BG_COLOR,
            fg='#888888',
            font=('Monospace', 8),
            anchor=tk.W
        )
        self.backup_target_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # ============================================================
```

---

### Step 3: Add Method to Handle Backup Button Click

**Location:** grep_flight_v2.py, add new method (good place: near other action methods around line 2200)

```python
    def _backup_current_target(self):
        """Backup the current target file"""
        if not BACKUP_SYSTEM_AVAILABLE:
            messagebox.showwarning(
                "Backup Not Available",
                "Backup system module not found.\n\n"
                "Ensure backup_system.py is in the grep_flight_v0_2b directory."
            )
            return

        # Get current target from target_var
        target = self.target_var.get().strip()

        if not target:
            messagebox.showwarning(
                "No Target",
                "No target file set.\n\n"
                "Please set a target using target.sh or the Browse button first."
            )
            return

        # Check if target is a file (not directory)
        if not os.path.isfile(target):
            # Try to get filename from pattern (if target is directory and pattern is filename)
            pattern = self.pattern_var.get().strip()
            if pattern and not os.path.isabs(pattern):
                # Pattern might be a filename
                potential_file = os.path.join(target, pattern)
                if os.path.isfile(potential_file):
                    target = potential_file
                else:
                    messagebox.showwarning(
                        "Not a File",
                        f"Target is not a file:\n{target}\n\n"
                        "Please target a specific file, not a directory."
                    )
                    return
            else:
                messagebox.showwarning(
                    "Not a File",
                    f"Target is not a file:\n{target}\n\n"
                    "Backup works with files only."
                )
                return

        # Show backup dialog
        show_backup_dialog(
            parent=self,
            target_path=target,
            engine=self.engine,
            add_traceback_func=self._add_traceback
        )
```

---

### Step 4: Update Backup Label When Target Changes

**Location:** grep_flight_v2.py, in the IPC handler where target is set (around line 576-625)

**Find this section (around line 617-625):**
```python
                self.target_var.set(parent_dir)
                self.engine.set_target(parent_dir)
                self.engine.log_debug(f"[TARGET_VAR] Set to parent dir: {parent_dir}", "DEBUG")

                # Inject filename into input line (Pattern)
                self.pattern_var.set(filename)
                self.engine.log_debug(f"[PATTERN_VAR] Set to filename: {filename}", "DEBUG")

                self.status_var.set(f"✅ Target: {path_obj.parent.name} | File: {filename}")
```

**ADD after this section:**
```python
                # Update backup label
                if hasattr(self, 'backup_target_label'):
                    self.backup_target_label.config(
                        text=f"📄 {filename}",
                        fg='#4ec9b0'
                    )
```

**Also add for directory targets (around line 610):**
```python
                if os.path.isdir(target_path):
                    # It's a directory: Lock target to it
                    self.target_var.set(target_path)
                    self.engine.set_target(target_path)
                    self.status_var.set(f"✅ Target (folder): {path_obj.name}")
                    self.engine.log_debug(f"[TARGET_VAR] Set to directory: {target_path}", "DEBUG")

                    # Update backup label
                    if hasattr(self, 'backup_target_label'):
                        self.backup_target_label.config(
                            text=f"📁 {path_obj.name} (folder - select specific file)",
                            fg='#888888'
                        )
```

---

## Visual Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Grep Tab                                                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Target: [__________________] [Browse] [📜]                 │
│  Pattern: [______________] [📜] [⚡]                         │
│                                                              │
│  Grep Tools: [G1] [G2] [G3] [G4] [G5]                       │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │ [W1] [W2] [W3] [W4] [W5] [W6] [W7] [W8]           │     │
│  │                                                     │     │
│  │ [📦 Backup Target] 📄 chat_backend.py  ◄── NEW!   │     │
│  │                                                     │     │
│  │ [🔭 Scope] [ [+] Add/Swap ] [⚙️]                  │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  Results: [results text area...]                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Usage Flow

### Example 1: Backup via target.sh

1. User runs: `./target.sh /path/to/important_file.py`
2. grep_flight receives `SET_TARGET` IPC message
3. Target set to parent directory
4. Pattern set to filename
5. **Backup label updates:** `📄 important_file.py`
6. User clicks **[📦 Backup Target]**
7. Backup dialog appears:
   ```
   ┌──────────────────────────────────────┐
   │  📦 Backup Target File               │
   ├──────────────────────────────────────┤
   │                                       │
   │  Target file resolved from target    │
   │  system:                              │
   │                                       │
   │  ┌─────────────────────────────────┐ │
   │  │ 📄 important_file.py            │ │
   │  │ 📁 /path/to                     │ │
   │  └─────────────────────────────────┘ │
   │                                       │
   │  Backup destination directory:       │
   │  [Same directory] /path/to [Browse] │
   │                                       │
   │  [Yes - Backup Now] [No - Cancel]   │
   └──────────────────────────────────────┘
   ```
8. User clicks **[Yes - Backup Now]**
9. File copied: `important_file_backup_20260116_235959.py`
10. Traceback shows:
    ```
    ✅ BACKUP SUCCESSFUL
       Source: important_file.py
       Backup: important_file_backup_20260116_235959.py
       Location: /path/to
       Time: 2026-01-16 23:59:59
    ```

### Example 2: Backup with Custom Location

1. User clicks **[📦 Backup Target]**
2. Dialog appears with current target
3. User clicks **[Browse...]**
4. Selects different directory: `/home/commander/backups/`
5. Clicks **[Yes - Backup Now]**
6. File backed up to: `/home/commander/backups/important_file_backup_20260116_235959.py`

---

## Testing Checklist

- [ ] Backup button appears above Scope button
- [ ] Backup label updates when target.sh sets a file
- [ ] Clicking backup with no target shows warning
- [ ] Clicking backup with directory target shows warning
- [ ] Backup dialog shows correct target name
- [ ] Default directory is same as source file
- [ ] Browse button works and updates destination
- [ ] Clicking "Yes" creates backup with timestamp
- [ ] Backup file has correct format: `name_backup_YYYYMMDD_HHMMSS.ext`
- [ ] Original file is unchanged
- [ ] Traceback shows backup success message
- [ ] Traceback shows backup failure if error occurs
- [ ] Success dialog shows after backup completes

---

## Future Enhancements

1. **Backup History**
   - Track all backups in `.docv2_workspace/backup_history.json`
   - Show list of backups for current file
   - Quick restore from backup

2. **Task Integration**
   - Link backups to task.json
   - Auto-backup when task starts
   - Track backups per task

3. **Restore Point Integration**
   - Create restore points with metadata
   - Auto-trigger based on conditions
   - One-click restore to previous state

4. **Git Integration** (if in git repo)
   - Offer git commit before backup
   - Show git diff
   - Create git tag for backup point

---

## Manual Application Instructions

1. **Copy backup_system.py** to grep_flight_v0_2b directory ✅
2. **Edit grep_flight_v2.py:**
   - Add import (Step 1)
   - Add backup button row (Step 2)
   - Add `_backup_current_target()` method (Step 3)
   - Add backup label updates (Step 4)
3. **Test** with target.sh
4. **Verify** traceback logging works

---

## Quick Apply (for testing)

If you want to test quickly, you can apply these changes manually or I can create a complete patched version of grep_flight_v2.py with all integrations.

Ready to integrate!
