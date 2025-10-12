# Trainer Folder Structure - Blueprint

## 📁 Complete Folder Layout

```
/Trainer/
│
├── TRAIN.desktop                           # Double-click launcher for training
├── TEST.desktop                            # Double-click launcher for testing
├── STRUCTURE.md                            # This file - complete blueprint
├── README.md                               # User-facing documentation
│
├── Models/                                 # All trained models
│   ├── training_Qwen-Custom_latest/        # Latest trained model
│   │   ├── checkpoints/                    # Training checkpoints
│   │   ├── logs/                           # Training logs
│   │   ├── exports/                        # Export formats (GGUF, etc.)
│   │   ├── config.json                     # Model configuration
│   │   ├── adapter_config.json             # LoRA adapter config
│   │   └── adapter_model.safetensors       # LoRA weights
│   │
│   └── training_<ModelName>_<timestamp>/   # Historical models
│
├── Training_Data-Sets/                     # All training datasets
│   │
│   ├── Tools/                              # OpenCode tool usage training
│   │   ├── file_operations.jsonl           # File read/write/edit examples
│   │   ├── search_operations.jsonl         # Search and grep examples
│   │   ├── git_operations.jsonl            # Git command examples
│   │   ├── system_operations.jsonl         # System info, process examples
│   │   └── error_recovery.jsonl            # Error handling examples
│   │
│   ├── App_Development/                    # Application development patterns
│   │   ├── api_design.jsonl                # API endpoint design
│   │   ├── database_queries.jsonl          # SQL and ORM examples
│   │   ├── testing_patterns.jsonl          # Unit/integration test writing
│   │   └── deployment.jsonl                # Deploy and CI/CD examples
│   │
│   ├── Coding/                             # General programming tasks
│   │   ├── algorithms.jsonl                # Algorithm implementation
│   │   ├── data_structures.jsonl           # Data structure usage
│   │   ├── refactoring.jsonl               # Code refactoring examples
│   │   └── debugging.jsonl                 # Debug workflow examples
│   │
│   └── Semantic_States/                    # Context-aware responses
│       ├── conversation_flow.jsonl         # Multi-turn conversations
│       ├── intent_detection.jsonl          # Detecting user intent
│       ├── clarification.jsonl             # Asking for clarification
│       └── context_retention.jsonl         # Remembering conversation context
│
└── Data/                                   # Scripts and utilities
    ├── config.py                           # Central configuration (paths, settings)
    ├── interactive_ui.py                   # UI library (menus, buttons, keyboard nav)
    │
    ├── tool_trainer.py                     # Main trainer orchestrator
    ├── training_data_generator.py          # Generate training examples
    ├── session_manager.py                  # Ollama API manager
    │
    ├── train_with_unsloth.py               # Unsloth fine-tuning script
    ├── test_trained_model.py               # Test trained models
    │
    ├── export_for_finetuning.py            # Export to multiple formats
    ├── reorganize.py                       # Folder reorganization script
    │
    ├── start_training.sh                   # Training launcher script
    ├── start_unsloth_training.sh           # Unsloth launcher script
    │
    └── exports/                            # Export cache
        ├── Modelfile_*                     # Ollama Modelfiles
        ├── training_data.jsonl             # JSONL format
        ├── hf_training_data.json           # Hugging Face format
        └── train_model.sh                  # Generated training script
```

---

## 📋 File Purposes

### Root Level

| File | Purpose | User Interaction |
|------|---------|------------------|
| `TRAIN.desktop` | Double-click launcher for training | Double-click to start |
| `TEST.desktop` | Double-click launcher for testing | Double-click after training |
| `STRUCTURE.md` | This blueprint document | Reference only |
| `README.md` | User documentation | Read for instructions |

### Models/

**Purpose**: Store all trained models and their outputs

**Naming**: `training_<ModelName>_<timestamp>/`

**Contents**:
- `checkpoints/` - Intermediate training states (for resume)
- `logs/` - Training logs (loss, metrics, etc.)
- `exports/` - GGUF, ONNX, or other export formats
- `config.json` - Model configuration
- `adapter_*.json/safetensors` - LoRA adapter files

**Example**:
```
Models/training_Qwen-Custom_20251004_120000/
├── checkpoints/
│   └── checkpoint-100/
├── logs/
│   └── training.log
├── exports/
│   └── model-q4_k_m.gguf
├── config.json
├── adapter_config.json
└── adapter_model.safetensors
```

### Training_Data-Sets/

