# OpenCode Trainer 🚀

**A comprehensive GUI-based training and evaluation system for fine-tuning small language models with OpenCode tool integration.**

> Version 1.9f - Mode Integration & UX Improvements

---

## 🎯 Overview

OpenCode Trainer is a powerful, user-friendly system for training, evaluating, and managing small language models (1.5B-7B parameters) with a focus on tool-calling capabilities. It integrates 37 OpenCode v1.2 advanced systems, providing a complete pipeline from data preparation to model deployment.

### Key Features

- 🖥️ **Full-Featured GUI** - Intuitive tkinter-based interface with 4 main tabs
- 🔧 **Tool System** - 20+ OpenCode tools with custom profiles and schemas
- 🎓 **Training Pipeline** - LoRA fine-tuning with CPU/GPU support via Unsloth
- 📊 **Evaluation Framework** - Comprehensive test suites and benchmarking
- 💬 **Chat Interface** - Interactive testing with advanced mode system
- 📈 **Analytics** - Real-time skill tracking and model comparison
- 🧬 **Lineage Tracking** - Full model ancestry and training history
- 🎮 **Gamification** - Model typing and ranking system (planned)

---

## 📋 Table of Contents

- [Features](#-features)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
- [Usage](#-usage)
- [Configuration](#-configuration)
- [Development](#-development)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

### 🏗️ Mode System (Standard / Fast / Smart / Think)

- **4 Operating Modes** with different system enablement levels
- **Per-Mode Parameters** - Customizable context tokens, resource usage, quality settings
- **Visual Indicators** - Shows which systems are active in each mode
- **Quick Switching** - Modal dialog for fast mode changes during chat

### 🔧 Tool Management

- **20+ OpenCode Tools** - File operations, search, git, web, system info
- **Tool Profiles** - Predefined configurations (read-only, dev-full, git-workflow)
- **Enable/Disable Control** - Fine-grained tool access management
- **Tool Schema Selector** - Dynamic schema switching in chat interface

### 🎓 Training System

- **LoRA Fine-Tuning** - Efficient adapter-based training
- **CPU/GPU Support** - Works with or without CUDA
- **Unsloth Integration** - 2x faster training on supported GPUs
- **Category-Based Training** - Organize training by skill categories
- **Auto-Evaluation** - Post-training benchmarking
- **Lineage Recording** - Track model family trees

### 📊 Evaluation & Benchmarking

- **Test Suites** - Tools, Coding, Reasoning, and custom suites
- **Per-Tool Metrics** - Success rates, confusion matrices, difficulty analysis
- **Real-Time Scoring** - Live evaluation during chat sessions
- **Comparison Mode** - Compare models side-by-side
- **Report Generation** - JSON evaluation reports with full details

### 💬 Chat Interface (Custom Code Tab)

- **Mode System** - Standard/Fast/Smart/Think modes
- **System Prompts** - Multiple prompt templates
- **Tool Schemas** - Dynamic tool filtering
- **Training Mode** - Collect data for fine-tuning
- **Chat History** - Session management and restoration
- **Advanced Settings** - 37 OpenCode systems with 252 settings

### 📈 Models Tab

- **Model Management** - View, organize, and compare models
- **Skills Display** - Runtime and evaluation skill tracking
- **Statistics** - Training history, performance metrics
- **Lineage View** - Model ancestry and evolution
- **GGUF Export** - Quantization for Ollama deployment
- **Adapter Management** - Merge, promote, and manage LoRA adapters

---

## 🚀 Installation

### Prerequisites

- **Python 3.10+**
- **Ubuntu 20.04+** or compatible Linux distribution
- **Ollama** installed and running ([installation guide](https://ollama.com/download))
- **8GB+ RAM** (16GB recommended)
- **NVIDIA GPU** with 8GB+ VRAM (optional, for training)

### Step 1: Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/OpenCode-Trainer.git
cd OpenCode-Trainer
```

### Step 2: Set Up Virtual Environment

```bash
# Create virtual environment
python3 -m venv Data/Data/venvs/unsloth

# Activate environment
source Data/Data/venvs/unsloth/bin/activate
```

### Step 3: Install Dependencies

```bash
# Install base dependencies
pip install -r requirements.txt

# Install Unsloth (GPU support, optional)
pip install "unsloth[cu121] @ git+https://github.com/unslothai/unsloth.git"

# Install OpenCode (if available)
pip install opencode
```

### Step 4: Create Necessary Directories

```bash
mkdir -p Models exports
mkdir -p Training_Data-Sets/Tools
mkdir -p Training_Data-Sets/Lineage
```

### Step 5: Verify Installation

```bash
# Test Python imports
python -c "import torch; import transformers; print('✓ Dependencies installed')"

# Verify Ollama
ollama list
```

---

## ⚡ Quick Start

### Launch the Trainer

```bash
cd /home/commander/Desktop/Trainer
source Data/Data/venvs/unsloth/bin/activate
python Data/interactive_trainer_gui.py
```

Or use the launch script:

```bash
chmod +x launch_trainer.sh
./launch_trainer.sh
```

### First Steps

1. **Models Tab** - View available base models
2. **Training Tab** - Select training scripts and datasets
3. **Custom Code Tab** - Test models with chat interface
4. **Run Training** - Fine-tune a model on your data

### Example Training Workflow

```python
# 1. Select base model: Qwen2.5-Coder-1.5B-Instruct
# 2. Choose training script: Tools category
# 3. Select datasets: tool_training_data.jsonl
# 4. Configure: 3 epochs, batch size 2, lr 2e-4
# 5. Click "Run Training"
# 6. Wait for completion + auto-evaluation
# 7. Export to GGUF and deploy to Ollama
```

---

## 🏛️ Architecture

### Directory Structure

```
OpenCode-Trainer/
├── Data/                          # Core application
│   ├── tabs/                      # UI components
│   │   ├── models_tab/           # Model management
│   │   ├── training_tab/         # Training interface
│   │   └── custom_code_tab/      # Chat & testing
│   ├── training_engine.py        # Training pipeline
│   ├── evaluation_engine.py      # Benchmarking system
│   ├── config.py                 # Configuration
│   └── interactive_trainer_gui.py # Main application
├── Training_Data-Sets/           # Data & assets
│   ├── Scripts/                  # Training scripts
│   ├── Tools/                    # Tool definitions
│   ├── Test/                     # Test suites
│   └── Prompts/                  # System prompts
├── extras/                       # Documentation
│   ├── blueprints/              # System blueprints
│   └── Plans/                   # Development plans
├── Models/                       # Trained models (local)
├── exports/                      # GGUF exports (local)
└── README.md                     # This file
```

### Key Components

| Component | Purpose | Lines |
|-----------|---------|-------|
| `interactive_trainer_gui.py` | Main GUI application | ~800 |
| `training_engine.py` | LoRA training pipeline | ~515 |
| `evaluation_engine.py` | Benchmarking system | ~600+ |
| `models_tab.py` | Model management UI | ~3900 |
| `chat_interface_tab.py` | Chat interface | ~2900 |
| `advanced_settings_tab.py` | OpenCode systems | ~740 |
| `lineage_tracker.py` | Model ancestry | ~464 |
| `tool_call_logger.py` | Data collection | ~288 |

---

## 📖 Usage

### Training a Model

1. **Open Training Tab**
2. **Select Base Model** from dropdown
3. **Choose Training Scripts** (checkbox categories)
4. **Select Datasets** (.jsonl files)
5. **Configure Parameters:**
   - Epochs: 3-5
   - Batch Size: 2-4
   - Learning Rate: 2e-4
   - Max Sequence Length: 2048
6. **Run Training** - Click "Start Training"
7. **Monitor Progress** in console
8. **Review Evaluation** when complete

### Testing Models (Chat Interface)

1. **Open Custom Code Tab → Chat**
2. **Select Model** from dropdown
3. **Mount Model** (click 📌 Mount)
4. **Choose Mode** (Standard/Fast/Smart/Think)
5. **Select System Prompt** and **Tool Schema**
6. **Chat** - Type message and send
7. **Enable Training Mode** to collect data

### Evaluating Models

1. **Open Custom Code Tab → Evaluation**
2. **Select Model** to evaluate
3. **Choose Test Suite** (Tools, Coding, Reasoning)
4. **Select System Prompt & Tool Schema**
5. **Run Benchmark** - Click "Run Evaluation"
6. **View Report** in Models Tab → Stats

### Managing Models

1. **Open Models Tab**
2. **View Model Info** - Click model name
3. **See Skills** - Runtime and evaluation data
4. **Check Lineage** - Model ancestry
5. **Export GGUF** - Quantize for Ollama
6. **Compare Models** - Side-by-side comparison

---

## ⚙️ Configuration

### Mode Settings (`mode_settings.json`)

```json
{
  "current_mode": "smart",
  "mode_parameters": {
    "smart": {
      "resource_usage": "50",
      "max_context_tokens": 8192,
      "generation_step_size": 64,
      "cpu_threads": "default"
    }
  }
}
```

### Tool Settings (`tool_settings.json`)

```json
{
  "enabled_tools": {
    "file_read": true,
    "file_write": true,
    "bash_execute": false,
    "git_operations": true
  }
}
```

### Advanced Settings (`advanced_settings.json`)

37 systems, 252 settings - see blueprints for details.

---

## 🛠️ Development

### Running Tests

```bash
# Unit tests (if available)
pytest tests/

# Integration test
python test_custom_code_tab.py
```

### Code Style

- Python 3.10+ features
- PEP 8 style guide
- Type hints recommended
- Docstrings for all functions

### Contributing Workflow

1. Fork repository
2. Create feature branch
3. Make changes
4. Test thoroughly
5. Submit pull request

See `CONTRIBUTING.md` for details (coming soon).

---

## 📚 Documentation

- **Blueprints** - `extras/blueprints/` - System architecture
- **Plans** - `extras/Plans/` - Development roadmap
- **GitHub Guide** - `GITHUB_UPLOAD_GUIDE.md` - Upload instructions

### Recent Versions

- **v1.9f** - Mode integration, UX improvements, tool fixes
- **v1.9e** - Chat history overhaul
- **v1.9d** - Temperature controls
- **v1.9c** - Full advanced integration (37 systems)

---

## 🤝 Contributing

Contributions are welcome! Areas needing help:

- [ ] Additional test suites
- [ ] Model gamification system (Phase 3)
- [ ] Tool profile training data generation
- [ ] Docker containerization
- [ ] Windows/Mac support
- [ ] Documentation improvements

---

## 📄 License

[Specify your license here - MIT, GPL, Apache, etc.]

---

## 🙏 Acknowledgments

- **Unsloth** - Fast training framework
- **OpenCode** - Tool system integration
- **Ollama** - Local model deployment
- **Hugging Face** - Transformers, PEFT, TRL, Datasets

---

## 📞 Contact

[Your contact information or project links]

- GitHub Issues: [Report bugs and request features]
- Discussions: [Ask questions and share ideas]

---

## 🗺️ Roadmap

### Completed ✅
- [x] Core training pipeline
- [x] Evaluation framework
- [x] Chat interface with modes
- [x] Tool system integration
- [x] Lineage tracking
- [x] Advanced settings (37 systems)

### In Progress 🚧
- [ ] Tool profile unification (Phase 1)
- [ ] Enhanced evaluation metrics (Phase 2)

### Planned 📋
- [ ] Model gamification & evolution (Phase 3)
- [ ] Type-based training selection
- [ ] Profile-based training data generation
- [ ] Export/Import configuration profiles

---

**Built with ❤️ for the open-source AI community**
