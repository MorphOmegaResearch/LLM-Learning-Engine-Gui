# Ollama Provider Module

## USB Integration Instructions

1. Copy your ollama module files to this directory:
   - `ollama_module.py` (main module)
   - Any additional dependencies

2. grep_flight will automatically detect and use modules from this location

3. Structure:
   ```
   babel_data/providers/ollama/
   ├── ollama_module.py
   ├── config.json (optional)
   └── README.md (this file)
   ```

## Status
Currently: False

## Testing
Run: `python3 provider_manager.py --test ollama`
