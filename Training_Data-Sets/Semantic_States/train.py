#!/usr/bin/env python3
"""
Training Script: Semantic_States Category
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
    """Train on Semantic_States category data"""
    category_name = SCRIPT_DIR.name
    
    print("=" * 60)
    print(f"  TRAINING: {category_name} Category")
    print("=" * 60)
    print()

    # Find all JSONL files in this category
    jsonl_files = list(SCRIPT_DIR.glob("*.jsonl"))

    if not jsonl_files:
        print("❌ No training data files found!")
        print(f"   Looking in: {SCRIPT_DIR}")
        print()
        print("Create training data files (.jsonl) in this directory")
        return

    print(f"📁 Found {len(jsonl_files)} training data file(s):")
    total_examples = 0
    for f in jsonl_files:
        with open(f) as file:
            count = sum(1 for _ in file)
            total_examples += count
        print(f"   • {f.name}: {count} examples")

    print(f"\n📊 Total: {total_examples} training examples")
    print()

    # Combine all JSONL files
    combined_data = DATA_DIR / f"temp_{category_name.lower()}_training.jsonl"
    print(f"📦 Combining data files → {combined_data.name}")

    with open(combined_data, 'w') as outfile:
        for jsonl_file in jsonl_files:
            with open(jsonl_file) as infile:
                for line in infile:
                    outfile.write(line)

    print("✓ Data files combined")
    print()

    # Training configuration
    config = {
        "category": category_name,
        "training_data_path": str(combined_data),
        "num_epochs": 3,
        "batch_size": 2,
        "learning_rate": 2e-4,
        "max_seq_length": 2048,
    }

    # Create and run training engine
    print("🚀 Initializing training engine...")
    print()

    engine = TrainingEngine(config)
    output_dir = engine.run_full_training()

    print()
    print(f"🎉 {category_name} category training complete!")
    print(f"📂 Model saved to: {output_dir}")
    print()


if __name__ == "__main__":
    main()
