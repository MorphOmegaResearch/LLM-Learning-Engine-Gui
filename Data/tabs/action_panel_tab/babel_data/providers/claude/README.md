# Claude Provider Module

## USB Integration Instructions

1. Copy your claude module files to this directory:
   - `claude_module.py` (main module)
   - Any additional dependencies

2. grep_flight will automatically detect and use modules from this location

3. Structure:
   ```
   babel_data/providers/claude/
   ├── claude_module.py
   ├── config.json (optional)
   └── README.md (this file)
   ```

## Status
Currently: True

## Testing
Run: `python3 provider_manager.py --test claude`
