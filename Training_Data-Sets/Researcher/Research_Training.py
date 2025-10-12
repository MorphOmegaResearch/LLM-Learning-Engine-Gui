#!/usr/bin/env python3
# Minimal training script template for category: Researcher
import os
from pathlib import Path
import sys

# Add project root to path to allow imports like 'from config import ...'
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from Data.training_engine import TrainingEngine

def main():
    print(f'Starting training script for category: Researcher')
    # This script runs within the context of the Runner Panel.
    # It receives all its configuration from environment variables set by the GUI.
    # Example of how to use the TrainingEngine:
    # engine = TrainingEngine()
    # engine.run_full_training()
    print('Training script finished.')

if __name__ == '__main__':
    main()
