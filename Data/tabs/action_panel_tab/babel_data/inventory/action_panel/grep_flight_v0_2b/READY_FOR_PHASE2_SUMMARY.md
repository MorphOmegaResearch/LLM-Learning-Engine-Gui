# Ready for Phase 2 - Simplified Integration Approach
**Created:** 2026-01-17 14:02
**User Break:** 30 minutes (~14:30 return)
**Status:** Plan revised, ready to proceed

---

## 🎯 Key Changes Based on Your Feedback

### ✅ What We're Keeping Simple:
1. **Use stable.json for "main branch"** - No new /versions/main_branch/ directory
2. **Provisions not full copies** - Only working files, not entire directory structures
3. **Integrate existing systems** - Use backup_manifest, stash_script, [Files] tab
4. **Milestone backups** - Store in main_dev/milestones/, not full version copies

### 🔧 What We're Fixing:
1. **[Browse...] button** - Will propagate context to grep_flight
2. **Context toggles** - Current Version | Main/Stable | Shared Projects
3. **Backup manifest integration** - Show as "Provisions" (working files)
4. **File lineage** - [Profile] button showing history/context

### 🆕 What We're Adding:
1. **stash_script controls** - In grep_flight [Inventory] > [Stash]
2. **[Profile] button** - Per-file history popup
3. **Target context propagation** - Auto-populate tasks from grep_flight target
4. **Provision display** - grep_flight [Inventory] shows working files from backups

---

## 📋 Revised Phase 2 Tasks (Next Session)

### Priority 1: Context Propagation (30 min)
- [ ] Fix [Browse...] button in warrior_gui
  - Set project via workspace_manager
  - Propagate to grep_flight if connected
  - Refresh UI and log

- [ ] Add context toggles to warrior_gui [Inventory]
  - Radio buttons: Current | Main/Stable | Shared
  - Route plans/tasks based on selection

### Priority 2: Provisions Display (30 min)
- [ ] Create [Provisions] sub-tab in grep_flight [Inventory]
  - Read backup_manifest.json latest 20 entries
  - Display with buttons: [Open] [Target] [Profile] [Stash]

- [ ] Implement [Profile] button popup
  - Show backup history
  - Show target context history
  - Show associated tasks
  - Show stash status

### Priority 3: Stash Integration (20 min)
- [ ] Create [Stash] sub-tab in grep_flight [Inventory]
  - Button: Stash Current Target
  - List: Show stashed files
  - Button per file: Unstash, Delete

---

## 🗂️ Directory Structure (Simplified)

```
Repository Root
├── .docv2_workspace/           # NEW repo-level workspace
│   ├── main_dev/
│   │   ├── milestones/         # Milestone backups (not full copies)
│   │   ├── plans/              # Shared planning docs
│   │   └── diffs/              # Cross-version diffs
│   │
│   └── projects/
│       ├── buisness/           # Business PROVISIONS only
│       │   └── {name}/
│       │       ├── inventory/  # Working files
│       │       └── knowledge/  # ag_forge KB
│       └── app_dev/            # App PROVISIONS only
│
└── versions/
    └── {stable_version}/       # From stable.json (current default)
        ├── .docv2_workspace/
        └── Modules/
```

**Key:** Provisions = Working files being tracked, NOT full directory copies

---

## 🔗 Integration Map

```
grep_flight target context
    ↓
warrior_gui (via app_ref)
    ↓
Task creation (auto-populate)
    ↓
Profile view (file lineage)

backup_manifest.json
    ↓
[Provisions] display
    ↓
[Profile] button (history)
    ↓
stash_script (quick access)

stable.json (current_stable_version)
    ↓
Context toggle "Main/Stable"
    ↓
Route plans to main_dev/
```

---

## 📊 What's Working vs What's Next

### ✅ Working Now:
- workspace_manager with repo-level support
- Backup system tracking working files
- Target context in grep_flight traceback
- stash_script for file shifting
- [Files] tab with directory listing

### 🔜 Next (After Break):
- Context propagation from Browse button
- Toggle between Current/Main/Shared contexts
- Provisions display from backup manifest
- Profile button for file lineage
- Stash controls in grep_flight

---

## 📝 Files to Touch (Next Session)

1. **warrior_gui.py** (already backed up)
   - Fix Browse button context propagation
   - Add context toggle UI in [Inventory] tab header
   - Update path routing based on toggle

2. **grep_flight_v2.py** (milestone backup exists)
   - Add [Inventory] tab with 3 sub-tabs:
     - [Provisions] - From backup manifest
     - [Stash] - stash_script controls
     - [Projects] - Shared provisions
   - Add [Profile] button functionality
   - Integrate stash_script

---

## ⏱️ Time Estimates

### Compact Session (~1-1.5 hours):
- Context propagation fix: 20 min
- Context toggles: 25 min
- Provisions display: 30 min
- Profile button: 20 min
- Stash controls: 15 min
- Testing: 15 min

**Total:** ~2 hours for full Phase 2

---

## 🎁 End Goal Reminder

**Complete Packages** with:
- Milestone backups (historical states)
- Provisions (current working files)
- Knowledge bases (ag_forge)
- Templates (reusable)
- Linear application workflow

**NOT:** Massive directory duplication

---

## 📄 Documentation Ready:
- ✅ IMPLEMENTATION_PLAN_REVISED.md
- ✅ WORKSPACE_MANAGER_AUDIT.md
- ✅ SESSION_NOTES_PHASE1_20260117.md
- ✅ PHASE1_COMPLETE_SUMMARY.md
- ✅ READY_FOR_PHASE2_SUMMARY.md (this file)

---

**Status:** Ready to proceed when you return!
**Estimated Start:** ~14:30
**Next Task:** Fix Browse button context propagation
**Have a good break!** ☕🍽️
