# OpenCode Tool Trainer

Comprehensive training system for teaching small LLMs (3B-4B parameters) to use OpenCode tools correctly.

## Features

### 🎯 Core Capabilities
- **Interactive Model Selection**: Browse and select from all available Ollama models
- **Safe Model Copying**: Clone models for training without affecting originals
- **Comprehensive Training Data**: 200+ examples covering all OpenCode tools
- **Live Training**: Real-time training and evaluation with Ollama API
- **Train/Eval Split**: Automatic 80/20 split for proper evaluation
- **Detailed Analytics**: Complete logs, stats, and performance metrics

### 📚 Training Scenarios
1. **File Operations**: read, write, edit, delete, copy, move
2. **Search Operations**: file_search, grep_search, directory_list
3. **System Operations**: system_info, process_manage
4. **Git Operations**: status, log, diff
5. **Web Operations**: web_search, web_fetch
6. **Auto-Chain Workflows**: Teaches automatic tool chaining behavior
7. **Error Recovery**: Handles failures gracefully
8. **Complex Workflows**: Multi-tool scenarios (project setup, debugging, code review)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run trainer (interactive)
./start_training.sh

# Or run directly
python3 tool_trainer.py
```

## Training Process

### 1. Model Selection
```
=== Available Ollama Models ===
1. qwen2.5-coder:1.5b
2. llama3.2:3b
3. phi3:3.8b

Select model (1-3):
```

### 2. Copy Model (Optional)
```
Copy 'qwen2.5-coder:1.5b' to new training model? (y/n): y
Enter new model name: qwen-tools-trained
```

### 3. Configure Training
```
Enter training duration in hours: 1.5
Enable live training with Ollama? (y/n): y
```

### 4. Training Execution
- Generates comprehensive training examples
- Splits into training (80%) and evaluation (20%) sets
- Trains model on each example
- Validates tool call format
- Evaluates on test set
- Saves all data and statistics

## Output Structure

```
training_<model>_<timestamp>/
├── logs/
│   └── training_<timestamp>.log          # Detailed training logs
├── training_data/
│   ├── training_set_<timestamp>.json     # Training examples
│   └── eval_set_<timestamp>.json         # Evaluation examples
└── stats/
    └── training_stats_<timestamp>.json   # Performance metrics
```

## Training Data Format

### Example Structure
```json
{
  "scenario": "file_write_basic",
  "conversation": [
    {
      "role": "user",
      "content": "Create a file called test.txt with hello world"
    },
    {
      "role": "assistant",
      "content": "{\"type\":\"tool_call\",\"name\":\"file_write\",\"args\":{\"file_path\":\"test.txt\",\"content\":\"Hello World\"}}"
    },
    {
      "role": "system",
      "content": "{\"success\":true,\"output\":\"File written successfully\"}"
    },
    {
      "role": "assistant",
      "content": "Created test.txt with content 'Hello World'"
    }
  ]
}
```

### Key Training Points

#### ✅ Correct Tool Format
```json
{"type":"tool_call","name":"file_write","args":{"file_path":"test.txt","content":"Hello"}}
```

#### ✅ Correct Parameter Names
- `file_path` (not `path`)
- `file_pattern` (not `pattern` for grep)
- `operation` (for git, process management)

#### ✅ Auto-Chain Awareness
Models learn that:
- `file_search` → automatically reads first result
- `directory_list` → automatically reads discovered files
- Both search results + file contents returned in one response

## Statistics & Metrics

### Training Summary
```
==================================================
              Training Summary
==================================================
Model: qwen-tools-trained
Duration: 1.25 hours
Training Examples: 160
Evaluation Examples: 40
Total Examples: 200
Successful Tool Calls: 152
Failed Tool Calls: 8
Invalid Formats: 12
Success Rate: 95.0%
Pass Rate: 82.5%
Avg Response Time: 850ms
Auto Chains Used: 25
==================================================
```

### Metrics Tracked
- **Success Rate**: % of tool calls that executed successfully
- **Pass Rate**: % of tool calls with correct JSON format
- **Invalid Formats**: Tool calls with malformed JSON
- **Response Time**: Average generation time per example
- **Auto Chains**: Number of auto-chain examples completed

## Advanced Usage

### Custom Configuration

```python
from tool_trainer import TrainingConfig, OpenCodeToolTrainer

config = TrainingConfig(
    model_name="your-model",
    training_hours=2.0,
    max_examples_per_tool=100,
    enable_auto_chains=True,
    enable_live_training=True,
    evaluation_split=0.2,
    temperature=0.3,
    context_length=4096
)

trainer = OpenCodeToolTrainer(config)
await trainer.train_model()
```

### Training Data Only (No Live Training)

```bash
# Generate training data without live training
python3 tool_trainer.py
# Select model
# Set duration
# Choose 'n' for live training
```

This will generate all training examples and save them for use with external fine-tuning tools.

## Integration

### With Fine-Tuning Tools
The generated training data can be used with:
- Ollama fine-tuning (when available)
- Hugging Face trainers
- OpenAI fine-tuning format (with conversion)
- Custom fine-tuning pipelines

### Format Conversion
```python
import json

# Load OpenCode training data
with open('training_set.json') as f:
    data = json.load(f)

# Convert to your format
# ... conversion logic ...
```

## Tips for Best Results

### 1. Start Small
- Begin with 1-2 hour training sessions
- Use 50-100 examples per tool category
- Evaluate before scaling up

### 2. Model Selection
- 3B-4B models work best (Qwen2.5-Coder, Llama3.2, Phi3)
- Smaller models may struggle with complex chains
- Larger models (7B+) may not need as much training

### 3. Focus Areas
- Emphasize correct JSON format
- Practice auto-chain scenarios
- Include error handling examples

### 4. Evaluation
- Use 20% evaluation split minimum
- Check pass rate (should be >80%)
- Monitor invalid format count

## Troubleshooting

### Ollama Not Running
```bash
# Start Ollama
ollama serve

# Or in background
nohup ollama serve > /dev/null 2>&1 &
```

### Model Not Found
```bash
# List available models
ollama list

# Pull a model
ollama pull qwen2.5-coder:1.5b
```

### Training Timeout
```python
# Increase timeout in session_manager.py
timeout=aiohttp.ClientTimeout(total=600)  # 10 minutes
```

### Memory Issues
```python
# Reduce batch size
config.max_examples_per_tool = 25  # Lower from 50
```

## License

This training system is designed for OpenCode and follows the same license as the main project.

## Support

For issues or questions:
1. Check the generated logs in `training_<model>/logs/`
2. Review training stats in `training_<model>/stats/`
3. Examine training data in `training_<model>/training_data/`
