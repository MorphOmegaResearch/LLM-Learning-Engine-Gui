# Refactoring Plan - Training Data Split & Interactive Launcher

## 🎯 Objective

Transform the monolithic training system into a modular, category-based system where:
1. Training data is split into individual files by category
2. Interactive launcher lets users select which datasets to train on
3. All scripts use the new directory structure
4. Easy to add new training categories

---

## 📊 Current State Analysis

### Current Training Data (19 examples in single file)
Located: `Data/exports/training_data.jsonl`

**Categories Found:**
1. **File Operations** (6 examples):
   - file_write_basic
   - file_edit_basic
   - file_read_basic
   - file_delete (error_recovery)

2. **Search Operations** (4 examples):
   - file_search_basic
   - grep_search_basic
   - directory_list_basic
   - auto_chain_search_read

3. **System Operations** (3 examples):
   - system_info_basic
   - process_list
   - system_inspection

4. **Git Operations** (1 example):
   - git_log

5. **Web Operations** (2 examples):
   - web_search_basic
   - web_research

6. **Workflows** (3 examples):
   - code_review
   - debug_session
   - project_setup
   - multi_tool_workflow

---

## 🗂️ New Directory Structure

```
Training_Data-Sets/
├── Tools/
│   ├── file_operations.jsonl           # file_read, write, edit, delete
│   ├── search_operations.jsonl         # file_search, grep, directory_list
│   ├── git_operations.jsonl            # git status, log, diff
│   ├── system_operations.jsonl         # system_info, process_manage
│   ├── web_operations.jsonl            # web_search, web_fetch
│   └── error_recovery.jsonl            # Error handling patterns
│
├── App_Development/
│   ├── api_design.jsonl                # REST API patterns
│   ├── database_queries.jsonl          # SQL, ORM
│   ├── testing_patterns.jsonl          # Unit tests, TDD
│   └── deployment.jsonl                # CI/CD, deploy scripts
│
├── Coding/
│   ├── algorithms.jsonl                # Sort, search algorithms
│   ├── data_structures.jsonl           # Lists, trees, graphs
│   ├── refactoring.jsonl               # Code cleanup
│   ├── debugging.jsonl                 # Debug workflows
│   └── project_setup.jsonl             # Project scaffolding
│
└── Semantic_States/
    ├── conversation_flow.jsonl         # Multi-turn dialogues
    ├── intent_detection.jsonl          # Understanding goals
    ├── clarification.jsonl             # Asking questions
    └── context_retention.jsonl         # Memory across turns
```

---

## 🔧 Implementation Steps

### Step 1: Data Splitting Script
**File**: `Data/split_training_data.py`

**Purpose**: Split monolithic JSONL into categorized files

**Logic**:
```python
# Map scenarios to categories
SCENARIO_MAPPING = {
    # Tools - File Operations
    "file_write_basic": ("Tools", "file_operations.jsonl"),
    "file_edit_basic": ("Tools", "file_operations.jsonl"),
    "file_read_basic": ("Tools", "file_operations.jsonl"),

    # Tools - Search Operations
    "file_search_basic": ("Tools", "search_operations.jsonl"),
    "grep_search_basic": ("Tools", "search_operations.jsonl"),
    "directory_list_basic": ("Tools", "search_operations.jsonl"),
    "auto_chain_search_read": ("Tools", "search_operations.jsonl"),

    # Tools - Git Operations
    "git_log": ("Tools", "git_operations.jsonl"),

    # Tools - System Operations
    "system_info_basic": ("Tools", "system_operations.jsonl"),
    "process_list": ("Tools", "system_operations.jsonl"),
    "system_inspection": ("Tools", "system_operations.jsonl"),

    # Tools - Web Operations
    "web_search_basic": ("Tools", "web_operations.jsonl"),
    "web_research": ("Tools", "web_operations.jsonl"),

    # Coding - Workflows
    "code_review": ("Coding", "debugging.jsonl"),
    "debug_session": ("Coding", "debugging.jsonl"),
    "project_setup": ("Coding", "project_setup.jsonl"),
    "multi_tool_workflow": ("Coding", "project_setup.jsonl"),

    # Error Recovery
    "error_recovery": ("Tools", "error_recovery.jsonl"),
}

# Read monolithic file
# For each example:
#   - Get scenario name
#   - Look up category and file in mapping
#   - Append to appropriate category file
# Result: Data distributed across category files
```

### Step 2: Interactive Training Launcher
**File**: `Data/interactive_trainer.py`

**Purpose**: GUI for selecting training datasets

