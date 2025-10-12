#!/bin/bash
# Quick start script for Unsloth training

echo "=========================================="
echo "  OpenCode Tool Training - Unsloth"
echo "=========================================="
echo ""

# Check GPU
if command -v nvidia-smi &> /dev/null; then
    echo "🎮 GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1
    echo ""
else
    echo "⚠️  No NVIDIA GPU detected"
    echo "Training will be slow on CPU"
    echo ""
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if training data exists
if [ ! -f "exports/training_data.jsonl" ]; then
    echo "❌ Training data not found!"
    echo "Run 'python3 tool_trainer.py' first to generate training data"
    exit 1
fi

# Count training examples
EXAMPLE_COUNT=$(wc -l < exports/training_data.jsonl)
echo "📚 Training data: $EXAMPLE_COUNT examples"
echo ""

# Confirm start
echo "This will:"
echo "  1. Download Qwen2.5-Coder-1.5B-Instruct model (~1.5GB)"
echo "  2. Fine-tune with LoRA adapters (~3 epochs)"
echo "  3. Save trained model to ./trained_model"
echo "  4. Convert to GGUF format for Ollama"
echo ""

read -p "Continue? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled"
    exit 0
fi

echo ""
echo "🚀 Starting training..."
echo ""

# Run training
python3 train_with_unsloth.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Training successful!"
    echo ""
    echo "Test your model:"
    echo "  python3 test_trained_model.py"
    echo ""
    echo "Or use in OpenCode:"
    echo "  Edit config.yaml and set:"
    echo "  model:"
    echo "    name: ./trained_model"
    echo "    provider: transformers"
else
    echo ""
    echo "❌ Training failed"
    exit 1
fi
