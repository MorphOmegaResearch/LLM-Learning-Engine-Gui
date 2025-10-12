# GitHub Upload Guide for OpenCode Trainer

## Overview
This guide explains what to upload to GitHub and how to handle the 7.6GB project efficiently.

## Repository Structure After Upload (< 50 MB)

```
OpenCode-Trainer/
├── Data/                           # Core application code (~11 MB)
│   ├── tabs/                       # UI tabs (models, training, custom code)
│   ├── training_engine.py          # Training engine
│   ├── evaluation_engine.py        # Evaluation system
│   ├── config.py                   # Configuration
│   ├── tool_trainer.py             # Tool training generator
│   └── interactive_trainer_gui.py  # Main GUI
├── Training_Data-Sets/             # Training data & test suites (~392 KB)
│   ├── Scripts/                    # Training scripts
│   ├── Tools/                      # Tool definitions & schemas
│   ├── Prompts/                    # System prompts
│   ├── Test/                       # Test suites
│   └── Schemas/                    # Tool schemas
├── extras/                         # Documentation & plans (~792 KB)
│   ├── blueprints/                 # System blueprints
│   └── Plans/                      # Project plans
├── .gitignore                      # Git ignore rules
├── README.md                       # Project documentation
├── requirements.txt                # Python dependencies
├── setup.sh                        # Setup script
└── GITHUB_UPLOAD_GUIDE.md          # This file

EXCLUDED (7.6 GB):
├── Data/Data/venvs/               # Virtual environments (7.5 GB)
├── Models/                        # Trained models (1.1 GB)
├── exports/                       # GGUF exports (949 MB)
└── __pycache__/                   # Python cache
```

## What to Upload (Total: ~12 MB)

### ✅ Essential Code (Must Upload)
```bash
Data/
├── tabs/                          # All UI components
│   ├── models_tab/
│   ├── training_tab/
│   └── custom_code_tab/
├── *.py                          # All Python scripts
├── config.py
├── training_engine.py
├── evaluation_engine.py
└── tool_trainer.py
```

### ✅ Configuration Templates
```bash
Data/tabs/custom_code_tab/
├── custom_code_settings.json     # Basic settings
├── advanced_settings.json        # Advanced systems config
├── mode_settings.json            # Mode configurations
├── tool_settings.json            # Tool enable/disable
├── system_prompts/               # System prompt templates
└── tool_schemas_configs/         # Tool schema profiles
```

### ✅ Training Assets
```bash
Training_Data-Sets/
├── Scripts/                      # Training scripts (Python/Shell)
├── Tools/                        # Tool definitions
├── Prompts/                      # System prompts
├── Test/                         # Test suites & questions
└── Schemas/                      # Tool JSON schemas
```

### ✅ Documentation
```bash
extras/
├── blueprints/                   # System architecture docs
└── Plans/                        # Development plans
```

### ✅ Project Root
```bash
.gitignore                        # Git ignore rules
README.md                         # Project documentation
requirements.txt                  # Python dependencies
setup.sh                          # Setup script
launch_trainer.sh                 # Launch script
```

## ❌ What NOT to Upload (7.6 GB excluded)

### Models & Weights (1.1 GB)
- `Models/` directory
- `*.safetensors`, `*.bin`, `*.pt` files
- Checkpoint directories
- **Why:** Too large for GitHub, users train their own models

### Exports (949 MB)
- `exports/` directory
- `*.gguf` files (quantized models)
- **Why:** Generated outputs, users create their own

### Virtual Environments (7.5 GB)
- `Data/Data/venvs/`
- Any `venv/`, `env/`, `.venv/` directories
- **Why:** Recreated with `pip install -r requirements.txt`

### Runtime Data
- `__pycache__/` directories
- `*.pyc`, `*.pyo` files
- Log files (`*.log`, `DeBug/`)
- Chat history sessions
- Tool call logs (runtime generated)
- **Why:** Temporary/generated files

## Step-by-Step Upload Process

### Method 1: GitHub Web UI (Recommended for First Upload)

1. **Create GitHub Repository**
   ```
   - Go to github.com
   - Click "New Repository"
   - Name: "OpenCode-Trainer" or similar
   - Add description
   - Choose Public or Private
   - DON'T initialize with README (we have one)
   ```

