#!/usr/bin/env python3
# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Central configuration for Trainer
Defines all paths and settings
"""

from pathlib import Path
from typing import Dict, List, Any # Added import for Any
from typing import Optional

# Root directories
TRAINER_ROOT = Path(__file__).parent.parent
DATA_DIR = TRAINER_ROOT / "Data"
MODELS_DIR = TRAINER_ROOT / "Models"
TRAINING_DATA_DIR = TRAINER_ROOT / "Training_Data-Sets"

# Training data subdirectories
TOOLS_DATA_DIR = TRAINING_DATA_DIR / "Tools"
APP_DEV_DATA_DIR = TRAINING_DATA_DIR / "App_Development"
CODING_DATA_DIR = TRAINING_DATA_DIR / "Coding"
SEMANTIC_DATA_DIR = TRAINING_DATA_DIR / "Semantic_States"
PROMPTS_DIR = TRAINING_DATA_DIR / "Prompts"
SCHEMAS_DIR = TRAINING_DATA_DIR / "Schemas"
PROMPTBOX_DIR = TRAINING_DATA_DIR / "PromptBox"

# Export directories
EXPORTS_DIR = DATA_DIR / "exports"
PROFILES_DIR = DATA_DIR / "profiles" # New: Profiles directory
TOOL_PROFILES_DIR = PROFILES_DIR / "Tools"
OLLAMA_ASSIGNMENTS_PATH = DATA_DIR / "ollama_assignments.json"

# L8 FIX: Sandbox directory for tool execution
THE_SANDBOX_DIR = TRAINER_ROOT / "The_SandBox"

# Ensure all directories exist
for dir_path in [MODELS_DIR, TRAINING_DATA_DIR, TOOLS_DATA_DIR,
                 APP_DEV_DATA_DIR, CODING_DATA_DIR, SEMANTIC_DATA_DIR,
                 PROMPTS_DIR, SCHEMAS_DIR, PROMPTBOX_DIR,
                 EXPORTS_DIR, PROFILES_DIR, TOOL_PROFILES_DIR, THE_SANDBOX_DIR]: # L8: Added THE_SANDBOX_DIR
    dir_path.mkdir(parents=True, exist_ok=True)

# Default training settings
DEFAULT_CONFIG = {
    "model": {
        "base_name": "unsloth/Qwen2.5-Coder-1.5B-Instruct",
        "max_seq_length": 2048,
        "load_in_4bit": True,
    },
    "lora": {
        "r": 16,
        "alpha": 16,
        "dropout": 0,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj",
                          "gate_proj", "up_proj", "down_proj"],
    },
    "training": {
        "batch_size": 2,
        "gradient_accumulation_steps": 4,
        "learning_rate": 2e-4,
        "num_epochs": 3,
        "warmup_steps": 5,
    },
    "paths": {
        "models_dir": str(MODELS_DIR),
        "training_data_dir": str(TRAINING_DATA_DIR),
        "exports_dir": str(EXPORTS_DIR),
    }
}

def get_latest_model_dir():
    """Get the most recently created model directory"""
    if not MODELS_DIR.exists():
        return None

    model_dirs = [d for d in MODELS_DIR.iterdir() if d.is_dir() and d.name.startswith('training_')]
    if not model_dirs:
        return None

    return max(model_dirs, key=lambda d: d.stat().st_mtime)


# --- WO-6a: variant naming helper ---------------------------------
def derive_variant_name(base_model: str, type_id: str) -> str:
    """
    Deterministic variant id from base + type.
    Example: 'Qwen2.5-0.5b-Instruct' + 'researcher' -> 'Qwen2.5-0.5b_researcher'
    """
    base = (base_model or "").strip().replace(" ", "_")
    # Trim common suffix to keep ids shorter
    base = base.replace("-Instruct", "")
    return f"{base}_{(type_id or '').strip()}".replace("__", "_")
# -------------------------------------------------------------------


import subprocess # New import for get_ollama_models

def get_ollama_models() -> List[str]:
    """
    Detects and returns a list of available Ollama models.

    Returns:
        A list of model names (e.g., ["llama2", "mistral"]).
        Returns an empty list if Ollama is not found or no models are available.
    """
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')
        if not lines:
            return []

        # Skip header line
        models = []
        for line in lines[1:]:
            parts = line.split()
            if parts:
                models.append(parts[0]) # Model name is the first part
        return sorted(models)
    except FileNotFoundError:
        print("Warning: Ollama command not found. Please ensure Ollama is installed and in your PATH.")
        return []
    except subprocess.CalledProcessError as e:
        print(f"Warning: Ollama command failed: {e.stderr}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred while listing Ollama models: {e}")
        return []


def get_local_pytorch_models() -> List[str]:
    """
    Scans MODELS_DIR for local PyTorch models (directories with config.json).

    Returns:
        A list of local model paths that can be used for training.
    """
    local_models = []

    if not MODELS_DIR.exists():
        return local_models

    # Scan for directories containing config.json (HuggingFace model format)
    for model_dir in MODELS_DIR.iterdir():
        if model_dir.is_dir():
            config_file = model_dir / "config.json"
            if config_file.exists():
                local_models.append(str(model_dir))

    return sorted(local_models)


def get_all_available_models() -> List[str]:
    """
    Returns a combined list of Ollama models and local PyTorch models.
    Local models are prefixed with "LOCAL: " for clarity.

    Returns:
        Combined list of available models for training.
    """
    models = []

    # Add local PyTorch models first (these can actually be trained)
    local_models = get_local_pytorch_models()
    for model_path in local_models:
        # Use just the directory name for display, but store full path
        model_name = Path(model_path).name
        models.append(f"LOCAL: {model_name} ({model_path})")

    # Add note separator
    if local_models and get_ollama_models():
        models.append("─" * 50)

    # Add Ollama models (for reference - cannot be trained directly)
    ollama_models = get_ollama_models()
    for model in ollama_models:
        models.append(f"OLLAMA: {model} (GGUF - not trainable)")

    return models


def get_all_trained_models() -> List[Dict]:
    """
    Discover ALL models available in the system:
    1. Local PyTorch models (base models in Models/)
    2. Trained models (Models/training_*)
    3. Ollama models (GGUF format)

    Returns:
        List of dicts with model metadata:
        [
            {
                "name": "Qwen2.5-0.5b-Instruct",
                "type": "pytorch",  # "pytorch", "trained", or "ollama"
                "path": Path object or None (for Ollama),
                "has_stats": True/False,
                "size": "500MB" or None
            },
            ...
        ]
    """
    import os

    all_models = []

    # 1. Local PyTorch models and trained models
    if MODELS_DIR.exists():
        for model_dir in MODELS_DIR.iterdir():
            if model_dir.is_dir():
                config_file = model_dir / "config.json"
                is_trained_dir = model_dir.name.startswith("training_")

                # Check if it's a PyTorch model (has config.json) OR a trained output directory
                if config_file.exists() or is_trained_dir:
                    # Determine if it's a trained model or base model
                    is_trained = is_trained_dir

                    # Check for stats
                    stats_file = MODELS_DIR / "stats" / f"{model_dir.name}.json"
                    has_stats = stats_file.exists()

                    # Get size
                    try:
                        size_bytes = sum(f.stat().st_size for f in model_dir.rglob('*') if f.is_file())
                        size_mb = size_bytes / (1024 * 1024)
                        if size_mb > 1024:
                            size_str = f"{size_mb/1024:.1f}GB"
                        else:
                            size_str = f"{size_mb:.0f}MB"
                    except:
                        size_str = "Unknown"

                    all_models.append({
                        "name": model_dir.name,
                        "type": "trained" if is_trained else "pytorch",
                        "path": model_dir,
                        "has_stats": has_stats,
                        "size": size_str
                    })

    # 2. Ollama models (GGUF format)
    ollama_models = get_ollama_models()
    for model_name in ollama_models:
        all_models.append({
            "name": model_name,
            "type": "ollama",
            "path": None,  # Ollama manages paths internally
            "has_stats": False,  # Ollama models don't have training stats
            "size": None  # Could query via ollama list, but skip for now
        })

    return all_models


def get_training_data_path(category: str = "Tools") -> Path:
    """
    Get training data path for a specific category

    Args:
        category: One of "Tools", "App_Development", "Coding", "Semantic_States"

    Returns:
        Path to training data directory
    """
    category_map = {
        "Tools": TOOLS_DATA_DIR,
        "App_Development": APP_DEV_DATA_DIR,
        "Coding": CODING_DATA_DIR,
        "Semantic_States": SEMANTIC_DATA_DIR,
    }

    return category_map.get(category, TOOLS_DATA_DIR)

def get_category_files(category: str) -> list:
    """
    Get all JSONL files in a category directory

    Args:
        category: Category name (Tools, Coding, etc.)

    Returns:
        List of Path objects to JSONL files
    """
    category_dir = get_training_data_path(category)
    if not category_dir.exists():
        return []
    return list(category_dir.glob("*.jsonl"))

def count_examples(file_path: Path) -> int:
    """
    Count examples in a JSONL file

    Args:
        file_path: Path to JSONL file

    Returns:
        Number of examples
    """
    try:
        with open(file_path) as f:
            return sum(1 for _ in f)
    except:
        return 0

def get_training_data_files(categories: list, subcategories: dict = None) -> list:
    """
    Get training data files for selected categories/subcategories

    Args:
        categories: List of category names ["Tools", "Coding", ...]
        subcategories: Optional dict mapping categories to specific files
                      {"Tools": ["file_operations", "search_operations"]}

    Returns:
        List of Path objects to JSONL files
    """
    files = []

    for category in categories:
        cat_dir = get_training_data_path(category)

        if subcategories and category in subcategories:
            # Specific subcategories
            for subcat in subcategories[category]:
                file_path = cat_dir / f"{subcat}.jsonl"
                if file_path.exists():
                    files.append(file_path)
        else:
            # All files in category
            files.extend(cat_dir.glob("*.jsonl"))

    return files

def get_category_info() -> dict:
    """
    Get information about all categories and their files

    Returns:
        Dict mapping categories to their files and example counts
        {
            "Tools": {
                "files": [Path(...), ...],
                "subcategories": {
                    "file_operations": {"path": Path(...), "count": 5},
                    ...
                },
                "total_examples": 15
            },
            ...
        }
    """
    import json
    categories = ["Tools", "App_Development", "Coding", "Semantic_States"]
    info = {}

    for category in categories:
        cat_dir = get_training_data_path(category)
        files = list(cat_dir.glob("*.jsonl")) if cat_dir.exists() else []

        subcats = {}
        total = 0

        for file in files:
            count = count_examples(file)
            subcat_name = file.stem  # Remove .jsonl extension
            subcats[subcat_name] = {
                "path": file,
                "count": count
            }
            total += count

        info[category] = {
            "files": files,
            "subcategories": subcats,
            "total_examples": total
        }

    return info

def create_model_output_dir(model_name: str) -> Path:
    """
    Create output directory for a new model

    Args:
        model_name: Name of the model being trained

    Returns:
        Path to new model output directory
    """
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_name = model_name.replace('/', '_').replace(':', '_')
    dir_name = f"training_{clean_name}_{timestamp}"

    output_dir = MODELS_DIR / dir_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (output_dir / "checkpoints").mkdir(exist_ok=True)
    (output_dir / "logs").mkdir(exist_ok=True)
    (output_dir / "exports").mkdir(exist_ok=True)

    return output_dir


# --- Training Data Management Functions ---

def create_category_folder(category_name: str) -> Path:
    """
    Creates a new category folder under TRAINING_DATA_DIR.
    Also updates the category_map in get_training_data_path if it's a new category.

    Args:
        category_name: The name of the new category.

    Returns:
        Path to the newly created category directory.

    Raises:
        FileExistsError: If the category folder already exists.
    """
    new_category_path = TRAINING_DATA_DIR / category_name
    if new_category_path.exists():
        raise FileExistsError(f"Category folder '{category_name}' already exists.")
    new_category_path.mkdir(parents=True, exist_ok=True)

    # Dynamically update the category_map in get_training_data_path
    # This is a bit hacky, but avoids re-importing or global state issues
    # A more robust solution might involve a class for config.
    # For now, we'll rely on the GUI to re-read category info.
    return new_category_path

def create_subcategory_file(category_name: str, subcategory_name: str, content: str = None) -> Path:
    """
    Creates a .jsonl file for a new subcategory within an existing category.

    Args:
        category_name: The name of the existing category.
        subcategory_name: The name of the new subcategory (will be used as filename).
        content: Optional content to write to the new file.

    Returns:
        Path to the newly created subcategory file.

    Raises:
        FileNotFoundError: If the category folder does not exist.
        FileExistsError: If the subcategory file already exists.
    """
    # First, try to get path from the dynamic map
    category_path = get_training_data_path(category_name)
    # If not found, assume it's a direct subdirectory of TRAINING_DATA_DIR
    if not category_path.exists() or category_name not in ["Tools", "App_Development", "Coding", "Semantic_States"]:
        category_path = TRAINING_DATA_DIR / category_name
        category_path.mkdir(parents=True, exist_ok=True)


    new_subcategory_path = category_path / f"{subcategory_name}.jsonl"
    if new_subcategory_path.exists():
        raise FileExistsError(f"Subcategory file '{subcategory_name}.jsonl' already exists in '{category_name}'.")

    # Create the file with optional content
    with open(new_subcategory_path, 'w') as f:
        if content:
            f.write(content)
        else:
            pass # Create empty file

    return new_subcategory_path


def create_script_file(category_name: str, script_name: str, content: str = None) -> Path:
    """
    Creates a .py script file in a given category.

    Args:
        category_name: The name of the category.
        script_name: The name of the script (with or without .py extension).
        content: Optional content to write to the new file.

    Returns:
        Path to the newly created script file.
    """
    category_path = TRAINING_DATA_DIR / category_name
    category_path.mkdir(parents=True, exist_ok=True)

    if not script_name.endswith('.py'):
        script_name += '.py'

    script_path = category_path / script_name
    if script_path.exists():
        raise FileExistsError(f"Script file '{script_name}' already exists in '{category_name}'.")

    with open(script_path, 'w') as f:
        if content:
            f.write(content)

    return script_path


def list_schema_categories() -> List[str]:
    """Scans the SCHEMAS_DIR for sub-directories to be used as categories."""
    if not SCHEMAS_DIR.exists():
        return []
    return sorted([d.name for d in SCHEMAS_DIR.iterdir() if d.is_dir()])


def create_schema_file(name: str, category: str = None, content: str = None) -> Path:
    """
    Creates a .json schema file, optionally within a category (sub-folder).

    Args:
        name: The name of the schema (without extension).
        category: Optional sub-folder to create the file in.
        content: Optional JSON string content to write to the new file.

    Returns:
        Path to the newly created schema file.
    """
    target_dir = SCHEMAS_DIR
    if category and category.strip():
        target_dir = SCHEMAS_DIR / category.strip()
    
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{name}.json"

    if file_path.exists():
        raise FileExistsError(f"Schema file '{name}.json' already exists in the specified location.")

    with open(file_path, 'w') as f:
        if content:
            f.write(content)
        else:
            # Default template
            import json
            json.dump({"tools": []}, f, indent=2)

    return file_path


def list_prompt_categories() -> List[str]:
    """Scans the PROMPTS_DIR for sub-directories to be used as categories."""
    if not PROMPTS_DIR.exists():
        return []
    return sorted([d.name for d in PROMPTS_DIR.iterdir() if d.is_dir()])


def create_prompt_file(name: str, category: str = None, content: str = None) -> Path:
    """
    Creates a .json prompt file, optionally within a category (sub-folder).

    Args:
        name: The name of the prompt (without extension).
        category: Optional sub-folder to create the file in.
        content: Optional JSON string content to write to the new file.

    Returns:
        Path to the newly created prompt file.
    """
    target_dir = PROMPTS_DIR
    if category and category.strip():
        target_dir = PROMPTS_DIR / category.strip()
    
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{name}.json"

    if file_path.exists():
        raise FileExistsError(f"Prompt file '{name}.json' already exists in the specified location.")

    with open(file_path, 'w') as f:
        if content:
            f.write(content)
        else:
            # Default template
            import json
            json.dump({"prompt": ""}, f, indent=2)

    return file_path

    return file_path


# --- Semantic States Management Functions ---
import json

def _list_semantic_files(file_prefix: str) -> List[str]:
    """
    Lists all JSON files in the SEMANTIC_DATA_DIR that match a given file_prefix.
    Returns the base names of these files (without the .json extension and without the prefix).
    """
    if not SEMANTIC_DATA_DIR.exists():
        return []
    
    files = []
    for f in SEMANTIC_DATA_DIR.glob(f"{file_prefix}_*.json"):
        files.append(f.stem.replace(f"{file_prefix}_", ""))
    return sorted(files)

def _load_semantic_file(file_prefix: str, name: str) -> Dict:
    """
    Loads a specific JSON file from SEMANTIC_DATA_DIR based on its file_prefix and name.
    """
    file_path = SEMANTIC_DATA_DIR / f"{file_prefix}_{name}.json"
    if not file_path.exists():
        raise FileNotFoundError(f"{file_prefix.replace('_', ' ').title()} '{name}' not found at {file_path}")
    with open(file_path, 'r') as f:
        return json.load(f)

def list_system_prompts() -> List[str]:
    """
    Lists all available system prompt names across supported locations.
    """
    names = set()
    # Legacy Semantic_States
    names.update(_list_semantic_files("system_prompt"))
    # New Prompts directory (category-based): any *.json basename
    if PROMPTS_DIR.exists():
        for p in PROMPTS_DIR.rglob("*.json"):
            names.add(p.stem)
    # PromptBox: *.txt files -> treat as prompts
    if PROMPTBOX_DIR.exists():
        for p in PROMPTBOX_DIR.glob("*.txt"):
            names.add(p.stem)
    return sorted(names)

def load_system_prompt(name: str) -> Dict:
    """
    Loads a specific system prompt by name from any supported location.
    """
    # 1) Semantic_States JSON
    try:
        return _load_semantic_file("system_prompt", name)
    except FileNotFoundError:
        pass
    # 2) Prompts directory JSON
    cand = None
    for p in PROMPTS_DIR.rglob("*.json"):
        if p.stem == name:
            cand = p; break
    if cand and cand.exists():
        with open(cand, 'r') as f:
            return json.load(f)
    # 3) PromptBox TXT → wrap as {"prompt": text}
    txt_path = PROMPTBOX_DIR / f"{name}.txt"
    if txt_path.exists():
        return {"prompt": txt_path.read_text()}
    raise FileNotFoundError(f"System prompt '{name}' not found in Semantic_States, Prompts, or PromptBox.")

def list_tool_schemas() -> List[str]:
    """
    Lists all available tool schema names across supported locations.
    """
    names = set()
    # Legacy Semantic_States
    names.update(_list_semantic_files("tool_schema"))
    # New Schemas directory (category-based): any *.json basename
    if SCHEMAS_DIR.exists():
        for p in SCHEMAS_DIR.rglob("*.json"):
            names.add(p.stem)
    return sorted(names)

def load_tool_schema(name: str) -> Dict:
    """
    Loads a specific tool schema by name from any supported location.
    """
    # 1) Semantic_States JSON
    try:
        return _load_semantic_file("tool_schema", name)
    except FileNotFoundError:
        pass
    # 2) Schemas directory JSON
    cand = None
    for p in SCHEMAS_DIR.rglob("*.json"):
        if p.stem == name:
            cand = p; break
    if cand and cand.exists():
        with open(cand, 'r') as f:
            return json.load(f)
    raise FileNotFoundError(f"Tool schema '{name}' not found in Semantic_States or Schemas directory.")


# -------------------------------
# Tool Profile (Unified) Support
# -------------------------------
def list_tool_profiles() -> List[str]:
    """Return names of Tool Profiles under Data/profiles/Tools."""
    if not TOOL_PROFILES_DIR.exists():
        return []
    names = []
    for p in sorted(TOOL_PROFILES_DIR.glob("*.json")):
        try:
            # L7 FIX: Filter out dotfiles, .bak, .tmp, and non-JSON files
            if p.is_file() and p.suffix == ".json" and not p.stem.startswith("."):
                names.append(p.stem)
        except Exception:
            continue
    return names

def load_tool_profile(name: str = "Default") -> Dict[str, Any]:
    """Load a Tool Profile by name with soft validation and defaults."""
    import shutil
    path = TOOL_PROFILES_DIR / f"{name}.json"
    bak_path = path.with_suffix(".json.bak")

    # M4 FIX: Auto-recovery from .bak if .json missing
    if not path.exists() and bak_path.exists():
        shutil.copy2(bak_path, path)

    if not path.exists():
        raise FileNotFoundError(f"Tool Profile '{name}' not found at {path}")

    # Default structure for missing sections
    defaults = {
        "tools": {"enabled_tools": {}, "risk_overrides": {}, "confirmation_policy": {}, "timeouts_sec": {}, "logging": {}},
        "execution": {"working_directory": str((Path(__file__).parent.parent / "The_SandBox")), "auto_update_working_dir": True},
        "chat": {"auto_mount_model": False, "auto_save_history": True, "history_retention_days": 30, "max_message_length": 8192},
        "orchestrator": {"enable_orchestrator": False, "enable_parsers": True, "enable_translators": True},
        "notes": ""
    }

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Soft-validate: inject missing top-level keys
        for key, default_value in defaults.items():
            if key not in data:
                data[key] = default_value
            elif isinstance(default_value, dict) and isinstance(data[key], dict):
                # Merge nested defaults
                for subkey, subval in default_value.items():
                    data[key].setdefault(subkey, subval)

        return data
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Invalid JSON in Tool Profile '{name}': {e}")

def save_tool_profile(name: str, profile: Dict[str, Any]) -> Path:
    """Save a Tool Profile by name with atomic write and backup."""
    import os
    from datetime import datetime
    TOOL_PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    profile = dict(profile or {})
    profile.setdefault("profile_name", name)
    profile.setdefault("version", "1.0")
    profile["updated_at"] = datetime.now().isoformat()

    # M5 FIX: Normalize defaults before save (same structure as load)
    defaults = {
        "tools": {"enabled_tools": {}, "risk_overrides": {}, "confirmation_policy": {}, "timeouts_sec": {}, "logging": {}},
        "execution": {"working_directory": str((Path(__file__).parent.parent / "The_SandBox")), "auto_update_working_dir": True},
        "chat": {"auto_mount_model": False, "auto_save_history": True, "history_retention_days": 30, "max_message_length": 8192},
        "orchestrator": {"enable_orchestrator": False, "enable_parsers": True, "enable_translators": True},
        "notes": ""
    }
    for key, default_value in defaults.items():
        if key not in profile:
            profile[key] = default_value
        elif isinstance(default_value, dict) and isinstance(profile[key], dict):
            for subkey, subval in default_value.items():
                profile[key].setdefault(subkey, subval)

    path = TOOL_PROFILES_DIR / f"{name}.json"
    tmp_path = path.with_suffix(".json.tmp")
    bak_path = path.with_suffix(".json.bak")

    # Atomic write: tmp → replace existing
    try:
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        # Backup existing file if present
        if path.exists():
            path.replace(bak_path)

        # Atomic replace
        tmp_path.replace(path)

        # H2 FIX: Directory fsync for durability (Linux-only; guard for Windows)
        if hasattr(os, "O_DIRECTORY"):
            dir_fd = os.open(str(TOOL_PROFILES_DIR), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        # On platforms without O_DIRECTORY (e.g., Windows), skip; atomic replace is sufficient.

        return path
    except Exception as e:
        # Cleanup tmp on failure
        if tmp_path.exists():
            tmp_path.unlink()
        raise RuntimeError(f"Failed to save Tool Profile '{name}': {e}")

def _load_legacy_tool_flags() -> Dict[str, bool]:
    """
    Read legacy enabled_tools from Tools tab's persistence.
    Expected shape matches current tools_tab usage.
    """
    # Legacy location (relative to custom_code_tab)
    legacy = Path(__file__).parent / "tabs" / "custom_code_tab" / "tool_settings.json"
    if legacy.exists():
        try:
            with open(legacy, "r") as f:
                data = json.load(f) or {}
            return (data.get("enabled_tools") or {}) if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}

def _load_legacy_custom_code_settings() -> Dict[str, Any]:
    """
    Read legacy chat/execution settings used by Settings tab.
    """
    legacy = Path(__file__).parent / "tabs" / "custom_code_tab" / "custom_code_settings.json"
    if legacy.exists():
        try:
            with open(legacy, "r") as f:
                data = json.load(f) or {}
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}

def _load_settings_flags() -> Dict[str, Any]:
    """
    Read a few orchestrator-related toggles from Data/settings.json with safe defaults.
    """
    path = DATA_DIR / "settings.json"
    defaults = {
        "enable_tool_orchestrator": False,
        "enable_parsers": True,
        "enable_translators": True
    }
    try:
        if path.exists():
            with open(path, "r") as f:
                raw = json.load(f) or {}
            # normalize expected keys if present
            merged = {
                "enable_tool_orchestrator": raw.get("enable_tool_orchestrator", defaults["enable_tool_orchestrator"]),
                "enable_parsers": raw.get("enable_parsers", defaults["enable_parsers"]),
                "enable_translators": raw.get("enable_translators", defaults["enable_translators"]),
            }
            return merged
    except Exception:
        pass
    return defaults

def migrate_tool_profile_from_legacy(name: str = "Default") -> Dict[str, Any]:
    """
    Create a unified Tool Profile from legacy files if a Tool Profile doesn't exist yet.
    Non-destructive: leaves legacy files as-is; callers may delete after verification.
    Idempotent: won't re-migrate if migration marker is present OR if profile already exists.
    """
    from datetime import datetime

    # H1 FIX: If profile exists at all, do NOT overwrite; only add marker if missing
    try:
        existing = load_tool_profile(name)
        # Profile exists; ensure it has a marker, then return
        if not existing.get("_migration_marker"):
            existing["_migration_marker"] = {
                "migrated_from": {"files": [], "at": datetime.now().isoformat(), "version": 1}
            }
            save_tool_profile(name, existing)
        return existing
    except FileNotFoundError:
        pass  # Doesn't exist yet; proceed with first-time migration

    enabled = _load_legacy_tool_flags()
    legacy_settings = _load_legacy_custom_code_settings()
    flags = _load_settings_flags()

    # Collect source file paths for audit trail
    legacy_tool_path = Path(__file__).parent / "tabs" / "custom_code_tab" / "tool_settings.json"
    legacy_settings_path = Path(__file__).parent / "tabs" / "custom_code_tab" / "custom_code_settings.json"
    settings_path = DATA_DIR / "settings.json"

    migration_marker = {
        "migrated_from": {
            "files": [
                str(p) for p in [legacy_tool_path, legacy_settings_path, settings_path] if p.exists()
            ],
            "at": datetime.now().isoformat(),
            "version": 1
        }
    }

    # Map legacy flat settings into unified sections
    working_directory = legacy_settings.get("working_directory") or str((Path(__file__).parent.parent / "The_SandBox"))
    chat = {
        "auto_mount_model": bool(legacy_settings.get("auto_mount_model", False)),
        "auto_save_history": bool(legacy_settings.get("auto_save_history", True)),
        "history_retention_days": int(legacy_settings.get("history_retention_days", 30)),
        "max_message_length": int(legacy_settings.get("max_message_length", 8192))
    }
    execution = {
        "working_directory": working_directory,
        "auto_update_working_dir": bool(legacy_settings.get("auto_update_working_dir", True)),
        "default_project_dir": legacy_settings.get("default_project_dir") or working_directory
    }
    orchestrator = {
        "enable_orchestrator": bool(flags.get("enable_tool_orchestrator", False)),
        "enable_parsers": bool(flags.get("enable_parsers", True)),
        "enable_translators": bool(flags.get("enable_translators", True))
    }
    profile = {
        "profile_name": name,
        "version": "1.0",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "tools": {
            "enabled_tools": enabled,
            "risk_overrides": {},
            "confirmation_policy": {
                "default_minimum_risk_to_confirm": "medium",
                "per_tool_minimum_risk_to_confirm": {}
            },
            "timeouts_sec": {},
            "logging": { "tool_calls": True, "verbose": False }
        },
        "execution": execution,
        "chat": chat,
        "orchestrator": orchestrator,
        "notes": "Auto-migrated from legacy settings",
        "_migration_marker": migration_marker
    }
    save_tool_profile(name, profile)
    return profile

def get_unified_tool_profile(name: str = "Default", *, migrate: bool = True) -> Dict[str, Any]:
    """Load a Tool Profile, optionally migrating from legacy sources on first use."""
    try:
        return load_tool_profile(name)
    except FileNotFoundError:
        if migrate:
            return migrate_tool_profile_from_legacy(name)
        raise


# --- Profile Management Functions ---
import json

def save_profile(profile_name: str, config: Dict) -> Path:
    """
    Saves a training configuration profile to a JSON file.

    Args:
        profile_name: The name of the profile (will be used as filename).
        config: A dictionary containing the training configuration.

    Returns:
        Path to the saved profile file.
    """
    profile_path = PROFILES_DIR / f"{profile_name}.json"
    with open(profile_path, 'w') as f:
        json.dump(config, f, indent=2)
    return profile_path

def load_profile(profile_name: str) -> Dict:
    """
    Loads a training configuration profile from a JSON file.

    Args:
        profile_name: The name of the profile to load.

    Returns:
        A dictionary containing the training configuration.

    Raises:
        FileNotFoundError: If the profile file does not exist.
    """
    profile_path = PROFILES_DIR / f"{profile_name}.json"
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile '{profile_name}' not found at {profile_path}")
    with open(profile_path, 'r') as f:
        return json.load(f)

def list_profiles() -> List[str]:
    """
    Lists all available training profile names.

    Returns:
        A list of profile names (filenames without .json extension).
    """
    return sorted([f.stem for f in PROFILES_DIR.glob("*.json")])


def get_ollama_model_info(model_name: str) -> str:
    """
    Retrieves detailed information for a specific Ollama model.

    Args:
        model_name: The full name of the Ollama model (e.g., "llama2:latest").

    Returns:
        A string containing the raw output from "ollama show <model_name>".
        Returns an error message string if the command fails.
    """
    try:
        result = subprocess.run(["ollama", "show", model_name], capture_output=True, text=True, check=True)
        return result.stdout
    except FileNotFoundError:
        return f"Error: Ollama command not found. Is Ollama installed and in your PATH?"
    except subprocess.CalledProcessError as e:
        return f"Error: Failed to get info for '{model_name}': {e.stderr}"
    except Exception as e:
        return f"An unexpected error occurred while getting model info for '{model_name}': {e}"


def parse_ollama_model_info(raw_info: str) -> Dict[str, str]:
    """
    Parses the raw output from 'ollama show <model_name>' into a dictionary of key details.

    Args:
        raw_info: The raw string output from 'ollama show'.

    Returns:
        A dictionary containing parsed model information.
    """
    parsed_data = {}
    lines = raw_info.split('\n')
    current_section = None

    for line in lines:
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # Detect section headers (not indented, ends with optional colon)
        if not line.startswith(' ') and not line.startswith('\t'):
            current_section = stripped.rstrip(':')
            continue

        # Parse indented key-value pairs
        if line.startswith(' ') or line.startswith('\t'):
            # Look for lines with at least 2 consecutive spaces (indicating key-value separation)
            if '    ' in line:  # At least 4 spaces
                parts = [p for p in line.split('    ') if p.strip()]
                if len(parts) >= 2:
                    key = parts[0].strip()
                    value = ' '.join(parts[1:]).strip()

                    # Create a normalized key
                    normalized_key = key.lower().replace(' ', '_')

                    # Add section prefix for better organization
                    if current_section and current_section.lower() not in ['license']:
                        section_prefix = current_section.lower().replace(' ', '_')
                        normalized_key = f"{section_prefix}_{normalized_key}"

                    parsed_data[normalized_key] = value

    return parsed_data


# Model Notes Management
MODEL_NOTES_DIR = TRAINER_ROOT / "model_notes"

def get_model_notes_dir(model_info: Dict) -> Path:
    """
    Get the directory where notes for a specific model are stored.
    Creates it if it doesn't exist.

    Args:
        model_info: Dictionary containing model metadata (name, type, path).

    Returns:
        Path to the model's notes directory.
    """
    model_type = model_info.get("type")
    
    if model_type in ["pytorch", "trained"]:
        # For local models, store notes inside the model's own directory
        base_path = Path(model_info["path"])
        notes_dir = base_path / "model_notes"
    else:
        # For Ollama models, use the central notes directory
        model_name = model_info["name"].replace('/', '_').replace(':', '_')
        notes_dir = MODEL_NOTES_DIR / model_name

    notes_dir.mkdir(parents=True, exist_ok=True)
    return notes_dir


def save_model_note(model_info: Dict, note_name: str, content: str) -> Path:
    """
    Save a note for a specific model.

    Args:
        model_info: Dictionary containing model metadata.
        note_name: Name of the note file (without .txt extension).
        content: Text content to save.

    Returns:
        Path to saved note file.
    """
    notes_dir = get_model_notes_dir(model_info)
    note_file = notes_dir / f"{note_name}.txt"
    with open(note_file, 'w') as f:
        f.write(content)
    return note_file


def load_model_note(model_info: Dict, note_name: str) -> str:
    """
    Load a note for a specific model.

    Args:
        model_info: Dictionary containing model metadata.
        note_name: Name of the note file (without .txt extension).

    Returns:
        Content of the note, or empty string if not found.
    """
    notes_dir = get_model_notes_dir(model_info)
    note_file = notes_dir / f"{note_name}.txt"
    if note_file.exists():
        return note_file.read_text()
    return ""


def list_model_notes(model_info: Dict) -> List[str]:
    """
    List all notes for a specific model.

    Args:
        model_info: Dictionary containing model metadata.

    Returns:
        List of note names (without .txt extension).
    """
    notes_dir = get_model_notes_dir(model_info)
    if not notes_dir.exists():
        return []
    return sorted([f.stem for f in notes_dir.glob("*.txt")])


def delete_model_note(model_info: Dict, note_name: str) -> bool:
    """
    Delete a note for a specific model.

    Args:
        model_info: Dictionary containing model metadata.
        note_name: Name of the note file (without .txt extension).

    Returns:
        True if deleted, False if not found.
    """
    notes_dir = get_model_notes_dir(model_info)
    note_file = notes_dir / f"{note_name}.txt"
    if note_file.exists():
        note_file.unlink()
        return True
    return False


# Training Stats Management
TRAINING_STATS_DIR = MODELS_DIR / "training_stats"

def get_training_stats_dir() -> Path:
    """
    Get the directory where training stats are stored.
    Creates it if it doesn't exist.

    Returns:
        Path to training stats directory
    """
    TRAINING_STATS_DIR.mkdir(parents=True, exist_ok=True)
    return TRAINING_STATS_DIR


def get_model_stats_file(model_name: str) -> Path:
    """
    Get the stats file path for a specific model.

    Args:
        model_name: Name of the model

    Returns:
        Path to stats JSON file
    """
    stats_dir = get_training_stats_dir()
    clean_name = model_name.replace('/', '_').replace(':', '_')
    return stats_dir / f"{clean_name}_stats.json"


def save_training_stats(model_name: str, stats: Dict, eval_report_path: Path = None) -> Path:
    """
    Save training statistics for a model.

    Args:
        model_name: Name of the model
        stats: Dictionary containing training statistics

    Returns:
        Path to saved stats file
    """
    import json
    from datetime import datetime

    stats_file = get_model_stats_file(model_name)

    # Load existing stats or create new
    if stats_file.exists():
        with open(stats_file, 'r') as f:
            existing_stats = json.load(f)
    else:
        existing_stats = {
            "model_name": model_name,
            "training_runs": [],
            "created": datetime.now().isoformat()
        }

    # Add new training run
    stats["timestamp"] = datetime.now().isoformat()
    stats["eval_report_path"] = str(eval_report_path) if eval_report_path else None
    existing_stats["training_runs"].append(stats)
    existing_stats["last_updated"] = datetime.now().isoformat()

    # Save updated stats
    with open(stats_file, 'w') as f:
        json.dump(existing_stats, f, indent=2)

    return stats_file


def load_training_stats(model_name: str) -> Dict:
    """
    Load training statistics for a model.

    Args:
        model_name: Name of the model

    Returns:
        Dictionary containing training statistics, or empty dict if not found
    """
    import json

    stats_file = get_model_stats_file(model_name)

    if stats_file.exists():
        with open(stats_file, 'r') as f:
            return json.load(f)

    return {
        "model_name": model_name,
        "training_runs": [],
        "created": None,
        "last_updated": None
    }


def get_latest_training_stats(model_name: str) -> Dict:
    """
    Get the most recent training run statistics for a model.

    Args:
        model_name: Name of the model

    Returns:
        Dictionary containing latest training stats, or None if no runs
    """
    stats = load_training_stats(model_name)

    if stats["training_runs"]:
        return stats["training_runs"][-1]

    return None


def delete_trained_model(model_path: Path) -> bool:
    """
    Delete a trained model directory and its associated stats.

    Args:
        model_path: Path to the trained model directory

    Returns:
        True if successfully deleted, False otherwise
    """
    import shutil

    try:
        model_name = model_path.name

        # Delete the model directory
        if model_path.exists() and model_path.is_dir():
            shutil.rmtree(model_path)

        # Delete associated stats file if it exists
        stats_file = MODELS_DIR / "stats" / f"{model_name}.json"
        if stats_file.exists():
            stats_file.unlink()

        return True
    except Exception as e:
        print(f"Error deleting model: {e}")
        return False

def get_model_skills(model_name: str) -> Dict[str, Dict[str, Any]]:
    """
    Determines a model's verified skills by analyzing its latest evaluation report.

    Args:
        model_name: The name of the model.

    Returns:
        A dictionary where keys are skill names and values are dictionaries
        containing 'status' ('Verified', 'Partial', 'Failed', 'Unverified') and 'details'.
    """
    import os
    import json
    from collections import defaultdict

    # Strategy: derive skills from the best available report (latest eval if present, else best baseline).
    # Persisted skills are used only as a last resort.

    evals_dir = MODELS_DIR / "evaluations"
    evals_dir.mkdir(parents=True, exist_ok=True)

    clean_name = model_name.replace('/', '_').replace(':', '_')

    report_data = None

    # 1) Latest evaluation report
    try:
        report_files = list(evals_dir.glob(f"{clean_name}_eval_*.json"))
        if report_files:
            latest_report_path = max(report_files, key=os.path.getctime)
            with open(latest_report_path, 'r') as f:
                report_data = json.load(f)
    except Exception:
        report_data = None

    # 2) Best baseline across matching keys (if no eval)
    if not report_data:
        try:
            idx = load_benchmarks_index() or {}
            models_idx = (idx.get('models') or {})
            import re
            def slug(s:str):
                return re.sub(r'[^a-z0-9]+', '', (s or '').lower())
            want = slug(model_name)
            candidates = []
            # From index keys
            for key, data in models_idx.items():
                if want in slug(key) or slug(key) in want:
                    for e in (data.get('entries') or []):
                        pth = e.get('path')
                        if pth and Path(pth).exists():
                            candidates.append(pth)
            # From filenames
            bdir = get_benchmarks_dir()
            for fp in bdir.glob('*.json'):
                nm = slug(fp.name)
                if want in nm or nm in want:
                    candidates.append(str(fp))
            # From file content (metadata.model_name or model_name)
            for fp in bdir.glob('*.json'):
                try:
                    with open(fp, 'r') as f:
                        d = json.load(f)
                    mname = (d.get('metadata', {}) or {}).get('model_name') or d.get('model_name') or ''
                    if mname and (want in slug(mname) or slug(mname) in want):
                        candidates.append(str(fp))
                except Exception:
                    continue
            # Dedup
            candidates = list(dict.fromkeys(candidates))
            # Choose best by pass_rate_percent
            best_score = -1.0
            for p in candidates:
                try:
                    with open(p, 'r') as f:
                        d = json.load(f)
                    pr = d.get('pass_rate_percent')
                    score = float(str(pr or '0').replace('%',''))
                    if score > best_score:
                        best_score = score; report_data = d
                except Exception:
                    continue
        except Exception:
            report_data = None

    # 3) Persisted skills (last resort)
    if not report_data:
        try:
            persisted = load_skills_file(model_name)
            if persisted:
                if isinstance(persisted, dict) and 'skills' in persisted:
                    skills_only = (persisted.get('skills') or {}).copy()
                    meta = persisted.get('meta') or {}
                    if meta:
                        skills_only['__meta__'] = {k: v for k, v in meta.items()}
                    return skills_only
                return persisted
        except Exception:
            pass
        return {"Overall Status": {"status": "Unverified", "details": "No evaluation reports or baselines found for this model."}}



    # Aggregate results by skill from selected report_data
    skill_results = defaultdict(lambda: {"passed": 0, "total": 0})
    for test_result in report_data.get("results", []):
        skill = test_result.get("skill")
        if skill:
            skill_results[skill]["total"] += 1
            if test_result.get("passed"):
                skill_results[skill]["passed"] += 1
    
    if not skill_results:
        return {"Overall Status": {"status": "Unverified", "details": "Evaluation report contains no test results."}}

    # Determine final status for each skill
    skills_status = {}
    for skill, counts in skill_results.items():
        passed = counts["passed"]
        total = counts["total"]
        details = f"Passed {passed}/{total} tests."
        
        if passed == total:
            status = "Verified"
        elif passed > 0:
            status = "Partial"
        else:
            status = "Failed"
            
        skills_status[skill] = {"status": status, "details": details}

    # Attach overall meta for UI convenience
    try:
        overall = report_data.get('pass_rate_percent')
        if overall:
            skills_status['__meta__'] = {
                'pass_rate_percent': overall,
                'prompt_name': report_data.get('metadata', {}).get('prompt_name'),
                'schema_name': report_data.get('metadata', {}).get('schema_name')
            }
    except Exception:
        pass

    print(f"DEBUG: get_model_skills for {model_name} returning with report_data: {report_data.get('pass_rate_percent') if report_data else 'None'}")
    return skills_status


def _get_runtime_skills(model_name: str) -> Dict[str, Dict[str, Any]]:
    """
    Extract runtime skills from tool call logs collected during actual model usage.
    This provides real-world skill assessment based on what tools the model successfully uses.

    Args:
        model_name: The name of the model

    Returns:
        Dictionary mapping skill (tool) names to their runtime statistics:
        {
            "file_read": {
                "status": "Verified",  # Verified (>=80%), Partial (>0%), or Failed (0%)
                "success_count": 15,
                "failure_count": 2,
                "success_rate": 88.2,
                "total_calls": 17,
                "last_used": "2025-01-15T10:30:00",
                "errors": ["Error: file not found", ...] (sample of recent errors)
            },
            ...
        }
    """
    from pathlib import Path
    import json
    from datetime import datetime

    # Try to import and use ToolCallLogger
    try:
        sys.path.insert(0, str(Path(__file__).parent / "tabs" / "custom_code_tab"))
        from tool_call_logger import ToolCallLogger

        logger = ToolCallLogger()
        stats = logger.get_tool_statistics(model_name)

        if not stats:
            return {}

        runtime_skills = {}

        for tool_name, tool_data in stats.items():
            success = tool_data.get('success', 0)
            failure = tool_data.get('failure', 0)
            total = success + failure

            if total == 0:
                continue

            success_rate = (success / total) * 100

            # Determine status based on success rate
            if success_rate >= 80:
                status = "Verified"
            elif success_rate > 0:
                status = "Partial"
            else:
                status = "Failed"

            runtime_skills[tool_name] = {
                "status": status,
                "success_count": success,
                "failure_count": failure,
                "success_rate": round(success_rate, 1),
                "total_calls": total,
                "errors": tool_data.get('errors', [])[:5]  # Keep last 5 errors
            }

        return runtime_skills

    except Exception as e:
        # If logger not available, try reading the log file directly
        try:
            log_file = TRAINING_DATA_DIR / "Tools" / "tool_realtime_data.jsonl"
            if not log_file.exists():
                return {}

            stats = {}
            with open(log_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)

                        # Filter by model
                        if entry.get('model') != model_name:
                            continue

                        tool = entry.get('tool', 'unknown')
                        success = entry.get('success', False)

                        if tool not in stats:
                            stats[tool] = {'success': 0, 'failure': 0, 'errors': []}

                        if success:
                            stats[tool]['success'] += 1
                        else:
                            stats[tool]['failure'] += 1
                            if len(stats[tool]['errors']) < 5:
                                stats[tool]['errors'].append(entry.get('result', ''))

                    except json.JSONDecodeError:
                        continue

            # Convert to runtime skills format
            runtime_skills = {}
            for tool_name, tool_data in stats.items():
                success = tool_data['success']
                failure = tool_data['failure']
                total = success + failure

                if total == 0:
                    continue

                success_rate = (success / total) * 100

                if success_rate >= 80:
                    status = "Verified"
                elif success_rate > 0:
                    status = "Partial"
                else:
                    status = "Failed"

                runtime_skills[tool_name] = {
                    "status": status,
                    "success_count": success,
                    "failure_count": failure,
                    "success_rate": round(success_rate, 1),
                    "total_calls": total,
                    "errors": tool_data['errors']
                }

            return runtime_skills

        except Exception:
            return {}


# --- Skills persistence ---
def get_skills_dir() -> Path:
    d = MODELS_DIR / "skills"
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_skills_path(model_name: str) -> Path:
    clean = model_name.replace('/', '_').replace(':', '_')
    return get_skills_dir() / f"{clean}.json"

def save_skills_file(model_name: str, skills: Dict[str, Dict[str, Any]], meta: Dict[str, Any] = None) -> Path:
    path = get_skills_path(model_name)
    try:
        payload = {"skills": skills}
        if meta:
            payload["meta"] = meta
        with open(path, 'w') as f:
            json.dump(payload, f, indent=2)
        return path
    except Exception:
        return path

def load_skills_file(model_name: str) -> Dict[str, Any]:
    path = get_skills_path(model_name)
    if not path.exists():
        return {}
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


# --- Evaluation Reports & Baselines ---

def get_evaluations_dir() -> Path:
    """
    Get/create the directory where evaluation reports are stored.
    """
    evals_dir = MODELS_DIR / "evaluations"
    evals_dir.mkdir(parents=True, exist_ok=True)
    return evals_dir


def list_evaluation_reports(model_name: str) -> List[Path]:
    """
    List saved evaluation reports for a given model.
    """
    evals_dir = get_evaluations_dir()
    clean = model_name.replace('/', '_').replace(':', '_')
    return sorted(evals_dir.glob(f"{clean}_eval_*.json"))


def load_latest_evaluation_report(model_name: str) -> Dict:
    """
    Load the latest evaluation report for a model. Returns {} if not found.
    """
    reports = list_evaluation_reports(model_name)
    if not reports:
        return {}
    latest = reports[-1]
    try:
        with open(latest, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


# --- Settings accessors (lightweight) ---

def get_settings_file_path() -> Path:
    """Return the path to the settings JSON file."""
    return DATA_DIR / "settings.json"


def get_regression_policy() -> Dict[str, Any]:
    """
    Read regression policy from settings.json with safe defaults.
    Structure:
    {
      "enabled": true,
      "alert_drop_percent": 5.0,
      "strict_block": false,
      "auto_rollback": false
    }
    """
    default_policy = {
        "enabled": True,
        "alert_drop_percent": 5.0,
        "strict_block": False,
        "auto_rollback": False,
    }
    settings_path = get_settings_file_path()
    try:
        if settings_path.exists():
            with open(settings_path, 'r') as f:
                data = json.load(f)
                policy = data.get("regression_policy", {}) or {}
                # Merge defaults
                merged = {**default_policy, **policy}
                return merged
    except Exception:
        pass
    return default_policy


def get_benchmarks_dir() -> Path:
    """
    Get/create the directory where baseline (pre-training) benchmarks are stored.
    """
    bdir = MODELS_DIR / "benchmarks"
    bdir.mkdir(parents=True, exist_ok=True)
    return bdir

# --- Baseline Catalog (Index) ---

def get_benchmarks_index_path() -> Path:
    return get_benchmarks_dir() / "index.json"

def load_benchmarks_index() -> Dict[str, Any]:
    path = get_benchmarks_index_path()
    if not path.exists():
        return {"models": {}}
    try:
        import json
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return {"models": {}}

def save_benchmarks_index(data: Dict[str, Any]) -> Path:
    path = get_benchmarks_index_path()
    try:
        import json
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return path
    except Exception:
        return path

def update_model_baseline_index(model_name: str, baseline_path: Path, meta: Dict[str, Any], set_active: bool = True) -> None:
    """Update the global baselines catalog for a model with a new entry and optionally set it active."""
    idx = load_benchmarks_index()
    clean = model_name.replace('/', '_').replace(':', '_')
    m = idx.setdefault('models', {}).setdefault(clean, {"entries": [], "active": None})
    entry = {
        "path": str(baseline_path),
        "suite": (meta or {}).get('suite') or (meta or {}).get('test_suite_name'),
        "schema": (meta or {}).get('schema_name'),
        "prompt": (meta or {}).get('prompt_name'),
        "timestamp": (meta or {}).get('timestamp')
    }
    # Avoid duplicates: replace if same path
    existing = [e for e in m["entries"] if e.get("path") == str(baseline_path)]
    if existing:
        m["entries"] = [e for e in m["entries"] if e.get("path") != str(baseline_path)] + [entry]
    else:
        m["entries"].append(entry)
    if set_active:
        m["active"] = entry
    save_benchmarks_index(idx)


def get_baseline_report_path(model_name: str) -> Path:
    """
    Get the canonical baseline path for a model.
    """
    clean = model_name.replace('/', '_').replace(':', '_')
    return get_benchmarks_dir() / f"{clean}_baseline.json"


def save_baseline_report(model_name: str, report_data: Dict) -> Path:
    """
    Save/update the baseline report for a model.
    """
    path = get_baseline_report_path(model_name)
    with open(path, 'w') as f:
        json.dump(report_data, f, indent=2)
    print(f"Baseline report saved to: {path}")
    return path


def load_baseline_report(model_name: str) -> Dict:
    """
    Load baseline report for a model. Returns {} if not found.
    """
    path = get_baseline_report_path(model_name)
    if not path.exists():
        return {}
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

# --- Level Baselines ---

def get_level_benchmarks_dir(base_model_name: str, level_name: str) -> Path:
    clean_base = base_model_name.replace('/', '_').replace(':', '_')
    clean_level = level_name.replace('/', '_').replace(':', '_')
    d = MODELS_DIR / 'levels' / clean_base / clean_level / 'benchmarks'
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_level_baseline_report_path(base_model_name: str, level_name: str) -> Path:
    return get_level_benchmarks_dir(base_model_name, level_name) / 'baseline.json'

def save_level_baseline_report(base_model_name: str, level_name: str, report_data: Dict) -> Path:
    path = get_level_baseline_report_path(base_model_name, level_name)
    with open(path, 'w') as f:
        json.dump(report_data, f, indent=2)
    return path

def load_level_baseline_report(base_model_name: str, level_name: str) -> Dict:
    path = get_level_baseline_report_path(base_model_name, level_name)
    if not path.exists():
        return {}
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def get_level_benchmarks_index_path(base_model_name: str, level_name: str) -> Path:
    return get_level_benchmarks_dir(base_model_name, level_name) / 'index.json'

def load_level_benchmarks_index(base_model_name: str, level_name: str) -> Dict[str, Any]:
    p = get_level_benchmarks_index_path(base_model_name, level_name)
    if not p.exists():
        return {"entries": [], "active": None}
    try:
        with open(p, 'r') as f:
            return json.load(f)
    except Exception:
        return {"entries": [], "active": None}

def save_level_benchmarks_index(base_model_name: str, level_name: str, data: Dict[str, Any]) -> Path:
    p = get_level_benchmarks_index_path(base_model_name, level_name)
    try:
        with open(p, 'w') as f:
            json.dump(data, f, indent=2)
        return p
    except Exception:
        return p

def update_level_baseline_index(base_model_name: str, level_name: str, baseline_path: Path, meta: Dict[str, Any], set_active: bool = True) -> None:
    idx = load_level_benchmarks_index(base_model_name, level_name)
    entry = {
        "path": str(baseline_path),
        "suite": (meta or {}).get('suite') or (meta or {}).get('test_suite_name'),
        "schema": (meta or {}).get('schema_name'),
        "prompt": (meta or {}).get('prompt_name'),
        "timestamp": (meta or {}).get('timestamp')
    }
    entries = idx.setdefault('entries', [])
    # Replace if same path
    entries = [e for e in entries if e.get('path') != str(baseline_path)] + [entry]
    idx['entries'] = entries
    if set_active:
        idx['active'] = entry
    save_level_benchmarks_index(base_model_name, level_name, idx)
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def get_test_suites() -> List[str]:
    """
    Scans the Test directory to find available test suites.
    Each subdirectory in Training_Data-Sets/Test is considered a suite.

    Returns:
        A list of test suite names.
    """
    test_root_dir = TRAINING_DATA_DIR / "Test"
    if not test_root_dir.exists():
        return []
    
    suites = [d.name for d in test_root_dir.iterdir() if d.is_dir()]
    return sorted(suites)

def save_evaluation_report(model_name: str, report_data: Dict) -> Path:
    """
    Saves an evaluation report for a model.

    Args:
        model_name: The name of the model.
        report_data: The dictionary containing the evaluation report.

    Returns:
        Path to the saved report file.
    """
    import json
    from datetime import datetime

    evals_dir = MODELS_DIR / "evaluations"
    evals_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_name = model_name.replace('/', '_').replace(':', '_')
    report_filename = f"{clean_name}_eval_{timestamp}.json"
    report_path = evals_dir / report_filename

    with open(report_path, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print(f"Evaluation report saved to: {report_path}")
    return report_path


# --- Behavior Profile Helpers ---
def _load_latest_eval_or_baseline(model_name: str) -> Dict:
    """Load the latest evaluation report; if none found, return the canonical baseline if present."""
    data = load_latest_evaluation_report(model_name)
    if data:
        return data
    try:
        return load_baseline_report(model_name)
    except Exception:
        return {}

def get_model_behavior_profile(model_name: str) -> Dict[str, Any]:
    """
    Returns a behavior profile summary for a model based on its latest eval (or baseline).
    Structure:
    {
      'overall': '82.5%',
      'per_tool': {...},
      'per_difficulty': {...},
      'per_policy': {...},
      'per_tag': {...},
      'confusions': {...},
      'arg_errors': {...},
      'json_valid_rate': '99.0%',
      'schema_valid_rate': '98.0%',
      'avg_elapsed_ms': 120,
      'avg_steps': 1.0,
      'suite': 'Tools',
      'prompt': '...',
      'schema': '...'
    }
    """
    rpt = _load_latest_eval_or_baseline(model_name) or {}
    if not rpt:
        return {}
    meta = rpt.get('metadata', {}) or {}
    metrics = rpt.get('metrics', {}) or {}
    return {
        'overall': rpt.get('pass_rate_percent'),
        'per_tool': metrics.get('per_tool') or {},
        'per_difficulty': metrics.get('per_difficulty') or {},
        'per_policy': metrics.get('per_policy') or {},
        'per_tag': metrics.get('per_tag') or {},
        'confusions': metrics.get('confusion_matrix') or {},
        'arg_errors': metrics.get('arg_errors') or {},
        'json_valid_rate': metrics.get('json_valid_rate'),
        'schema_valid_rate': metrics.get('schema_valid_rate'),
        'avg_elapsed_ms': metrics.get('avg_elapsed_ms'),
        'avg_steps': metrics.get('avg_steps'),
        'behavior': metrics.get('behavior') or {},
        'suite': meta.get('suite'),
        'prompt': meta.get('prompt_name'),
        'schema': meta.get('schema_name')
    }


if __name__ == "__main__":
    print("Trainer Configuration")
    print("=" * 60)
    print()
    print(f"Root: {TRAINER_ROOT}")
    print(f"Data: {DATA_DIR}")
    print(f"Models: {MODELS_DIR}")
    print(f"Training Data: {TRAINING_DATA_DIR}")
    print()
    print("Training Data Categories:")
    print(f"  Tools: {TOOLS_DATA_DIR}")
    print(f"  App Development: {APP_DEV_DATA_DIR}")
    print(f"  Coding: {CODING_DATA_DIR}")
    print(f"  Semantic States: {SEMANTIC_DATA_DIR}")
    print()
    print(f"Exports: {EXPORTS_DIR}")
    print()

    latest = get_latest_model_dir()
    if latest:
        print(f"Latest model: {latest.name}")
    else:
        print("No trained models found")


# === Model Profiles (atomic IO) ===
from pathlib import Path
import os, json, shutil
from datetime import datetime

MODEL_PROFILES_DIR = Path("Data/profiles/Models")
MODEL_PROFILES_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MODEL_PROFILE = {
    "parameter_size_b": 0.0,
    "class_level": "novice",
    "skills": {},
    "stats": {},
    "badges": []
}

# --- Lineage (ULID) helpers -------------------------------------------------
def generate_ulid() -> str:
    """Return a ULID string if ulid lib available; otherwise UUID4 hex fallback."""
    try:
        import ulid
        return str(ulid.new())
    except Exception:
        import uuid, time
        # time-seeded uuid fallback for rough ordering; clearly marked
        return f"FALLBACK-{int(time.time())}-{uuid.uuid4().hex}"

def ensure_lineage_id(variant_id: str) -> str:
    """Ensure the model profile for variant has a lineage_id; return it."""
    try:
        mp = load_model_profile(variant_id) or {}
        lid = mp.get("lineage_id")
        if not lid:
            lid = generate_ulid()
            mp["lineage_id"] = lid
            save_model_profile(variant_id, mp)
        return lid
    except Exception:
        # last-resort
        return generate_ulid()

def get_lineage_id(variant_id: str) -> str | None:
    try:
        mp = load_model_profile(variant_id) or {}
        return mp.get("lineage_id")
    except Exception:
        return None

def _normalize_model_profile_defaults(mp: dict) -> dict:
    out = dict(DEFAULT_MODEL_PROFILE)
    out.update(mp or {})
    # ensure required sub-objects exist
    out.setdefault("skills", {})
    out.setdefault("stats", {})
    out.setdefault("badges", [])
    return out


# --- WO-6b: list saved model profiles (variants) --------------------
from pathlib import Path

def list_model_profiles() -> list[dict]:
    """
    Return a list of {variant_id, base_model, assigned_type, path}
    discovered under MODEL_PROFILES_DIR. Missing keys default to ''.
    """
    out = []
    mp_dir = Path(MODEL_PROFILES_DIR)  # already defined in this file
    if not mp_dir.exists():
        return out
    for p in mp_dir.glob("*.json"):
        try:
            data = _read_json(str(p)) or {}
            out.append({
                "variant_id": data.get("trainee_name") or data.get("variant_id") or p.stem,
                "base_model": data.get("base_model", ""),
                "assigned_type": data.get("assigned_type") or data.get("type_id", ""),
                "path": str(p),
            })
        except Exception:
            pass
    return out


def get_variant_class(variant_id: str) -> str:
    """Return the class level for a stored Model Profile variant, defaulting to 'novice'."""
    try:
        mp = load_model_profile(variant_id) or {}
        # Accept legacy keys if present
        return (mp.get("class_level") or mp.get("class") or "novice")
    except Exception:
        return "novice"


# --- WO-6f: Variant management helpers (rename/duplicate/delete) ---
import shutil as _shutil

def _mp_path(variant_id: str) -> Path:
    return Path(MODEL_PROFILES_DIR) / f"{variant_id}.json"

def _tp_path(variant_id: str) -> Path:
    return Path(TRAINING_PROFILES_DIR) / f"{variant_id}.json"

def rename_variant(old: str, new: str):
    for getter in (_mp_path, _tp_path):
        p_old, p_new = getter(old), getter(new)
        if p_old.exists():
            p_new.parent.mkdir(parents=True, exist_ok=True)
            os.replace(p_old, p_new)

def duplicate_variant(src: str, dst: str):
    for getter in (_mp_path, _tp_path):
        p_src, p_dst = getter(src), getter(dst)
        if p_src.exists():
            p_dst.parent.mkdir(parents=True, exist_ok=True)
            _shutil.copy2(p_src, p_dst)

def delete_variant(variant_id: str):
    for getter in (_mp_path, _tp_path):
        p = getter(variant_id)
        if p.exists():
            p.unlink()


# WO-6m: Unified training profiles list (legacy + type)
def list_legacy_training_profiles() -> list[dict]:
    try:
        return [{"id": p.stem, "kind": "legacy"} for p in PROFILES_DIR.glob("*.json") if p.name != "settings.json"]
    except Exception:
        return []

def list_type_training_profiles() -> list[dict]:
    try:
        return [{"id": p.stem, "kind": "type"} for p in TRAINING_PROFILES_DIR.glob("*.json")]
    except Exception:
        return []

def list_all_training_profiles() -> list[dict]:
    return list_legacy_training_profiles() + list_type_training_profiles()


# WO-6s: Variant visual properties
def update_variant_visuals(variant_id: str, badges: list[str], color: str):
    mp = load_model_profile(variant_id) or {}
    mp["badges"] = list(badges or [])
    mp["color"] = color or ""
    save_model_profile(variant_id, mp)


# WO-6z: Variant stats path helper
def get_variant_stats_path(variant_id: str) -> str:
    p = DATA_DIR / "Stats" / f"{variant_id}.json"
    return str(p) if p.exists() else ""

# --- Ollama assignments (variant -> list of ollama tags) ---
def load_ollama_assignments() -> dict:
    try:
        if OLLAMA_ASSIGNMENTS_PATH.exists():
            with open(OLLAMA_ASSIGNMENTS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_ollama_assignments(data: dict):
    try:
        with open(OLLAMA_ASSIGNMENTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("[config] save_ollama_assignments error:", e)

def add_ollama_assignment(variant_id: str, tag: str):
    """Assign a GGUF tag to a variant, storing lineage-aware structure when possible."""
    data = load_ollama_assignments() or {}
    # Backward-compatible structure: allow plain list; prefer v2 with lineage and tag_index
    lid = ensure_lineage_id(variant_id)
    # Variants bucket may be a dict or list in legacy
    entry = data.get(variant_id)
    if isinstance(entry, dict):
        tags = set(entry.get('tags') or [])
        tags.add(tag)
        entry['tags'] = sorted(tags)
        entry['lineage_id'] = entry.get('lineage_id') or lid
        data[variant_id] = entry
    else:
        # legacy list; upgrade minimally
        lst = set(entry or [])
        lst.add(tag)
        data[variant_id] = sorted(lst)
    # Maintain tag_index
    tag_index = data.get('tag_index') or {}
    tag_index[tag] = lid
    data['tag_index'] = tag_index
    save_ollama_assignments(data)

def list_assigned_ollama_tags() -> set:
    data = load_ollama_assignments() or {}
    out = set()
    for k, v in data.items():
        if k == 'tag_index':
            continue
        if isinstance(v, dict):
            tags = v.get('tags') or []
        else:
            tags = v or []
        for t in (tags or []):
            out.add(t)
    return out

def get_assigned_tags_by_lineage(lineage_id: str) -> list[str]:
    """Return assigned tags for a given lineage id (empty list if none)."""
    data = load_ollama_assignments() or {}
    res = set()
    # Scan variant entries for matching lineage_id
    for k, v in data.items():
        if k == 'tag_index':
            continue
        if isinstance(v, dict) and v.get('lineage_id') == lineage_id:
            for t in (v.get('tags') or []):
                res.add(t)
    return sorted(res)

def get_lineage_for_tag(tag: str) -> str | None:
    """Reverse-lookup lineage id for a GGUF tag if available."""
    data = load_ollama_assignments() or {}
    ti = data.get('tag_index') or {}
    return ti.get(tag)


# --- WO-6j: UI state persistence helpers ---
SETTINGS_PATH = DATA_DIR / "settings.json"

def load_ui_state() -> dict:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("ui_state", {})
    except Exception:
        return {}

def save_ui_state(state: dict):
    try:
        data = {}
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        data["ui_state"] = state
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("[Settings] save_ui_state error:", e)



def _profile_path(name: str) -> Path:
    safe = name.strip().replace(os.sep, "_")
    return MODEL_PROFILES_DIR / f"{safe}.json"

def load_model_profile(name: str) -> dict:
    """Load; if .json missing but .bak exists, auto-restore; inject defaults."""
    p = _profile_path(name)
    if not p.exists():
        bak = p.with_suffix(".json.bak")
        if bak.exists():
            shutil.copy2(bak, p)
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return _normalize_model_profile_defaults(data)

def save_model_profile(name: str, data: dict) -> Path:
    """Atomic write with backup + dir fsync guard (Windows-safe)."""
    final_path = _profile_path(name)
    tmp_path = final_path.with_suffix(".json.tmp")
    bak_path = final_path.with_suffix(".json.bak")

    data = _normalize_model_profile_defaults(data)

    try:
        validate_model_profile(data)
    except Exception as e:
        # Fail fast: don't persist invalid structure
        raise

    # rotate backup if present
    if final_path.exists():
        shutil.copy2(final_path, bak_path)

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, final_path)

    # directory fsync (Linux/Unix only)
    if hasattr(os, "O_DIRECTORY"):
        dir_fd = os.open(str(MODEL_PROFILES_DIR), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    return final_path

# === Types Catalog & Schema Validation ===
from pathlib import Path as _Path
import json as _json

TYPE_CATALOG_PATH = _Path("Data/type_catalog.json")
TYPE_CATALOG_SCHEMA_PATH = _Path("Data/Schemas/type_catalog.schema.json")
MODEL_PROFILE_SCHEMA_PATH = _Path("Data/Schemas/model_profile.schema.json")

def _read_json(_p: _Path):
    """Robust JSON reader: returns {} on error and prints a concise warning."""
    try:
        with open(_p, "r", encoding="utf-8") as f:
            return _json.load(f)
    except Exception as e:
        try:
            print(f"[config] JSON read failed: {_p} — {e}")
        except Exception:
            pass
        return {}

def _maybe_validate(instance: dict, schema_path: _Path, *, what: str):
    """
    Best-effort JSON Schema validation. If 'jsonschema' isn't installed,
    we skip with a soft note. Keeps runtime flexible while enabling CI gate later.
    """
    try:
        import jsonschema  # type: ignore
    except Exception:
        # Soft skip: validation is optional at runtime, will be enforced in CI.
        return
    try:
        schema = _read_json(schema_path)
        jsonschema.validate(instance=instance, schema=schema)
    except Exception as e:
        raise ValueError(f"{what} validation failed: {e}") from e

def load_type_catalog() -> dict:
    """
    Load the authoritative Type Catalog and (optionally) validate against schema.
    Returns the catalog dict: { 'types': [...], 'legend': {...} }.
    """
    catalog = _read_json(TYPE_CATALOG_PATH) or {}
    try:
        _maybe_validate(catalog, TYPE_CATALOG_SCHEMA_PATH, what="Type Catalog")
    except Exception as e:
        # Harden: validation errors shouldn't crash runtime; log only
        print(f"[config] Type Catalog validation warning: {e}")
    return catalog

def list_types() -> list[str]:
    """List available type ids from the catalog."""
    cat = load_type_catalog()
    return [t.get("id") for t in cat.get("types", []) if isinstance(t, dict) and t.get("id")]

def get_type_by_id(type_id: str) -> dict | None:
    """Fetch a type entry by id from the catalog."""
    cat = load_type_catalog()
    for t in cat.get("types", []):
        if isinstance(t, dict) and t.get("id") == type_id:
            return t
    return None

def get_training_plan_for_type(type_id: str) -> tuple[list[str], list[str]]:
    """
    Returns (recipes, evals) for the given type_id from the Type Catalog.
    """
    t = get_type_by_id(type_id)
    if not t:
        return ([], [])
    recipes = list(t.get("default_training_recipes", []))
    evals = list(t.get("first_evals", []))
    return (recipes, evals)

def get_training_plan_for_model(trainee_name: str) -> tuple[list[str], list[str]]:
    """
    Loads Model Profile and returns (recipes, evals) based on assigned_type.
    """
    try:
        mp = load_model_profile(trainee_name)
    except Exception:
        return ([], [])
    assigned = mp.get("assigned_type")
    if isinstance(assigned, list):
        assigned = assigned[0] if assigned else None
    if not assigned:
        return ([], [])
    return get_training_plan_for_type(str(assigned))

def validate_model_profile(instance: dict):
    """
    Optional validation for Model Profiles. Call before or after normalization
    in save_model_profile(). Raises ValueError if invalid (when jsonschema is present).
    """
    _maybe_validate(instance, MODEL_PROFILE_SCHEMA_PATH, what="Model Profile")

# === Training Profiles (atomic IO) ===
from pathlib import Path as _TPath
import os as _os

TRAINING_PROFILES_DIR = _TPath("Data/profiles/Training")
TRAINING_PROFILES_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TRAINING_PROFILE = {
    "base_model": "",
    "assigned_type": "",
    "selected_scripts": [],
    "selected_prompts": [],
    "selected_schemas": [],
    "lineage_id": "",
    "runner_settings": {
        "max_time_min": 20,
        "max_runs": 1,
        "delay_sec": 0,
        "mixed_precision": True,
        "save_checkpoints": False,
        "enable_stat_saving": True,
        "gradient_accum": 16,
        "warmup_steps": 5,
        "enable_baseline_skill_tests": True,
        "auto_run_pre_eval": True,
        "auto_run_post_eval": True,
        "use_system_prompt": True,
        "use_tool_schema": True,
    },
    "evals_plan": []
}

def _tp_path(name: str) -> _TPath:
    safe = name.strip().replace(_os.sep, "_")
    return TRAINING_PROFILES_DIR / f"{safe}.json"

def _normalize_training_profile(tp: dict) -> dict:
    out = dict(DEFAULT_TRAINING_PROFILE)
    out.update(tp or {})
    out.setdefault("selected_scripts", [])
    out.setdefault("selected_prompts", [])
    out.setdefault("selected_schemas", [])
    out.setdefault("runner_settings", dict(DEFAULT_TRAINING_PROFILE["runner_settings"]))
    out.setdefault("evals_plan", [])
    return out

def list_training_profiles() -> list:
    return sorted([p.stem for p in TRAINING_PROFILES_DIR.glob("*.json") if not p.name.startswith(".")])

def load_training_profile(name: str) -> dict:
    p = _tp_path(name)
    if not p.exists():
        bak = p.with_suffix(".json.bak")
        if bak.exists():
            shutil.copy2(bak, p)
    with open(p, "r", encoding="utf-8") as f:
        data = _json.load(f)
    return _normalize_training_profile(data)

def save_training_profile(name: str, data: dict):
    final_path = _tp_path(name)
    tmp_path = final_path.with_suffix(".json.tmp")
    bak_path = final_path.with_suffix(".json.bak")

    data = _normalize_training_profile(data)

    if final_path.exists():
        shutil.copy2(final_path, bak_path)

    with open(tmp_path, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        _os.fsync(f.fileno())
    _os.replace(tmp_path, final_path)

    if hasattr(_os, "O_DIRECTORY"):
        dfd = _os.open(str(TRAINING_PROFILES_DIR), _os.O_RDONLY | _os.O_DIRECTORY)
        try:
            _os.fsync(dfd)
        finally:
            _os.close(dfd)
    return final_path

def build_training_profile_from_type(trainee_name: str, base_model: str, type_id: str) -> dict:
    """
    Deterministic mapping from Type Catalog → Training Profile.
    Uses default_training_recipes + first_evals.
    """
    recipes, evals = get_training_plan_for_type(type_id)
    tp = {
        "base_model": base_model,
        "assigned_type": type_id,
        "selected_scripts": list(recipes or []),
        "evals_plan": list(evals or []),
        "runner_settings": dict(DEFAULT_TRAINING_PROFILE["runner_settings"]),
    }
    try:
        tp["lineage_id"] = ensure_lineage_id(trainee_name)
    except Exception:
        tp["lineage_id"] = tp.get("lineage_id") or ""
    return _normalize_training_profile(tp)

def upsert_training_profile_for_model(trainee_name: str, base_model: str, type_id: str) -> dict:
    tp = build_training_profile_from_type(trainee_name, base_model, type_id)
    try:
        existing = load_training_profile(trainee_name)
        # merge "sticky" choices the user might have tweaked:
        if existing.get("selected_prompts"):
            tp["selected_prompts"] = existing["selected_prompts"]
        if existing.get("selected_schemas"):
            tp["selected_schemas"] = existing["selected_schemas"]
    except Exception:
        pass
    save_training_profile(trainee_name, tp)
    return tp
