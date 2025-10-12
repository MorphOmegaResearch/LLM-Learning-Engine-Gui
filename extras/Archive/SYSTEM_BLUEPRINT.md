# 🏗️ OpenCode Trainer System - Complete Blueprint

**Version**: 1.0
**Date**: 2025-10-04
**Status**: Production Ready

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Directory Structure](#directory-structure)
4. [Data Flow](#data-flow)
5. [Component Specifications](#component-specifications)
6. [API Reference](#api-reference)
7. [Configuration System](#configuration-system)
8. [Extension Points](#extension-points)
9. [Maintenance Guide](#maintenance-guide)
10. [Troubleshooting](#troubleshooting)

---

## System Overview

### Purpose
Train small language models (1.5B-4B parameters) to use OpenCode tools correctly through fine-tuning with LoRA adapters.

### Key Features
- ✅ Graphical interface for training data selection
- ✅ Modular training data organized by category
- ✅ Category-based training (select what to train on)
- ✅ Simplified user-facing terminology
- ✅ Automated model output management
- ✅ Environment-based configuration

### Technology Stack
- **GUI**: Python Tkinter
- **Training**: Unsloth (LoRA fine-tuning)
- **Model**: Qwen2.5-Coder-1.5B-Instruct
- **Data Format**: JSONL (JSON Lines)
- **Configuration**: Python modules + environment variables

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        USER LAYER                           │
│  ┌──────────────┐                                          │
│  │ TRAIN.desktop│  ← Double-click to launch                │
│  └──────┬───────┘                                          │
└─────────┼──────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  interactive_trainer_gui.py                          │  │
│  │  - Visual checkboxes for category selection          │  │
│  │  - Live preview panel                                │  │
│  │  - Training configuration (runs, batch, strength)    │  │
│  │  - Launches training subprocess                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │
          │ Environment Variables:
          │ - TRAINING_DATA_FILE
          │ - TRAINING_EPOCHS
          │ - TRAINING_BATCH_SIZE
          │ - TRAINING_LEARNING_RATE
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                      BUSINESS LAYER                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  train_with_unsloth.py                               │  │
│  │  - Reads env vars for configuration                  │  │
│  │  - Loads training data from selected files           │  │
│  │  - Applies LoRA adapters to base model               │  │
│  │  - Fine-tunes with selected parameters               │  │
│  │  - Saves to timestamped output directory             │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                  │
│                           │ Uses                             │
│                           ▼                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  config.py (Configuration Module)                    │  │
│  │  - Centralized path definitions                      │  │
│  │  - Category management functions                     │  │
│  │  - File discovery and counting                       │  │
│  │  - Model directory creation                          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                       DATA LAYER                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Training_Data-Sets/                                 │  │
│  │  ├── Tools/                                          │  │
│  │  │   ├── file_operations.jsonl                       │  │
│  │  │   ├── search_operations.jsonl                     │  │
│  │  │   ├── git_operations.jsonl                        │  │
│  │  │   ├── system_operations.jsonl                     │  │
│  │  │   ├── web_operations.jsonl                        │  │
│  │  │   └── error_recovery.jsonl                        │  │
│  │  ├── Coding/                                         │  │
│  │  │   ├── debugging.jsonl                             │  │
│  │  │   └── project_setup.jsonl                         │  │
│  │  ├── App_Development/ (empty - extension point)     │  │
│  │  └── Semantic_States/ (empty - extension point)     │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Models/                                             │  │
│  │  └── training_<ModelName>_<timestamp>/              │  │
│  │      ├── checkpoints/                                │  │
│  │      ├── logs/                                       │  │
│  │      ├── exports/                                    │  │
│  │      ├── config.json                                 │  │
│  │      ├── adapter_config.json                         │  │
│  │      └── adapter_model.safetensors                   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

### Complete File Tree

```
/Trainer/
│
├── TRAIN.desktop                      # Desktop launcher (entry point)
├── TEST.desktop                       # Model testing launcher
├── SYSTEM_BLUEPRINT.md                # This file - complete system design
├── STRUCTURE.md                       # Directory layout documentation
├── REFACTORING_PLAN.md                # Implementation history
├── IMPLEMENTATION_COMPLETE.md         # Completion summary
│
├── Models/                            # OUTPUT: Trained models
│   └── training_<ModelName>_YYYYMMDD_HHMMSS/
│       ├── checkpoints/               # Training checkpoints
│       ├── logs/                      # Training logs
│       ├── exports/                   # GGUF/ONNX exports
│       ├── config.json                # Model configuration
│       ├── adapter_config.json        # LoRA adapter config
│       └── adapter_model.safetensors  # LoRA weights
│
├── Training_Data-Sets/                # INPUT: Training examples
│   │
│   ├── Tools/                         # OpenCode tool usage (15 examples)
│   │   ├── file_operations.jsonl      # file_read, write, edit, delete (3)
│   │   ├── search_operations.jsonl    # file_search, grep, directory_list (4)
│   │   ├── git_operations.jsonl       # git status, log, diff (1)
│   │   ├── system_operations.jsonl    # system_info, process_manage (3)
│   │   ├── web_operations.jsonl       # web_search, web_fetch (2)
│   │   └── error_recovery.jsonl       # Error handling patterns (2)
│   │
│   ├── Coding/                        # Programming patterns (4 examples)
│   │   ├── debugging.jsonl            # Debug workflows (2)
│   │   └── project_setup.jsonl        # Project scaffolding (2)
│   │
│   ├── App_Development/               # EXTENSION POINT (empty)
│   │   ├── api_design.jsonl           # (not yet created)
│   │   ├── database_queries.jsonl     # (not yet created)
│   │   ├── testing_patterns.jsonl     # (not yet created)
│   │   └── deployment.jsonl           # (not yet created)
│   │
│   └── Semantic_States/               # EXTENSION POINT (empty)
│       ├── conversation_flow.jsonl    # (not yet created)
│       ├── intent_detection.jsonl     # (not yet created)
│       ├── clarification.jsonl        # (not yet created)
│       └── context_retention.jsonl    # (not yet created)
│
└── Data/                              # LOGIC: All executable code
    │
    ├── config.py                      # CORE: Centralized configuration
    │   • get_training_data_path()     # Returns category directory path
    │   • get_category_files()         # Lists JSONL files in category
    │   • count_examples()             # Counts lines in JSONL file
    │   • get_training_data_files()    # Gets files for selected categories
    │   • get_category_info()          # Returns category structure + counts
    │   • create_model_output_dir()    # Creates timestamped output dir
    │   • get_latest_model_dir()       # Finds most recent model
    │
    ├── interactive_trainer_gui.py     # PRESENTATION: Main GUI
    │   • TrainingGUI class            # Tkinter window manager
    │   • create_ui()                  # Builds GUI layout
    │   • create_category_panel()      # Category checkboxes
    │   • create_config_panel()        # Training config spinners
    │   • create_preview_panel()       # Live summary display
    │   • start_training()             # Launches training subprocess
    │
    ├── train_with_unsloth.py          # TRAINING: Fine-tuning engine
    │   • Loads base model             # Qwen2.5-Coder-1.5B-Instruct
    │   • Applies LoRA adapters        # r=16, alpha=16
    │   • Reads env vars               # From GUI
    │   • Fine-tunes model             # With selected data
    │   • Saves to Models/             # Timestamped directory
    │
    ├── split_training_data.py         # UTILITY: Data organization
    │   • split_training_data()        # Splits monolithic JSONL
    │   • SCENARIO_MAPPING             # Maps scenarios to categories
    │
    ├── test_trained_model.py          # TESTING: Model validation
    │   • Loads trained model          # From Models/
    │   • Runs test prompts            # Validates tool call format
    │
    ├── interactive_ui.py              # UI LIBRARY: Terminal menus
    │   • InteractiveUI class          # (fallback - not currently used)
    │   • menu()                       # Keyboard-navigated menus
    │   • confirm()                    # Yes/No prompts
    │
    ├── test_workflow.py               # TESTING: Workflow validation
    │   • Tests category info          # Validates data loading
    │   • Tests file selection         # Validates filtering
    │
    ├── start_unsloth_training.sh      # LEGACY: Shell launcher
    │   (replaced by GUI)
    │
    └── exports/                       # CACHE: Temporary files
        ├── training_data.jsonl        # Combined training data
        ├── hf_training_data.json      # Hugging Face format
        └── Modelfile_*                # Ollama Modelfiles
```

---

## Data Flow

### Complete Training Workflow

```
Step 1: USER INITIATION
┌──────────────────────────────────────┐
│ User double-clicks TRAIN.desktop     │
└──────────────┬───────────────────────┘
               │
               ▼
Step 2: GUI LAUNCH
┌──────────────────────────────────────┐
│ interactive_trainer_gui.py runs      │
│ - Calls get_category_info()          │
│ - Displays categories with counts    │
│ - Shows checkboxes for selection     │
└──────────────┬───────────────────────┘
               │
               ▼
Step 3: USER CONFIGURATION
┌──────────────────────────────────────┐
│ User selects:                        │
│ ☑ Tools                              │
│   ☑ file_operations.jsonl (3)        │
│   ☑ search_operations.jsonl (4)      │
│ ☑ Coding                             │
│   ☑ debugging.jsonl (2)              │
│                                      │
│ Training Runs: 3                     │
│ Batch Size: 2                        │
│ Learning Strength: 2e-4              │
│                                      │
│ [Start Training] ← Click             │
└──────────────┬───────────────────────┘
               │
               ▼
Step 4: FILE COMBINATION
┌──────────────────────────────────────┐
│ GUI.start_training()                 │
│ - Calls get_training_data_files()    │
│ - Returns: [file_ops.jsonl,          │
│             search_ops.jsonl,        │
│             debugging.jsonl]         │
│ - Combines into temp file:           │
│   Data/temp_training_data.jsonl      │
│   (9 examples total)                 │
└──────────────┬───────────────────────┘
               │
               ▼
Step 5: ENVIRONMENT SETUP
┌──────────────────────────────────────┐
│ GUI sets environment variables:      │
│ TRAINING_DATA_FILE =                 │
│   /path/to/temp_training_data.jsonl  │
│ TRAINING_EPOCHS = 3                  │
│ TRAINING_BATCH_SIZE = 2              │
│ TRAINING_LEARNING_RATE = 2e-4        │
└──────────────┬───────────────────────┘
               │
               ▼
Step 6: SUBPROCESS LAUNCH
┌──────────────────────────────────────┐
│ subprocess.run([                     │
│   "python3",                         │
│   "train_with_unsloth.py"            │
│ ], env=environment_vars)             │
│                                      │
│ GUI closes, terminal takes over      │
└──────────────┬───────────────────────┘
               │
               ▼
Step 7: TRAINING INITIALIZATION
┌──────────────────────────────────────┐
│ train_with_unsloth.py                │
│ - Reads env vars                     │
│ - Creates output dir:                │
│   Models/training_Qwen-Custom_       │
│          20251004_120000/            │
│ - Loads base model from Unsloth      │
│ - Applies LoRA adapters (r=16)       │
└──────────────┬───────────────────────┘
               │
               ▼
Step 8: DATA LOADING
┌──────────────────────────────────────┐
│ load_training_data()                 │
│ - Opens temp_training_data.jsonl     │
│ - Parses each line as JSON           │
│ - Converts to Hugging Face Dataset   │
│ - Formats with chat template         │
│ Result: Dataset with 9 examples      │
└──────────────┬───────────────────────┘
               │
               ▼
Step 9: FINE-TUNING
┌──────────────────────────────────────┐
│ SFTTrainer.train()                   │
│ Epoch 1/3:                           │
│   Example 1/9 → Update weights       │
│   Example 2/9 → Update weights       │
│   ... (9 total)                      │
│ Epoch 2/3:                           │
│   Example 1/9 → Update weights       │
│   ...                                │
│ Epoch 3/3:                           │
│   ...                                │
│ Total: 27 weight updates             │
└──────────────┬───────────────────────┘
               │
               ▼
Step 10: MODEL SAVING
┌──────────────────────────────────────┐
│ model.save_pretrained()              │
│ Saves to Models/training_*/          │
│ - adapter_config.json                │
│ - adapter_model.safetensors          │
│ - config.json                        │
│                                      │
│ Optional: Export to GGUF             │
└──────────────┬───────────────────────┘
               │
               ▼
Step 11: CLEANUP
┌──────────────────────────────────────┐
│ - Delete temp_training_data.jsonl    │
│ - Print success message              │
│ - Exit with code 0                   │
└──────────────────────────────────────┘
```

---

## Component Specifications

### 1. TRAIN.desktop

**Type**: Desktop Entry File
**Purpose**: User entry point for training
**Location**: `/Trainer/TRAIN.desktop`

**Specification**:
```ini
[Desktop Entry]
Version=1.0
Type=Application
Name=Train Model
Comment=Start Unsloth training for OpenCode tools
Exec=python3 /home/commander/Desktop/Trainer/Data/interactive_trainer_gui.py
Icon=system-run
Terminal=false
Categories=Development;
Path=/home/commander/Desktop/Trainer
```

**Behavior**:
- Double-click launches Python GUI
- No terminal window (Terminal=false)
- Runs in Trainer directory context

---

### 2. config.py

**Type**: Python Module
**Purpose**: Centralized configuration and path management
**Location**: `/Trainer/Data/config.py`

**Public API**:

```python
# Path Constants
TRAINER_ROOT: Path              # /home/commander/Desktop/Trainer
DATA_DIR: Path                  # TRAINER_ROOT/Data
MODELS_DIR: Path                # TRAINER_ROOT/Models
TRAINING_DATA_DIR: Path         # TRAINER_ROOT/Training_Data-Sets
TOOLS_DATA_DIR: Path            # TRAINING_DATA_DIR/Tools
APP_DEV_DATA_DIR: Path          # TRAINING_DATA_DIR/App_Development
CODING_DATA_DIR: Path           # TRAINING_DATA_DIR/Coding
SEMANTIC_DATA_DIR: Path         # TRAINING_DATA_DIR/Semantic_States
EXPORTS_DIR: Path               # DATA_DIR/exports

# Functions
def get_training_data_path(category: str) -> Path:
    """
    Args:
        category: "Tools", "App_Development", "Coding", "Semantic_States"
    Returns:
        Path to category directory
    """

def get_category_files(category: str) -> List[Path]:
    """
    Args:
        category: Category name
    Returns:
        List of .jsonl files in category
    """

def count_examples(file_path: Path) -> int:
    """
    Args:
        file_path: Path to JSONL file
    Returns:
        Number of lines (examples) in file
    """

def get_training_data_files(
    categories: List[str],
    subcategories: Dict[str, List[str]] = None
) -> List[Path]:
    """
    Args:
        categories: ["Tools", "Coding", ...]
        subcategories: {
            "Tools": ["file_operations", "search_operations"],
            "Coding": ["debugging"]
        }
    Returns:
        List of selected JSONL file paths

    Example:
        files = get_training_data_files(
            ["Tools"],
            {"Tools": ["file_operations"]}
        )
        # Returns: [Path("Training_Data-Sets/Tools/file_operations.jsonl")]
    """

def get_category_info() -> Dict[str, Dict]:
    """
    Returns:
        {
            "Tools": {
                "files": [Path(...), ...],
                "subcategories": {
                    "file_operations": {"path": Path(...), "count": 3},
                    "search_operations": {"path": Path(...), "count": 4},
                    ...
                },
                "total_examples": 15
            },
            "Coding": {...},
            ...
        }
    """

def create_model_output_dir(model_name: str) -> Path:
    """
    Creates: Models/training_{clean_name}_{timestamp}/

    Args:
        model_name: "Qwen-Custom" or "unsloth/Qwen2.5-Coder-1.5B"
    Returns:
        Path to created directory
    Side Effects:
        Creates subdirectories: checkpoints/, logs/, exports/
    """

def get_latest_model_dir() -> Path:
    """
    Returns:
        Path to most recently modified model directory in Models/
        None if no models found
    """
```

**Internal Logic**:
- Paths computed from `__file__` location
- All directories created on import if missing
- Category map: `{"Tools": TOOLS_DATA_DIR, ...}`

---

### 3. interactive_trainer_gui.py

**Type**: Python GUI Application
**Purpose**: Visual interface for training configuration
**Location**: `/Trainer/Data/interactive_trainer_gui.py`

**Class Structure**:

```python
class TrainingGUI:
    """Main GUI application class"""

    # State Variables
    category_vars: Dict[str, BooleanVar]              # {category: checked}
    subcategory_vars: Dict[Tuple[str, str], BooleanVar]  # {(cat, subcat): checked}
    config_vars: Dict[str, IntVar|StringVar]          # Training config

    # UI Methods
    def create_ui(self):
        """Build complete GUI layout"""

    def create_category_panel(self, parent):
        """Left panel: Category checkboxes"""

    def create_config_panel(self, parent):
        """Right panel top: Training settings"""

    def create_preview_panel(self, parent):
        """Right panel bottom: Live summary"""

    def create_buttons(self, parent):
        """Bottom: Action buttons"""

    # Logic Methods
    def toggle_category(self, category):
        """When category toggled, toggle all subcategories"""

    def update_preview(self, event=None):
        """Rebuild summary text in preview panel"""

    def get_selected_files(self) -> List[Path]:
        """Collect selected training file paths"""

    def start_training(self):
        """
        1. Validate selection
        2. Combine files into temp_training_data.jsonl
        3. Set environment variables
        4. Launch train_with_unsloth.py subprocess
        5. Close GUI
        """
```

**GUI Layout Specification**:

```
Window: 900x700 pixels, dark theme (#2b2b2b background)

+-----------------------------------------------------------+
| Header (80px, #1e1e1e)                                   |
| "🚀 OpenCode Training Launcher" (24pt, #61dafb)          |
+-----------------------------------------------------------+
|                                                           |
| +------------------------+  +---------------------------+ |
| | Left Panel             |  | Right Panel (350px)       | |
| | (Category Selection)   |  |                           | |
| |                        |  | +----------------------+  | |
| | Canvas (scrollable)    |  | | Config Panel         |  | |
| |   ☑ Tools (15)         |  | | Training Runs: [3]   |  | |
| |     ☑ File Ops (3)     |  | | Batch Size: [2]      |  | |
| |     ☑ Search (4)       |  | | Learning: [2e-4]     |  | |
| |   ☑ Coding (4)         |  | +----------------------+  | |
| |     ☑ Debugging (2)    |  |                           | |
| |   ☐ App Dev (0)        |  | +----------------------+  | |
| |   ☐ Semantic (0)       |  | | Preview Panel        |  | |
| |                        |  | | (ScrolledText)       |  | |
| |                        |  | | Summary of selection |  | |
| |                        |  | +----------------------+  | |
| +------------------------+  +---------------------------+ |
|                                                           |
| +-------------------------------------------------------+ |
| | Bottom Buttons (70px)                                 | |
| | [☑ Select All] [☐ Deselect All]   [🚀 Start] [❌ Cancel] | |
| +-------------------------------------------------------+ |
+-----------------------------------------------------------+
```

**Color Scheme**:
- Background: `#2b2b2b` (dark gray)
- Panels: `#363636` (lighter gray)
- Accent: `#61dafb` (cyan blue)
- Text: `#ffffff` (white)
- Dim text: `#888888` (gray)
- Success: `#4CAF50` (green)
- Error: `#f44336` (red)

---

### 4. train_with_unsloth.py

**Type**: Python Training Script
**Purpose**: Fine-tune model with Unsloth + LoRA
**Location**: `/Trainer/Data/train_with_unsloth.py`

**Environment Variables** (inputs from GUI):
```python
TRAINING_DATA_FILE: str         # Path to combined JSONL
TRAINING_EPOCHS: str            # "3"
TRAINING_BATCH_SIZE: str        # "2"
TRAINING_LEARNING_RATE: str     # "2e-4"
```

**Configuration**:
```python
# Model
MODEL_NAME = "unsloth/Qwen2.5-Coder-1.5B-Instruct"
MAX_SEQ_LENGTH = 2048
LOAD_IN_4BIT = True

# LoRA
LORA_R = 16
LORA_ALPHA = 16
LORA_DROPOUT = 0
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj",
                   "gate_proj", "up_proj", "down_proj"]

# Training (from env vars)
NUM_EPOCHS = int(os.getenv("TRAINING_EPOCHS", "3"))
BATCH_SIZE = int(os.getenv("TRAINING_BATCH_SIZE", "2"))
LEARNING_RATE = float(os.getenv("TRAINING_LEARNING_RATE", "2e-4"))
GRADIENT_ACCUMULATION_STEPS = 4
```

**Training Process**:
1. Load base model from Unsloth
2. Apply LoRA adapters (16-rank)
3. Load training data (JSONL → Dataset)
4. Create SFTTrainer with TrainingArguments
5. Train for N epochs
6. Save LoRA adapters to output dir
7. Optional: Export to GGUF

**Output Structure**:
```
Models/training_Qwen-Custom_20251004_120000/
├── adapter_config.json         # LoRA configuration
├── adapter_model.safetensors   # LoRA weights (~50MB)
├── config.json                 # Model config
├── checkpoints/                # Training checkpoints
├── logs/                       # Training logs
└── exports/                    # GGUF/ONNX exports
```

---

### 5. Training Data Format

**File Format**: JSONL (JSON Lines)
**Extension**: `.jsonl`
**Location**: `Training_Data-Sets/<Category>/<subcategory>.jsonl`

**Line Format**:
```json
{
  "messages": [
    {"role": "user", "content": "Create a file called test.txt"},
    {"role": "assistant", "content": "{\"type\":\"tool_call\",\"name\":\"file_write\",\"args\":{\"file_path\":\"test.txt\",\"content\":\"\"}}"},
    {"role": "system", "content": "{\"success\":true,\"output\":\"File written\"}"},
    {"role": "assistant", "content": "Created test.txt"}
  ],
  "scenario": "file_write_basic"
}
```

**Field Specifications**:
- `messages`: Array of message objects
  - `role`: "user" | "assistant" | "system"
  - `content`: String (tool calls are JSON strings)
- `scenario`: String identifier (for tracking/debugging)

**Tool Call Format** (in assistant messages):
```json
{
  "type": "tool_call",
  "name": "file_write",
  "args": {
    "file_path": "test.txt",
    "content": "Hello World"
  }
}
```

---

## Configuration System

### Environment Variables

**Set by**: `interactive_trainer_gui.py`
**Read by**: `train_with_unsloth.py`

| Variable | Type | Example | Purpose |
|----------|------|---------|---------|
| `TRAINING_DATA_FILE` | Path | `/path/to/temp.jsonl` | Combined training data |
| `TRAINING_EPOCHS` | Integer | `"3"` | Number of training runs |
| `TRAINING_BATCH_SIZE` | Integer | `"2"` | Examples per update |
| `TRAINING_LEARNING_RATE` | Float | `"2e-4"` | Learning strength |

### Path Configuration

**Defined in**: `config.py`
**Computed from**: `__file__` location

```python
# All paths relative to Trainer root
TRAINER_ROOT = Path(__file__).parent.parent
DATA_DIR = TRAINER_ROOT / "Data"
MODELS_DIR = TRAINER_ROOT / "Models"
TRAINING_DATA_DIR = TRAINER_ROOT / "Training_Data-Sets"
```

**Benefits**:
- Works regardless of Trainer location
- No hardcoded absolute paths
- Easy to relocate entire directory

---

## Extension Points

### 1. Adding New Training Categories

**Steps**:
1. Create directory: `Training_Data-Sets/New_Category/`
2. Add JSONL files: `example_data.jsonl`
3. Update `config.py` (if hardcoded):
   ```python
   NEW_CATEGORY_DIR = TRAINING_DATA_DIR / "New_Category"
   ```
4. Add to category list in `get_category_info()`:
   ```python
   categories = ["Tools", "Coding", "New_Category", ...]
   ```

**That's it!** GUI will auto-discover the category.

---

### 2. Adding Training Data

**Format**:
```bash
# Create new file
nano Training_Data-Sets/Tools/new_operations.jsonl

# Add examples (one per line)
{"messages": [...], "scenario": "operation_name"}
{"messages": [...], "scenario": "another_operation"}
```

**No code changes needed** - GUI will auto-count examples.

---

### 3. Custom Training Profiles

**Future Enhancement** - Not yet implemented

**Design**:
```python
# Data/profiles/quick_tools.json
{
  "name": "Quick Tools",
  "description": "Fast training on essential tools",
  "categories": ["Tools"],
  "subcategories": {
    "Tools": ["file_operations", "search_operations"]
  },
  "config": {
    "training_runs": 2,
    "batch_size": 4,
    "learning_strength": "2e-4"
  }
}
```

**Implementation**:
1. Create `Data/profiles/` directory
2. Add load/save methods to GUI class
3. Add profile selector to GUI
4. Load profile → set checkboxes + config

---

### 4. Custom Base Models

**Current**: Hardcoded to `unsloth/Qwen2.5-Coder-1.5B-Instruct`

**To change**:
Edit `train_with_unsloth.py`:
```python
MODEL_NAME = "unsloth/Llama-3.2-3B-Instruct"
```

**Future Enhancement**:
Add model selector to GUI, pass as env var.

---

## Maintenance Guide

### Regular Tasks

**Weekly**:
- Check `Models/` directory size
- Archive old models: `tar -czf archive.tar.gz Models/training_old_*/`

**Monthly**:
- Review training data quality
- Add new examples to categories
- Update documentation if structure changes

**Per Training Run**:
- Check logs: `tail -f Models/training_*/logs/*`
- Monitor disk space: `du -sh Models/`
- Test model: `python3 test_trained_model.py`

### Backup Strategy

**What to backup**:
- ✅ `Training_Data-Sets/` - All training examples
- ✅ `SYSTEM_BLUEPRINT.md` - This file
- ✅ `config.py` - Path configuration
- ⚠️ `Models/` - Only latest 2-3 models (large files)

**What NOT to backup**:
- ❌ `Data/exports/` - Temporary cache
- ❌ `Data/__pycache__/` - Python cache

**Backup command**:
```bash
cd /home/commander/Desktop
tar -czf Trainer_backup_$(date +%Y%m%d).tar.gz \
  --exclude='Models/training_*' \
  --exclude='Data/__pycache__' \
  --exclude='Data/exports' \
  Trainer/
```

### Version Control

**Recommended**:
```bash
cd /home/commander/Desktop/Trainer
git init
git add Training_Data-Sets/ Data/*.py *.md *.desktop
git commit -m "Initial trainer system"
```

**Ignore**:
```gitignore
Models/
Data/__pycache__/
Data/exports/
Data/temp_*.jsonl
*.pyc
```

---

## Troubleshooting

### Issue: GUI doesn't launch

**Symptoms**: Double-clicking TRAIN.desktop does nothing

**Debug**:
```bash
cd /home/commander/Desktop/Trainer/Data
python3 interactive_trainer_gui.py
# Check error output
```

**Common causes**:
1. Tkinter not installed: `sudo apt install python3-tk`
2. Path error in .desktop file
3. Python syntax error in GUI code

**Fix**:
- Check terminal output for errors
- Verify TRAIN.desktop Exec path
- Test GUI directly from terminal

---

### Issue: Training data not found

**Symptoms**: GUI shows "0 examples" for all categories

**Debug**:
```bash
cd /home/commander/Desktop/Trainer/Data
python3 test_workflow.py
# Check category loading
```

**Common causes**:
1. Data not split yet
2. Wrong directory structure
3. Empty JSONL files

**Fix**:
```bash
# Re-split data
cd /home/commander/Desktop/Trainer/Data
python3 split_training_data.py

# Verify files
ls -lh ../Training_Data-Sets/Tools/
```

---

### Issue: Training fails

**Symptoms**: Training starts but crashes with error

**Debug**:
```bash
# Check last few lines of error
# Look for:
# - CUDA out of memory
# - File not found
# - Module import error
```

**Common causes**:
1. GPU memory: Reduce batch size
2. Missing dependencies: `pip install unsloth trl`
3. Invalid training data: Check JSONL format

**Fix by cause**:
1. Edit GUI, set Batch Size to 1
2. Install missing packages
3. Validate JSONL: `python3 -m json.tool file.jsonl`

---

### Issue: Model quality poor

**Symptoms**: Trained model doesn't output tool calls correctly

**Debug**:
```bash
cd /home/commander/Desktop/Trainer/Data
python3 test_trained_model.py
```

**Common causes**:
1. Too few training runs (epochs)
2. Not enough training examples
3. Learning rate too high/low

**Fix**:
1. Increase Training Runs to 5
2. Add more examples to Training_Data-Sets/
3. Try Learning Strength: 1e-4 or 3e-4

---

## Appendix

### A. File Size Reference

| Component | Typical Size |
|-----------|--------------|
| Base model download | ~1.5 GB |
| LoRA adapters | ~50 MB |
| Training data (JSONL) | ~100 KB |
| GGUF export | ~1.0 GB |
| Full trained model dir | ~50-100 MB |

### B. Training Time Estimates

| Examples | Epochs | GPU | CPU |
|----------|--------|-----|-----|
| 19 | 3 | ~5 min | ~2 hr |
| 50 | 3 | ~12 min | ~4 hr |
| 100 | 5 | ~40 min | ~8 hr |
| 200 | 5 | ~1.5 hr | ~16 hr |

*GPU: NVIDIA RTX 3060+, CPU: Modern 8-core*

### C. Parameter Recommendations

| Model Size | Training Runs | Batch Size | Learning Strength |
|------------|---------------|------------|-------------------|
| 1.5B | 3-5 | 2-4 | 2e-4 |
| 3B | 3-4 | 1-2 | 2e-4 |
| 7B | 2-3 | 1 | 1e-4 |

### D. Glossary

| Term | User-Facing | Technical | Meaning |
|------|-------------|-----------|---------|
| Training Runs | Training Runs | Epochs | How many times model sees all data |
| Batch Size | Batch Size | Batch Size | Examples processed before update |
| Learning Strength | Learning Strength | Learning Rate | Size of weight updates |
| Category | Category | Directory | Top-level data organization |
| Subcategory | Subcategory | JSONL file | Specific training data file |

---

## Document Control

**Version**: 1.0
**Last Updated**: 2025-10-04
**Author**: System Architect
**Status**: Production

**Change Log**:
- 2025-10-04: Initial blueprint creation

**Review Schedule**: Monthly or after major changes

**Related Documents**:
- `STRUCTURE.md` - Directory layout
- `REFACTORING_PLAN.md` - Implementation history
- `IMPLEMENTATION_COMPLETE.md` - Feature completion summary

---

**END OF BLUEPRINT**

*This document represents the complete, final design of the OpenCode Trainer System.
No further reorganization should be needed - all extension points are documented above.*
