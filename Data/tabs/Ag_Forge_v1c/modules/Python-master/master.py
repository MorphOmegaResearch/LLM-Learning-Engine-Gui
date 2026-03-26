import argparse
import sys
import os
import json
from pathlib import Path

# Adjust Python path to allow importing modules from subdirectories
# This assumes master.py is in the Python-master/ directory
repo_root = Path(__file__).parent.resolve()
sys.path.append(str(repo_root))
sys.path.append(str(repo_root / "train"))
sys.path.append(str(repo_root / "Data")) # For config imports

# Import specific functions/classes from your modules

# Machine Learning Examples
try:
    from machine_learning import linear_regression
    from machine_learning import k_means_clust
    from machine_learning import apriori_algorithm
except ImportError as e:
    print(f"Could not import ML module: {e}")
    linear_regression = None
    k_means_clust = None
    apriori_algorithm = None

# Neural Network Examples
try:
    from neural_network import simple_neural_network
    from neural_network import perceptron # This is disabled in your dir, but kept for structural example
    from neural_network import two_hidden_layers_neural_network
except ImportError as e:
    print(f"Could not import NN module: {e}")
    simple_neural_network = None
    perceptron = None
    two_hidden_layers_neural_network = None

# Conversions Example
try:
    from conversions import binary_to_decimal
    from conversions import temperature_conversions
except ImportError as e:
    print(f"Could not import Conversions module: {e}")
    binary_to_decimal = None
    temperature_conversions = None

# Ciphers Example
try:
    from ciphers import caesar_cipher
except ImportError as e:
    print(f"Could not import Ciphers module: {e}")
    caesar_cipher = None

# LLM Fine-Tuning & Evaluation Pipeline Imports
try:
    from training_data_generator import TrainingDataGenerator
    from split_training_data import split_training_data
    from training_engine import TrainingEngine
    from evaluation_engine import EvaluationEngine
    from merge_and_export import merge_and_export
    from export_base_to_gguf import export_base_to_gguf
    from config import DATA_DIR, MODELS_DIR
except ImportError as e:
    print(f"Could not import LLM pipeline module: {e}")
    TrainingDataGenerator = None
    split_training_data = None
    TrainingEngine = None
    EvaluationEngine = None
    merge_and_export = None
    export_base_to_gguf = None
    DATA_DIR = Path(".")
    MODELS_DIR = Path(".")


# --- Wrapper Functions for Orchestration ---

def run_linear_regression_wrapper(args):
    """Wrapper for the linear_regression script."""
    if not linear_regression:
        print("Linear Regression module not available.")
        return
    print("Running Linear Regression...")
    try:
        print("Note: The linear_regression script runs a predefined example.")
        linear_regression.main()
    except Exception as e:
        print(f"Error running linear regression: {e}")

def run_kmeans_wrapper(args):
    """Wrapper for the K-Means Clustering script."""
    if not k_means_clust:
        print("K-Means Clustering module not available.")
        return
    print("Running K-Means Clustering...")
    try:
        from sklearn import datasets as ds
        dataset = ds.load_iris()
        k = args.k_clusters
        heterogeneity = []
        initial_centroids = k_means_clust.get_initial_centroids(dataset["data"], k, seed=args.seed)
        centroids, cluster_assignment = k_means_clust.kmeans(
            dataset["data"],
            k,
            initial_centroids,
            maxiter=args.max_iterations,
            record_heterogeneity=heterogeneity,
            verbose=True,
        )
        print(f"K-Means finished. Centroids: {centroids}")
        if args.plot:
            k_means_clust.plot_heterogeneity(heterogeneity, k)
            k_means_clust.plot_kmeans(dataset["data"], centroids, cluster_assignment)

    except Exception as e:
        print(f"Error running K-Means: {e}")

