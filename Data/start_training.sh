#!/bin/bash
# Quick start script for OpenCode Tool Trainer

echo "=========================================="
echo "  OpenCode Tool Training System"
echo "=========================================="
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "Warning: Ollama is not installed or not in PATH"
    echo "Please install Ollama from: https://ollama.ai"
    exit 1
fi

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Warning: Ollama is not running"
    echo "Please start Ollama first: ollama serve"
    exit 1
fi

# Check dependencies
if ! python3 -c "import aiohttp" 2>/dev/null; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
fi

# Run trainer
echo "Starting trainer..."
echo ""
python3 tool_trainer.py
