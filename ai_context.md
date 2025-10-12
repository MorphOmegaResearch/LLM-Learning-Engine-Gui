# 🧭 OpenCode Trainer — AI Context Initialization

- **System Mode:** GUI (Tkinter)
- **Active Version:** v1.9f — Mode Integration & UX Improvements
- **Entry Point:** `Data/interactive_trainer_gui.py`
- **Legacy Systems:** CLI/TUI version manager (archived in `/Artifacts/` and `/experiments/`)
- **Do Not Use:** `/version` or TUI commands — superseded by GUI build

---

## 📋 Quick Overview

OpenCode Trainer is a **full GUI-based LLM training and evaluation framework**.
It integrates **37 OpenCode v1.2 subsystems** with mode control (Standard, Fast, Smart, Think).

**Key Features:**
- 4-tab GUI: Models, Training, Custom Code (Chat), Evaluation
- LoRA fine-tuning with Unsloth support (CPU/GPU)
- Comprehensive evaluation framework with test suites
- Tool management system (20+ tools, custom profiles)
- Lineage tracking and model ancestry
- Real-time skill tracking and analytics

**Legacy Notice:**
Files in `/Artifacts/` and `experiments/v1.2old_sometoollogic/` are **historical records** for prior TUI implementations. They are **NOT active code** and should **NOT be executed or modified**.

---

## 🏗️ Architecture at a Glance

```
Active System (GUI v1.9f)
├── Data/
│   ├── interactive_trainer_gui.py   ← Main entry point
│   ├── training_engine.py           ← Training pipeline
│   ├── evaluation_engine.py         ← Benchmarking
│   ├── config.py                    ← Central configuration
│   └── tabs/                        ← UI components
│       ├── models_tab/              ← Model management
│       ├── training_tab/            ← Training interface
│       └── custom_code_tab/         ← Chat & evaluation
│           ├── lineage_tracker.py   ← Model ancestry
│           ├── tool_call_logger.py  ← Data collection
│           └── sub_tabs/            ← Mode, Advanced, Tools
├── Training_Data-Sets/              ← Data & test suites
├── extras/                          ← Documentation & plans
├── Models/                          ← Trained models (gitignored)
└── exports/                         ← GGUF exports (gitignored)

Legacy Systems (ARCHIVED)
├── Data/tabs/custom_code_tab/Artifacts/          ← Old TUI blueprints
└── Data/tabs/custom_code_tab/experiments/v1.2old_sometoollogic/
```

---

## 🔍 For AI Agents / Assistants

### Before Any Code Changes:

1. **Read this file** (`ai_context.md`)
2. **Read** `project_manifest.yaml` for component registry
3. **Check** `extras/blueprints/` for latest system architecture
4. **Verify** you're working in active components (not `/Artifacts/`)

### Quick Validation Check:

```python
from pathlib import Path
import yaml

# Load manifest
manifest = yaml.safe_load(Path("project_manifest.yaml").read_text())

print(f"Active System: {manifest['system_mode']}")
print(f"Version: {manifest['active_version']}")
print(f"Entry Point: {manifest['entry_point']}")

# Verify file is in active components
def is_active_component(filepath: str) -> bool:
    active = manifest['components']
    for category in active.values():
        if any(comp in filepath for comp in category):
            return True
    return False
```

### Code Modification Policy:

✅ **SAFE TO MODIFY:**
- Files under `Data/tabs/` (except `/Artifacts/` and `/experiments/`)
- `Data/*.py` core files
- `Training_Data-Sets/` (data and configs)
- Documentation files

❌ **DO NOT MODIFY:**
- `Data/tabs/custom_code_tab/Artifacts/` (archived)
- `Data/tabs/custom_code_tab/experiments/v1.2old_sometoollogic/` (archived)
- Anything marked with `[SYSTEM: LEGACY_TUI | STATUS: ARCHIVE]` header

---

## 📂 Key Configuration Files

| File | Purpose |
|------|---------|
| `mode_settings.json` | Mode parameters (Standard/Fast/Smart/Think) |
| `advanced_settings.json` | 37 OpenCode systems, 252 settings |
| `tool_settings.json` | Tool enable/disable states |
| `custom_code_settings.json` | Basic UI settings |

---

## 🚀 Development Workflow

### For New Features:
1. Check `extras/Plans/12oct_25_plan.txt` for planned work
2. Follow phase structure (Phase 1: Tools, Phase 2: Eval, Phase 3: Gamification)
3. Update relevant blueprint in `extras/blueprints/`
4. Test changes in GUI before committing

### For Bug Fixes:
1. Identify affected component in `project_manifest.yaml`
2. Check if component has recent changes in git history
3. Verify fix doesn't affect other dependent components
4. Test in both Standard and Smart modes

### For Documentation:
1. Update `README.md` for user-facing changes
2. Update blueprint in `extras/blueprints/` for architecture changes
3. Add notes to `extras/Plans/` for future work

---

## 🔗 Investigation Findings (12 Oct 2025)

Recent investigations documented in `extras/Plans/12oct_25_plan.txt`:

1. ✅ **Training Data Selection** - Manual, can be automated by model Type
2. ✅ **Lineage Tracking** - Fully functional, ready for Evolution events
3. ✅ **Chat Data Pipeline** - Working correctly, model name is primary key
4. ✅ **Tool Profiles** - Can generate training data dynamically (feasible)

---

## 📞 For Help

- **README.md** - Installation and usage guide
- **GITHUB_UPLOAD_GUIDE.md** - Repository management
- **extras/blueprints/** - System architecture details
- **extras/Plans/** - Development roadmap and findings

---

## 🎯 Current Status (v1.9f)

**Completed:**
- ✅ Core training pipeline with LoRA
- ✅ Evaluation framework with test suites
- ✅ Chat interface with 4 modes
- ✅ 37 OpenCode systems integrated
- ✅ Lineage tracking system
- ✅ Tool management with profiles

**In Progress:**
- 🚧 Tool profile unification (Phase 1)
- 🚧 Enhanced evaluation metrics (Phase 2)

**Planned:**
- 📋 Model gamification & evolution (Phase 3)
- 📋 Type-based training selection
- 📋 Profile-based training data generation

---

**Last Updated:** 2025-10-13
**System Version:** 1.9f
**For questions:** Check `project_manifest.yaml` or latest blueprint
