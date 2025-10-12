#!/usr/bin/env python3
"""
Training Script: Tools Category
Trains the model on OpenCode tool usage examples
"""

import sys
from pathlib import Path

# Add parent directories to path
SCRIPT_DIR = Path(__file__).parent
TRAINER_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = TRAINER_ROOT / "Data"
sys.path.insert(0, str(DATA_DIR))

from training_engine import TrainingEngine


def main():
    """Train on Tools category data"""
    import os

    print("=" * 60)
    print("  TRAINING: Tools Category")
    print("  OpenCode Tool Usage Training")
    print("=" * 60)
    print()

    # Check if specific files were selected via GUI
    selected_files_env = os.getenv("TRAINING_DATA_FILES", "")

    print(f"🔍 DEBUG: TRAINING_DATA_FILES = '{selected_files_env}'")

    if selected_files_env:
        # Use files selected in GUI
        jsonl_files = [Path(f.strip()) for f in selected_files_env.split(",") if f.strip()]
        print(f"📋 Using {len(jsonl_files)} selected file(s) from GUI")
        for jf in jsonl_files:
            print(f"   → {jf}")
    else:
        # Find all JSONL files in this category
        jsonl_files = list(SCRIPT_DIR.glob("*.jsonl"))
        print(f"📁 Found {len(jsonl_files)} training data file(s) in category")

    if not jsonl_files:
        print("❌ No training data files found!")
        print(f"   Looking in: {SCRIPT_DIR}")
        return

    print(f"\n📊 Selected training files:")
    total_examples = 0
    for f in jsonl_files:
        if not f.exists():
            print(f"   ⚠️  {f} - NOT FOUND (skipping)")
            continue
        with open(f) as file:
            count = sum(1 for _ in file)
            total_examples += count
        print(f"   • {f.name}: {count} examples")

    print(f"\n📊 Total: {total_examples} training examples")
    print()

    # Combine all JSONL files into one
    combined_data = DATA_DIR / "temp_tools_training.jsonl"

    # Delete old temp file to ensure fresh data
    if combined_data.exists():
        combined_data.unlink()
        print(f"🗑️  Removed old temp file")

    print(f"📦 Combining data files → {combined_data.name}")

    with open(combined_data, 'w') as outfile:
        for jsonl_file in jsonl_files:
            if not jsonl_file.exists():
                continue
            with open(jsonl_file) as infile:
                for line in infile:
                    outfile.write(line)

    print("✓ Data files combined")
    print()

    # Training configuration - optimized for 8GB RAM
    config = {
        "category": "Tools",
        "training_data_path": str(combined_data),
        "num_epochs": int(os.getenv("TRAINING_EPOCHS", "1")),  # 1 epoch for testing
        "batch_size": int(os.getenv("TRAINING_BATCH_SIZE", "1")),  # Batch size 1 for 8GB RAM
        "learning_rate": float(os.getenv("TRAINING_LEARNING_RATE", "2e-4")),
        "max_seq_length": int(os.getenv("TRAINING_MAX_SEQ_LENGTH", "128")),  # Reduced to 128 for extreme low memory
        "gradient_accumulation_steps": int(os.getenv("RUNNER_GRADIENT_ACCUMULATION", "32")),  # High accumulation for low memory
        # Model will be read from environment or use default
    }

    # Create and run training engine
    print("🚀 Initializing training engine...")
    print()

    engine = TrainingEngine(config)
    output_dir = engine.run_full_training()

    print()
    print("🎉 Tools category training complete!")
    print(f"📂 Model saved to: {output_dir}")
    print()
    print("Next steps:")
    print("  1. Test the model in the Models tab")
    print("  2. Export to Ollama for use in OpenCode")
    print()


if __name__ == "__main__":
    main()
