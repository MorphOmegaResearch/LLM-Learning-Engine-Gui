# 🔒 Backup Protocol - Mandatory Before Implementation

**CRITICAL REMINDER:** Always backup files before modifications and after milestone testing.

---

## Before Starting Any Implementation Task

### 1. Identify Files to Modify
Review the task/phase to determine which files will be edited.

### 2. Create Backups
For each file, create a timestamped backup:

**Format:** `{filename}_backup_{YYYYMMDD_HHMMSS}.{ext}`

**Example:**
```bash
workspace_manager_backup_20260117_140530.py
warrior_gui_backup_20260117_140530.py
grep_flight_v2_backup_20260117_140530.py
```

### 3. Update backup_manifest.json
Add each backup to the manifest using this structure:

```json
{
  "/absolute/path/to/original_file.py": [
    {
      "backup_path": "/absolute/path/to/backup_file.py",
      "timestamp": "2026-01-17T14:05:30.123456",
      "backup_name": "backup_file_backup_20260117_140530.py"
    }
  ]
}
```

### 4. Verify in Restore Menu
Launch grep_flight and check that the backup appears in the restore dropdown.

---

## After Milestone Testing (Success)

### 1. Create Post-Testing Backup
Mark the tested, working state:

**Format:** `{filename}_milestone{N}_tested_{YYYYMMDD_HHMMSS}.{ext}`

**Example:**
```bash
grep_flight_v2_milestone2_tested_20260117_180000.py
```

### 2. Update Milestones.md
Document the completion:

```xml
</Milestone_2>:
- {Feature Description}
- Backup Created After Testing: {Y}
- {/path/to/backup_milestone2_tested_20260117_180000.py}
<Milestone_2/>. {Complete}
```

### 3. Document Revert Instructions
Create clear steps for reverting if issues arise later:

```markdown
## Revert Procedure - Milestone 2

If cascading failures occur:

1. Stop all running processes (warrior_gui, grep_flight)
2. Open grep_flight in standalone mode
3. Use [🔄 Restore] button for each file:
   - workspace_manager.py → Select "milestone2_tested" backup
   - warrior_gui.py → Select "milestone2_tested" backup
   - grep_flight_v2.py → Select "milestone2_tested" backup
4. Restart systems
5. Verify functionality

**Alternative:** Use pre-implementation backups to return to Milestone 1 state.
```

---

## Backup Checklist Template

```markdown
### Pre-Implementation Backups (Milestone 2)
- [ ] workspace_manager.py → workspace_manager_backup_YYYYMMDD_HHMMSS.py
- [ ] warrior_gui.py → warrior_gui_backup_YYYYMMDD_HHMMSS.py
- [ ] grep_flight_v2.py → grep_flight_v2_backup_YYYYMMDD_HHMMSS.py
- [ ] planner_wizard.py → planner_wizard_backup_YYYYMMDD_HHMMSS.py
- [ ] code_alchemist.py → code_alchemist_backup_YYYYMMDD_HHMMSS.py
- [ ] backup_manifest.json updated ✅
- [ ] Verified in restore menu ✅

### Post-Testing Backups (Milestone 2)
- [ ] All modified files → {filename}_milestone2_tested_YYYYMMDD_HHMMSS.py
- [ ] backup_manifest.json updated ✅
- [ ] Milestones.md updated ✅
- [ ] Revert instructions documented ✅
```

---

## Emergency Restore Procedure

**If system becomes unstable during implementation:**

1. **Immediate Stop:** Close all Warrior Flow applications
2. **Launch Standalone grep_flight:**
   ```bash
   cd /path/to/grep_flight_v0_2b/
   python3 grep_flight_v2.py --gui
   ```
3. **Access Restore Menu:** Click 🔄 Restore button
4. **Select Pre-Implementation Backup:** Choose the backup created BEFORE the current phase
5. **Restore All Modified Files:** One by one from the restore dropdown
6. **Verify Restore:**
   - Check file timestamps
   - Open files to verify content
   - Test basic functionality
7. **Document Issue:**
   - Note which change caused the failure
   - Add to session notes
   - Review before re-attempting

---

## Backup Storage Best Practices

### Location
All backups should remain in the same directory as the original file for easy discovery.

### Retention
- Keep pre-implementation backups for entire milestone
- Keep post-testing backups indefinitely (milestone markers)
- Clean up intermediate backups after milestone complete
- Keep at least last 20 backups per file (grep_flight limit)

### Naming Convention
```
{original_filename}_{backup_type}_{timestamp}.{ext}

backup_type options:
- backup         (general backup)
- milestone{N}   (milestone marker)
- tested         (post-test marker)
- Bug            (auto-created by restore system)
```

---

**Remember:** A backup takes 1 second. Recovery from data loss takes hours. Always backup first!
