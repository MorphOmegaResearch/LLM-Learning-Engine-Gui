#!/bin/bash
# ============================================================================
# OpenCode Trainer - Automated Setup Script
# ============================================================================

set -e  # Exit on error

echo "============================================================================"
echo "  OpenCode Trainer Setup"
echo "============================================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 not found. Please install Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    print_error "Python $REQUIRED_VERSION or higher required. Found: $PYTHON_VERSION"
    exit 1
fi

print_success "Python $PYTHON_VERSION detected"

# Check for Ollama
echo ""
echo "Checking for Ollama..."
if ! command -v ollama &> /dev/null; then
    print_warning "Ollama not found. Install from: https://ollama.com/download"
else
    print_success "Ollama installed"
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
VENV_PATH="Data/Data/venvs/unsloth"

if [ -d "$VENV_PATH" ]; then
    print_warning "Virtual environment already exists at $VENV_PATH"
    read -p "Delete and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_PATH"
        python3 -m venv "$VENV_PATH"
        print_success "Virtual environment recreated"
    else
        print_warning "Using existing virtual environment"
    fi
else
    mkdir -p "$(dirname "$VENV_PATH")"
    python3 -m venv "$VENV_PATH"
    print_success "Virtual environment created at $VENV_PATH"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"
print_success "Virtual environment activated"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip -q
print_success "Pip upgraded"

# Install dependencies
echo ""
echo "Installing dependencies from requirements.txt..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    print_success "Dependencies installed"
else
    print_error "requirements.txt not found"
    exit 1
fi

# Ask about Unsloth
echo ""
read -p "Install Unsloth for GPU acceleration? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing Unsloth..."
    pip install "unsloth[cu121] @ git+https://github.com/unslothai/unsloth.git"
    print_success "Unsloth installed"
else
    print_warning "Skipping Unsloth installation (CPU mode only)"
fi

# Ask about OpenCode
echo ""
read -p "Install OpenCode? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing OpenCode..."
    if pip install opencode 2>/dev/null; then
        print_success "OpenCode installed"
    else
        print_warning "OpenCode not available via pip. Install manually if needed."
    fi
else
    print_warning "Skipping OpenCode installation"
fi

# Create necessary directories
echo ""
echo "Creating necessary directories..."
mkdir -p Models
mkdir -p exports
mkdir -p Training_Data-Sets/Tools
mkdir -p Training_Data-Sets/Lineage
mkdir -p Data/tabs/custom_code_tab/chat_history
print_success "Directories created"

# Verify installation
echo ""
echo "Verifying installation..."
python3 -c "import torch; import transformers; import datasets; import peft; import trl" 2>/dev/null
if [ $? -eq 0 ]; then
    print_success "All core packages verified"
else
    print_error "Some packages failed to import. Check installation."
fi

# Create launch script
echo ""
echo "Creating launch script..."
cat > launch_trainer.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source Data/Data/venvs/unsloth/bin/activate
python Data/interactive_trainer_gui.py
EOF
chmod +x launch_trainer.sh
print_success "Launch script created: ./launch_trainer.sh"

# Print success message
echo ""
echo "============================================================================"
print_success "Setup complete!"
echo "============================================================================"
echo ""
echo "Next steps:"
echo "  1. Activate environment: source Data/Data/venvs/unsloth/bin/activate"
echo "  2. Launch trainer: ./launch_trainer.sh"
echo "  3. Or run manually: python Data/interactive_trainer_gui.py"
echo ""
echo "For Ollama models:"
echo "  - List: ollama list"
echo "  - Pull: ollama pull qwen2.5-coder:1.5b"
echo ""
echo "Documentation:"
echo "  - README.md - Full documentation"
echo "  - GITHUB_UPLOAD_GUIDE.md - GitHub setup"
echo "  - extras/blueprints/ - System architecture"
echo ""
print_success "Happy training! 🚀"
echo ""