**Purpose**: Organized training data by category

#### Tools/
OpenCode tool usage patterns. Each file contains examples for specific tool categories:
- `file_operations.jsonl` - file_read, file_write, file_edit, file_delete
- `search_operations.jsonl` - file_search, grep_search, directory_list
- `git_operations.jsonl` - git status, log, diff, operations
- `system_operations.jsonl` - system_info, process_manage
- `error_recovery.jsonl` - Handling tool failures gracefully

**Format**:
```json
{"messages": [
  {"role": "user", "content": "Create a file"},
  {"role": "assistant", "content": "{\"type\":\"tool_call\",...}"}
], "scenario": "file_write_basic"}
```

#### App_Development/
Application development patterns:
- `api_design.jsonl` - REST API design, endpoint creation
- `database_queries.jsonl` - SQL queries, ORM usage
- `testing_patterns.jsonl` - Writing tests, TDD
- `deployment.jsonl` - Deployment scripts, CI/CD

#### Coding/
General programming tasks:
- `algorithms.jsonl` - Sorting, searching, graph algorithms
- `data_structures.jsonl` - Lists, trees, hashmaps usage
- `refactoring.jsonl` - Code cleanup, optimization
- `debugging.jsonl` - Finding and fixing bugs

#### Semantic_States/
Context-aware behavior:
- `conversation_flow.jsonl` - Multi-turn conversations
- `intent_detection.jsonl` - Understanding user goals
- `clarification.jsonl` - Asking follow-up questions
- `context_retention.jsonl` - Remembering previous context

### Data/

**Purpose**: All executable scripts and utilities

| File | Purpose | Run When |
|------|---------|----------|
| `config.py` | Central config (paths, settings) | Imported by other scripts |
| `interactive_ui.py` | UI library for menus/buttons | Imported by interactive scripts |
| `tool_trainer.py` | Main orchestrator | When generating training data |
| `training_data_generator.py` | Generate examples | Called by tool_trainer.py |
| `session_manager.py` | Ollama API client | Called by tool_trainer.py |
| `train_with_unsloth.py` | Unsloth fine-tuning | When doing real training |
| `test_trained_model.py` | Test trained models | After training completes |
| `export_for_finetuning.py` | Export to formats | After data generation |
| `start_*.sh` | Bash launchers | From desktop or terminal |

---

## 🔄 Workflow Overview

### 1. Generate Training Data
```
User → TRAIN.desktop → start_training.sh → tool_trainer.py
                                          ↓
                           training_data_generator.py
                                          ↓
                        Training_Data-Sets/Tools/*.jsonl
                                          ↓
                              Data/exports/*.jsonl
```

### 2. Train Model
```
User → start_unsloth_training.sh → train_with_unsloth.py
                                          ↓
                        Read: Data/exports/training_data.jsonl
                                          ↓
                             Download base model
                                          ↓
                          Apply LoRA adapters
                                          ↓
                         Fine-tune (3 epochs)
                                          ↓
                Save: Models/training_<model>_<timestamp>/
```

### 3. Test Model
```
User → TEST.desktop → test_trained_model.py
                                ↓
               Load: Models/training_<latest>/
                                ↓
                    Run test prompts
                                ↓
                      Display results
```

### 4. Use in OpenCode
```
Edit: config.yaml
  model:
    name: /path/to/Trainer/Models/training_<latest>
    provider: transformers
                 ↓
        Start OpenCode
                 ↓
    Model uses tool calls correctly!
```

---

## 🎯 Key Design Principles

