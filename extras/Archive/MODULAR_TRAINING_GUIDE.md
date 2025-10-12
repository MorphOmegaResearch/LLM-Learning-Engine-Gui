# Modular Training System Guide

## 🎯 Overview

The training system has been refactored from a single monolithic script into a **modular, category-based architecture**:

- ✅ **Core Training Engine** - Shared library (`training_engine.py`)
- ✅ **Category-Specific Scripts** - One per category (`train.py` in each folder)
- ✅ **GUI Integration** - Manage and run scripts from Categories tab

---

## 📂 Structure

```
Trainer/
├── Data/
│   ├── training_engine.py          # Core engine (shared)
│   └── train_with_unsloth.py       # Legacy (kept for reference)
│
└── Training_Data-Sets/
    ├── Tools/
    │   ├── train.py                # Tools-specific training
    │   ├── file_operations.jsonl   # Training data
    │   └── *.jsonl                 # More data files
    │
    ├── Coding/
    │   └── train.py                # Coding-specific training
    │
    ├── App_Development/
    │   └── train.py                # App Dev-specific training
    │
    └── Semantic_States/
        └── train.py                # Semantic States training
```

---

## 🔧 Core Engine: `training_engine.py`

**Purpose:** Reusable training library using Unsloth

**Key Features:**
- Model loading and LoRA configuration
- Training data processing
- SFT Trainer setup
- Model saving and GGUF export
- Training statistics tracking

**Usage:**
```python
from training_engine import TrainingEngine

config = {
    "category": "Tools",
    "training_data_path": "path/to/data.jsonl",
    "num_epochs": 3,
    "batch_size": 2,
    "learning_rate": 2e-4
}

engine = TrainingEngine(config)
output_dir = engine.run_full_training()
```

---

## 📝 Category Scripts

Each category folder has its own `train.py` that:

1. **Discovers** all `.jsonl` training data files in its folder
2. **Combines** them into one temporary file
3. **Configures** training parameters for that category
4. **Uses** the core `TrainingEngine` to execute training
5. **Saves** the trained model with category name

**Example: Tools/train.py**
```bash
cd /path/to/Trainer/Training_Data-Sets/Tools
python3 train.py
```

Output:
```
=============================================================
  TRAINING: Tools Category
  OpenCode Tool Usage Training
=============================================================

📁 Found 1 training data file(s):
   • file_operations.jsonl: 15 examples

📊 Total: 15 training examples

🚀 Initializing training engine...
[Training output...]

🎉 Tools category training complete!
📂 Model saved to: Models/training_Tools_Qwen2.5-Coder-1.5B_20251004_085300
```

---

## 🖥️ GUI Integration

### Categories Tab

**Purpose:** View, edit, and manage training scripts

**Workflow:**
1. Click a **category button** (e.g., "Tools")
2. Scripts section shows all `.py` files in that category
3. Click a **script** (e.g., "train.py") to edit it
4. Make changes in the editor
5. Click **💾 Save Script**

**Buttons:**
- **➕ New Category** - Create new training category
- **➕ New Script** - Add custom training script to category
- **🗑️ Delete Script** - Remove a script
- **📁 Open Folder** - Open category folder in file manager

---

## 🚀 Running Training

### Method 1: From GUI (Coming Soon)
Runner tab will allow selecting and executing scripts

### Method 2: Command Line
```bash
# Train specific category
cd /path/to/Trainer/Training_Data-Sets/Tools
python3 train.py

# Or from anywhere
python3 /path/to/Trainer/Training_Data-Sets/Tools/train.py
```

### Method 3: From Category Folder
```bash
cd /path/to/Trainer/Training_Data-Sets/Coding
./train.py  # If executable
```

---

## ⚙️ Customization

### Per-Category Configuration

Edit the `config` dictionary in each category's `train.py`:

```python
config = {
    "category": "Tools",
    "training_data_path": str(combined_data),
    "num_epochs": 5,              # Increase training runs
    "batch_size": 4,              # Larger batches
    "learning_rate": 1e-4,        # Lower learning rate
    "max_seq_length": 4096,       # Longer sequences
    "lora_r": 32,                 # Larger LoRA rank
}
```

### Creating Custom Scripts

Use **➕ New Script** button in Categories tab, or:

```bash
cd /path/to/Trainer/Training_Data-Sets/Tools
cp train.py train_custom.py
# Edit train_custom.py
```

---

## 📊 Training Output

Each training run creates:

```
Models/
└── training_Tools_Qwen2.5-Coder-1.5B_20251004_085300/
    ├── adapter_config.json
    ├── adapter_model.safetensors
    ├── config.json
    ├── tokenizer_config.json
    └── ...
```

Plus GGUF export:
```
Models/
└── training_Tools_Qwen2.5-Coder-1.5B_20251004_085300_gguf/
    └── [GGUF files for Ollama]
```

---

## 🔄 Migration from Old System

**Old:** Single `train_with_unsloth.py` with environment variables

**New:** Category-specific scripts using `training_engine.py`

**Backwards Compatible:**
- Old `train_with_unsloth.py` still works
- New system adds category organization
- Both can coexist

---

## 📝 Adding New Categories

1. **Create folder:**
   ```bash
   mkdir /path/to/Trainer/Training_Data-Sets/MyCategory
   ```

2. **Add training data:**
   ```bash
   # Add .jsonl files to folder
   ```

3. **Copy training script:**
   ```bash
   cp Tools/train.py MyCategory/train.py
   ```

4. **Edit script:**
   Update category name and configuration

5. **Refresh GUI:**
   Click any category to refresh the list

---

## 🎓 Best Practices

1. **Separate concerns** - Keep different training types in different categories
2. **Name meaningfully** - Use descriptive category and script names
3. **Version scripts** - Create dated copies before major changes
4. **Test incrementally** - Start with small epochs, increase gradually
5. **Monitor output** - Check `Models/` folder for results
6. **Track stats** - Use Models tab to view training statistics

---

## 🐛 Troubleshooting

### "No training data files found"
- Ensure `.jsonl` files exist in category folder
- Check file permissions

### "Training engine not found"
- Verify `training_engine.py` exists in `Data/` folder
- Check Python path configuration

### "CUDA/GPU errors"
- Ensure running on machine with NVIDIA GPU
- Check Unsloth installation

### Script changes not appearing in GUI
- Close and reopen the GUI
- Check file was saved correctly

---

## 📚 References

- Core Engine: `/Data/training_engine.py`
- Category Scripts: `/Training_Data-Sets/*/train.py`
- GUI Panel: `/Data/tabs/training_tab/category_manager_panel.py`
- Legacy Script: `/Data/train_with_unsloth.py`