**Flow**:
```
1. Display main menu:
   ┌─────────────────────────────────────┐
   │  Select Training Data Categories    │
   ├─────────────────────────────────────┤
   │  ☑ Tools (19 examples)              │
   │  ☐ App Development (0 examples)     │
   │  ☐ Coding (4 examples)              │
   │  ☐ Semantic States (0 examples)     │
   │                                     │
   │  [A] Select All                     │
   │  [N] Select None                    │
   │  [Enter] Continue                   │
   └─────────────────────────────────────┘

2. Sub-menu for selected category (e.g., Tools):
   ┌─────────────────────────────────────┐
   │  Tools - Select Subcategories       │
   ├─────────────────────────────────────┤
   │  ☑ File Operations (6)              │
   │  ☑ Search Operations (4)            │
   │  ☑ Git Operations (1)               │
   │  ☑ System Operations (3)            │
   │  ☑ Web Operations (2)               │
   │  ☑ Error Recovery (3)               │
   │                                     │
   │  [Enter] Continue                   │
   └─────────────────────────────────────┘

3. Training configuration:
   ┌─────────────────────────────────────┐
   │  Training Configuration             │
   ├─────────────────────────────────────┤
   │  Total Examples: 19                 │
   │                                     │
   │  Epochs: [3]        (↑↓ to adjust) │
   │  Batch Size: [2]    (↑↓ to adjust) │
   │  Learning Rate: [2e-4]              │
   │                                     │
   │  [Enter] Start Training             │
   │  [ESC] Cancel                       │
   └─────────────────────────────────────┘

4. Execute training with selected data
```

**Key Features**:
- Uses `interactive_ui.py` for keyboard navigation
- Checkboxes for category selection (Space to toggle)
- Shows example counts per category
- Combines selected datasets into training input
- Saves selection profile for reuse

### Step 3: Update Training Scripts

#### A. `train_with_unsloth.py`
**Changes**:
```python
# OLD:
TRAINING_DATA_PATH = "exports/training_data.jsonl"

# NEW:
from config import get_training_data_files

# Load based on selected categories
categories = ["Tools", "Coding"]  # From launcher
subcategories = {
    "Tools": ["file_operations", "search_operations"],
    "Coding": ["debugging"]
}

training_files = get_training_data_files(categories, subcategories)
# Returns: [
#   "Training_Data-Sets/Tools/file_operations.jsonl",
#   "Training_Data-Sets/Tools/search_operations.jsonl",
#   "Training_Data-Sets/Coding/debugging.jsonl"
# ]

# Combine all selected files into single dataset
dataset = combine_datasets(training_files)
```

#### B. `config.py`
**Add new functions**:
```python
def get_category_files(category: str) -> List[Path]:
    """Get all JSONL files in a category directory"""
    category_dir = get_training_data_path(category)
    return list(category_dir.glob("*.jsonl"))

def count_examples(file_path: Path) -> int:
    """Count examples in a JSONL file"""
    with open(file_path) as f:
        return sum(1 for _ in f)

def get_training_data_files(
    categories: List[str],
    subcategories: Dict[str, List[str]] = None
) -> List[Path]:
    """
    Get training data files for selected categories/subcategories

    Args:
        categories: ["Tools", "Coding", ...]
        subcategories: {
            "Tools": ["file_operations", "search_operations"],
            "Coding": ["debugging"]
        }

    Returns:
        List of Path objects to JSONL files
    """
    files = []
    for category in categories:
        cat_dir = get_training_data_path(category)

        if subcategories and category in subcategories:
            # Specific subcategories
            for subcat in subcategories[category]:
                file_path = cat_dir / f"{subcat}.jsonl"
                if file_path.exists():
                    files.append(file_path)
        else:
            # All files in category
            files.extend(cat_dir.glob("*.jsonl"))

    return files

def load_training_profile(profile_name: str) -> Dict:
    """Load saved training profile (category selections)"""
    profile_path = DATA_DIR / "profiles" / f"{profile_name}.json"
    with open(profile_path) as f:
        return json.load(f)

def save_training_profile(profile_name: str, config: Dict):
    """Save training profile for reuse"""
    profile_dir = DATA_DIR / "profiles"
    profile_dir.mkdir(exist_ok=True)
    profile_path = profile_dir / f"{profile_name}.json"
    with open(profile_path, 'w') as f:
        json.dump(config, f, indent=2)
```

### Step 4: Update Desktop Launcher
**File**: `TRAIN.desktop`

**New Exec**:
```
Exec=bash -c "cd /home/commander/Desktop/Trainer/Data && python3 interactive_trainer.py"
```

This launches the interactive menu instead of going straight to training.