2. **Initialize Git Locally**
   ```bash
   cd /home/commander/Desktop/Trainer
   git init
   git add .
   git commit -m "Initial commit: OpenCode Trainer v1.9f"
   ```

3. **Link to GitHub**
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/OpenCode-Trainer.git
   git branch -M main
   git push -u origin main
   ```

### Method 2: GitHub CLI (Faster)

```bash
cd /home/commander/Desktop/Trainer

# Install GitHub CLI if not installed
# sudo apt install gh

gh auth login
gh repo create OpenCode-Trainer --public --source=. --remote=origin --push
```

### Method 3: ZIP Upload (If Git Fails)

```bash
cd /home/commander/Desktop/Trainer

# Create clean archive (excludes .gitignore patterns)
git init
git add .
git archive -o ../OpenCode-Trainer.zip HEAD

# Upload OpenCode-Trainer.zip via GitHub web UI
```

## Verify Upload Size

Before pushing, check the size:

```bash
cd /home/commander/Desktop/Trainer

# Show what will be committed (should be < 50 MB)
git add .
du -sh $(git ls-files) | awk '{total+=$1} END {print total "M"}'

# Or check with git directly
git count-objects -vH
```

## Post-Upload Setup for Other Developers

After cloning, developers need to:

```bash
# 1. Clone repository
git clone https://github.com/YOUR_USERNAME/OpenCode-Trainer.git
cd OpenCode-Trainer

# 2. Create virtual environment
python3 -m venv Data/Data/venvs/unsloth

# 3. Activate and install dependencies
source Data/Data/venvs/unsloth/bin/activate
pip install -r requirements.txt

# 4. Create necessary directories
mkdir -p Models exports
mkdir -p Training_Data-Sets/Tools
mkdir -p Training_Data-Sets/Lineage

# 5. Run setup script (if provided)
chmod +x setup.sh
./setup.sh
```

## Managing Large Model Files (Optional)

If you want to share trained models:

### Option A: Git LFS (Large File Storage)
```bash
git lfs install
git lfs track "*.safetensors"
git lfs track "*.gguf"
git add .gitattributes
git commit -m "Add LFS tracking"
```

### Option B: External Storage
- Upload models to Hugging Face Hub
- Share Google Drive/Dropbox links in README
- Use release attachments (< 2GB each)

## Repository Maintenance

### Keep .gitignore Updated
```bash
# Add new patterns as needed
echo "new_large_dir/" >> .gitignore
git add .gitignore
git commit -m "Update gitignore"
```

### Check Repository Size
```bash
# Should stay under 100MB for optimal GitHub performance
git count-objects -vH
```

### Clean Up if Needed
```bash
# Remove accidentally committed large files
git filter-branch --tree-filter 'rm -rf Models/' HEAD
git push origin --force
```

## Troubleshooting

### "File too large" Error
```bash
# Find large files
find . -type f -size +10M

# Check what's being committed
git ls-files --cached | xargs du -sh | sort -h | tail -20

# Remove from staging
git rm --cached path/to/large/file
```

### Push Rejected
```bash
# If pushing fails due to size
git push origin main --force-with-lease
```

### Clean Working Directory
```bash
# Remove untracked files matching .gitignore
git clean -fdX
```

## Expected GitHub Repository Size

| Component              | Size      |
|------------------------|-----------|
| Source Code (Data/)    | ~11 MB    |
| Training Assets        | ~400 KB   |
| Documentation          | ~800 KB   |
| Configuration          | ~100 KB   |
| **Total**              | **~12 MB**|

**Excluded:** 7.6 GB (models, venvs, exports)

## Next Steps After Upload

1. ✅ Create README.md with project overview
2. ✅ Add LICENSE file (MIT, GPL, etc.)
3. ✅ Create CONTRIBUTING.md for contributors
4. ✅ Add requirements.txt for dependencies
5. ✅ Create setup.sh for automated setup
6. ✅ Add GitHub Actions for CI/CD (optional)
7. ✅ Create release tags for versions

## Questions?

Check .gitignore to see what's excluded. The repository should be ~12MB after upload.