### 1. **Separation of Concerns**
- **Models/**: Outputs only (trained models)
- **Training_Data-Sets/**: Inputs only (training examples)
- **Data/**: Logic only (scripts and utilities)

### 2. **Category Organization**
Training data is split by **purpose**:
- Tools → Learning tool usage
- App_Development → Learning app patterns
- Coding → Learning programming
- Semantic_States → Learning context

This allows **mix-and-match training**:
```python
# Train on only tools
train(data=["Tools"])

# Train on tools + coding
train(data=["Tools", "Coding"])

# Train on everything
train(data=["Tools", "App_Development", "Coding", "Semantic_States"])
```

### 3. **Timestamped Outputs**
Every model gets unique timestamp:
```
Models/training_Qwen-Custom_20251004_120000/
Models/training_Qwen-Custom_20251004_140000/
Models/training_Qwen-Custom_20251004_160000/
```

Never overwrites previous models → Easy to compare versions.

### 4. **Centralized Config**
`Data/config.py` is single source of truth:
```python
from Data.config import MODELS_DIR, TRAINING_DATA_DIR, get_latest_model_dir

# All scripts use these paths
# No hardcoded paths elsewhere
```

### 5. **Interactive UI**
All user interaction goes through `interactive_ui.py`:
- Keyboard navigation (↑↓←→)
- Visual buttons and menus
- Consistent styling
- No raw `input()` prompts

---

## 🛠️ Extending the System

### Adding New Training Data Category

1. **Create folder**:
```bash
mkdir Training_Data-Sets/New_Category
```

2. **Add to config.py**:
```python
NEW_CATEGORY_DIR = TRAINING_DATA_DIR / "New_Category"

def get_training_data_path(category: str = "Tools"):
    category_map = {
        # ... existing ...
        "New_Category": NEW_CATEGORY_DIR,
    }
```

3. **Create data files**:
```bash
# Training_Data-Sets/New_Category/examples.jsonl
{"messages": [...], "scenario": "..."}
```

4. **Use in training**:
```python
train(data=["Tools", "New_Category"])
```

### Adding New Training Method

1. **Create script** in `Data/`:
```python
# Data/train_with_new_method.py
from config import MODELS_DIR, TRAINING_DATA_DIR
# ... implementation
```

2. **Create launcher**:
```bash
# Data/start_new_training.sh
#!/bin/bash
python3 Data/train_with_new_method.py
```

3. **Create desktop file** (optional):
```desktop
# TRAIN_NEW.desktop
Exec=x-terminal-emulator -e bash -c "cd ... && ./start_new_training.sh"
```

---

## 📊 Path Reference Quick Guide

```python
# Import config
from Data.config import *

# Get directories
TRAINER_ROOT          # /home/commander/Desktop/Trainer
MODELS_DIR            # /home/commander/Desktop/Trainer/Models
TRAINING_DATA_DIR     # /home/commander/Desktop/Trainer/Training_Data-Sets
DATA_DIR              # /home/commander/Desktop/Trainer/Data

# Get category directories
TOOLS_DATA_DIR        # Training_Data-Sets/Tools
APP_DEV_DATA_DIR      # Training_Data-Sets/App_Development
CODING_DATA_DIR       # Training_Data-Sets/Coding
SEMANTIC_DATA_DIR     # Training_Data-Sets/Semantic_States

# Utility functions
get_latest_model_dir()                    # Returns Path to latest model
get_training_data_path("Tools")           # Returns Path to category
create_model_output_dir("model-name")     # Creates new output dir with timestamp
```

---

## ✅ Checklist for New Scripts

When creating new scripts:

- [ ] Import paths from `Data/config.py` (not hardcoded)
- [ ] Use `interactive_ui.py` for user interaction (not raw input)
- [ ] Save outputs to `Models/training_<name>_<timestamp>/`
- [ ] Read data from `Training_Data-Sets/<category>/`
- [ ] Log to `Models/<training_dir>/logs/`
- [ ] Export to `Models/<training_dir>/exports/`
- [ ] Add entry to this STRUCTURE.md file
- [ ] Create launcher script in `Data/`
- [ ] Create desktop file if user-facing

---

## 🔍 Troubleshooting

### "File not found" errors
→ Check you're using paths from `config.py`, not hardcoded strings

### "Can't find latest model"
→ Use `get_latest_model_dir()` from config.py

### "Training data missing"
→ Check `Training_Data-Sets/<category>/*.jsonl` files exist

### "Permission denied"
→ Make sure scripts are executable: `chmod +x Data/*.sh`

### Desktop files don't launch
→ Run: `chmod +x *.desktop && gio set *.desktop metadata::trusted true`

---

## 📝 Maintenance

### Weekly
- Clean old model checkpoints: `rm -rf Models/*/checkpoints/checkpoint-*`
- Archive old models: `tar -czf archive.tar.gz Models/training_old_*/`

### Monthly
- Review training data quality
- Add new examples to Training_Data-Sets/
- Update model configs if better settings found

### Per Training Run
- Check logs: `tail -f Models/training_latest/logs/training.log`
- Monitor disk space: `du -sh Models/`
- Test model before deploying: `python3 Data/test_trained_model.py`

---

**This blueprint ensures**:
- ✅ No circular reorganizations (structure is final)
- ✅ Clear separation of inputs/outputs/logic
- ✅ Easy to extend with new categories
- ✅ Consistent paths across all scripts
- ✅ User-friendly with double-click launchers
