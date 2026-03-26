#!/usr/bin/env python3
"""
Provider Manager - Graceful provider detection and module loading
Supports: Claude, Gemini, Ollama, Morph
Searches: babel_data/providers/ for USB module integration
"""

import subprocess
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class ProviderStatus:
    """Provider availability status"""
    available: bool
    version: Optional[str] = None
    error: Optional[str] = None
    module_path: Optional[Path] = None


class ProviderManager:
    """
    Manages AI provider detection, configuration, and graceful fallbacks.

    Search paths (in order):
    1. babel_data/providers/{provider_name}/
    2. System PATH (for CLIs like claude, gemini, ollama)
    3. Default relative paths (for Morph profiles)
    """

    def __init__(self, babel_root: Path = None):
        if babel_root is None:
            babel_root = Path(__file__).parent.parent.parent

        self.babel_root = Path(babel_root)
        self.providers_dir = self.babel_root / "babel_data" / "providers"
        self.providers_dir.mkdir(parents=True, exist_ok=True)

        # Provider configurations
        self.provider_configs = {
            'claude': {
                'cli': 'claude',
                'check_cmd': ['claude', '--version'],
                'module_subpath': 'claude_module.py'
            },
            'gemini': {
                'cli': 'gemini',
                'check_cmd': ['gemini', '--version'],
                'module_subpath': 'gemini_module.py'
            },
            'ollama': {
                'cli': 'ollama',
                'check_cmd': ['ollama', '--version'],
                'module_subpath': 'ollama_module.py'
            },
            'morph': {
                'cli': None,  # Script-based, not CLI
                'check_cmd': None,
                'module_subpath': 'morph_module.py',
                'profiles_subpath': 'morph_profiles'
            }
        }

    def check_provider(self, provider_id: str) -> ProviderStatus:
        """
        Check if provider is available with graceful error handling.

        Returns:
            ProviderStatus with availability, version, and error details
        """
        config = self.provider_configs.get(provider_id)
        if not config:
            return ProviderStatus(False, error=f"Unknown provider: {provider_id}")

        # 1. Check babel_data/providers/ first (USB modules)
        provider_module_dir = self.providers_dir / provider_id
        if provider_module_dir.exists():
            module_file = provider_module_dir / config['module_subpath']
            if module_file.exists():
                return ProviderStatus(
                    True,
                    version="babel_module",
                    module_path=module_file
                )

        # 2. Check system CLI
        if config['check_cmd']:
            try:
                result = subprocess.run(
                    config['check_cmd'],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                if result.returncode == 0:
                    version = result.stdout.strip() or "installed"
                    return ProviderStatus(True, version=version)
                else:
                    return ProviderStatus(
                        False,
                        error=f"CLI exists but returned error: {result.stderr[:100]}"
                    )
            except FileNotFoundError:
                return ProviderStatus(
                    False,
                    error=f"CLI '{config['cli']}' not found in PATH"
                )
            except subprocess.TimeoutExpired:
                return ProviderStatus(
                    False,
                    error=f"CLI '{config['cli']}' check timed out"
                )
            except Exception as e:
                return ProviderStatus(
                    False,
                    error=f"Check failed: {str(e)}"
                )

        # 3. Morph special case (script-based)
        if provider_id == 'morph':
            # Check for morph profiles
            morph_profiles_dir = self.providers_dir / 'morph' / 'morph_profiles'
            if morph_profiles_dir.exists() and list(morph_profiles_dir.glob('*.json')):
                return ProviderStatus(
                    True,
                    version="profile_based",
                    module_path=morph_profiles_dir
                )
            else:
                return ProviderStatus(
                    False,
                    error="Morph profiles not found in babel_data/providers/morph/morph_profiles/"
                )

        return ProviderStatus(False, error="No valid installation found")

    def get_available_providers(self) -> Dict[str, ProviderStatus]:
        """Get status of all providers."""
        return {
            provider_id: self.check_provider(provider_id)
            for provider_id in self.provider_configs.keys()
        }

    def get_provider_models(self, provider_id: str) -> Tuple[List[str], Optional[str]]:
        """
        Get available models for provider with error handling.

        Returns:
            (models_list, error_message)
        """
        status = self.check_provider(provider_id)

        if not status.available:
            return ([f"⚠️ {provider_id.capitalize()} not available"], status.error)

        if provider_id == 'ollama':
            return self._get_ollama_models()
        elif provider_id == 'claude':
            return self._get_claude_models()
        elif provider_id == 'gemini':
            return self._get_gemini_models()
        elif provider_id == 'morph':
            return self._get_morph_models()

        return ([f"⚠️ Unknown provider: {provider_id}"], None)

    def _get_ollama_models(self) -> Tuple[List[str], Optional[str]]:
        """Get Ollama models with graceful fallback."""
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    models = []
                    for line in lines[1:]:
                        parts = line.split()
                        if parts:
                            models.append(parts[0])
                    if models:
                        return (models, None)

            # Fallback: suggest installation
            return (
                ["⚠️ No models found", "Install with: ollama pull llama3.1"],
                "Ollama is installed but no models found"
            )
        except Exception as e:
            return (
                ["⚠️ Ollama unavailable", "Install from: https://ollama.ai"],
                f"Error: {str(e)}"
            )

    def _get_claude_models(self) -> Tuple[List[str], Optional[str]]:
        """Get Claude models (predefined)."""
        return ([
            "claude-sonnet-4-5-20250929",
            "claude-opus-4-6",
            "claude-haiku-4-5-20251001",
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229"
        ], None)

    def _get_gemini_models(self) -> Tuple[List[str], Optional[str]]:
        """Get Gemini models (predefined)."""
        return ([
            "gemini-3-pro-preview",
            "gemini-2.0-flash-exp",
            "gemini-1.5-pro-latest",
            "gemini-1.5-flash-latest"
        ], None)

    def _get_morph_models(self) -> Tuple[List[str], Optional[str]]:
        """Get Morph models (all providers aggregated)."""
        models = ["🎨 Morph (Auto-route)"]
        errors = []

        # Aggregate from other providers
        for provider_id in ['ollama', 'claude', 'gemini']:
            provider_models, error = self.get_provider_models(provider_id)
            if error:
                errors.append(f"{provider_id}: {error}")
            else:
                models.append(f"--- {provider_id.capitalize()} ---")
                models.extend([m for m in provider_models if not m.startswith('⚠️')])

        error_msg = " | ".join(errors) if errors else None
        return (models, error_msg)

    def create_provider_readme(self, provider_id: str):
        """Create README for USB module integration."""
        provider_dir = self.providers_dir / provider_id
        provider_dir.mkdir(parents=True, exist_ok=True)

        readme = provider_dir / "README.md"
        config = self.provider_configs[provider_id]

        content = f"""# {provider_id.capitalize()} Provider Module

## USB Integration Instructions

1. Copy your {provider_id} module files to this directory:
   - `{config['module_subpath']}` (main module)
   - Any additional dependencies

2. grep_flight will automatically detect and use modules from this location

3. Structure:
   ```
   babel_data/providers/{provider_id}/
   ├── {config['module_subpath']}
   ├── config.json (optional)
   └── README.md (this file)
   ```

## Status
Currently: {self.check_provider(provider_id).available}

## Testing
Run: `python3 provider_manager.py --test {provider_id}`
"""

        with open(readme, 'w') as f:
            f.write(content)

        print(f"✅ Created README: {readme}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Provider Manager')
    parser.add_argument('--check', help='Check specific provider')
    parser.add_argument('--list', action='store_true', help='List all providers')
    parser.add_argument('--models', help='Get models for provider')
    parser.add_argument('--create-readme', help='Create README for provider')

    args = parser.parse_args()

    manager = ProviderManager()

    if args.check:
        status = manager.check_provider(args.check)
        print(f"\n{args.check.capitalize()} Status:")
        print(f"  Available: {status.available}")
        if status.version:
            print(f"  Version: {status.version}")
        if status.module_path:
            print(f"  Module: {status.module_path}")
        if status.error:
            print(f"  Error: {status.error}")

    elif args.list:
        print("\n=== Provider Status ===\n")
        statuses = manager.get_available_providers()
        for provider_id, status in statuses.items():
            symbol = "✅" if status.available else "⚠️"
            print(f"{symbol} {provider_id.capitalize()}: {status.version or status.error}")

    elif args.models:
        models, error = manager.get_provider_models(args.models)
        print(f"\n{args.models.capitalize()} Models:")
        for model in models:
            print(f"  - {model}")
        if error:
            print(f"\nWarning: {error}")

    elif args.create_readme:
        manager.create_provider_readme(args.create_readme)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