def run_apriori_wrapper(args):
    """Wrapper for the Apriori Algorithm script."""
    if not apriori_algorithm:
        print("Apriori Algorithm module not available.")
        return
    print("Running Apriori Algorithm...")
    try:
        data = apriori_algorithm.load_data()
        frequent_itemsets = apriori_algorithm.apriori(data=data, min_support=args.min_support)
        print("Frequent Itemsets:")
        for itemset, support in frequent_itemsets:
            print(f"{itemset}: {support}")
    except Exception as e:
        print(f"Error running Apriori: {e}")

def run_simple_nn_wrapper(args):
    """Wrapper for the simple_neural_network script."""
    if not simple_neural_network:
        print("Simple Neural Network module not available.")
        return
    print("Running Simple Neural Network...")
    try:
        print("Note: The simple_neural_network script runs a predefined example.")
        if __name__ == '__main__':
            expected_val = 32
            num_props = 450000
            result = simple_neural_network.forward_propagation(expected_val, num_props)
            print(f"Simple NN Result for expected {expected_val}: {result}")
    except Exception as e:
        print(f"Error running simple neural network: {e}")

def run_two_hidden_nn_wrapper(args):
    """Wrapper for the two_hidden_layers_neural_network script."""
    if not two_hidden_layers_neural_network:
        print("Two Hidden Layers NN module not available.")
        return
    print("Running Two Hidden Layers Neural Network...")
    try:
        print("Note: The two_hidden_layers_neural_network script runs a predefined example.")
        result = two_hidden_layers_neural_network.example()
        print(f"Two Hidden Layers NN example prediction: {result}")
    except Exception as e:
        print(f"Error running two hidden layers neural network: {e}")

def convert_binary_to_decimal_wrapper(args):
    """Wrapper for binary_to_decimal conversion."""
    if not binary_to_decimal:
        print("Binary to Decimal Conversion module not available.")
        return
    print(f"Converting binary '{args.binary_string}' to decimal...")
    try:
        result = binary_to_decimal.binary_to_decimal_func(args.binary_string)
        print(f"Decimal result: {result}")
    except Exception as e:
        print(f"Error converting binary to decimal: {e}")

def convert_temp_wrapper(args):
    """Wrapper for temperature conversion."""
    if not temperature_conversions:
        print("Temperature Conversion module not available.")
        return
    print(f"Converting {args.value} {args.from_unit} to {args.to_unit}...")
    try:
        value = float(args.value)
        from_unit = args.from_unit.lower()
        to_unit = args.to_unit.lower()

        if from_unit == 'celsius' and to_unit == 'fahrenheit':
            result = temperature_conversions.celsius_to_fahrenheit(value)
        elif from_unit == 'fahrenheit' and to_unit == 'celsius':
            result = temperature_conversions.fahrenheit_to_celsius(value)
        elif from_unit == 'celsius' and to_unit == 'kelvin':
            result = temperature_conversions.celsius_to_kelvin(value)
        elif from_unit == 'kelvin' and to_unit == 'celsius':
            result = temperature_conversions.kelvin_to_celsius(value)
        elif from_unit == 'fahrenheit' and to_unit == 'kelvin':
            result = temperature_conversions.fahrenheit_to_kelvin(value)
        elif from_unit == 'kelvin' and to_unit == 'fahrenheit':
            result = temperature_conversions.kelvin_to_fahrenheit(value)
        else:
            print("Unsupported temperature conversion or units.")
            return

        print(f"Conversion result: {result:.2f} {to_unit.capitalize()}")
    except ValueError:
        print("Invalid value for conversion. Please provide a number.")
    except Exception as e:
        print(f"Error performing temperature conversion: {e}")

def encrypt_caesar_wrapper(args):
    """Wrapper for Caesar Cipher encryption."""
    if not caesar_cipher:
        print("Caesar Cipher module not available.")
        return
    print(f"Encrypting message with Caesar Cipher (shift {args.shift})...")
    try:
        encrypted_message = caesar_cipher.encrypt_message(args.message, args.shift)
        print(f"Encrypted message: {encrypted_message}")
    except Exception as e:
        print(f"Error encrypting message: {e}")