### Step 5: Migration Script
**File**: `Data/migrate_to_new_structure.py`

**Purpose**: One-time migration of existing data

**Steps**:
1. Run `split_training_data.py` to split monolithic file
2. Move split files to `Training_Data-Sets/` subdirectories
3. Create empty placeholder files for future categories
4. Update all script imports to use `config.py` paths
5. Create default training profile

---

## 🎨 User Experience Flow

### Old Way:
```
Double-click TRAIN.desktop
  ↓
Script immediately starts training with ALL data
  ↓
No control over what's being trained
```

### New Way:
```
Double-click TRAIN.desktop
  ↓
Interactive menu appears:
  "What do you want to train on?"

  ☑ Tools (19 examples)
    ↓ (expand)
    ☑ File Operations (6)
    ☑ Search Operations (4)
    ☐ Git Operations (1)  ← User unchecks
    ...

  ☐ App Development (0)  ← Empty category
  ☑ Coding (4)

  [Continue]
  ↓
Configuration screen:
  "Training 17 examples (Tools + Coding)"
  Epochs: 3
  Batch: 2

  [Start Training]
  ↓
Training begins with ONLY selected categories
  ↓
Model trained specifically on chosen data
```

---

## 📋 File Changes Summary

### New Files:
1. `Data/split_training_data.py` - Split monolithic data
2. `Data/interactive_trainer.py` - Interactive launcher GUI
3. `Data/migrate_to_new_structure.py` - One-time migration
4. `Data/profiles/` - Saved training profiles
5. `Training_Data-Sets/Tools/*.jsonl` - Split data files
6. `Training_Data-Sets/Coding/*.jsonl` - Split data files

### Modified Files:
1. `Data/config.py` - Add new helper functions
2. `Data/train_with_unsloth.py` - Use category-based loading
3. `TRAIN.desktop` - Point to interactive launcher
4. `STRUCTURE.md` - Update documentation

### Unchanged:
- `Data/interactive_ui.py` - Already perfect for this
- `Models/` - Output structure stays same
- `Data/test_trained_model.py` - Works with any trained model

---

## ✅ Benefits

### 1. Modularity
- Train on only what you need
- Easy to add new categories
- Clear organization

### 2. Experimentation
```python
# Compare training results:
Train A: Tools only → 80% accuracy on tools
Train B: Tools + Coding → 85% on tools, 75% on coding
Train C: Everything → 70% on everything
```

### 3. Incremental Training
```python
Day 1: Train on Tools (fast, 19 examples)
Day 2: Add Coding (27 examples total)
Day 3: Add App_Development (50+ examples total)
```

### 4. Easy Category Addition
```bash
# Add new category
mkdir Training_Data-Sets/New_Category
echo '{"messages":[...]}' > Training_Data-Sets/New_Category/examples.jsonl

# It appears in launcher automatically!
```

---

## 🔄 Migration Process (For User)

```bash
cd /home/commander/Desktop/Trainer/Data

# Step 1: Split existing data
python3 split_training_data.py

# Step 2: Migrate to new structure
python3 migrate_to_new_structure.py

# Step 3: Test interactive launcher
python3 interactive_trainer.py

# Step 4: Done! Old files backed up to Data/backup/
```

---

## 🚀 Future Enhancements

### Phase 2:
- **Training Profiles**: Save/load category selections
  - "Quick Tools" profile
  - "Full Stack" profile
  - "Custom" profile

### Phase 3:
- **Data Augmentation**: Auto-generate variations
- **Example Editor**: GUI for adding/editing examples
- **Quality Metrics**: Track which categories improve model most

### Phase 4:
- **Remote Data Sources**: Pull examples from GitHub, HuggingFace
- **Collaborative Training**: Share training datasets
- **Auto-categorization**: AI suggests categories for new examples

---

## 📊 Estimated Work

| Task | Time | Difficulty |
|------|------|------------|
| `split_training_data.py` | 30min | Easy |
| `interactive_trainer.py` | 2hr | Medium |
| Update `config.py` | 30min | Easy |
| Update `train_with_unsloth.py` | 1hr | Medium |
| Migration script | 1hr | Easy |
| Testing & debugging | 2hr | Medium |
| Documentation updates | 30min | Easy |
| **Total** | **7.5hr** | **Medium** |

---

## 🎯 Next Step

**Proceed with implementation?**

If yes, I'll start with:
1. Create `split_training_data.py`
2. Run it to split current data
3. Create `interactive_trainer.py`
4. Update config.py
5. Test the full flow
6. Update all documentation

This gives you a professional, scalable training system with zero circular reorganizations.
