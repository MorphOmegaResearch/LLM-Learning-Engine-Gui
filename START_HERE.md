# 🚀 Quick Start for AI Assistants

**Copy/paste this into a new Claude session to load project context:**

---

## Project Context Initialization

I'm working on the **OpenCode Trainer** project located at:
```
/home/commander/Desktop/Trainer
```

**GitHub Repository:**
```
https://github.com/TravelingMerchant-glitch/LLM-Learning-Engine-Gui
```

**Please read these files first for full context:**
1. `ai_context.md` - Complete project overview and guidelines
2. `project_manifest.yaml` - System architecture and component registry

**Check current development status:**
- `extras/Plans/` - Review latest plan files for active work

---

## Quick Alternative

If short on time, just say:

```
OpenCode Trainer project at /home/commander/Desktop/Trainer
Read ai_context.md for context
```

---

## What You Should Know After Reading

- System type and version
- Active vs legacy code locations
- Component architecture
- Current development priorities

---

## Common Tasks

```bash
# View project structure
cat ai_context.md

# Check component registry
cat project_manifest.yaml

# Browse development plans
ls extras/Plans/

# Verify file tags
python3 tools/context_guard.py --report-only
```

---

## Git Workflow (Local)

Branches
- `main`: stable, runnable UI.
- `dev`: active development (features/fixes).
- `docs/blueprint-v2`: documentation updates for Blueprint v2.

Basics
```bash
# Ensure repo is initialized
git status

# Create and switch to docs branch for blueprint updates
git checkout -b docs/blueprint-v2

# Stage and commit changes
git add extras/blueprints/Trainer_Blue_Print_v2.0.txt \
        Data/tabs/settings_tab/settings_tab.py \
        Data/tabs/custom_code_tab/sub_tabs/projects_interface_tab.py \
        Data/tabs/custom_code_tab/sub_tabs/chat_interface_tab.py \
        Data/tabs/custom_code_tab/projects_manager.py \
        Data/config.py \
        START_HERE.md
git commit -m "docs: add Blueprint v2, update Help and START_HERE"

# Merge back to dev (optional, local)
git checkout dev
git merge --no-ff docs/blueprint-v2 -m "merge: Blueprint v2 docs into dev"

# Keep working on dev or open a PR if remote is configured
```

Blueprints & Plans
- Latest blueprint: `extras/blueprints/Trainer_Blue_Print_v2.0.txt`
- Research archives: `extras/Research/`
- Historical blueprints: `extras/blueprints/`

Common update batch (current work)
- Per‑project working_dir lifecycle (create/auto‑switch)
- Unified ToDo manager (Main/Project toggle)
- Plans & Tests categories + Plan template dialog
- OS Trash integration + window size persistence
- UI hardening & indicator fixes

Commit style
- Prefix: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`
- Scope: short context, e.g., `ui/temp`, `settings/todo`.

---

**After loading context, you can help with:**
- Feature development
- Bug fixes
- Code reviews
- Documentation updates
- Architecture questions
