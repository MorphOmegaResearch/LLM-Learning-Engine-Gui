#!/usr/bin/env python3
# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
OpenCode Tool Training System
Trains small LLMs (3B-4B params) to use OpenCode tools correctly
"""

import os
import json
import asyncio
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import sys

# Import our modules
from training_data_generator import TrainingDataGenerator
from session_manager import TrainingSessionManager
from export_for_finetuning import TrainingDataExporter

@dataclass
class TrainingConfig:
    """Configuration for the training session"""
    model_name: str
    training_hours: float = 1.0
    output_dir: str = "./training_results"
    log_level: str = "INFO"
    max_examples_per_tool: int = 50
    enable_auto_chains: bool = True
    enable_live_training: bool = True
    enable_baseline_tests: bool = True # New: Control whether to run baseline skill tests
    enable_stat_saving: bool = True # New: Control whether to save training statistics
    temperature: float = 0.3
    context_length: int = 4096
    evaluation_split: float = 0.2  # 20% for evaluation

@dataclass
class TrainingStats:
    """Track training statistics"""
    total_examples: int = 0
    training_examples: int = 0
    eval_examples: int = 0
    successful_tool_calls: int = 0
    failed_tool_calls: int = 0
    invalid_formats: int = 0
    auto_chains_used: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    avg_response_time_ms: float = 0.0
    pass_rate: float = 0.0
    baseline_skills_results: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 3600  # hours
        return 0.0

    @property
    def success_rate(self) -> float:
        total = self.successful_tool_calls + self.failed_tool_calls
        return (self.successful_tool_calls / total * 100) if total > 0 else 0.0

class OpenCodeToolTrainer:
    """Comprehensive trainer for OpenCode tool system"""

    def __init__(self, config: TrainingConfig):
        self.config = config
        self.stats = TrainingStats()
        self.setup_logging()
        self.training_data = []
        self.eval_data = []
        self.data_generator = TrainingDataGenerator()

    def setup_logging(self):
        """Setup comprehensive logging"""
        log_dir = Path(self.config.output_dir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"training_{timestamp}.log"

        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    async def get_available_models(self) -> List[str]:
        """Get list of available Ollama models"""
        try:
            result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                models = []
                for line in lines:
                    if line.strip():
                        model_name = line.split()[0]
                        models.append(model_name)
                return models
            else:
                self.logger.error("Failed to get Ollama models")
                return []
        except Exception as e:
            self.logger.error(f"Error getting models: {e}")
            return []

    async def select_model(self) -> Optional[str]:
        """Interactive model selection with copy option"""
        models = await self.get_available_models()

        if not models:
            self.logger.error("No Ollama models found!")
            return None

        print("\n=== Available Ollama Models ===")
        for i, model in enumerate(models, 1):
            print(f"{i}. {model}")

        while True:
            try:
                choice = input(f"\nSelect model (1-{len(models)}) or 'q' to quit: ").strip()
                if choice.lower() == 'q':
                    return None

                idx = int(choice) - 1
                if 0 <= idx < len(models):
                    selected_model = models[idx]

                    # Ask if user wants to copy the model first
                    copy_choice = input(f"Copy '{selected_model}' to new training model? (y/n): ").strip().lower()
                    if copy_choice == 'y':
                        new_name = input("Enter new model name: ").strip()
                        if new_name:
                            if await self.copy_model(selected_model, new_name):
                                return new_name
                            else:
                                continue

                    return selected_model
                else:
                    print("Invalid selection")
            except ValueError:
                print("Please enter a valid number")

    async def copy_model(self, source_model: str, new_name: str) -> bool:
        """Copy a model to new name"""
        try:
            self.logger.info(f"Copying {source_model} to {new_name}...")
            result = subprocess.run(['ollama', 'cp', source_model, new_name],
                                  capture_output=True, text=True)

            if result.returncode == 0:
                self.logger.info(f"Successfully created {new_name}")
                return True
            else:
                self.logger.error(f"Failed to copy model: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Error copying model: {e}")
            return False

    def generate_training_examples(self) -> List[Dict[str, Any]]:
        """Generate comprehensive training examples"""
        examples = []

        # File operations examples
        examples.extend(self._generate_file_ops_examples())
        # Search operations examples
        examples.extend(self._generate_search_examples())
        # System operations examples
        examples.extend(self._generate_system_examples())
        # Git operations examples
        examples.extend(self._generate_git_examples())
        # Web operations examples
        examples.extend(self._generate_web_examples())
        # Auto-chain examples (CRITICAL for small models)
        if self.config.enable_auto_chains:
            examples.extend(self._generate_auto_chain_examples())

        # Add scenario-based examples
        scenario_examples = self.data_generator.generate_all_scenarios()
        examples.extend(scenario_examples)

        return examples

    def _generate_file_ops_examples(self) -> List[Dict[str, Any]]:
        """Generate file operation training examples"""
        examples = []

        # CORRECT: file_write with file_path parameter
        examples.append({
            "scenario": "file_write_basic",
            "conversation": [
                {"role": "user", "content": "Create a new file called test.txt with hello world"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"file_write","args":{"file_path":"test.txt","content":"Hello World"}}'},
                {"role": "system", "content": '{"success":true,"output":"File written successfully: test.txt"}'},
                {"role": "assistant", "content": "Created test.txt with content 'Hello World'"}
            ]
        })

        # File operations with subdirectories
        examples.append({
            "scenario": "file_write_subdir",
            "conversation": [
                {"role": "user", "content": "Create a file in the docs folder called readme.md"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"file_write","args":{"file_path":"docs/readme.md","content":"# Documentation\\n\\nProject docs here.","create_dirs":true}}'},
                {"role": "system", "content": '{"success":true,"output":"File written successfully: docs/readme.md"}'},
                {"role": "assistant", "content": "Created docs/readme.md with documentation template"}
            ]
        })

        # File read examples
        examples.append({
            "scenario": "file_read_basic",
            "conversation": [
                {"role": "user", "content": "Read the contents of config.yaml"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"file_read","args":{"file_path":"config.yaml"}}'},
                {"role": "system", "content": '{"success":true,"output":"version: 1.0\\nname: myapp\\nport: 8080"}'},
                {"role": "assistant", "content": "config.yaml contains: version 1.0, name: myapp, port: 8080"}
            ]
        })

        # File read with line range
        examples.append({
            "scenario": "file_read_range",
            "conversation": [
                {"role": "user", "content": "Show me lines 10-20 of main.py"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"file_read","args":{"file_path":"main.py","start_line":10,"end_line":20}}'},
                {"role": "system", "content": '{"success":true,"output":"def process():\\n    pass\\n\\ndef main():\\n    process()"}'},
                {"role": "assistant", "content": "Lines 10-20 of main.py show the process() and main() functions"}
            ]
        })

        # File edit examples
        examples.append({
            "scenario": "file_edit_basic",
            "conversation": [
                {"role": "user", "content": "Change version 1.0 to version 2.0 in config.yaml"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"file_edit","args":{"file_path":"config.yaml","old_text":"version: 1.0","new_text":"version: 2.0"}}'},
                {"role": "system", "content": '{"success":true,"output":"File edited successfully: 1 replacement made"}'},
                {"role": "assistant", "content": "Updated config.yaml from version 1.0 to 2.0"}
            ]
        })

        return examples[:self.config.max_examples_per_tool]

    def _generate_search_examples(self) -> List[Dict[str, Any]]:
        """Generate search operation training examples"""
        examples = []

        examples.append({
            "scenario": "file_search_basic",
            "conversation": [
                {"role": "user", "content": "Find all Python files"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"file_search","args":{"pattern":"*.py","path":"."}}'},
                {"role": "system", "content": '{"success":true,"output":"main.py\\nutils.py\\nconfig.py"}'},
                {"role": "assistant", "content": "Found 3 Python files: main.py, utils.py, config.py"}
            ]
        })

        examples.append({
            "scenario": "grep_search_basic",
            "conversation": [
                {"role": "user", "content": "Search for the word function in Python files"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"grep_search","args":{"pattern":"function","path":".","file_pattern":"*.py"}}'},
                {"role": "system", "content": '{"success":true,"output":"utils.py:15:def function_name():\\nmain.py:42:    function_call()"}'},
                {"role": "assistant", "content": "Found 'function' in 2 places: utils.py line 15 (definition) and main.py line 42 (call)"}
            ]
        })

        examples.append({
            "scenario": "directory_list_basic",
            "conversation": [
                {"role": "user", "content": "List the current directory"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"directory_list","args":{"path":"."}}'},
                {"role": "system", "content": '{"success":true,"output":"file  1024 main.py\\ndir      0 src\\nfile  2048 config.yaml"}'},
                {"role": "assistant", "content": "Current directory contains: main.py (1KB), src/ (directory), config.yaml (2KB)"}
            ]
        })

        return examples[:self.config.max_examples_per_tool]

    def _generate_system_examples(self) -> List[Dict[str, Any]]:
        """Generate system operation training examples"""
        examples = []

        examples.append({
            "scenario": "system_info_basic",
            "conversation": [
                {"role": "user", "content": "Show me system info"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"system_info","args":{}}'},
                {"role": "system", "content": '{"success":true,"output":"CPU: 15% Memory: 26% Disk: 17%"}'},
                {"role": "assistant", "content": "System: CPU 15%, Memory 26%, Disk 17%"}
            ]
        })

        examples.append({
            "scenario": "process_list",
            "conversation": [
                {"role": "user", "content": "Show Python processes"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"process_manage","args":{"operation":"list","pattern":"python"}}'},
                {"role": "system", "content": '{"success":true,"output":"PID 1234: python3 (CPU: 10%)"}'},
                {"role": "assistant", "content": "Found Python process: PID 1234 using 10% CPU"}
            ]
        })

        return examples[:self.config.max_examples_per_tool]

    def _generate_git_examples(self) -> List[Dict[str, Any]]:
        """Generate git operation training examples"""
        examples = []

        examples.append({
            "scenario": "git_status",
            "conversation": [
                {"role": "user", "content": "Check git status"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"git_operations","args":{"operation":"status"}}'},
                {"role": "system", "content": '{"success":true,"output":" M modified_file.py\\n?? new_file.txt"}'},
                {"role": "assistant", "content": "Git status: modified_file.py (modified), new_file.txt (untracked)"}
            ]
        })

        examples.append({
            "scenario": "git_log",
            "conversation": [
                {"role": "user", "content": "Show recent git commits"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"git_operations","args":{"operation":"log","limit":3}}'},
                {"role": "system", "content": '{"success":true,"output":"abc123 Fix bug\\ndef456 Add feature\\nghi789 Initial commit"}'},
                {"role": "assistant", "content": "Recent commits: abc123 (Fix bug), def456 (Add feature), ghi789 (Initial commit)"}
            ]
        })

        return examples[:self.config.max_examples_per_tool]

    def _generate_web_examples(self) -> List[Dict[str, Any]]:
        """Generate web operation training examples"""
        examples = []

        examples.append({
            "scenario": "web_search_basic",
            "conversation": [
                {"role": "user", "content": "Search for Python documentation"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"web_search","args":{"query":"Python documentation","max_results":3}}'},
                {"role": "system", "content": '{"success":true,"output":"Python Docs: https://docs.python.org\\nPython Tutorial: https://docs.python.org/tutorial"}'},
                {"role": "assistant", "content": "Found Python documentation at https://docs.python.org"}
            ]
        })

        return examples[:self.config.max_examples_per_tool]

    def _generate_auto_chain_examples(self) -> List[Dict[str, Any]]:
        """Generate auto-chain examples - CRITICAL for small models"""
        examples = []

        # Auto-chain: file_search -> file_read
        examples.append({
            "scenario": "auto_chain_search_read",
            "conversation": [
                {"role": "user", "content": "Find README files and show contents"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"file_search","args":{"pattern":"README*","path":"."}}'},
                {"role": "system", "content": '{"success":true,"output":"README.md\\n# My Project\\nDescription here\\n\\n(File contents auto-chained)"}'},
                {"role": "assistant", "content": "Found README.md. Contents: # My Project - Description here"}
            ]
        })

        return examples[:self.config.max_examples_per_tool]

    def split_train_eval(self, examples: List[Dict[str, Any]]) -> tuple:
        """Split examples into training and evaluation sets"""
        import random
        random.shuffle(examples)

        split_idx = int(len(examples) * (1 - self.config.evaluation_split))
        return examples[:split_idx], examples[split_idx:]

    def save_training_data(self):
        """Save generated training data"""
        data_dir = Path(self.config.output_dir) / "training_data"
        data_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save training set
        train_file = data_dir / f"training_set_{timestamp}.json"
        with open(train_file, 'w') as f:
            json.dump(self.training_data, f, indent=2)
        self.logger.info(f"Training data saved to {train_file}")

        # Save eval set
        eval_file = data_dir / f"eval_set_{timestamp}.json"
        with open(eval_file, 'w') as f:
            json.dump(self.eval_data, f, indent=2)
        self.logger.info(f"Evaluation data saved to {eval_file}")

    def save_training_stats(self):
        """Save training statistics"""
        stats_dir = Path(self.config.output_dir) / "stats"
        stats_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stats_file = stats_dir / f"training_stats_{timestamp}.json"

        stats_data = {
            "model": self.config.model_name,
            "duration_hours": self.stats.duration,
            "training_examples": self.stats.training_examples,
            "eval_examples": self.stats.eval_examples,
            "total_examples": self.stats.total_examples,
            "successful_tool_calls": self.stats.successful_tool_calls,
            "failed_tool_calls": self.stats.failed_tool_calls,
            "invalid_formats": self.stats.invalid_formats,
            "success_rate": self.stats.success_rate,
            "pass_rate": self.stats.pass_rate,
            "auto_chains_used": self.stats.auto_chains_used,
            "avg_response_time_ms": self.stats.avg_response_time_ms,
            "start_time": self.stats.start_time.isoformat() if self.stats.start_time else None,
            "end_time": self.stats.end_time.isoformat() if self.stats.end_time else None,
            "config": {
                "training_hours": self.config.training_hours,
                "max_examples_per_tool": self.config.max_examples_per_tool,
                "enable_auto_chains": self.config.enable_auto_chains,
                "enable_live_training": self.config.enable_live_training,
                "evaluation_split": self.config.evaluation_split
            },
            "baseline_skills_results": self.stats.baseline_skills_results
        }

        with open(stats_file, 'w') as f:
            json.dump(stats_data, f, indent=2)

        self.logger.info(f"Training stats saved to {stats_file}")

    def export_training_data(self):
        """Export training data in multiple formats for fine-tuning"""
        export_dir = Path(self.config.output_dir) / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        # Determine base model name (strip tags)
        base_model = self.config.model_name.split(':')[0] if ':' in self.config.model_name else self.config.model_name

        # Create exporter
        exporter = TrainingDataExporter(self.training_data, str(export_dir))

        # Export in all formats
        exports = exporter.export_all(
            model_name=f"{base_model}-opencode-tools",
            base_model=self.config.model_name
        )

        self.logger.info("Training data exported for fine-tuning")
        self.logger.info(f"Export directory: {export_dir}")

        # Print instructions
        print(f"\n{'='*60}")
        print(f"{'Fine-Tuning Instructions':^60}")
        print(f"{'='*60}")
        print(f"\n⚠️  IMPORTANT: 'Live training' only validates the model.")
        print(f"To actually train the model, run:\n")
        print(f"  cd {export_dir}")
        print(f"  ./train_model.sh")
        print(f"\nOr manually:")
        print(f"  ollama create {base_model}-opencode-tools -f {export_dir}/Modelfile_{base_model}-opencode-tools")
        print(f"\nSee REAL_TRAINING_GUIDE.md for details.")
        print(f"{'='*60}\n")

        # Print summary
        print(f"\n{'='*50}")
        print(f"{'Training Summary':^50}")
        print(f"{'='*50}")
        print(f"Model: {self.config.model_name}")
        print(f"Duration: {self.stats.duration:.2f} hours")
        print(f"Training Examples: {self.stats.training_examples}")
        print(f"Evaluation Examples: {self.stats.eval_examples}")
        print(f"Total Examples: {self.stats.total_examples}")
        print(f"Successful Tool Calls: {self.stats.successful_tool_calls}")
        print(f"Failed Tool Calls: {self.stats.failed_tool_calls}")
        print(f"Invalid Formats: {self.stats.invalid_formats}")
        print(f"Success Rate: {self.stats.success_rate:.1f}%")
        print(f"Pass Rate: {self.stats.pass_rate:.1f}%")
        print(f"Avg Response Time: {self.stats.avg_response_time_ms:.0f}ms")
        print(f"Auto Chains Used: {self.stats.auto_chains_used}")
        print(f"{'='*50}\n")

    async def train_model(self):
        """Main training loop"""
        self.stats.start_time = datetime.now()
        self.logger.info(f"Starting training for model: {self.config.model_name}")

        # Generate training data
        self.logger.info("Generating training examples...")
        all_examples = self.generate_training_examples()

        # Generate baseline skill tests (if enabled)
        baseline_skill_tests = []
        if self.config.enable_baseline_tests:
            self.logger.info("Generating baseline skill tests...")
            baseline_skill_tests = self.data_generator.generate_baseline_skill_tests()
            self.logger.info(f"Generated {len(baseline_skill_tests)} baseline skill tests.")

        # Split into train/eval
        self.training_data, self.eval_data = self.split_train_eval(all_examples)
        self.stats.training_examples = len(self.training_data)
        self.stats.eval_examples = len(self.eval_data)
        self.stats.total_examples = len(all_examples)

        self.logger.info(f"Generated {self.stats.total_examples} total examples")
        self.logger.info(f"Training: {self.stats.training_examples}, Evaluation: {self.stats.eval_examples}")

        # Save training data
        self.save_training_data()

        # Export training data for fine-tuning
        self.logger.info("Exporting training data for fine-tuning...")
        self.export_training_data()

        # Live validation with Ollama (if enabled)
        if self.config.enable_live_training:
            self.logger.info("Starting live validation session with Ollama...")
            print("\n⚠️  Running validation (inference only, not actual training)...")

            async with TrainingSessionManager() as session:
                # Check Ollama is running
                if not await session.check_ollama_running():
                    self.logger.error("Ollama is not running! Please start Ollama first.")
                    return

                # Load model
                self.logger.info(f"Loading model {self.config.model_name}...")
                if not await session.load_model(self.config.model_name):
                    self.logger.error("Failed to load model")
                    return

                # Run baseline skill tests (if enabled)
                if self.config.enable_baseline_tests and baseline_skill_tests:
                    self.logger.info("Running baseline skill tests...")
                    baseline_results = {}
                    for i, test_example in enumerate(baseline_skill_tests, 1):
                        skill_name = test_example.get("skill_name", f"unknown_skill_{i}")
                        self.logger.info(f"  Running baseline test {i}/{len(baseline_skill_tests)}: {skill_name}")

                        result = await session.train_with_example(self.config.model_name, test_example)

                        if result.get("success") and result.get("valid_format"):
                            baseline_results[skill_name] = {"passed": True, "details": result}
                            self.logger.info(f"    ✓ Test for '{skill_name}' PASSED.")
                        else:
                            baseline_results[skill_name] = {"passed": False, "details": result}
                            self.logger.warning(f"    ✗ Test for '{skill_name}' FAILED. Error: {result.get('error', 'Invalid format')}")
                        
                        await asyncio.sleep(0.1) # Brief delay

                    self.stats.baseline_skills_results = baseline_results
                    self.logger.info("Baseline skill tests complete.")
                else:
                    self.logger.info("Baseline skill tests disabled or no tests generated.")

                # Train on examples (original validation loop)
                self.logger.info("Running validation on training examples...")
                for i, example in enumerate(self.training_data, 1):
                    self.logger.info(f"  Validating example {i}/{len(self.training_data)}: {example.get('scenario', 'unknown')}")

                    result = await session.train_with_example(self.config.model_name, example)

                    if result.get("success"):
                        if result.get("valid_format"):
                            self.stats.successful_tool_calls += 1
                        else:
                            self.stats.invalid_formats += 1
                    else:
                        self.stats.failed_tool_calls += 1

                    # Update response time
                    metrics = result.get("metrics", {})
                    if "total_duration_ms" in metrics:
                        self.stats.avg_response_time_ms += metrics["total_duration_ms"]

                    await asyncio.sleep(0.5)  # Brief delay between examples

                # Calculate average response time
                if self.stats.training_examples > 0:
                    self.stats.avg_response_time_ms /= self.stats.training_examples

                # Evaluate model
                self.logger.info("Evaluating model on test set...")
                eval_results = await session.evaluate_model(self.config.model_name, self.eval_data)

                self.stats.pass_rate = eval_results.get("pass_rate", 0.0)
                self.logger.info(f"Evaluation complete: {eval_results['passed']}/{eval_results['total']} passed ({self.stats.pass_rate:.1f}%)")

        else:
            self.logger.info("Live training disabled. Training data generated and saved.")

        self.stats.end_time = datetime.now()

        # Save statistics
        self.save_training_stats()

        self.logger.info("Training completed!")

async def main():
    """Main entry point"""
    print("=" * 60)
    print(" " * 10 + "OpenCode Tool Training System")
    print("=" * 60)
    print()

    # Get model selection
    temp_config = TrainingConfig(model_name="temp")
    trainer = OpenCodeToolTrainer(temp_config)

    model_name = await trainer.select_model()
    if not model_name:
        print("No model selected. Exiting.")
        return

    # Get training configuration
    while True:
        try:
            hours = float(input("\nEnter training duration in hours (e.g., 1.5): ").strip())
            if hours > 0:
                break
            else:
                print("Please enter a positive number")
        except ValueError:
            print("Please enter a valid number")

    # Enable live training?
    print("\n" + "="*60)
    print("⚠️  NOTE: 'Live training' = model validation, NOT actual training")
    print("Ollama API doesn't support real-time fine-tuning.")
    print("Use the exported Modelfile for actual training.")
    print("="*60)
    live_choice = input("\nEnable live validation with Ollama? (y/n): ").strip().lower()
    enable_live = live_choice == 'y'

    # Create final config
    config = TrainingConfig(
        model_name=model_name,
        training_hours=hours,
        enable_live_training=enable_live,
        output_dir=f"./training_{model_name.replace(':', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    # Start training
    print(f"\nStarting training session...")
    print(f"Model: {model_name}")
    print(f"Duration: {hours} hours")
    print(f"Live Training: {'Enabled' if enable_live else 'Disabled'}")
    print(f"Output: {config.output_dir}")
    print()

    trainer = OpenCodeToolTrainer(config)
    await trainer.train_model()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTraining interrupted by user.")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