# --- LLM Fine-Tuning & Evaluation Pipeline Wrappers ---

def generate_training_data_wrapper(args):
    """Wrapper for training_data_generator.py"""
    if not TrainingDataGenerator:
        print("Training Data Generator module not available.")
        return
    print(f"Generating training data to {args.output_file}...")
    try:
        generator = TrainingDataGenerator()
        all_examples = generator.generate_all_scenarios()

        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            for example in all_examples:
                f.write(json.dumps(example["conversation"]) + '\n') # TrainingEngine expects list of messages
        print(f"Successfully generated {len(all_examples)} training examples to {output_path}")
    except Exception as e:
        print(f"Error generating training data: {e}")

def split_training_data_wrapper(args):
    """Wrapper for split_training_data.py"""
    if not split_training_data:
        print("Split Training Data module not available.")
        return
    print("Splitting training data...")
    try:
        # The split_training_data script currently expects SOURCE_FILE to be in train/exports/training_data.jsonl
        # and outputs to Training_Data-Sets/
        # For dynamic input, split_training_data.py would need to be refactored.
        print("Note: split_training_data.py uses predefined paths.")
        split_training_data()
    except Exception as e:
        print(f"Error splitting training data: {e}")

def run_training_wrapper(args):
    """Wrapper for training_engine.py"""
    if not TrainingEngine:
        print("Training Engine module not available.")
        return
    print(f"Starting LLM training with base model: {args.base_model}...")
    try:
        config = {
            "model_name": args.base_model,
            "training_data_path": args.training_data_file,
            "num_epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "max_seq_length": args.max_seq_length,
            "output_dir": args.output_dir,
            "lora_r": args.lora_r,
            "lora_alpha": args.lora_alpha,
            "lora_dropout": args.lora_dropout,
            "gradient_accumulation_steps": args.gradient_accumulation_steps,
            "max_steps": args.max_steps,
            "save_checkpoints": args.save_checkpoints,
            "checkpoint_interval": args.checkpoint_interval,
            "use_mixed_precision": args.use_mixed_precision,
            "warmup_steps": args.warmup_steps,
            "early_stopping_enabled": args.early_stopping_enabled,
            "early_stopping_patience": args.early_stopping_patience,
            "max_training_time": args.max_training_time,
        }
        trainer = TrainingEngine(config=config)
        final_output_dir = trainer.run_full_training()
        print(f"LLM Training completed. Model saved to: {final_output_dir}")
    except Exception as e:
        print(f"Error during LLM training: {e}")

