#!/usr/bin/env python3
"""
OpenCode Tool Training with Unsloth
Fast fine-tuning for tool usage
"""

import json
import torch
import os
from pathlib import Path
from datetime import datetime
from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import Dataset

# Import config for paths
import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import MODELS_DIR, DATA_DIR, save_training_stats

# Configuration
MAX_SEQ_LENGTH = 2048
DTYPE = None  # Auto-detect
LOAD_IN_4BIT = True  # Use 4-bit quantization

# Model configuration
MODEL_NAME = os.getenv("BASE_MODEL", "unsloth/Qwen2.5-Coder-1.5B-Instruct")  # Get model from env or use default

# Get training data path from environment (set by GUI) or use default
TRAINING_DATA_PATH = os.getenv("TRAINING_DATA_FILE", str(DATA_DIR / "exports" / "training_data.jsonl"))

# Get training config from environment (set by GUI) or use defaults
NUM_EPOCHS = int(os.getenv("TRAINING_EPOCHS", "3"))
BATCH_SIZE = int(os.getenv("TRAINING_BATCH_SIZE", "2"))
LEARNING_RATE = float(os.getenv("TRAINING_LEARNING_RATE", "2e-4"))

# Create timestamped output directory in Models/
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
# Clean model name for directory
clean_model_name = MODEL_NAME.replace("unsloth/", "").replace("-Instruct", "").replace("/", "_")
OUTPUT_DIR = MODELS_DIR / f"training_{clean_model_name}_{timestamp}"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Training configuration
GRADIENT_ACCUMULATION_STEPS = 4
MAX_STEPS = -1  # -1 means train for full epochs

# LoRA configuration
LORA_R = 16
LORA_ALPHA = 16
LORA_DROPOUT = 0
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj",
                   "gate_proj", "up_proj", "down_proj"]

print("=" * 60)
print("  OpenCode Tool Training with Unsloth")
print("=" * 60)
print()

print(f"📁 Training Data: {TRAINING_DATA_PATH}")
print(f"📊 Configuration:")
print(f"   Training Runs (Epochs): {NUM_EPOCHS}")
print(f"   Batch Size: {BATCH_SIZE}")
print(f"   Learning Rate: {LEARNING_RATE}")
print(f"📂 Output Directory: {OUTPUT_DIR}")
print()

# Load model and tokenizer
print(f"📦 Loading model: {MODEL_NAME}")
print(f"   Using 4-bit quantization: {LOAD_IN_4BIT}")

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=DTYPE,
    load_in_4bit=LOAD_IN_4BIT,
)

print("✓ Model loaded")
print()

# Apply LoRA adapters
print(f"🔧 Applying LoRA adapters (r={LORA_R}, alpha={LORA_ALPHA})")

model = FastLanguageModel.get_peft_model(
    model,
    r=LORA_R,
    target_modules=TARGET_MODULES,
    lora_alpha=LORA_ALPHA,
    lora_dropout=LORA_DROPOUT,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)

print("✓ LoRA adapters applied")
print()

# Load training data
print(f"📚 Loading training data: {TRAINING_DATA_PATH}")

def load_training_data(path):
    """Load JSONL training data and convert to dataset"""
    data = []
    with open(path, 'r') as f:
        for line in f:
            example = json.loads(line)
            messages = example.get("messages", [])

            # Convert messages to chat format
            conversation = []
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")

                if role == "system":
                    conversation.append({"role": "system", "content": content})
                elif role == "user":
                    conversation.append({"role": "user", "content": content})
                elif role == "assistant":
                    conversation.append({"role": "assistant", "content": content})

            # Format as text using tokenizer's chat template
            if conversation:
                text = tokenizer.apply_chat_template(
                    conversation,
                    tokenize=False,
                    add_generation_prompt=False
                )
                data.append({"text": text})

    return Dataset.from_list(data)

dataset = load_training_data(TRAINING_DATA_PATH)
print(f"✓ Loaded {len(dataset)} training examples")
print()

# Setup trainer
print("🎯 Setting up trainer")
print(f"   Batch size: {BATCH_SIZE}")
print(f"   Gradient accumulation: {GRADIENT_ACCUMULATION_STEPS}")
print(f"   Learning rate: {LEARNING_RATE}")
print(f"   Epochs: {NUM_EPOCHS}")
print()

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    dataset_num_proc=2,
    packing=False,  # Don't pack sequences
    args=TrainingArguments(
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        warmup_steps=5,
        max_steps=MAX_STEPS,
        num_train_epochs=NUM_EPOCHS,
        learning_rate=LEARNING_RATE,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir=OUTPUT_DIR,
        report_to="none",  # Don't report to wandb/tensorboard
        save_steps=100,
        save_total_limit=2,
    ),
)

# Train!
print("🚀 Starting training...")
print("=" * 60)
print()

trainer_stats = trainer.train()

print()
print("=" * 60)
print("✓ Training complete!")
print()
print(f"📊 Training Stats:")
print(f"   Total steps: {trainer_stats.global_step}")
print(f"   Training loss: {trainer_stats.training_loss:.4f}")
print(f"   Time: {trainer_stats.metrics.get('train_runtime', 0):.2f}s")
print()

# Save model
print(f"💾 Saving model to {OUTPUT_DIR}")

model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print("✓ Model saved")
print()

# Save training statistics
print("📈 Saving training statistics...")
try:
    enable_stat_saving = os.getenv("RUNNER_ENABLE_STAT_SAVING", "True").lower() == "true"
    if enable_stat_saving:
        stats_data = {
            "total_steps": trainer_stats.global_step,
            "training_loss": float(trainer_stats.training_loss),
            "eval_loss": float(trainer_stats.metrics.get('eval_loss', 0.0)), # Add eval_loss
            "train_runtime": float(trainer_stats.metrics.get('train_runtime', 0)),
            "epochs": NUM_EPOCHS,
            "batch_size": BATCH_SIZE,
            "learning_rate": LEARNING_RATE,
            "training_examples": len(dataset),
            "output_dir": str(OUTPUT_DIR.name),
            "base_model": MODEL_NAME
        }
        save_training_stats(MODEL_NAME, stats_data)
        print("✓ Statistics saved")
    else:
        print("ℹ️ Statistics saving disabled by runner settings.")
except Exception as e:
    print(f"⚠️  Failed to save statistics: {e}")
print()



print("=" * 60)
print("  Training Complete!")
print("=" * 60)
print()
print("Next steps:")
print("1. Test the model:")
print(f"   python3 test_trained_model.py")
print()
print("2. Or load in OpenCode:")
print(f"   - Edit config.yaml")
print(f"   - Set model.name: {OUTPUT_DIR}")
print()
