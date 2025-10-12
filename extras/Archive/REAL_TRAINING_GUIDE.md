# Real Training Guide for OpenCode Tools

## ⚠️ IMPORTANT: Understanding "Live Training"

The current "live training" feature **does NOT actually train the model**. It only validates that the model can respond to examples. This is a limitation of Ollama's API - it doesn't support real-time fine-tuning.

### What Actually Happens:
- ✅ Training data is generated (200+ examples)
- ✅ Model is loaded
- ❌ "Training" is just inference (asking model questions)
- ❌ Model doesn't learn from examples
- ❌ Model responds conversationally instead of with tool calls

### Why 0% Pass Rate?
The model hasn't been trained on tool usage, so it responds like a normal chatbot instead of outputting JSON tool calls.

---

## ✅ How to Actually Train Your Model

### Step 1: Generate Training Data
```bash
# Run the trainer to generate data
python3 tool_trainer.py

# Choose your model
# Set duration (doesn't matter for data generation)
# DISABLE live training (n) - we just want the data
```

This creates: `training_<model>_<timestamp>/training_data/training_set_<timestamp>.json`

### Step 2: Export for Fine-Tuning
```bash
# Export training data in all formats
python3 export_for_finetuning.py training_Qwen-Custom_20251004_050452/training_data/training_set_20251004_050452.json

# Or specify custom names
python3 export_for_finetuning.py \
    --data training_set.json \
    --model-name qwen-opencode-tools \
    --base-model qwen2.5-coder:1.5b \
    --output exports/
```

This creates:
- `Modelfile_<model>` - Ollama format
- `training_data.jsonl` - Generic JSONL format
- `hf_training_data.json` - Hugging Face format
- `train_model.sh` - Automated training script

### Step 3: Fine-Tune with Ollama

#### Option A: Automated Script
```bash
cd exports/
./train_model.sh
```

#### Option B: Manual Command
```bash
cd exports/
ollama create qwen-opencode-tools -f Modelfile_qwen-opencode-tools
```

### Step 4: Test Your Trained Model
```bash
# Test in terminal
ollama run qwen-opencode-tools

# Ask it to use a tool
> "Create a file called test.txt with hello world"

# It should respond with:
> {"type":"tool_call","name":"file_write","args":{"file_path":"test.txt","content":"Hello World"}}
```

### Step 5: Use in OpenCode
Edit your `config.yaml`:
```yaml
model:
  name: qwen-opencode-tools  # Your trained model
  temperature: 0.3
  max_tokens: 2048
```

---

## 📊 Expected Results After Training

### Before Training:
```
User: "Create a file called test.txt"
Model: "Sure! I can help you create that file. You can use the touch command..."
❌ Conversational response, no tool call
```

### After Training:
```
User: "Create a file called test.txt"
Model: {"type":"tool_call","name":"file_write","args":{"file_path":"test.txt","content":""}}
✅ Proper tool call JSON
```

---

## 🔧 Alternative Fine-Tuning Methods

### Method 1: Ollama Modelfile (Recommended)
- **Pros**: Simple, built into Ollama
- **Cons**: Limited customization
- **Use case**: Quick training for small models

```bash
ollama create model-name -f Modelfile
```

### Method 2: Hugging Face Transformers
- **Pros**: Full control, advanced features
- **Cons**: Complex setup, requires GPU
- **Use case**: Production models, advanced tuning

```python
from transformers import AutoModelForCausalLM, TrainingArguments, Trainer
# ... full fine-tuning code
```

### Method 3: Unsloth (Fast Fine-Tuning)
- **Pros**: 2x faster, less memory
- **Cons**: Limited model support
- **Use case**: Fast iteration

```python
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained(...)
# ... training code
```

### Method 4: LLaMA Factory
- **Pros**: GUI, easy to use, many features
- **Cons**: Another tool to learn
- **Use case**: Non-programmers, experimentation

```bash
llamafactory-cli train --config training_config.yaml
```

---

## 📈 Training Tips

### 1. Start Small
- Use 50-100 examples first
- Test after training
- Scale up if results are good

### 2. Quality Over Quantity
- Better to have 50 perfect examples than 500 mediocre ones
- Focus on the tools you use most
- Include error recovery examples

### 3. Model Selection
Best models for tool training:
- ✅ **Qwen2.5-Coder 1.5B-3B**: Fast, good results
- ✅ **Llama 3.2 3B**: Balanced performance
- ✅ **Phi-3 3.8B**: Good reasoning
- ⚠️ **Smaller (<1B)**: May struggle with complex tool chains
- ⚠️ **Larger (>7B)**: Slower, may not need training

### 4. Test Before and After
```bash
# Before training
ollama run qwen2.5-coder:1.5b
> "List Python files"
> Response: (conversational)

# After training
ollama run qwen-opencode-tools
> "List Python files"
> Response: {"type":"tool_call",...}
```

---

## 🐛 Troubleshooting

### Issue: Model still responds conversationally after training
**Solution**:
- Check that training completed successfully (`ollama list` should show your model)
- Verify training data format (should be JSON tool calls)
- Try more training examples (increase from 50 to 200)

### Issue: Model outputs malformed JSON
**Solution**:
- Add more examples with correct JSON format
- Lower temperature (0.1-0.3)
- Add validation examples to training data

### Issue: Model hallucinates parameters
**Solution**:
- Add examples showing what to do when parameters are missing
- Include error recovery scenarios
- Train on "ask user for clarification" examples

### Issue: Training takes too long
**Solution**:
- Use smaller base model (1.5B instead of 3B)
- Reduce number of examples
- Use GPU if available

---

## 📚 What's in the Training Data?

### File Operations (35% of examples)
- file_read, file_write, file_edit, file_delete
- With and without directories
- Error handling (file not found, permissions)

### Search Operations (25% of examples)
- file_search with patterns
- grep_search with regex
- directory_list
- Auto-chain behaviors

### System Operations (15% of examples)
- system_info
- process_manage
- bash_execute (careful with this one!)

### Git Operations (10% of examples)
- git status, log, diff
- Workflow scenarios

### Complex Workflows (15% of examples)
- Multi-tool scenarios
- Project setup flows
- Debug session flows
- Code review flows

---

## ✅ Success Metrics

After training, your model should achieve:
- **>80% pass rate**: Correct JSON format
- **>90% success rate**: Tool calls execute without errors
- **<5% invalid formats**: Malformed JSON
- **Auto-chain understanding**: Knows when files are auto-read

Test with:
```bash
python3 tool_trainer.py
# Choose your TRAINED model
# Enable live training (y)
# Check final statistics
```

---

## 🎓 Next Steps

1. Generate your training data
2. Export to Modelfile format
3. Run `ollama create`
4. Test with OpenCode
5. Iterate based on results

Happy training! 🚀