def run_evaluation_wrapper(args):
    """Wrapper for evaluation_engine.py"""
    if not EvaluationEngine:
        print("Evaluation Engine module not available.")
        return
    print(f"Running evaluation for model: {args.model_name} on suite: {args.test_suite}...")
    try:
        # Resolve tests_dir relative to the repo root
        tests_dir = repo_root / "Training_Data-Sets" / "Test"
        engine = EvaluationEngine(tests_dir=tests_dir)
        results = engine.run_benchmark(
            args.model_name,
            args.test_suite,
            system_prompt_name=args.system_prompt,
            tool_schema_name=args.tool_schema,
            sample_fraction=args.sample_fraction,
            inference_override=args.inference_override
        )
        print("\n--- Evaluation Results ---")
        print(json.dumps(results, indent=2))
        if args.output_file:
            with open(args.output_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to {args.output_file}")
    except Exception as e:
        print(f"Error during evaluation: {e}")

def run_merge_export_wrapper(args):
    """Wrapper for merge_and_export.py"""
    if not merge_and_export: 
        print("Merge and Export module not available.")
        return
    print(f"Merging {args.adapter_path} into {args.base_model} and exporting to GGUF...")
    try:
        output_path = merge_and_export(args.base_model, args.adapter_path, args.output_dir, args.quantization_method)
        if output_path:
            print(f"Merged and exported GGUF model to: {output_path}")
        else:
            print("GGUF export failed.")
    except Exception as e:
        print(f"Error during merge and export: {e}")

def run_export_base_wrapper(args):
    """Wrapper for export_base_to_gguf.py"""
    if not export_base_to_gguf:
        print("Export Base to GGUF module not available.")
        return
    print(f"Exporting base model {args.base_model} to GGUF...")
    try:
        output_path = export_base_to_gguf(args.base_model, args.output_dir, args.quantization_method)
        if output_path:
            print(f"Exported base GGUF model to: {output_path}")
        else:
            print("Base GGUF export failed.")
    except Exception as e:
        print(f"Error during base model export: {e}")


# --- Main Dispatcher ---

def main():
    parser = argparse.ArgumentParser(
        description="Master Orchestrator for Python-master repository functionalities.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument('--list-commands', action='store_true',
                        help='List all available commands and exit.')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Existing ML/NN/Conversion/Cipher commands
    if linear_regression:
        lr_parser = subparsers.add_parser('linear_regression', help='Run Linear Regression example.')
        lr_parser.set_defaults(func=run_linear_regression_wrapper)

    if k_means_clust:
        kmeans_parser = subparsers.add_parser('kmeans', help='Run K-Means Clustering example (Iris dataset).')
        kmeans_parser.add_argument('--k-clusters', type=int, default=3, help='Number of clusters (K).')
        kmeans_parser.add_argument('--max-iterations', type=int, default=100, help='Maximum iterations for K-Means.')
        kmeans_parser.add_argument('--seed', type=int, default=0, help='Seed for initial centroid generation.')
        kmeans_parser.add_argument('--plot', action='store_true', help='Display plots for heterogeneity and clustering.')
        kmeans_parser.set_defaults(func=run_kmeans_wrapper)

    if apriori_algorithm:
        apriori_parser = subparsers.add_parser('apriori', help='Run Apriori Algorithm example.')
        apriori_parser.add_argument('--min-support', type=int, default=2, help='Minimum support count for itemsets.')
        apriori_parser.set_defaults(func=run_apriori_wrapper)

    if simple_neural_network:
        snn_parser = subparsers.add_parser('simple_nn', help='Run Simple Neural Network example.')
        snn_parser.set_defaults(func=run_simple_nn_wrapper)

    if two_hidden_layers_neural_network:
        thlnn_parser = subparsers.add_parser('two_hidden_nn', help='Run Two Hidden Layers Neural Network example.')
        thlnn_parser.set_defaults(func=run_two_hidden_nn_wrapper)

    if binary_to_decimal:
        b2d_parser = subparsers.add_parser('bin2dec', help='Convert binary string to decimal.')
        b2d_parser.add_argument('binary_string', type=str, help='The binary string to convert (e.g., "1011").')
        b2d_parser.set_defaults(func=convert_binary_to_decimal_wrapper)

    if temperature_conversions:
        temp_parser = subparsers.add_parser('temp_convert', help='Convert temperature between units.')
        temp_parser.add_argument('value', type=str, help='The temperature value.')
        temp_parser.add_argument('from_unit', type=str, help='Unit to convert from (e.g., "celsius", "fahrenheit", "kelvin").')
        temp_parser.add_argument('to_unit', type=str, help='Unit to convert to (e.g., "celsius", "fahrenheit", "kelvin").')
        temp_parser.set_defaults(func=convert_temp_wrapper)

    if caesar_cipher:
        caesar_parser = subparsers.add_parser('caesar_encrypt', help='Encrypt a message using Caesar Cipher.')
        caesar_parser.add_argument('message', type=str, help='The message to encrypt.')
        caesar_parser.add_argument('shift', type=int, default=3, help='The shift value for the cipher.')
        caesar_parser.set_defaults(func=encrypt_caesar_wrapper)

    # --- LLM Fine-Tuning & Evaluation Pipeline Commands ---

    if TrainingDataGenerator:
        gen_data_parser = subparsers.add_parser('generate_data', help='Generate synthetic training data for LLM fine-tuning.')
        gen_data_parser.add_argument('--output-file', type=str, default=str(DATA_DIR / "exports" / "training_data.jsonl"),
                                     help='Path to save the generated training data (JSONL format).')
        gen_data_parser.set_defaults(func=generate_training_data_wrapper)
    
    if split_training_data:
        split_data_parser = subparsers.add_parser('split_data', help='Split monolithic training data into categorized files.')
        split_data_parser.set_defaults(func=split_training_data_wrapper)

    if TrainingEngine:
        train_llm_parser = subparsers.add_parser('train_llm', help='Start LLM fine-tuning process using Unsloth/Transformers.')
        train_llm_parser.add_argument('--base-model', type=str, default=os.getenv("BASE_MODEL", "unsloth/Qwen2.5-Coder-1.5B-Instruct"),
                                      help='Hugging Face model ID or path to local base model.')
        train_llm_parser.add_argument('--training-data-file', type=str, default=os.getenv("TRAINING_DATA_FILE", str(DATA_DIR / "exports" / "training_data.jsonl")),
                                      help='Path to the training data file (JSONL format).')
        train_llm_parser.add_argument('--epochs', type=int, default=int(os.getenv("TRAINING_EPOCHS", "3")),
                                      help='Number of training epochs.')
        train_llm_parser.add_argument('--batch-size', type=int, default=int(os.getenv("TRAINING_BATCH_SIZE", "2")),
                                      help='Per-device training batch size.')
        train_llm_parser.add_argument('--learning-rate', type=float, default=float(os.getenv("TRAINING_LEARNING_RATE", "2e-4")),
                                      help='Learning rate for the optimizer.')
        train_llm_parser.add_argument('--max-seq-length', type=int, default=2048,
                                      help='Maximum sequence length for tokenizer.')
        train_llm_parser.add_argument('--output-dir', type=str, default=None,
                                      help='Output directory for the trained model. Defaults to a timestamped dir in MODELS_DIR.')
        train_llm_parser.add_argument('--lora-r', type=int, default=16, help='LoRA attention dimension (r).')
        train_llm_parser.add_argument('--lora-alpha', type=int, default=16, help='Alpha parameter for LoRA scaling.')
        train_llm_parser.add_argument('--lora-dropout', type=float, default=0.0, help='Dropout probability for LoRA layers.')
        train_llm_parser.add_argument('--gradient-accumulation-steps', type=int, default=int(os.getenv("RUNNER_GRADIENT_ACCUMULATION", "4")),
                                      help='Number of updates steps to accumulate before performing a backward/update pass.')
        train_llm_parser.add_argument('--max-steps', type=int, default=-1,
                                      help='If > 0: set total number of training steps to perform. -1 means train for full epochs.')
        train_llm_parser.add_argument('--save-checkpoints', type=bool, default=os.getenv("RUNNER_SAVE_CHECKPOINTS", "True").lower() == "true",
                                      help='Whether to save checkpoints during training.')
        train_llm_parser.add_argument('--checkpoint-interval', type=int, default=int(os.getenv("RUNNER_CHECKPOINT_INTERVAL", "100")),
                                      help='Number of steps between saving checkpoints.')
        train_llm_parser.add_argument('--use-mixed-precision', type=bool, default=os.getenv("RUNNER_MIXED_PRECISION", "True").lower() == "true",
                                      help='Whether to use mixed precision (FP16/BF16) training.')
        train_llm_parser.add_argument('--warmup-steps', type=int, default=int(os.getenv("RUNNER_WARMUP_STEPS", "5")),
                                      help='Number of warmup steps for learning rate scheduler.')
        train_llm_parser.add_argument('--early-stopping-enabled', type=bool, default=os.getenv("RUNNER_EARLY_STOPPING", "False").lower() == "true",
                                      help='Enable early stopping during training.')
        train_llm_parser.add_argument('--early-stopping-patience', type=int, default=int(os.getenv("RUNNER_EARLY_STOPPING_PATIENCE", "3")),
                                      help='Number of evaluation steps to wait before stopping if no improvement.')
        train_llm_parser.add_argument('--max-training-time', type=int, default=int(os.getenv("RUNNER_MAX_TIME", "120")),
                                      help='Maximum training time in minutes. 0 for no limit.')
        train_llm_parser.set_defaults(func=run_training_wrapper)

    if EvaluationEngine:
        eval_llm_parser = subparsers.add_parser('evaluate_llm', help='Evaluate a fine-tuned LLM adapter on a test suite.')
        eval_llm_parser.add_argument('--model-name', type=str, required=True,
                                     help='Name of the model (adapter) to evaluate (e.g., training_Qwen2.5-Coder-1.5B_20231027_123456).')
        eval_llm_parser.add_argument('--test-suite', type=str, default="Tools",
                                     help='Name of the test suite to run (e.g., "Tools", "All").')
        eval_llm_parser.add_argument('--system-prompt', type=str, default=None,
                                     help='Optional: name of the system prompt to use for inference.')
        eval_llm_parser.add_argument('--tool-schema', type=str, default=None,
                                     help='Optional: name of the tool schema to use for inference.')
        eval_llm_parser.add_argument('--sample-fraction', type=float, default=None,
                                     help='Optional: fraction of test cases to sample (e.g., 0.1 for 10%%).')
        eval_llm_parser.add_argument('--inference-override', type=str, default=None,
                                     help='Optional: Override model used for inference (e.g., a specific Ollama model tag).')
        eval_llm_parser.add_argument('--output-file', type=str, default=None,
                                     help='Optional: Path to save the evaluation results (JSON format).')
        eval_llm_parser.set_defaults(func=run_evaluation_wrapper)
    
    if merge_and_export:
        merge_export_parser = subparsers.add_parser('merge_export', help='Merge LoRA adapter into base model and export to GGUF.')
        merge_export_parser.add_argument('--base-model', type=str, required=True,
                                         help='Path to the base model directory or Hugging Face ID.')
        merge_export_parser.add_argument('--adapter-path', type=str, required=True,
                                         help='Path to the LoRA adapter directory (output of train_llm).')
        merge_export_parser.add_argument('--output-dir', type=str, default=str(MODELS_DIR.parent / "exports" / "gguf"),
                                         help='Directory to save the GGUF file.')
        merge_export_parser.add_argument('--quantization-method', type=str, default="q4_k_m",
                                         help='Quantization method (e.g., q4_k_m, q5_k_m, q8_0).')
        merge_export_parser.set_defaults(func=run_merge_export_wrapper)

    if export_base_to_gguf:
        export_base_parser = subparsers.add_parser('export_base', help='Export a base PyTorch model directly to GGUF format.')
        export_base_parser.add_argument('--base-model', type=str, required=True,
                                        help='Path to the base model directory or Hugging Face ID.')
        export_base_parser.add_argument('--output-dir', type=str, default=str(MODELS_DIR.parent / "exports" / "gguf"),
                                        help='Directory to save the GGUF file.')
        export_base_parser.add_argument('--quantization-method', type=str, default="q4_k_m",
                                        help='Quantization method (e.g., q4_k_m, q5_k_m, q8_0).')
        export_base_parser.set_defaults(func=run_export_base_wrapper)


    args = parser.parse_args()

    if args.list_commands:
        print("Available commands:")
        # Dynamically list commands from subparsers.choices
        for command_name, subparser in subparsers.choices.items():
            print(f"- {command_name}: {subparser.help}")
        return

    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
