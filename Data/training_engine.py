#!/usr/bin/env python3
"""
Core Training Engine - Shared library for category-specific training
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime

# Prefer importing Unsloth before transformers/trl/peft for optimal patches
try:
    from unsloth import FastLanguageModel
    UNSLOTH_AVAILABLE = True
except (ImportError, NotImplementedError):
    UNSLOTH_AVAILABLE = False

import torch
from trl import SFTTrainer
from transformers import TrainingArguments, AutoModelForCausalLM, AutoTokenizer, TrainerCallback, TrainerControl
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

# Import config and logger
import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import MODELS_DIR, DATA_DIR, save_training_stats, save_evaluation_report
from evaluation_engine import EvaluationEngine
from logger_util import log_message

if not UNSLOTH_AVAILABLE:
    # logger will be initialized below; guard with print as well
    try:
        log_message("ENGINE: ⚠️ Unsloth not available - using standard Transformers (CPU mode)")
    except Exception:
        print("ENGINE: ⚠️ Unsloth not available - using standard Transformers (CPU mode)")

# Custom Callback for Time Limit
class TimeLimitCallback(TrainerCallback):
    def __init__(self, max_time_minutes=120):
        self.max_time_seconds = max_time_minutes * 60
        self.start_time = 0

    def on_train_begin(self, args, state, control, **kwargs):
        self.start_time = time.time()
        log_message(f"ENGINE: TimeLimitCallback initialized. Max time: {self.max_time_seconds / 60:.2f} minutes.")

    def on_step_end(self, args, state, control, **kwargs):
        elapsed_time = time.time() - self.start_time
        if elapsed_time > self.max_time_seconds:
            log_message(f"ENGINE: Time limit of {self.max_time_seconds / 60:.2f} minutes reached. Stopping training.")
            control.should_training_stop = True
        return control

class TrainingEngine:
    """Core training engine with CPU/GPU support"""

    def __init__(self, config=None):
        log_message("ENGINE: Initializing TrainingEngine...")
        self.config = config or {}

        raw_model_name = self.config.get("model_name", os.getenv("BASE_MODEL", "unsloth/Qwen2.5-Coder-1.5B-Instruct"))

        def _normalize_model_input_string(s: str) -> str:
            if not s:
                return s
            s = s.strip()
            # If value looks like "LOCAL: Name (/full/path)", prefer the explicit path in parentheses
            if "(" in s and ")" in s:
                try:
                    inside = s[s.index("(")+1:s.rindex(")")].strip()
                    if inside:
                        return inside
                except Exception:
                    pass
            # If prefixed with LOCAL:/OLLAMA: keep only the part after ':'
            if ":" in s and s.split(":", 1)[0].strip().upper() in {"LOCAL", "OLLAMA"}:
                s = s.split(":", 1)[1].strip()
            return s

        normalized = _normalize_model_input_string(raw_model_name)
        # Back-compat stripping only for Ollama tags like "llama3:instruct" (no slash in tag segment)
        if ":" in normalized and "/" not in normalized.split(":")[-1]:
            self.model_name = normalized.split(":")[0]
            log_message(f"ENGINE: Stripped Ollama tag: {normalized} → {self.model_name}")
        else:
            self.model_name = normalized

        self.training_data_path = self.config.get("training_data_path", os.getenv("TRAINING_DATA_FILE"))
        self.num_epochs = self.config.get("num_epochs", int(os.getenv("TRAINING_EPOCHS", "3")))
        self.batch_size = self.config.get("batch_size", int(os.getenv("TRAINING_BATCH_SIZE", "2")))
        self.learning_rate = self.config.get("learning_rate", float(os.getenv("TRAINING_LEARNING_RATE", "2e-4")))
        self.max_seq_length = self.config.get("max_seq_length", 2048)
        self.dtype = self.config.get("dtype", None)
        self.load_in_4bit = self.config.get("load_in_4bit", torch.cuda.is_available())
        self.use_cpu = not torch.cuda.is_available()
        self.lora_r = self.config.get("lora_r", 16)
        self.lora_alpha = self.config.get("lora_alpha", 16)
        self.lora_dropout = self.config.get("lora_dropout", 0)
        self.target_modules = self.config.get("target_modules", ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
        self.gradient_accumulation_steps = self.config.get("gradient_accumulation_steps", int(os.getenv("RUNNER_GRADIENT_ACCUMULATION", "4")))
        self.max_steps = self.config.get("max_steps", -1)
        self.save_checkpoints = os.getenv("RUNNER_SAVE_CHECKPOINTS", "True").lower() == "true"
        self.checkpoint_interval = int(os.getenv("RUNNER_CHECKPOINT_INTERVAL", "100"))
        self.use_mixed_precision = os.getenv("RUNNER_MIXED_PRECISION", "True").lower() == "true"
        self.warmup_steps = int(os.getenv("RUNNER_WARMUP_STEPS", "5"))
        self.early_stopping_enabled = os.getenv("RUNNER_EARLY_STOPPING", "False").lower() == "true"
        self.early_stopping_patience = int(os.getenv("RUNNER_EARLY_STOPPING_PATIENCE", "3"))
        # Note: Early Stopping functionality depends on the 'transformers' library version.
        # If the installed version is too old, this feature will be gracefully disabled.
        self.max_training_time = int(os.getenv("RUNNER_MAX_TIME", "120"))

        if self.config.get("output_dir"):
            self.output_dir = Path(self.config["output_dir"])
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_model_name = self.model_name.replace("unsloth/", "").replace("-Instruct", "").replace("/", "_")
            category = self.config.get("category", "general")
            self.output_dir = MODELS_DIR / f"training_{category}_{clean_model_name}_{timestamp}"

        self.output_dir.mkdir(parents=True, exist_ok=True)
        log_message(f"ENGINE: Output directory set to: {self.output_dir}")

        self.model, self.tokenizer, self.dataset, self.trainer = None, None, None, None
        # Enforce offline mode by default to avoid unintended network calls during training
        self.offline_mode = True if os.getenv("HF_HUB_OFFLINE", "1").lower() in {"1", "true", "yes"} else False
        if self.offline_mode:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["HUGGINGFACE_OFFLINE"] = "1"

    def print_config(self):
        log_message("=" * 60)
        log_message("  Training Engine Configuration")
        log_message("=" * 60)
        log_message(f"📦 Model: {self.model_name}")
        log_message(f"📁 Training Data: {self.training_data_path}")
        log_message(f"📂 Output: {self.output_dir}")
        log_message("\n📊 Training Parameters:")
        log_message(f"   Epochs: {self.num_epochs}")
        log_message(f"   Batch Size: {self.batch_size}")
        log_message(f"   Learning Rate: {self.learning_rate}")
        log_message(f"   Max Seq Length: {self.max_seq_length}")
        log_message(f"   Gradient Accumulation: {self.gradient_accumulation_steps}")
        log_message("\n🔧 LoRA Configuration:")
        log_message(f"   r={self.lora_r}, alpha={self.lora_alpha}, dropout={self.lora_dropout}")
        log_message("\n⚡ Runner Settings:")
        log_message(f"   Mixed Precision (FP16): {self.use_mixed_precision}")
        log_message(f"   Warmup Steps: {self.warmup_steps}")
        log_message(f"   Save Checkpoints: {self.save_checkpoints}")
        if self.save_checkpoints:
            log_message(f"   Checkpoint Interval: {self.checkpoint_interval} steps")
        log_message(f"   Early Stopping: {self.early_stopping_enabled}")
        if self.early_stopping_enabled:
            log_message(f"   Early Stopping Patience: {self.early_stopping_patience} epochs")
        log_message(f"   Max Training Time: {self.max_training_time} minutes")
        log_message(f"\n🌐 Network: {'OFFLINE' if self.offline_mode else 'ONLINE (local-files-only set)'}")

    def load_model(self):
        # Resolve model path/name preference: local dir under MODELS_DIR if available, else raw name/ID
        model_path = Path(self.model_name)
        resolved_name = None
        if model_path.exists() and model_path.is_dir():
            resolved_name = str(model_path)
        else:
            candidate = MODELS_DIR / self.model_name
            if candidate.exists() and candidate.is_dir():
                resolved_name = str(candidate)
            else:
                # No local match found
                if self.offline_mode:
                    log_message(f"ENGINE: ERROR: Offline mode active and local model not found: {self.model_name}")
                    raise FileNotFoundError(f"Offline mode: local model not found: {self.model_name}")
                resolved_name = self.model_name  # Fallback to hub ID (only if not offline)

        is_local_path = Path(resolved_name).exists() and Path(resolved_name).is_dir()

        log_message(f"ENGINE: 📦 Loading {'LOCAL model' if is_local_path else 'model'}: {resolved_name}")
        log_message(f"ENGINE:    Mode: {'GPU (Unsloth)' if UNSLOTH_AVAILABLE and not self.use_cpu else 'CPU (Transformers)'}")
        log_message(f"ENGINE:    4-bit quantization: {self.load_in_4bit}")

        if self.use_cpu:
            log_message("ENGINE: ⚠️ WARNING: CPU Training Mode. This will be 10-100x slower than GPU.")

        # Optional auth token for private/blocked hub models
        hf_token = os.getenv('HUGGINGFACE_TOKEN') or os.getenv('HF_TOKEN') or os.getenv('HUGGINGFACEHUB_API_TOKEN')

        if UNSLOTH_AVAILABLE and not self.use_cpu:
            self.model, self.tokenizer = FastLanguageModel.from_pretrained(
                model_name=resolved_name,
                max_seq_length=self.max_seq_length,
                dtype=self.dtype,
                load_in_4bit=self.load_in_4bit,
            )
            log_message("ENGINE: ✓ Model loaded with Unsloth.")
            log_message("ENGINE: 🔧 Applying LoRA adapters (Unsloth)...")
            self.model = FastLanguageModel.get_peft_model(self.model, r=self.lora_r, target_modules=self.target_modules, lora_alpha=self.lora_alpha, lora_dropout=self.lora_dropout, bias="none", use_gradient_checkpointing="unsloth", random_state=3407)
        else:
            log_message(f"ENGINE:    Loading with standard Transformers ({'local path' if is_local_path else 'CPU mode'})...")
            # Pass token for hub download if present (ignored for local paths)
            tok_kwargs = {"token": hf_token} if (hf_token and not is_local_path and not self.offline_mode) else {}
            mdl_kwargs = {"token": hf_token} if (hf_token and not is_local_path and not self.offline_mode) else {}
            # Always prefer local files only to prevent accidental network calls
            tok_kwargs["local_files_only"] = True
            mdl_kwargs["local_files_only"] = True
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(resolved_name, **tok_kwargs)
                self.model = AutoModelForCausalLM.from_pretrained(
                    resolved_name,
                    torch_dtype=torch.float32,
                    device_map="cpu",
                    low_cpu_mem_usage=True,
                    **mdl_kwargs,
                )
            except Exception as e:
                log_message(f"ENGINE: ERROR loading model '{resolved_name}': {e}")
                raise
            log_message("ENGINE: ✓ Model loaded.")
            log_message("ENGINE: 🔧 Applying LoRA adapters (PEFT)...")
            peft_config = LoraConfig(r=self.lora_r, lora_alpha=self.lora_alpha, lora_dropout=self.lora_dropout, target_modules=self.target_modules, bias="none", task_type="CAUSAL_LM")
            self.model = get_peft_model(self.model, peft_config)
        
        log_message("ENGINE: ✓ LoRA adapters applied.")

    def load_training_data(self):
        if not self.training_data_path or not Path(self.training_data_path).exists():
            log_message(f"ENGINE ERROR: Training data not found: {self.training_data_path}")
            raise FileNotFoundError(f"Training data not found: {self.training_data_path}")

        log_message(f"ENGINE: 📚 Loading training data: {self.training_data_path}")
        data = []
        invalid_lines = 0
        total_lines = 0
        with open(self.training_data_path, 'r') as f:
            for raw_line in f:
                total_lines += 1
                line = raw_line.strip()
                if not line:
                    # Skip blank/whitespace-only lines commonly present in JSONL
                    continue
                try:
                    example = json.loads(line)
                except json.JSONDecodeError as e:
                    invalid_lines += 1
                    log_message(f"ENGINE: ⚠️ Skipping malformed JSONL line {total_lines}: {e}")
                    continue

                messages = example.get("messages", [])
                conversation = []
                for msg in messages:
                    if msg.get("role") in ["system", "user", "assistant"]:
                        conversation.append({"role": msg.get("role", ""), "content": msg.get("content", "")})
                if conversation:
                    text = self.tokenizer.apply_chat_template(conversation, tokenize=False, add_generation_prompt=False)
                    data.append({"text": text})

        self.dataset = Dataset.from_list(data)
        log_message(f"ENGINE: ✓ Loaded {len(self.dataset)} training examples from {total_lines} lines ({invalid_lines} skipped).")

    def setup_trainer(self):
        log_message("ENGINE: 🎯 Setting up trainer...")
        log_message(f"ENGINE:    Batch size: {self.batch_size}, Grad Accum: {self.gradient_accumulation_steps}, LR: {self.learning_rate}, Epochs: {self.num_epochs}")
        max_threads = int(os.getenv("RUNNER_MAX_CPU_THREADS", "4"))
        torch.set_num_threads(max_threads)
        log_message(f"ENGINE: ⚙️  CPU threads limited to: {max_threads}")

        # Callbacks for Time Limits
        callbacks = []
        if self.max_training_time > 0:
            callbacks.append(TimeLimitCallback(max_time_minutes=self.max_training_time))

        # Base Training Arguments
        base_args = {
            "per_device_train_batch_size": self.batch_size, "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "warmup_steps": self.warmup_steps, "max_steps": self.max_steps, "num_train_epochs": self.num_epochs,
            "learning_rate": self.learning_rate, "fp16": self.use_mixed_precision and torch.cuda.is_available() and not torch.cuda.is_bf16_supported(),
            "bf16": torch.cuda.is_available() and torch.cuda.is_bf16_supported(), "logging_steps": 1, "optim": "adamw_8bit" if torch.cuda.is_available() else "adamw_torch",
            "weight_decay": 0.01, "lr_scheduler_type": "linear", "seed": 3407, "output_dir": self.output_dir, "report_to": "none",
            "save_steps": self.checkpoint_interval if self.save_checkpoints else 99999999, "save_total_limit": 2,
            "use_cpu": (not torch.cuda.is_available()), "gradient_checkpointing": True, "dataloader_num_workers": 0,
        }

        # --- Safe Gating for Early Stopping ---
        # This block attempts to configure Early Stopping. It is wrapped in a try-except
        # to handle potential TypeError if the installed 'transformers' library version
        # does not support the required arguments (e.g., 'evaluation_strategy').
        try:
            eval_dataset = None
            if self.early_stopping_enabled:
                from transformers import EarlyStoppingCallback
                callbacks.append(EarlyStoppingCallback(early_stopping_patience=self.early_stopping_patience))
                log_message(f"ENGINE:    - EarlyStoppingCallback enabled with patience={self.early_stopping_patience}.")
                
                # Add arguments required for evaluation
                base_args.update({
                    "evaluation_strategy": "steps",
                    "eval_steps": self.checkpoint_interval,
                    "load_best_model_at_end": True,
                    "metric_for_best_model": "loss",
                    "greater_is_better": False,
                })
                eval_dataset = self.dataset # Use training set for eval metric
            
            training_args = TrainingArguments(**base_args)
            
            # TRL version compatibility: prefer 'processing_class' over deprecated 'tokenizer'
            try:
                self.trainer = SFTTrainer(
                    model=self.model,
                    args=training_args,
                    train_dataset=self.dataset,
                    eval_dataset=eval_dataset,
                    processing_class=self.tokenizer,
                    callbacks=callbacks,
                )
                log_message("ENGINE: ✓ SFTTrainer configured with processing_class (current TRL).")
            except TypeError as e2:
                if "unexpected keyword argument 'processing_class'" in str(e2):
                    # Older TRL versions expect 'tokenizer' and may allow max_seq_length
                    self.trainer = SFTTrainer(
                        model=self.model,
                        args=training_args,
                        train_dataset=self.dataset,
                        eval_dataset=eval_dataset,
                        tokenizer=self.tokenizer,
                        max_seq_length=self.max_seq_length,
                        callbacks=callbacks,
                    )
                    log_message("ENGINE: ✓ SFTTrainer configured with tokenizer (legacy TRL).")
                else:
                    raise
            log_message("ENGINE: ✓ Early Stopping configuration attempted successfully.")
        except TypeError as e:
            # This specific TypeError indicates an older transformers version.
            if "unexpected keyword argument 'evaluation_strategy'" in str(e) or "evaluation_strategy" in str(e):
                log_message("ENGINE: ⚠️ WARNING: Early Stopping is enabled in UI but not fully supported by the installed 'transformers' library. This feature will be gracefully disabled for this run.")
                
                # Fallback: remove early stopping args and re-create trainer without them
                base_args.pop("evaluation_strategy", None)
                base_args.pop("eval_steps", None)
                base_args.pop("load_best_model_at_end", None)
                base_args.pop("metric_for_best_model", None)
                base_args.pop("greater_is_better", None)
                
                # Remove EarlyStoppingCallback if it was added
                callbacks = [cb for cb in callbacks if not isinstance(cb, EarlyStoppingCallback)]
                
                training_args = TrainingArguments(**base_args)
                # Re-create trainer without early stopping args; respect TRL signature
                try:
                    self.trainer = SFTTrainer(
                        model=self.model,
                        args=training_args,
                        train_dataset=self.dataset,
                        eval_dataset=None, # No eval dataset if no evaluation strategy
                        processing_class=self.tokenizer,
                        callbacks=callbacks,
                    )
                    log_message("ENGINE: ✓ SFTTrainer setup complete without Early Stopping (processing_class).")
                except TypeError as e2:
                    if "unexpected keyword argument 'processing_class'" in str(e2):
                        self.trainer = SFTTrainer(
                            model=self.model,
                            args=training_args,
                            train_dataset=self.dataset,
                            eval_dataset=None,
                            tokenizer=self.tokenizer,
                            max_seq_length=self.max_seq_length,
                            callbacks=callbacks,
                        )
                        log_message("ENGINE: ✓ SFTTrainer setup complete without Early Stopping (legacy tokenizer).")
                    else:
                        raise
            else:
                # It's a different, unexpected TypeError, so we should not hide it.
                log_message(f"ENGINE: ERROR - An unexpected TypeError occurred during trainer setup: {e}")
                raise e

        log_message("ENGINE: ✓ SFTTrainer setup complete.")

    def train(self):
        log_message("ENGINE: 🚀 Starting training...")
        trainer_stats = self.trainer.train()
        log_message("ENGINE: ✓ Training complete!")
        log_message(f"ENGINE: 📊 Training Stats: Steps={trainer_stats.global_step}, Loss={trainer_stats.training_loss:.4f}, Time={trainer_stats.metrics.get('train_runtime', 0):.2f}s")
        return trainer_stats

    def save_model(self, trainer_stats=None):
        log_message(f"ENGINE: 💾 Saving model to {self.output_dir}")
        self.model.save_pretrained(self.output_dir)
        self.tokenizer.save_pretrained(self.output_dir)
        log_message("ENGINE: ✓ Model saved.")

        if trainer_stats:
            log_message("ENGINE: 📈 Saving training statistics...")
            try:
                stats_data = {
                    "total_steps": trainer_stats.global_step, "training_loss": float(trainer_stats.training_loss),
                    "train_runtime": float(trainer_stats.metrics.get('train_runtime', 0)), "epochs": self.num_epochs,
                    "batch_size": self.batch_size, "learning_rate": self.learning_rate, "training_examples": len(self.dataset),
                    "output_dir": str(self.output_dir.name), "base_model": self.model_name, "category": self.config.get("category", "general")
                }
                save_training_stats(self.model_name, stats_data)
                log_message("ENGINE: ✓ Statistics saved.")
            except Exception as e:
                log_message(f"ENGINE: ⚠️ Failed to save statistics: {e}")
                import traceback
                traceback.print_exc()

    def export_gguf(self):
        log_message("ENGINE: 📦 Converting to GGUF format for Ollama...")
        log_message("ENGINE: Note: GGUF conversion requires external tools (llama.cpp or Unsloth)")
        log_message(f"ENGINE: To convert manually, run: python llama.cpp/convert.py {self.output_dir} --outfile model.gguf --outtype q4_K_M")

    def run_full_training(self):
        log_message("ENGINE: --- Starting Full Training Pipeline ---")
        self.print_config()
        self.load_model()
        self.load_training_data()
        self.setup_trainer()
        trainer_stats = self.train()
        self.save_model(trainer_stats)

        # --- Post-training Evaluation ---
        log_message("ENGINE: 🧪 Starting post-training evaluation...")
        try:
            # Determine model name for evaluation (the newly trained adapter)
            eval_model_name = self.output_dir.name

            # Get test suite, system prompt, and tool schema from config or defaults
            # For now, use hardcoded "Tools" suite and no specific prompt/schema
            # In future, these could come from the training config or user selection
            test_suite_name = "Tools" # Default for now
            system_prompt_name = None # Default for now
            tool_schema_name = None # Default for now

            # Initialize EvaluationEngine
            from config import TRAINING_DATA_DIR # Import here to avoid circular dependency
            test_suite_dir = TRAINING_DATA_DIR / "Test"
            eval_engine = EvaluationEngine(tests_dir=test_suite_dir)

            # Run benchmark
            eval_results = eval_engine.run_benchmark(
                eval_model_name,
                test_suite_name,
                system_prompt_name=system_prompt_name,
                tool_schema_name=tool_schema_name
            )

            if "error" not in eval_results:
                eval_report_path = save_evaluation_report(eval_model_name, eval_results)
                log_message(f"ENGINE: ✓ Post-training evaluation report saved to: {eval_report_path}")
                # Update training stats with eval report path
                stats_data = {
                    "total_steps": trainer_stats.global_step, "training_loss": float(trainer_stats.training_loss),
                    "train_runtime": float(trainer_stats.metrics.get('train_runtime', 0)), "epochs": self.num_epochs,
                    "batch_size": self.batch_size, "learning_rate": self.learning_rate, "training_examples": len(self.dataset),
                    "output_dir": str(self.output_dir.name), "base_model": self.model_name, "category": self.config.get("category", "general")
                }
                save_training_stats(eval_model_name, stats_data, eval_report_path) # Pass eval_model_name as model_name for stats
            else:
                log_message(f"ENGINE: ⚠️ Post-training evaluation failed: {eval_results['error']}")
        except Exception as e:
            log_message(f"ENGINE: ⚠️ An error occurred during post-training evaluation: {e}")

        # --- Record Lineage ---
        log_message("ENGINE: 📝 Recording model lineage...")
        try:
            from tabs.custom_code_tab.lineage_tracker import get_tracker
            lineage_tracker = get_tracker()

            # Record this training in lineage
            success = lineage_tracker.record_training(
                model_name=self.output_dir.name,  # New adapter model name
                base_model=self.model_name,  # Base model it was trained from
                training_date=datetime.now().isoformat(),
                training_data_source=str(Path(self.training_data_path).name) if self.training_data_path else None,
                training_method="LoRA fine-tune",
                metadata={
                    "epochs": self.num_epochs,
                    "batch_size": self.batch_size,
                    "learning_rate": self.learning_rate,
                    "max_seq_length": self.max_seq_length,
                    "lora_r": self.lora_r,
                    "lora_alpha": self.lora_alpha,
                    "lora_dropout": self.lora_dropout,
                    "training_examples": len(self.dataset),
                    "training_loss": float(trainer_stats.training_loss) if trainer_stats else None,
                    "category": self.config.get("category", "general")
                }
            )

            if success:
                log_message("ENGINE: ✓ Lineage recorded successfully")
            else:
                log_message("ENGINE: ⚠️ Failed to record lineage")

        except Exception as e:
            log_message(f"ENGINE: ⚠️ Error recording lineage: {e}")

        log_message("ENGINE: ✅ Adapter Model Saved.")
        log_message(f"ENGINE: Training complete. Adapter model saved to: {self.output_dir}")
        try:
            user_input = input("  ➡️ Proceed with GGUF export for Ollama? (y/N): ")
        except EOFError:
            user_input = 'n'

        if user_input.lower().strip() == 'y':
            log_message("ENGINE: User confirmed GGUF export.")
            self.export_gguf()
        else:
            log_message("ENGINE: User skipped GGUF export.")

        log_message("ENGINE: --- Training Pipeline Finished ---")
        return self.output_dir
