#!/usr/bin/env python3
"""
Chat Tab Orchestrator - Provider-agnostic AI coordinator
Maintains persistent plan/todo context and orchestrates CLI spawn workers.
"""

import json
import subprocess
import sys
from pathlib import Path

class Orchestrator:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = Path(__file__).parent / "babel_data/inventory/chat_orchestrator_config.json"

        with open(config_path) as f:
            self.config = json.load(f)['orchestrator']

        self.providers = {p['id']: p for p in self.config['providers']}

    def build_command(self, provider_id, model_id, prompt):
        """Build CLI command with appropriate flags for provider/model."""
        provider = self.providers.get(provider_id)
        if not provider:
            raise ValueError(f"Unknown provider: {provider_id}")

        # Find model
        model = None
        for m in provider['models']:
            if m['id'] == model_id:
                model = m
                break

        if not model:
            raise ValueError(f"Unknown model {model_id} for provider {provider_id}")

        # Build command
        cmd_parts = [provider['cli']]

        # Add base flags
        cmd_parts.extend(provider['base_flags'])

        # Add model-specific flag
        if 'flag' in model:
            cmd_parts.extend(model['flag'].split())

        # Add prompt
        cmd_parts.append(prompt)

        return cmd_parts

    def invoke(self, provider_id, model_id, prompt):
        """Invoke the orchestrator with given provider/model/prompt."""
        cmd = self.build_command(provider_id, model_id, prompt)

        print(f"[Orchestrator] Invoking: {' '.join(cmd[:3])}... (model: {model_id})")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            return "[ERROR] Orchestrator timeout (120s)"
        except Exception as e:
            return f"[ERROR] {str(e)}"

    def list_providers(self):
        """List available providers and models."""
        print("\n=== Available Providers & Models ===\n")
        for provider_id, provider in self.providers.items():
            print(f"📦 {provider['name']} (id: {provider_id})")
            for model in provider['models']:
                print(f"   └─ {model['name']} (id: {model['id']})")
            print()

    def test_coordination(self):
        """Test orchestrator → worker coordination."""
        print("\n=== Testing Orchestrator-Worker Coordination ===\n")

        # Test Claude orchestrator
        print("[1] Testing Claude Sonnet as orchestrator...")
        response = self.invoke(
            'claude',
            'sonnet',
            'How many todos in ~/plans/todos.json? Just the number.'
        )
        print(f"Response: {response.strip()}\n")

        # Test with different model
        print("[2] Testing Claude Haiku as fast worker...")
        response = self.invoke(
            'claude',
            'haiku',
            'Read ~/plans/todos.json and tell me the title of todo #104. Just the title.'
        )
        print(f"Response: {response.strip()}\n")

        print("✅ Coordination test complete!")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Chat Tab Orchestrator')
    parser.add_argument('--list', action='store_true', help='List providers and models')
    parser.add_argument('--test', action='store_true', help='Test coordination')
    parser.add_argument('--provider', '-p', help='Provider ID (claude, gemini, ollama, morph)')
    parser.add_argument('--model', '-m', help='Model ID')
    parser.add_argument('prompt', nargs='*', help='Prompt to send')

    args = parser.parse_args()

    orchestrator = Orchestrator()

    if args.list:
        orchestrator.list_providers()
    elif args.test:
        orchestrator.test_coordination()
    elif args.provider and args.model and args.prompt:
        prompt = ' '.join(args.prompt)
        response = orchestrator.invoke(args.provider, args.model, prompt)
        print(response)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
